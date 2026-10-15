
import asyncio
import logging
import random
from dataclasses import dataclass

import discord
from discord.ext import commands
import yt_dlp


# =========================================================
# SETTINGS
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

# روم إرسال إشعارات بدء تشغيل الأغاني
PLAYING_ANNOUNCEMENT_CHANNEL_ID = 1559250563475054652

MAX_QUEUE_SIZE = 50
DEFAULT_VOLUME = 0.50

PURPLE = discord.Color.from_rgb(182, 108, 255)
GREEN = discord.Color.from_rgb(80, 200, 140)
RED = discord.Color.from_rgb(230, 75, 100)
GOLD = discord.Color.from_rgb(255, 190, 75)

YTDL_OPTIONS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": False,
    "skip_download": True,
    "cachedir": False,
    "socket_timeout": 20,
    "retries": 3,
    "extractor_retries": 3,
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
# EMBED HELPERS
# =========================================================

def make_embed(title, description=None, color=PURPLE):
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=discord.utils.utcnow(),
    )
    embed.set_footer(text="DIAA MUSIC • Interactive Music System")
    return embed


async def private_message(interaction, title, description, color=PURPLE):
    embed = make_embed(title, description, color)

    if interaction.response.is_done():
        await interaction.followup.send(
            embed=embed,
            ephemeral=True,
        )
    else:
        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )


# =========================================================
# SONG SEARCH MODAL
# =========================================================

class SongSearchModal(discord.ui.Modal):
    def __init__(self, cog):
        super().__init__(
            title="🎵 تشغيل أغنية",
            timeout=180,
        )
        self.cog = cog

        self.query = discord.ui.TextInput(
            label="اسم الأغنية أو رابطها",
            placeholder="اكتب اسم الأغنية أو رابط YouTube...",
            min_length=1,
            max_length=200,
            required=True,
        )
        self.add_item(self.query)

    async def on_submit(self, interaction: discord.Interaction):
        await self.cog.enqueue_from_interaction(
            interaction,
            str(self.query.value).strip(),
        )


# =========================================================
# VOLUME MODAL
# =========================================================

class VolumeModal(discord.ui.Modal):
    def __init__(self, cog):
        super().__init__(
            title="🔊 التحكم بالصوت",
            timeout=180,
        )
        self.cog = cog

        self.level = discord.ui.TextInput(
            label="مستوى الصوت من 1 إلى 100",
            placeholder="مثال: 50",
            min_length=1,
            max_length=3,
            required=True,
        )
        self.add_item(self.level)

    async def on_submit(self, interaction: discord.Interaction):
        if not await self.cog.check_interaction(interaction):
            return

        try:
            level = int(str(self.level.value).strip())
        except ValueError:
            await private_message(
                interaction,
                "❌ قيمة غير صحيحة",
                "اكتب رقمًا من 1 إلى 100.",
                RED,
            )
            return

        if not 1 <= level <= 100:
            await private_message(
                interaction,
                "❌ خارج النطاق",
                "مستوى الصوت يجب أن يكون من 1 إلى 100.",
                RED,
            )
            return

        guild = interaction.guild
        self.cog.volumes[guild.id] = level / 100

        voice = guild.voice_client
        if (
            voice
            and voice.source
            and isinstance(voice.source, discord.PCMVolumeTransformer)
        ):
            voice.source.volume = level / 100

        await private_message(
            interaction,
            "🔊 تم تغيير الصوت",
            f"مستوى الصوت الحالي: **{level}%**",
            GREEN,
        )


# =========================================================
# REMOVE SONG MODAL
# =========================================================

