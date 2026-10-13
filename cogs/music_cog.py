
import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

import discord
from discord.ext import commands
import yt_dlp


# =========================================================
# SETTINGS - عدّل الآيديّات هنا
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
    "default_search": "ytsearch1",
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


# =========================================================
# DATA
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

        # جلسة واحدة لكل سيرفر
        self.queues = {}
        self.workers = {}
        self.current_songs = {}
        self.volumes = {}
        self.locks = {}

        # خيارات yt-dlp
        self.ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

    def get_lock(self, guild_id):
        if guild_id not in self.locks:
            self.locks[guild_id] = asyncio.Lock()
        return self.locks[guild_id]

    def get_queue(self, guild_id):
        return self.queues.setdefault(guild_id, [])

    async def check_context(self, ctx):
        if ctx.guild is None:
            await ctx.send("❌ أوامر الموسيقى تعمل داخل السيرفر فقط.")
            return False

        if ctx.channel.id not in ALLOWED_TEXT_CHANNEL_IDS:
            await ctx.send("❌ هذا الروم غير مسموح لأوامر الموسيقى.")
            return False

        return True

    async def get_voice_channel(self, ctx):
        if not isinstance(ctx.author, discord.Member):
            return None

        voice = ctx.author.voice

        if voice is None or voice.channel is None:
            await ctx.send("❌ ادخل رومًا صوتيًا أولًا.")
            return None

        channel = voice.channel

        if channel.id not in ALLOWED_VOICE_CHANNEL_IDS:
            await ctx.send("❌ هذا الروم الصوتي غير مسموح.")
            return None

        return channel

    async def search_song(self, query):
        def extract():
            return self.ytdl.extract_info(
                query,
                download=False,
            )

        info = await asyncio.to_thread(extract)

        if not info:
            return None

        # اختيار أول نتيجة عند البحث النصي
        if "entries" in info:
            entries = info.get("entries") or []
            info = next(
                (entry for entry in entries if entry),
                None,
            )

        if not info:
            return None

        stream_url = info.get("url")
        webpage_url = info.get("webpage_url")
        title = info.get("title", "أغنية بدون عنوان")

        if not stream_url:
            return None

        return Song(
            title=title,
            webpage_url=webpage_url or stream_url,
            stream_url=stream_url,
            requester_id=0,
            text_channel_id=0,
        )

    async def get_voice_client(self, ctx, channel):
        voice = ctx.guild.voice_client

        if voice and voice.is_connected():
            if voice.channel.id != channel.id:
                await ctx.send(
                    "❌ البوت يشغّل في روم صوتي آخر حاليًا. "
                    "انتظر انتهاء الجلسة أو استخدم غادر أولًا."
                )
                return None

            return voice

        try:
            return await channel.connect(
                self_deaf=True,
                timeout=30,
                reconnect=True,
            )
        except Exception:
            logging.exception("Music voice connection failed")
            await ctx.send(
                "❌ تعذر الاتصال بالروم الصوتي. "
                "تحقق من صلاحيات البوت وإعدادات الصوت."
            )
            return None

    async def start_worker(self, ctx):
        guild_id = ctx.guild.id

        task = self.workers.get(guild_id)

        if task is None or task.done():
            self.workers[guild_id] = asyncio.create_task(
                self.music_worker(ctx.guild)
            )

    async def music_worker(self, guild):
        guild_id = guild.id

        try:
            while self.queues.get(guild_id):
                song = self.queues[guild_id].pop(0)
                self.current_songs[guild_id] = song

                voice = guild.voice_client

                if voice is None or not voice.is_connected():
                    break

                loop = asyncio.get_running_loop()
                finished = asyncio.Event()

                try:
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
                                "Music playback error: %s",
                                error,
                            )

                        loop.call_soon_threadsafe(finished.set)

                    voice.play(source, after=after_play)

                    text_channel = self.bot.get_channel(
                        song.text_channel_id
                    )

                    if text_channel:
                        await text_channel.send(
                            f"🎶 **يتم التشغيل الآن:** "
                            f"[{song.title}]({song.webpage_url})"
                        )

                    await finished.wait()

                except asyncio.CancelledError:
                    raise

                except Exception:
                    logging.exception("Could not play song")

                    text_channel = self.bot.get_channel(
                        song.text_channel_id
                    )

                    if text_channel:
                        try:
                            await text_channel.send(
                                f"❌ تعذر تشغيل **{song.title}**."
                            )
                        except discord.HTTPException:
                            pass

                finally:
                    self.current_songs.pop(guild_id, None)

        except asyncio.CancelledError:
            raise

        finally:
            current_task = asyncio.current_task()

            if self.workers.get(guild_id) is current_task:
                self.workers.pop(guild_id, None)

            # معالجة الأغاني التي أضيفت قرب انتهاء المهمة
            if self.queues.get(guild_id):
                self.workers[guild_id] = asyncio.create_task(
                    self.music_worker(guild)
                )

    # =====================================================
    # PLAY
    # =====================================================

    @commands.command(name="تشغيل", aliases=["شغل"])
    async def play(self, ctx, *, query: str):
        if not await self.check_context(ctx):
            return

        channel = await self.get_voice_channel(ctx)

        if channel is None:
            return

        guild_id = ctx.guild.id

        async with self.get_lock(guild_id):
            voice = ctx.guild.voice_client

            if voice and voice.is_connected():
                if voice.channel.id != channel.id:
                    await ctx.send(
                        "❌ البوت موجود في روم صوتي آخر."
                    )
                    return

            queue = self.get_queue(guild_id)

            if len(queue) >= MAX_QUEUE_SIZE:
                await ctx.send(
                    f"❌ وصلت القائمة إلى الحد الأقصى "
                    f"({MAX_QUEUE_SIZE} أغنية)."
                )
                return

            status = await ctx.send(
                f"🔎 جاري البحث عن: **{query}**..."
            )

            try:
                song = await self.search_song(query)

            except Exception:
                logging.exception("YouTube search failed")
                await status.edit(
                    content=(
                        "❌ تعذر البحث عن الأغنية. "
                        "قد تكون خدمة البحث غير متاحة حاليًا."
                    )
                )
                return

            if song is None:
                await status.edit(
                    content="❌ لم أجد نتيجة قابلة للتشغيل."
                )
                return

            song.requester_id = ctx.author.id
            song.text_channel_id = ctx.channel.id

            voice = await self.get_voice_client(ctx, channel)

            if voice is None:
                return

            queue.append(song)

            position = len(queue)

            await status.edit(
                content=(
                    f"✅ تمت إضافة **{song.title}** "
                    f"إلى قائمة الانتظار.\n"
                    f"📍 ترتيبها في القائمة: {position}"
                )
            )

            await self.start_worker(ctx)

    # =====================================================
    # SKIP
    # =====================================================

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

    # =====================================================
    # PAUSE
    # =====================================================

    @commands.command(name="مؤقت", aliases=["إيقاف_مؤقت"])
    async def pause(self, ctx):
        if not await self.check_context(ctx):
            return

        voice = ctx.guild.voice_client

        if voice and voice.is_playing():
            voice.pause()
            await ctx.send("⏸️ تم إيقاف الأغنية مؤقتًا.")
        else:
            await ctx.send("❌ لا توجد أغنية تعمل حاليًا.")

    # =====================================================
    # RESUME
    # =====================================================

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

    # =====================================================
    # STOP AND CLEAR
    # =====================================================

    @commands.command(name="إيقاف", aliases=["وقف"])
    async def stop(self, ctx):
        if not await self.check_context(ctx):
            return

        guild_id = ctx.guild.id
        voice = ctx.guild.voice_client

        self.queues[guild_id] = []

        if voice and (voice.is_playing() or voice.is_paused()):
            voice.stop()

        await ctx.send("⏹️ تم إيقاف التشغيل وتفريغ القائمة.")

    # =====================================================
    # QUEUE
    # =====================================================

    @commands.command(name="القائمة", aliases=["طابور"])
    async def show_queue(self, ctx):
        if not await self.check_context(ctx):
            return

        guild_id = ctx.guild.id
        current = self.current_songs.get(guild_id)
        queue = self.get_queue(guild_id)

        lines = []

        if current:
            lines.append(
                f"🎶 الآن: **{current.title}**"
            )

        if queue:
            lines.append("\n**قائمة الانتظار:**")

            for index, song in enumerate(queue[:15], start=1):
                lines.append(
                    f"`{index}.` {song.title}"
                )

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
            color=discord.Color.from_rgb(182, 108, 255),
        )

        await ctx.send(embed=embed)

    # =====================================================
    # NOW PLAYING
    # =====================================================

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

    # =====================================================
    # REMOVE SONG BY POSITION
    # =====================================================

    @commands.command(name="حذف")
    async def remove_song(self, ctx, position: int):
        if not await self.check_context(ctx):
            return

        queue = self.get_queue(ctx.guild.id)

        if position < 1 or position > len(queue):
            await ctx.send("❌ رقم الأغنية غير صحيح.")
            return

        song = queue.pop(position - 1)

        await ctx.send(
            f"🗑️ تم حذف **{song.title}** من القائمة."
        )

    # =====================================================
    # SHUFFLE
    # =====================================================

    @commands.command(name="خلط", aliases=["عشوائي"])
    async def shuffle(self, ctx):
        import random

        if not await self.check_context(ctx):
            return

        queue = self.get_queue(ctx.guild.id)

        if len(queue) < 2:
            await ctx.send("❌ تحتاج القائمة إلى أغنيتين على الأقل.")
            return

        random.shuffle(queue)

        await ctx.send("🔀 تم خلط قائمة الانتظار.")

    # =====================================================
    # REPEAT CURRENT SONG
    # =====================================================

    @commands.command(name="كرر", aliases=["تكرار"])
    async def repeat(self, ctx):
        if not await self.check_context(ctx):
            return

        guild_id = ctx.guild.id
        song = self.current_songs.get(guild_id)

        if song is None:
            await ctx.send("❌ لا توجد أغنية تعمل حاليًا.")
            return

        queue = self.get_queue(guild_id)

        if len(queue) >= MAX_QUEUE_SIZE:
            await ctx.send("❌ قائمة الانتظار ممتلئة.")
            return

        queue.insert(0, Song(
            title=song.title,
            webpage_url=song.webpage_url,
            stream_url=song.stream_url,
            requester_id=ctx.author.id,
            text_channel_id=ctx.channel.id,
        ))

        await ctx.send(
            f"🔁 ستُضاف **{song.title}** للتشغيل مرة أخرى."
        )

    # =====================================================
    # VOLUME
    # =====================================================

    @commands.command(name="صوت", aliases=["مستوى_الصوت"])
    async def volume(self, ctx, level: int):
        if not await self.check_context(ctx):
            return

        if not 1 <= level <= 100:
            await ctx.send("❌ حدد مستوى صوت من 1 إلى 100.")
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

        await ctx.send(f"🔊 تم ضبط الصوت على {level}%.")

    # =====================================================
    # LEAVE
    # =====================================================

    @commands.command(name="غادر", aliases=["اخرج"])
    async def leave(self, ctx):
        if not await self.check_context(ctx):
            return

        guild_id = ctx.guild.id
        voice = ctx.guild.voice_client

        self.queues[guild_id] = []

        if voice:
            if voice.is_playing() or voice.is_paused():
                voice.stop()

            await voice.disconnect(force=True)

        await ctx.send("👋 غادرت الروم الصوتي.")

    # =====================================================
    # HELP
    # =====================================================

    @commands.command(name="مساعدة", aliases=["ميوزك"])
    async def music_help(self, ctx):
        if not await self.check_context(ctx):
            return

        embed = discord.Embed(
            title="🎵 أوامر الموسيقى",
            description=(
                "```text\n"
                "تشغيل اسم الأغنية\n"
                "تخطي\n"
                "مؤقت\n"
                "كمل\n"
                "إيقاف\n"
                "القائمة\n"
                "الآن\n"
                "حذف رقم\n"
                "خلط\n"
                "كرر\n"
                "صوت 50\n"
                "غادر\n"
                "مساعدة\n"
                "```"
            ),
            color=discord.Color.from_rgb(182, 108, 255),
        )

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(MusicCog(bot))
