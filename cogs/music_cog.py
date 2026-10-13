
import asyncio
import logging
import random
from dataclasses import dataclass

import discord
from discord.ext import commands
import yt_dlp


# =========================================================
# SETTINGS - الرومات المسموحة
# =========================================================

ALLOWED_TEXT_CHANNEL_IDS = {
    1559631856972988416,
    1559631892519588051,
    1559631935213674496,
}

ALLOWED_VOICE_CHANNEL_IDS = {
    1555550971436736662,
    1555551005641281606,
    1555551467652259880,
    1555550258602442803,
}

MAX_QUEUE_SIZE = 50
DEFAULT_VOLUME = 0.50

YTDL_OPTIONS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "skip_download": True,
}

FFMPEG_OPTIONS = {
    "before_options": (
        "-reconnect 1 "
        "-reconnect_streamed 1 "
        "-reconnect_delay_max 5"
    ),
    "options": "-vn",
}

PURPLE = discord.Color.from_rgb(182, 108, 255)


# =========================================================
# SONG DATA
# =========================================================

@dataclass
class Song:
    title: str
    webpage_url: str
    stream_url: str
    requester_id: int
    text_channel_id: int


# =========================================================
# MUSIC COG
# =========================================================

class MusicCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

        # جلسة مستقلة لكل سيرفر
        self.queues = {}
        self.workers = {}
        self.current_songs = {}
        self.volumes = {}
        self.locks = {}
        self.repeat_enabled = {}

        self.ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

    # -----------------------------------------------------
    # INTERNAL HELPERS
    # -----------------------------------------------------

    def get_lock(self, guild_id):
        if guild_id not in self.locks:
            self.locks[guild_id] = asyncio.Lock()
        return self.locks[guild_id]

    def get_queue(self, guild_id):
        return self.queues.setdefault(guild_id, [])

    async def check_context(self, ctx):
        if ctx.guild is None:
            await ctx.send("❌ هذا الأمر يعمل داخل السيرفر فقط.")
            return False

        if ctx.channel.id not in ALLOWED_TEXT_CHANNEL_IDS:
            await ctx.send(
                "❌ استخدم أوامر الموسيقى في الرومات المسموحة فقط."
            )
            return False

        return True

    async def get_voice_channel(self, ctx):
        if not isinstance(ctx.author, discord.Member):
            return None

        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("❌ ادخل رومًا صوتيًا أولًا.")
            return None

        channel = ctx.author.voice.channel

        if channel.id not in ALLOWED_VOICE_CHANNEL_IDS:
            await ctx.send("❌ هذا الروم الصوتي غير مسموح.")
            return None

        return channel

    async def search_song(self, query):
        """البحث عن الأغنية ثم استخراج رابط الصوت الفعلي."""

        def extract():
            # البحث الصريح باستخدام ytsearch1
            results = self.ytdl.extract_info(
                f"ytsearch1:{query}",
                download=False,
            )

            if not results:
                return None

            entries = results.get("entries") or []
            info = next(
                (entry for entry in entries if entry),
                None,
            )

            if not info:
                # إذا أعاد yt-dlp نتيجة فيديو مباشرة
                info = results

            webpage_url = (
                info.get("webpage_url")
                or info.get("original_url")
            )

            if not webpage_url:
                video_id = info.get("id")
                if video_id:
                    webpage_url = (
                        "https://www.youtube.com/watch?v="
                        + video_id
                    )

            if not webpage_url:
                return None

            # استخراج رابط صوت حديث من صفحة الفيديو
            details = self.ytdl.extract_info(
                webpage_url,
                download=False,
            )

            if not details:
                return None

            stream_url = details.get("url")
            title = details.get(
                "title",
                info.get("title", "أغنية بدون عنوان"),
            )

            if not stream_url:
                formats = details.get("formats") or []
                audio_formats = [
                    item for item in formats
                    if item.get("url")
                    and item.get("acodec") != "none"
                ]

                if audio_formats:
                    stream_url = audio_formats[-1]["url"]

            if not stream_url:
                return None

            return Song(
                title=title,
                webpage_url=webpage_url,
                stream_url=stream_url,
                requester_id=0,
                text_channel_id=0,
            )

        return await asyncio.to_thread(extract)

    async def refresh_stream(self, song):
        """تحديث رابط الصوت قبل التشغيل، لأن بعض الروابط مؤقتة."""

        def extract():
            info = self.ytdl.extract_info(
                song.webpage_url,
                download=False,
            )

            if not info or not info.get("url"):
                return None

            return (
                info.get("title", song.title),
                info["url"],
            )

        result = await asyncio.to_thread(extract)

        if result:
            song.title, song.stream_url = result

        return result is not None

    async def get_voice_client(self, guild, channel):
        voice = guild.voice_client

        if voice and voice.is_connected():
            if voice.channel.id != channel.id:
                return None

            return voice

        return await channel.connect(
            self_deaf=True,
            timeout=30,
            reconnect=True,
        )

    async def start_worker(self, guild):
        guild_id = guild.id
        task = self.workers.get(guild_id)

        if task is None or task.done():
            self.workers[guild_id] = asyncio.create_task(
                self.music_worker(guild)
            )

    async def music_worker(self, guild):
        guild_id = guild.id
        this_task = asyncio.current_task()

        try:
            while self.queues.get(guild_id):
                song = self.queues[guild_id].pop(0)
                self.current_songs[guild_id] = song

                try:
                    voice = guild.voice_client

                    if not voice or not voice.is_connected():
                        break

                    # لا تستخدم رابط الصوت القديم إذا انتهت صلاحيته
                    if not await self.refresh_stream(song):
                        channel = self.bot.get_channel(
                            song.text_channel_id
                        )
                        if channel:
                            await channel.send(
                                f"❌ تعذر تجهيز الأغنية: **{song.title}**"
                            )
                        continue

                    loop = asyncio.get_running_loop()
                    finished = asyncio.Event()

                    source = discord.PCMVolumeTransformer(
                        discord.FFmpegPCMAudio(
                            song.stream_url,
                            **FFMPEG_OPTIONS,
                        ),
                        volume=self.volumes.get(
                            guild_id,
                            DEFAULT_VOLUME,
                        ),
                    )

                    def after_play(error):
                        if error:
                            logging.error(
                                "Playback error in guild %s: %s",
                                guild_id,
                                error,
                            )

                        loop.call_soon_threadsafe(finished.set)

                    voice.play(source, after=after_play)

                    channel = self.bot.get_channel(
                        song.text_channel_id
                    )

                    if channel:
                        await channel.send(
                            f"🎶 **يتم التشغيل الآن:** "
                            f"[{song.title}]({song.webpage_url})"
                        )

                    await finished.wait()

                    # كرر الأغنية إذا كان التكرار مفعّلًا
                    if self.repeat_enabled.get(guild_id, False):
                        self.queues.setdefault(
                            guild_id, []
                        ).insert(0, Song(
                            title=song.title,
                            webpage_url=song.webpage_url,
                            stream_url=song.stream_url,
                            requester_id=song.requester_id,
                            text_channel_id=song.text_channel_id,
                        ))

                except asyncio.CancelledError:
                    raise

                except Exception:
                    logging.exception(
                        "Music worker error in guild %s",
                        guild_id,
                    )

                    channel = self.bot.get_channel(
                        song.text_channel_id
                    )

                    if channel:
                        try:
                            await channel.send(
                                f"❌ تعذر تشغيل **{song.title}**."
                            )
                        except discord.HTTPException:
                            pass

                finally:
                    self.current_songs.pop(guild_id, None)

        except asyncio.CancelledError:
            raise

        finally:
            if self.workers.get(guild_id) is this_task:
                self.workers.pop(guild_id, None)

            # لا تفقد الأغاني التي أضيفت قرب انتهاء المهمة
            if self.queues.get(guild_id):
                await self.start_worker(guild)

    # -----------------------------------------------------
    # PLAY
    # -----------------------------------------------------

    @commands.command(name="تشغيل", aliases=["شغل"])
    async def play(self, ctx, *, query: str):
        if not await self.check_context(ctx):
            return

        channel = await self.get_voice_channel(ctx)
        if channel is None:
            return

        status = await ctx.send(
            f"🔎 جاري البحث عن **{query}**..."
        )

        try:
            song = await self.search_song(query)

        except Exception:
            logging.exception("YouTube search failed")

            await status.edit(
                content=(
                    "❌ فشل البحث عن الأغنية. "
                    "راجع سجلات Railway لمعرفة السبب."
                )
            )
            return

        if song is None:
            await status.edit(
                content="❌ لم أجد أغنية قابلة للتشغيل."
            )
            return

        guild_id = ctx.guild.id

        song.requester_id = ctx.author.id
        song.text_channel_id = ctx.channel.id

        try:
            async with self.get_lock(guild_id):
                voice = ctx.guild.voice_client

                # يمنع الانتقال بين رومات الصوت في السيرفر نفسه
                if voice and voice.is_connected():
                    if voice.channel.id != channel.id:
                        await status.edit(
                            content=(
                                "❌ البوت يشغّل في روم صوتي آخر "
                                "في هذا السيرفر حاليًا."
                            )
                        )
                        return

                queue = self.get_queue(guild_id)

                if len(queue) >= MAX_QUEUE_SIZE:
                    await status.edit(
                        content="❌ قائمة الانتظار ممتلئة."
                    )
                    return

                if not voice or not voice.is_connected():
                    voice = await self.get_voice_client(
                        ctx.guild,
                        channel,
                    )

                queue.append(song)
                position = len(queue)

                await status.edit(
                    content=(
                        f"✅ تمت إضافة **{song.title}** "
                        f"إلى قائمة الانتظار.\n"
                        f"📍 ترتيبها: {position}"
                    )
                )

            await self.start_worker(ctx.guild)

        except Exception:
            logging.exception("Could not join voice channel")
            await status.edit(
                content=(
                    "❌ تعذر الاتصال بالروم الصوتي. "
                    "تحقق من صلاحيات البوت وإعدادات الصوت."
                )
            )

    # -----------------------------------------------------
    # SKIP
    # -----------------------------------------------------

    @commands.command(name="تخطي", aliases=["التالي"])
    async def skip(self, ctx):
        if not await self.check_context(ctx):
            return

        voice = ctx.guild.voice_client

        if voice and voice.is_playing():
            voice.stop()
            await ctx.send("⏭️ تم تخطي الأغنية.")
        else:
            await ctx.send("❌ لا توجد أغنية تعمل حاليًا.")

    # -----------------------------------------------------
    # PAUSE / RESUME
    # -----------------------------------------------------

    @commands.command(name="مؤقت", aliases=["إيقاف_مؤقت"])
    async def pause(self, ctx):
        if not await self.check_context(ctx):
            return

        voice = ctx.guild.voice_client

        if voice and voice.is_playing():
            voice.pause()
            await ctx.send("⏸️ تم إيقاف التشغيل مؤقتًا.")
        else:
            await ctx.send("❌ لا توجد أغنية تعمل حاليًا.")

    @commands.command(name="كمل", aliases=["استئناف"])
    async def resume(self, ctx):
        if not await self.check_context(ctx):
            return

        voice = ctx.guild.voice_client

        if voice and voice.is_paused():
            voice.resume()
            await ctx.send("▶️ تم استئناف التشغيل.")
        else:
            await ctx.send("❌ لا توجد أغنية متوقفة مؤقتًا.")

    # -----------------------------------------------------
    # STOP / CLEAR
    # -----------------------------------------------------

    @commands.command(name="إيقاف", aliases=["وقف"])
    async def stop(self, ctx):
        if not await self.check_context(ctx):
            return

        guild_id = ctx.guild.id
        self.queues[guild_id] = []
        self.repeat_enabled[guild_id] = False

        voice = ctx.guild.voice_client

        if voice and (voice.is_playing() or voice.is_paused()):
            voice.stop()

        await ctx.send("⏹️ تم إيقاف الأغنية وتفريغ القائمة.")

    # -----------------------------------------------------
    # QUEUE
    # -----------------------------------------------------

    @commands.command(name="القائمة", aliases=["طابور"])
    async def show_queue(self, ctx):
        if not await self.check_context(ctx):
            return

        guild_id = ctx.guild.id
        current = self.current_songs.get(guild_id)
        queue = self.get_queue(guild_id)

        lines = []

        if current:
            lines.append(f"🎶 الآن: **{current.title}**")

        if queue:
            lines.append("\n**قائمة الانتظار:**")

            for index, song in enumerate(queue[:15], start=1):
                lines.append(f"`{index}.` {song.title}")

            if len(queue) > 15:
                lines.append(
                    f"... و{len(queue) - 15} أغنية أخرى."
                )

        if not lines:
            await ctx.send("📭 لا توجد أغاني في القائمة.")
            return

        embed = discord.Embed(
            title="🎵 قائمة الموسيقى",
            description="\n".join(lines),
            color=PURPLE,
        )
        await ctx.send(embed=embed)

    # -----------------------------------------------------
    # NOW PLAYING
    # -----------------------------------------------------

    @commands.command(name="الآن", aliases=["الحالية"])
    async def now_playing(self, ctx):
        if not await self.check_context(ctx):
            return

        song = self.current_songs.get(ctx.guild.id)

        if not song:
            await ctx.send("❌ لا توجد أغنية تعمل حاليًا.")
            return

        await ctx.send(
            f"🎶 **الأغنية الحالية:** "
            f"[{song.title}]({song.webpage_url})"
        )

    # -----------------------------------------------------
    # REMOVE SONG
    # -----------------------------------------------------

    @commands.command(name="حذف")
    async def remove_song(self, ctx, position: int):
        if not await self.check_context(ctx):
            return

        queue = self.get_queue(ctx.guild.id)

        if position < 1 or position > len(queue):
            await ctx.send("❌ رقم الأغنية غير صحيح.")
            return

        song = queue.pop(position - 1)
        await ctx.send(f"🗑️ تم حذف **{song.title}**.")

    # -----------------------------------------------------
    # SHUFFLE
    # -----------------------------------------------------

    @commands.command(name="خلط", aliases=["عشوائي"])
    async def shuffle(self, ctx):
        if not await self.check_context(ctx):
            return

        queue = self.get_queue(ctx.guild.id)

        if len(queue) < 2:
            await ctx.send("❌ تحتاج القائمة إلى أغنيتين على الأقل.")
            return

        random.shuffle(queue)
        await ctx.send("🔀 تم خلط قائمة الانتظار.")

    # -----------------------------------------------------
    # REPEAT TOGGLE
    # -----------------------------------------------------

    @commands.command(name="كرر", aliases=["تكرار"])
    async def repeat(self, ctx):
        if not await self.check_context(ctx):
            return

        guild_id = ctx.guild.id
        self.repeat_enabled[guild_id] = not (
            self.repeat_enabled.get(guild_id, False)
        )

        if self.repeat_enabled[guild_id]:
            await ctx.send("🔁 تم تفعيل تكرار الأغاني.")
        else:
            await ctx.send("➡️ تم إيقاف تكرار الأغاني.")

    # -----------------------------------------------------
    # VOLUME
    # -----------------------------------------------------

    @commands.command(name="صوت", aliases=["مستوى_الصوت"])
    async def volume(self, ctx, level: int):
        if not await self.check_context(ctx):
            return

        if not 1 <= level <= 100:
            await ctx.send("❌ حدد مستوى الصوت من 1 إلى 100.")
            return

        guild_id = ctx.guild.id
        self.volumes[guild_id] = level / 100

        voice = ctx.guild.voice_client

        if (
            voice
            and voice.source
            and isinstance(
                voice.source,
                discord.PCMVolumeTransformer,
            )
        ):
            voice.source.volume = level / 100

        await ctx.send(f"🔊 مستوى الصوت الآن {level}%.")

    # -----------------------------------------------------
    # LEAVE
    # -----------------------------------------------------

    @commands.command(name="غادر", aliases=["اخرج"])
    async def leave(self, ctx):
        if not await self.check_context(ctx):
            return

        guild_id = ctx.guild.id
        self.queues[guild_id] = []
        self.repeat_enabled[guild_id] = False

        voice = ctx.guild.voice_client

        if voice:
            if voice.is_playing() or voice.is_paused():
                voice.stop()

            await voice.disconnect(force=True)

        await ctx.send("👋 غادرت الروم الصوتي.")

    # -----------------------------------------------------
    # HELP
    # -----------------------------------------------------

    @commands.command(name="مساعدة", aliases=["ميوزك"])
    async def music_help(self, ctx):
        if not await self.check_context(ctx):
            return

        embed = discord.Embed(
            title="🎵 أوامر الموسيقى",
            description=(
                "```text\n"
                "تشغيل\n"
                "تخطي\n"
                "مؤقت\n"
                "كمل\n"
                "إيقاف\n"
                "القائمة\n"
                "الان\n"
                "حذف رقم\n"
                "خلط\n"
                "كرر\n"
                "صوت 50\n"
                "غادر\n"
                "مساعدة\n"
                "```"
            ),
            color=PURPLE,
        )

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(MusicCog(bot))