class RemoveSongModal(discord.ui.Modal):
    def __init__(self, cog):
        super().__init__(
            title="🗑️ حذف أغنية من القائمة",
            timeout=180,
        )
        self.cog = cog

        self.position = discord.ui.TextInput(
            label="رقم الأغنية في قائمة الانتظار",
            placeholder="مثال: 2",
            min_length=1,
            max_length=4,
            required=True,
        )
        self.add_item(self.position)

    async def on_submit(self, interaction: discord.Interaction):
        if not await self.cog.check_interaction(interaction):
            return

        try:
            position = int(str(self.position.value).strip())
        except ValueError:
            await private_message(
                interaction,
                "❌ رقم غير صحيح",
                "اكتب رقم الأغنية في القائمة.",
                RED,
            )
            return

        queue = self.cog.get_queue(interaction.guild.id)

        if position < 1 or position > len(queue):
            await private_message(
                interaction,
                "❌ الأغنية غير موجودة",
                "تحقق من رقم الأغنية باستخدام زر القائمة.",
                RED,
            )
            return

        song = queue.pop(position - 1)

        await private_message(
            interaction,
            "🗑️ تم حذف الأغنية",
            f"تم حذف **{song.title}** من قائمة الانتظار.",
            GREEN,
        )


# =========================================================
# PERMANENT INTERACTIVE DASHBOARD
# =========================================================

class MusicDashboard(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    async def allowed(self, interaction):
        return await self.cog.check_interaction(interaction)

    @discord.ui.button(
        label="تشغيل",
        emoji="🎵",
        style=discord.ButtonStyle.success,
        custom_id="diaa_music:play",
        row=0,
    )
    async def play_button(self, interaction, button):
        if not await self.allowed(interaction):
            return

        await interaction.response.send_modal(
            SongSearchModal(self.cog)
        )

    @discord.ui.button(
        label="إيقاف مؤقت",
        emoji="⏸️",
        style=discord.ButtonStyle.secondary,
        custom_id="diaa_music:pause",
        row=0,
    )
    async def pause_button(self, interaction, button):
        if not await self.allowed(interaction):
            return

        voice = interaction.guild.voice_client

        if voice and voice.is_playing():
            voice.pause()
            await private_message(
                interaction,
                "⏸️ تم إيقاف الموسيقى مؤقتًا",
                "الأغنية محفوظة في مكانها. اضغط **كمل** للمتابعة.",
                GREEN,
            )
        else:
            await private_message(
                interaction,
                "⚠️ لا توجد أغنية تعمل",
                "لا توجد أغنية يمكن إيقافها مؤقتًا.",
                RED,
            )

    @discord.ui.button(
        label="كمل",
        emoji="▶️",
        style=discord.ButtonStyle.success,
        custom_id="diaa_music:resume",
        row=0,
    )
    async def resume_button(self, interaction, button):
        if not await self.allowed(interaction):
            return

        voice = interaction.guild.voice_client

        if voice and voice.is_paused():
            voice.resume()
            await private_message(
                interaction,
                "▶️ عادت الموسيقى",
                "تم استئناف الأغنية من نفس المكان.",
                GREEN,
            )
        else:
            await private_message(
                interaction,
                "⚠️ لا توجد أغنية متوقفة",
                "أوقف الأغنية مؤقتًا أولًا.",
                RED,
            )

    @discord.ui.button(
        label="تخطي",
        emoji="⏭️",
        style=discord.ButtonStyle.primary,
        custom_id="diaa_music:skip",
        row=0,
    )
    async def skip_button(self, interaction, button):
        if not await self.allowed(interaction):
            return

        voice = interaction.guild.voice_client

        if voice and (voice.is_playing() or voice.is_paused()):
            self.cog.skip_requested.add(interaction.guild.id)
            voice.stop()

            await private_message(
                interaction,
                "⏭️ تم تخطي الأغنية",
                "سيتم الانتقال إلى الأغنية التالية.",
                GREEN,
            )
        else:
            await private_message(
                interaction,
                "⚠️ لا توجد أغنية",
                "لا توجد أغنية لتخطيها.",
                RED,
            )

    @discord.ui.button(
        label="إنهاء",
        emoji="⏹️",
        style=discord.ButtonStyle.danger,
        custom_id="diaa_music:end",
        row=0,
    )
    async def end_button(self, interaction, button):
        if not await self.allowed(interaction):
            return

        guild_id = interaction.guild.id
        self.cog.queues[guild_id] = []
        self.cog.repeat_enabled[guild_id] = False
        self.cog.skip_requested.add(guild_id)

        voice = interaction.guild.voice_client

        if voice and (voice.is_playing() or voice.is_paused()):
            voice.stop()

        await private_message(
            interaction,
            "⏹️ تم إنهاء التشغيل",
            "تم إنهاء الأغنية الحالية وتفريغ قائمة الانتظار.",
            GREEN,
        )

    @discord.ui.button(
        label="القائمة",
        emoji="📜",
        style=discord.ButtonStyle.secondary,
        custom_id="diaa_music:queue",
        row=1,
    )
    async def queue_button(self, interaction, button):
        if not await self.allowed(interaction):
            return

        guild_id = interaction.guild.id
        queue = self.cog.get_queue(guild_id)
        current = self.cog.current_songs.get(guild_id)

        embed = make_embed("📜 | قائمة الموسيقى")

        if current:
            embed.add_field(
                name="🎶 يتم تشغيلها الآن",
                value=f"[{current.title}]({current.webpage_url})",
                inline=False,
            )

        if queue:
            lines = []

            for index, song in enumerate(queue[:15], start=1):
                lines.append(
                    f"`{index}.` [{song.title}]({song.webpage_url})"
                )

            if len(queue) > 15:
                lines.append(
                    f"\n... وهناك {len(queue) - 15} أغنية أخرى."
                )

            embed.add_field(
                name="⏳ قائمة الانتظار",
                value="\n".join(lines),
                inline=False,
            )
        elif not current:
            embed.description = "لا توجد أغانٍ في القائمة حاليًا."
        else:
            embed.add_field(
                name="⏳ قائمة الانتظار",
                value="لا توجد أغانٍ أخرى تنتظر التشغيل.",
                inline=False,
            )

        embed.add_field(
            name="📊 العدد",
            value=f"{len(queue)} أغنية في الانتظار",
            inline=True,
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )

    @discord.ui.button(
        label="الأغنية الحالية",
        emoji="🎧",
        style=discord.ButtonStyle.secondary,
        custom_id="diaa_music:now",
        row=1,
    )
    async def now_button(self, interaction, button):
        if not await self.allowed(interaction):
            return

        song = self.cog.current_songs.get(interaction.guild.id)

        if not song:
            await private_message(
                interaction,
                "🎧 لا توجد أغنية",
                "لا توجد أغنية مسجلة على أنها تعمل حاليًا.",
                RED,
            )
            return

        embed = make_embed(
            "🎧 | الأغنية الحالية",
            f"**[{song.title}]({song.webpage_url})**",
            GREEN,
        )
        embed.add_field(
            name="👤 طلبها",
            value=f"<@{song.requester_id}>",
            inline=True,
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )

    @discord.ui.button(
        label="خلط",
        emoji="🔀",
        style=discord.ButtonStyle.secondary,
        custom_id="diaa_music:shuffle",
        row=1,
    )
    async def shuffle_button(self, interaction, button):
        if not await self.allowed(interaction):
            return

        queue = self.cog.get_queue(interaction.guild.id)

        if len(queue) < 2:
            await private_message(
                interaction,
                "🔀 لا توجد أغانٍ كافية",
                "أضف أغنيتين على الأقل إلى قائمة الانتظار.",
                RED,
            )
            return

        random.shuffle(queue)

        await private_message(
            interaction,
            "🔀 تم خلط القائمة",
            "تم تغيير ترتيب الأغاني المنتظرة.",
            GREEN,
        )

    @discord.ui.button(
        label="تكرار",
        emoji="🔁",
        style=discord.ButtonStyle.secondary,
        custom_id="diaa_music:repeat",
        row=1,
    )
    async def repeat_button(self, interaction, button):
        if not await self.allowed(interaction):
            return

        guild_id = interaction.guild.id

        self.cog.repeat_enabled[guild_id] = not (
            self.cog.repeat_enabled.get(guild_id, False)
        )

        if self.cog.repeat_enabled[guild_id]:
            await private_message(
                interaction,
                "🔁 تم تفعيل التكرار",
                "ستتكرر الأغنية الحالية حتى يتم إيقاف التكرار أو تخطيها.",
                GREEN,
            )
        else:
            await private_message(
                interaction,
                "➡️ تم إيقاف التكرار",
                "لن تتم إعادة الأغنية الحالية تلقائيًا.",
                GREEN,
            )

    @discord.ui.button(
        label="حذف أغنية",
        emoji="🗑️",
        style=discord.ButtonStyle.danger,
        custom_id="diaa_music:remove",
        row=1,
    )
    async def remove_button(self, interaction, button):
        if not await self.allowed(interaction):
            return

        await interaction.response.send_modal(
            RemoveSongModal(self.cog)
        )

    @discord.ui.button(
        label="الصوت",
        emoji="🔊",
        style=discord.ButtonStyle.secondary,
        custom_id="diaa_music:volume",
        row=2,
    )
    async def volume_button(self, interaction, button):
        if not await self.allowed(interaction):
            return

        await interaction.response.send_modal(
            VolumeModal(self.cog)
        )

    @discord.ui.button(
        label="تعال",
        emoji="📍",
        style=discord.ButtonStyle.primary,
        custom_id="diaa_music:come",
        row=2,
    )
    async def come_button(self, interaction, button):
        if not await self.allowed(interaction):
            return

        member = interaction.user

        if not isinstance(member, discord.Member):
            await private_message(
                interaction,
                "❌ تعذر تحديد العضو",
                "استخدم الزر من داخل السيرفر.",
                RED,
            )
            return

        if not member.voice or not member.voice.channel:
            await private_message(
                interaction,
                "🎧 ادخل رومًا صوتيًا أولًا",
                "بعد دخولك الروم اضغط زر تعال.",
                RED,
            )
            return

        channel = member.voice.channel

        if channel.id not in ALLOWED_VOICE_CHANNEL_IDS:
            await private_message(
                interaction,
                "🔒 روم غير مسموح",
                "انتقل إلى أحد الرومات الصوتية المسموحة.",
                RED,
            )
            return

        try:
            async with self.cog.get_lock(interaction.guild.id):
                voice = interaction.guild.voice_client

                if voice and voice.is_connected():
                    if voice.channel.id == channel.id:
                        await private_message(
                            interaction,
                            "📍 أنا موجود هنا",
                            f"البوت موجود في {channel.mention} بالفعل.",
                            GREEN,
                        )
                        return

                    await voice.move_to(channel)
                else:
                    await channel.connect(
                        self_deaf=True,
                        timeout=30,
                        reconnect=True,
                    )

            await private_message(
                interaction,
                "🚀 تم الانتقال",
                f"انتقل البوت إلى {channel.mention}.",
                GREEN,
            )

        except Exception:
            logging.exception("Voice move failed")
            await private_message(
                interaction,
                "❌ تعذر الانتقال",
                "تحقق من صلاحيات الاتصال والتحدث في الروم.",
                RED,
            )

    @discord.ui.button(
        label="مغادرة",
        emoji="👋",
        style=discord.ButtonStyle.danger,
        custom_id="diaa_music:leave",
        row=2,
    )
    async def leave_button(self, interaction, button):
        if not await self.allowed(interaction):
            return

        guild_id = interaction.guild.id
        self.cog.queues[guild_id] = []
        self.cog.repeat_enabled[guild_id] = False
        self.cog.skip_requested.add(guild_id)

        voice = interaction.guild.voice_client

        if voice:
            if voice.is_playing() or voice.is_paused():
                voice.stop()

            await voice.disconnect(force=True)

        await private_message(
            interaction,
            "👋 غادرت الروم",
            "تم فصل البوت عن الروم الصوتي وتفريغ القائمة.",
            GREEN,
        )

    @discord.ui.button(
        label="الأوامر",
        emoji="📖",
        style=discord.ButtonStyle.secondary,
        custom_id="diaa_music:help",
        row=2,
    )
    async def help_button(self, interaction, button):
        if not await self.allowed(interaction):
            return

        embed = make_embed(
            "📖 | دليل لوحة الموسيقى",
            "استخدم الأزرار للتحكم بالموسيقى دون كتابة الأوامر.",
        )

        embed.add_field(
            name="🎵 التشغيل",
            value="**تشغيل:** اكتب اسم الأغنية أو رابطها في النافذة.",
            inline=False,
        )
        embed.add_field(
            name="⏯️ التحكم",
            value=(
                "**إيقاف مؤقت:** يوقف الأغنية مؤقتًا.\n"
                "**كمل:** يستأنفها من مكان التوقف.\n"
                "**تخطي:** ينتقل إلى التالية.\n"
                "**إنهاء:** يوقف التشغيل ويفرغ القائمة."
            ),
            inline=False,
        )
        embed.add_field(
            name="📜 إدارة القائمة",
            value=(
                "**القائمة:** عرض الأغاني المنتظرة.\n"
                "**حذف أغنية:** اكتب رقمها في القائمة.\n"
                "**خلط:** يغيّر ترتيب الأغاني.\n"
                "**تكرار:** يعيد الأغنية الحالية."
            ),
            inline=False,
        )
        embed.add_field(
            name="🔊 الصوت والاتصال",
            value=(
                "**الصوت:** تغيير المستوى من 1 إلى 100.\n"
                "**تعال:** ينقل البوت إلى رومك المسموح.\n"
                "**مغادرة:** يفصل البوت عن الروم الصوتي.\n"
                "**الأغنية الحالية:** يعرض تفاصيل الأغنية."
            ),
            inline=False,
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )


# =========================================================
# MUSIC COG
# =========================================================

class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.queues = {}
        self.workers = {}
        self.current_songs = {}
        self.volumes = {}
        self.locks = {}
        self.repeat_enabled = {}
        self.skip_requested = set()

        self.ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)
        self.dashboard = MusicDashboard(self)

    async def cog_load(self):
        # تسجيل الأزرار الدائمة حتى تستمر بعد إعادة التشغيل
        self.bot.add_view(self.dashboard)

    def get_lock(self, guild_id):
        if guild_id not in self.locks:
            self.locks[guild_id] = asyncio.Lock()
        return self.locks[guild_id]

    def get_queue(self, guild_id):
        return self.queues.setdefault(guild_id, [])

    async def check_interaction(self, interaction):
        if interaction.guild is None:
            await private_message(
                interaction,
                "🔒 أمر خاص بالسيرفر",
                "استخدم اللوحة من داخل سيرفر Discord.",
                RED,
            )
            return False

        if interaction.channel_id not in ALLOWED_TEXT_CHANNEL_IDS:
            await private_message(
                interaction,
                "📍 روم غير مسموح",
                "استخدم لوحة الموسيقى في الرومات النصية المخصصة فقط.",
                RED,
            )
            return False

        return True

    async def get_member_voice_channel(self, interaction):
        member = interaction.user

        if not isinstance(member, discord.Member):
            await private_message(
                interaction,
                "❌ تعذر تحديد العضو",
                "استخدم اللوحة من داخل السيرفر.",
                RED,
            )
            return None

        if not member.voice or not member.voice.channel:
            await private_message(
                interaction,
                "🎧 ادخل رومًا صوتيًا",
                "يجب أن تدخل رومًا صوتيًا قبل تشغيل الموسيقى.",
                RED,
            )
            return None

        channel = member.voice.channel

        if channel.id not in ALLOWED_VOICE_CHANNEL_IDS:
            await private_message(
                interaction,
                "🔒 روم صوتي غير مسموح",
                "انتقل إلى أحد الرومات الصوتية المحددة.",
                RED,
            )
            return None

        return channel

    # -----------------------------------------------------
    # SEARCH
    # -----------------------------------------------------

    async def search_song(self, query):
        def extract():
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
                return None

            webpage_url = (
                info.get("webpage_url")
                or info.get("original_url")
            )

            if not webpage_url and info.get("id"):
                webpage_url = (
                    "https://www.youtube.com/watch?v="
                    + info["id"]
                )

            if not webpage_url:
                return None

            details = self.ytdl.extract_info(
                webpage_url,
                download=False,
            )

            if not details:
                return None

            stream_url = details.get("url")

            if not stream_url:
                audio_formats = [
                    item
                    for item in details.get("formats", [])
                    if item.get("url")
                    and item.get("acodec") != "none"
                ]

                if audio_formats:
                    stream_url = audio_formats[-1]["url"]

            if not stream_url:
                return None

            return Song(
                title=details.get(
                    "title",
                    info.get("title", "أغنية بدون عنوان"),
                ),
                webpage_url=webpage_url,
                stream_url=stream_url,
                requester_id=0,
                text_channel_id=0,
            )

        return await asyncio.to_thread(extract)
    # -----------------------------------------------------
    # ADD SONG FROM MODAL
    # -----------------------------------------------------

    async def enqueue_from_interaction(self, interaction, query):
        if not await self.check_interaction(interaction):
            return

        channel = await self.get_member_voice_channel(interaction)
        if channel is None:
            return

        await interaction.response.defer(
            ephemeral=True,
            thinking=True,
        )

        try:
            song = await self.search_song(query)
        except Exception:
            logging.exception("YouTube search failed")

            await interaction.followup.send(
                embed=make_embed(
                    "❌ | فشل البحث",
                    "تعذر البحث عن الأغنية. حاول مجددًا لاحقًا.",
                    RED,
                ),
                ephemeral=True,
            )
            return

        if song is None:
            await interaction.followup.send(
                embed=make_embed(
                    "🔍 | لم أجد الأغنية",
                    "جرّب كتابة اسم آخر أو الصق رابط فيديو صالح.",
                    RED,
                ),
                ephemeral=True,
            )
            return

        guild = interaction.guild
        guild_id = guild.id
        song.requester_id = interaction.user.id
        song.text_channel_id = interaction.channel_id

        try:
            async with self.get_lock(guild_id):
                voice = guild.voice_client

                if voice and voice.is_connected():
                    if voice.channel.id != channel.id:
                        await interaction.followup.send(
                            embed=make_embed(
                                "🔊 | البوت في روم آخر",
                                "اضغط زر **تعال** أولًا لنقل البوت إلى رومك.",
                                RED,
                            ),
                            ephemeral=True,
                        )
                        return

                queue = self.get_queue(guild_id)

                if len(queue) >= MAX_QUEUE_SIZE:
                    await interaction.followup.send(
                        embed=make_embed(
                            "📭 | القائمة ممتلئة",
                            "وصلت قائمة الانتظار إلى الحد الأقصى.",
                            RED,
                        ),
                        ephemeral=True,
                    )
                    return

                if not voice or not voice.is_connected():
                    await channel.connect(
                        self_deaf=True,
                        timeout=30,
                        reconnect=True,
                    )

                queue.append(song)
                position = len(queue)

            embed = make_embed(
                "✅ | تمت إضافة الأغنية",
                f"**[{song.title}]({song.webpage_url})**",
                GREEN,
            )
            embed.add_field(
                name="📍 ترتيبها في الانتظار",
                value=str(position),
                inline=True,
            )
            embed.add_field(
                name="👤 طلبها",
                value=interaction.user.mention,
                inline=True,
            )

            await interaction.followup.send(
                embed=embed,
                ephemeral=True,
            )

            await self.start_worker(guild)

        except Exception:
            logging.exception("Could not queue song")

            await interaction.followup.send(
                embed=make_embed(
                    "❌ | تعذر إضافة الأغنية",
                    "تحقق من صلاحيات البوت في الروم الصوتي.",
                    RED,
                ),
                ephemeral=True,
            )

    # -----------------------------------------------------
    # WORKER
    # -----------------------------------------------------

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
                        self.queues[guild_id].insert(0, song)
                        break

                    if not await self.refresh_stream(song):
                        announcement_channel = self.bot.get_channel(
                            PLAYING_ANNOUNCEMENT_CHANNEL_ID
                        )

                        if announcement_channel:
                            await announcement_channel.send(
                                embed=make_embed(
                                    "❌ | تعذر تجهيز الأغنية",
                                    f"لم أتمكن من تشغيل **{song.title}**.",
                                    RED,
                                )
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

                    # إرسال إعلان التشغيل إلى الروم المحدد فقط
                    announcement_channel = self.bot.get_channel(
                        PLAYING_ANNOUNCEMENT_CHANNEL_ID
                    )

                    if announcement_channel is None:
                        try:
                            announcement_channel = (
                                await self.bot.fetch_channel(
                                    PLAYING_ANNOUNCEMENT_CHANNEL_ID
                                )
                            )
                        except discord.HTTPException:
                            announcement_channel = None

                    if announcement_channel is not None:
                        embed = make_embed(
                            "🎶 | يتم التشغيل الآن",
                            f"**[{song.title}]({song.webpage_url})**",
                            GREEN,
                        )
                        embed.add_field(
                            name="👤 طلب الأغنية",
                            value=f"<@{song.requester_id}>",
                            inline=True,
                        )

                        try:
                            await announcement_channel.send(embed=embed)
                        except discord.HTTPException:
                            logging.exception(
                                "Could not send playback announcement"
                            )

                    await finished.wait()

                    was_skipped = guild_id in self.skip_requested
                    self.skip_requested.discard(guild_id)

                    if (
                        self.repeat_enabled.get(guild_id, False)
                        and not was_skipped
                    ):
                        self.queues.setdefault(
                            guild_id, []
                        ).insert(
                            0,
                            Song(
                                title=song.title,
                                webpage_url=song.webpage_url,
                                stream_url=song.stream_url,
                                requester_id=song.requester_id,
                                text_channel_id=song.text_channel_id,
                            ),
                        )

                except asyncio.CancelledError:
                    raise

                except Exception:
                    logging.exception(
                        "Music worker error in guild %s",
                        guild_id,
                    )

                    announcement_channel = self.bot.get_channel(
                        PLAYING_ANNOUNCEMENT_CHANNEL_ID
                    )

                    if announcement_channel:
                        try:
                            await announcement_channel.send(
                                embed=make_embed(
                                    "❌ | خطأ في التشغيل",
                                    f"تعذر تشغيل **{song.title}**.",
                                    RED,
                                )
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

            if self.queues.get(guild_id):
                await self.start_worker(guild)

    # -----------------------------------------------------
    # SEND DASHBOARD
    # -----------------------------------------------------

    @commands.command(
        name="لوحة",
        aliases=["لوحة_الموسيقى", "ميوزك"],
    )
    async def music_dashboard(self, ctx):
        if ctx.guild is None:
            return

        if ctx.channel.id not in ALLOWED_TEXT_CHANNEL_IDS:
            await ctx.send(
                embed=make_embed(
                    "📍 | روم غير مسموح",
                    "أرسل اللوحة في أحد رومات الموسيقى المخصصة.",
                    RED,
                )
            )
            return

        embed = make_embed(
            "🎵 | DIAA MUSIC",
            (
                "مرحبًا بك في لوحة التحكم بالموسيقى.\n\n"
                "اضغط على الأزرار بالأسفل للتحكم بالتشغيل "
                "وإدارة قائمة الانتظار.\n\n"
                "🎶 **تشغيل** — اكتب اسم الأغنية أو رابطها.\n"
                "⏸️ **إيقاف مؤقت** — أوقف الأغنية مؤقتًا.\n"
                "▶️ **كمل** — تابع من مكان التوقف.\n"
                "⏭️ **تخطي** — انتقل إلى الأغنية التالية.\n"
                "⏹️ **إنهاء** — أوقف التشغيل وامسح القائمة.\n\n"
                "📜 اعرض القائمة، غيّر الصوت، اخلط الأغاني، "
                "أو انقل البوت إلى رومك من الأزرار الأخرى.\n\n"
                "🔒 نتائج البحث والتحكم تظهر لك بشكل خاص."
            ),
        )

        embed.add_field(
            name="🔊 مستوى الصوت الافتراضي",
            value=f"{int(DEFAULT_VOLUME * 100)}%",
            inline=True,
        )
        embed.add_field(
            name="📚 الحد الأقصى للقائمة",
            value=f"{MAX_QUEUE_SIZE} أغنية",
            inline=True,
        )

        await ctx.send(
            embed=embed,
            view=self.dashboard,
        )


async def setup(bot):
    await bot.add_cog(MusicCog(bot))
