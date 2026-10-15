import asyncio
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

PLAYING_ANNOUNCEMENT_CHANNEL_ID = 1559250563475054652

MAX_QUEUE_SIZE = 50
DEFAULT_VOLUME = 0.50

PURPLE = discord.Color.from_rgb(182, 108, 255)
GREEN = discord.Color.from_rgb(80, 200, 140)
RED = discord.Color.from_rgb(230, 75, 100)

logging.basicConfig(level=logging.INFO)

YTDL_OPTIONS = {
"format": "bestaudio/best",
"noplaylist": True,
"quiet": True,
"no_warnings": False,
"skip_download": True,
"cachedir": False,
"socket_timeout": 25,
"retries": 2,
"extractor_retries": 2,
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

from dataclasses import dataclass

@dataclass
class Song:
    title: str
    webpage_url: str
    stream_url: str
    requester_id: int
    text_channel_id: int

# =========================================================
# EMBEDS
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
# SEARCH MODAL
# =========================================================

class SongSearchModal(discord.ui.Modal):
def init(self, cog):
super().init(title="🎵 تشغيل أغنية", timeout=180)
self.cog = cog

    self.query = discord.ui.TextInput(
        label="اسم الأغنية أو رابطها",
        placeholder="اكتب اسم الأغنية أو رابط YouTube...",
        min_length=1,
        max_length=200,
        required=True,
    )
    self.add_item(self.query)

async def on_submit(self, interaction):
    await self.cog.enqueue_from_interaction(
        interaction,
        str(self.query.value).strip(),
    )

# =========================================================
# VOLUME MODAL
# =========================================================

class VolumeModal(discord.ui.Modal):
def init(self, cog):
super().init(title="🔊 التحكم بالصوت", timeout=180)
self.cog = cog

    self.level = discord.ui.TextInput(
        label="مستوى الصوت من 1 إلى 100",
        placeholder="مثال: 50",
        min_length=1,
        max_length=3,
        required=True,
    )
    self.add_item(self.level)

async def on_submit(self, interaction):
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
def init(self, cog):
super().init(title="🗑️ حذف أغنية من القائمة", timeout=180)
self.cog = cog

    self.position = discord.ui.TextInput(
        label="رقم الأغنية في قائمة الانتظار",
        placeholder="مثال: 2",
        min_length=1,
        max_length=4,
        required=True,
    )
    self.add_item(self.position)

async def on_submit(self, interaction):
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
# MUSIC DASHBOARD
# =========================================================

class MusicDashboard(discord.ui.View):
def init(self, cog):
super().init(timeout=None)
self.cog = cog

async def allowed(self, interaction):
    return await self.cog.check_interaction(interaction)

@discord.ui.button(
    label="تشغيل", emoji="🎵",
    style=discord.ButtonStyle.success,
    custom_id="diaa_music:play", row=0,
)
async def play_button(self, interaction, button):
    if await self.allowed(interaction):
        await interaction.response.send_modal(
            SongSearchModal(self.cog)
        )

@discord.ui.button(
    label="إيقاف مؤقت", emoji="⏸️",
    style=discord.ButtonStyle.secondary,
    custom_id="diaa_music:pause", row=0,
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
            "اضغط **كمل** للمتابعة.",
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
    label="كمل", emoji="▶️",
    style=discord.ButtonStyle.success,
    custom_id="diaa_music:resume", row=0,
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
            "تم استئناف الأغنية.",
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
    label="تخطي", emoji="⏭️",
    style=discord.ButtonStyle.primary,
    custom_id="diaa_music:skip", row=0,
)
async def skip_button(self, interaction, button):
    if not await self.allowed(interaction):
        return

    guild_id = interaction.guild.id
    voice = interaction.guild.voice_client

    if voice and (voice.is_playing() or voice.is_paused()):
        self.cog.skip_requested.add(guild_id)
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
    label="إنهاء", emoji="⏹️",
    style=discord.ButtonStyle.danger,
    custom_id="diaa_music:end", row=0,
)
async def end_button(self, interaction, button):
    if not await self.allowed(interaction):
        return

    guild_id = interaction.guild.id
    self.cog.get_queue(guild_id).clear()
    self.cog.repeat_enabled[guild_id] = False
    self.cog.skip_requested.add(guild_id)

    voice = interaction.guild.voice_client
    if voice and (voice.is_playing() or voice.is_paused()):
        voice.stop()

    await private_message(
        interaction,
        "⏹️ تم إنهاء التشغيل",
        "تم تفريغ قائمة الانتظار وإيقاف الأغنية الحالية.",
        GREEN,
    )

@discord.ui.button(
    label="القائمة", emoji="📜",
    style=discord.ButtonStyle.secondary,
    custom_id="diaa_music:queue", row=1,
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
            name="🎶 الأغنية الحالية",
            value=f"[{current.title}]({current.webpage_url})",
            inline=False,
        )

    if queue:
        lines = [
            f"`{i}.` [{song.title}]({song.webpage_url})"
            for i, song in enumerate(queue[:15], start=1)
        ]

        if len(queue) > 15:
            lines.append(
                f"... وهناك {len(queue) - 15} أغنية أخرى."
            )

        embed.add_field(
            name="⏳ الأغاني المنتظرة",
            value="\n".join(lines),
            inline=False,
        )
    elif not current:
        embed.description = "لا توجد أغانٍ في القائمة حاليًا."
    else:
        embed.add_field(
            name="⏳ الأغاني المنتظرة",
            value="لا توجد أغانٍ أخرى تنتظر التشغيل.",
            inline=False,
        )

    embed.add_field(
        name="📊 عدد الأغاني المنتظرة",
        value=str(len(queue)),
        inline=True,
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True,
    )

@discord.ui.button(
    label="الأغنية الحالية", emoji="🎧",
    style=discord.ButtonStyle.secondary,
    custom_id="diaa_music:now", row=1,
)
async def now_button(self, interaction, button):
    if not await self.allowed(interaction):
        return

    song = self.cog.current_songs.get(interaction.guild.id)

    if not song:
        await private_message(
            interaction,
            "🎧 لا توجد أغنية",
            "لا توجد أغنية قيد التشغيل حاليًا.",
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
    label="خلط", emoji="🔀",
    style=discord.ButtonStyle.secondary,
    custom_id="diaa_music:shuffle", row=1,
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
    label="تكرار", emoji="🔁",
    style=discord.ButtonStyle.secondary,
    custom_id="diaa_music:repeat", row=1,
)
async def repeat_button(self, interaction, button):
    if not await self.allowed(interaction):
        return

    guild_id = interaction.guild.id
    enabled = not self.cog.repeat_enabled.get(guild_id, False)
    self.cog.repeat_enabled[guild_id] = enabled

    await private_message(
        interaction,
        "🔁 التكرار",
        "تم تفعيل التكرار." if enabled else "تم إيقاف التكرار.",
        GREEN,
    )

@discord.ui.button(
    label="حذف أغنية", emoji="🗑️",
    style=discord.ButtonStyle.danger,
    custom_id="diaa_music:remove", row=1,
)
async def remove_button(self, interaction, button):
    if await self.allowed(interaction):
        await interaction.response.send_modal(
            RemoveSongModal(self.cog)
        )

@discord.ui.button(
    label="الصوت", emoji="🔊",
    style=discord.ButtonStyle.secondary,
    custom_id="diaa_music:volume", row=2,
)
async def volume_button(self, interaction, button):
    if await self.allowed(interaction):
        await interaction.response.send_modal(
            VolumeModal(self.cog)
        )

@discord.ui.button(
    label="تعال", emoji="📍",
    style=discord.ButtonStyle.primary,
    custom_id="diaa_music:come", row=2,
)
async def come_button(self, interaction, button):
    if not await self.allowed(interaction):
        return

    member = interaction.user
    if not isinstance(member, discord.Member):
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
                if voice.channel.id != channel.id:
                    await voice.move_to(channel)
            else:
                await channel.connect(
                    self_deaf=True,
                    timeout=30,
                    reconnect=True,
                )

        await private_message(
            interaction,
            "📍 تم الانتقال",
            f"البوت متصل الآن بـ {channel.mention}.",
            GREEN,
        )

        await self.cog.start_worker(interaction.guild)

    except Exception:
        logging.exception("Voice connection/move failed")
        await private_message(
            interaction,
            "❌ تعذر الاتصال",
            "تحقق من صلاحيات الاتصال والتحدث في الروم.",
            RED,
        )

@discord.ui.button(
    label="مغادرة", emoji="👋",
    style=discord.ButtonStyle.danger,
    custom_id="diaa_music:leave", row=2,
)
async def leave_button(self, interaction, button):
    if not await self.allowed(interaction):
        return

    guild_id = interaction.guild.id
    self.cog.get_queue(guild_id).clear()
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
        "تم فصل البوت وتفريغ قائمة الانتظار.",
        GREEN,
    )

@discord.ui.button(
    label="الأوامر", emoji="📖",
    style=discord.ButtonStyle.secondary,
    custom_id="diaa_music:help", row=2,
)
async def help_button(self, interaction, button):
    if not await self.allowed(interaction):
        return

    embed = make_embed(
        "📖 | دليل لوحة الموسيقى",
        "استخدم الأزرار للتحكم بالموسيقى.",
    )
    embed.add_field(
        name="🎵 التشغيل",
        value="**تشغيل:** اكتب اسم الأغنية أو رابطها.",
        inline=False,
    )
    embed.add_field(
        name="⏯️ التحكم",
        value=(
            "**إيقاف مؤقت**، **كمل**، **تخطي**، **إنهاء**.\n"
            "**القائمة** لعرض الأغاني المنتظرة.\n"
            "**الأغنية الحالية** لعرض الأغنية الجاري تشغيلها."
        ),
        inline=False,
    )
    embed.add_field(
        name="🔊 إدارة الموسيقى",
        value=(
            "**خلط**، **تكرار**، **حذف أغنية**، **الصوت**.\n"
            "**تعال** للاتصال برومك الصوتي، و**مغادرة** للفصل."
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
def init(self, bot):
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
            "استخدم اللوحة من داخل السيرفر.",
            RED,
        )
        return False

    if interaction.channel_id not in ALLOWED_TEXT_CHANNEL_IDS:
        await private_message(
            interaction,
            "📍 روم غير مسموح",
            "استخدم لوحة الموسيقى في الرومات المخصصة.",
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
# SEARCH SONG
# -----------------------------------------------------

async def search_song(self, query):
    def extract():
        # دعم رابط YouTube أو البحث باسم الأغنية.
        target = query
        if not query.startswith(("https://", "http://")):
            target = f"ytsearch1:{query}"

        result = self.ytdl.extract_info(
            target,
            download=False,
        )

        if not result:
            return None

        if result.get("entries") is not None:
            entries = result.get("entries") or []
            info = next((entry for entry in entries if entry), None)
        else:
            info = result

        if not info:
            return None

        webpage_url = (
            info.get("webpage_url")
            or info.get("original_url")
            or query
        )

        if not webpage_url.startswith(("https://", "http://")):
            video_id = info.get("id")
            if not video_id:
                return None
            webpage_url = (
                f"https://www.youtube.com/watch?v={video_id}"
            )

        return Song(
            title=info.get("title", "أغنية بدون عنوان"),
            webpage_url=webpage_url,
            stream_url=info.get("url", ""),
            requester_id=0,
            text_channel_id=0,
        )

    return await asyncio.to_thread(extract)

# -----------------------------------------------------
# REFRESH STREAM - FIXED
# -----------------------------------------------------

async def refresh_stream(self, song):
    """تجديد رابط الصوت قبل التشغيل."""

    def extract():
        info = self.ytdl.extract_info(
            song.webpage_url,
            download=False,
        )

        if not info:
            return None

        stream_url = info.get("url")

        if not stream_url:
            formats = [
                item
                for item in info.get("formats", [])
                if item.get("url")
                and item.get("acodec") != "none"
            ]

            if formats:
                stream_url = formats[-1]["url"]

        if not stream_url:
            return None

        return info.get("title", song.title), stream_url

    try:
        result = await asyncio.to_thread(extract)

        if not result:
            logging.error(
                "No audio stream returned for: %s",
                song.webpage_url,
            )
            return False

        song.title, song.stream_url = result
        return True

    except Exception:
        logging.exception(
            "Failed to refresh audio stream for %s",
            song.webpage_url,
        )
        return False

# -----------------------------------------------------
# ADD SONG
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
        logging.exception("Song search failed")

        await interaction.followup.send(
            embed=make_embed(
                "❌ | فشل البحث",
                "تعذر جلب الأغنية. قد يكون YouTube قد رفض الطلب.",
                RED,
            ),
            ephemeral=True,
        )
        return

    if song is None:
        await interaction.followup.send(
            embed=make_embed(
                "🔍 | لم أجد الأغنية",
                "جرّب اسمًا آخر أو رابط فيديو صالحًا.",
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
                            "اضغط زر **تعال** لنقل البوت إلى رومك.",
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

            # تضاف الأغنية مرة واحدة إلى قائمة الانتظار.
            queue.append(song)
            position = len(queue)

        await interaction.followup.send(
            embed=make_embed(
                "✅ | تمت إضافة الأغنية",
                f"**[{song.title}]({song.webpage_url})**",
                GREEN,
            ),
            ephemeral=True,
        )

        await self.start_worker(guild)

    except Exception:
        logging.exception("Could not enqueue song")

        await interaction.followup.send(
            embed=make_embed(
                "❌ | تعذر إضافة الأغنية",
                "تحقق من اتصال البوت وصلاحيات الروم الصوتي.",
                RED,
            ),
            ephemeral=True,
        )

# -----------------------------------------------------
# WORKER MANAGEMENT
# -----------------------------------------------------

async def start_worker(self, guild):
    guild_id = guild.id
    task = self.workers.get(guild_id)

    if task is None or task.done():
        self.workers[guild_id] = asyncio.create_task(
            self.music_worker(guild)
        )

async def send_announcement(self, title, description, color=GREEN):
    channel = self.bot.get_channel(
        PLAYING_ANNOUNCEMENT_CHANNEL_ID
    )

    if channel is None:
        try:
            channel = await self.bot.fetch_channel(
                PLAYING_ANNOUNCEMENT_CHANNEL_ID
            )
        except Exception:
            logging.exception("Could not fetch announcement channel")
            return

    try:
        await channel.send(
            embed=make_embed(title, description, color)
        )
    except Exception:
        logging.exception("Could not send announcement")

async def music_worker(self, guild):
    guild_id = guild.id
    this_task = asyncio.current_task()

    try:
        while self.get_queue(guild_id):
            # تُنقل الأغنية إلى current_songs عند محاولة تشغيلها.
            song = self.get_queue(guild_id).pop(0)
            self.current_songs[guild_id] = song

            try:
                voice = guild.voice_client

                if not voice or not voice.is_connected():
                    # لا نحذف الأغنية إذا انقطع الاتصال.
                    self.get_queue(guild_id).insert(0, song)
                    logging.warning(
                        "Voice disconnected; returned song to queue."
                    )
                    break

                if not await self.refresh_stream(song):
                    # فشل جلب الصوت: نخبر المستخدم بسبب الفشل ونكمل.
                    await self.send_announcement(
                        "❌ | تعذر تجهيز الأغنية",
                        (
                            f"لم أتمكن من جلب الصوت لـ **{song.title}**.\n"
                            "تحقق من سجل Railway لمعرفة سبب الرفض."
                        ),
                        RED,
                    )
                    continue

                # إعادة التحقق من اتصال الصوت قبل بدء التشغيل.
                voice = guild.voice_client
                if not voice or not voice.is_connected():
                    self.get_queue(guild_id).insert(0, song)
                    break

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

                await self.send_announcement(
                    "🎶 | يتم التشغيل الآن",
                    (
                        f"**[{song.title}]({song.webpage_url})**\n"
                        f"👤 طلب الأغنية: <@{song.requester_id}>"
                    ),
                    GREEN,
                )

                # ننتظر انتهاء الأغنية أو تخطيها.
                await finished.wait()

                was_skipped = guild_id in self.skip_requested
                self.skip_requested.discard(guild_id)

                # تكرار الأغنية فقط عند انتهائها طبيعيًا.
                if (
                    self.repeat_enabled.get(guild_id, False)
                    and not was_skipped
                ):
                    self.get_queue(guild_id).insert(
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

                await self.send_announcement(
                    "❌ | خطأ في التشغيل",
                    (
                        f"تعذر تشغيل **{song.title}**.\n"
                        "راجع سجل Railway لمعرفة الخطأ."
                    ),
                    RED,
                )

            finally:
                self.current_songs.pop(guild_id, None)

    except asyncio.CancelledError:
        raise

    finally:
        if self.workers.get(guild_id) is this_task:
            self.workers.pop(guild_id, None)

        # إذا أضيفت أغنية قرب نهاية العامل، شغّل عاملًا جديدًا.
        if self.get_queue(guild_id):
            await self.start_worker(guild)

# -----------------------------------------------------
# DASHBOARD COMMAND
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
            "🎵 **تشغيل:** اكتب اسم الأغنية أو رابطها.\n"
            "⏸️ **إيقاف مؤقت** و ▶️ **كمل** للتحكم بالتشغيل.\n"
            "⏭️ **تخطي** للانتقال إلى التالية.\n"
            "⏹️ **إنهاء** لتفريغ قائمة الانتظار.\n\n"
            "📜 اعرض القائمة، غيّر الصوت، اخلط الأغاني، "
            "أو انقل البوت إلى رومك من الأزرار.\n\n"
            "🔒 ردود التحكم تظهر لك بشكل خاص."
        ),
    )

    embed.add_field(
        name="🔊 الصوت الافتراضي",
        value=f"{int(DEFAULT_VOLUME * 100)}%",
        inline=True,
    )
    embed.add_field(
        name="📚 الحد الأقصى",
        value=f"{MAX_QUEUE_SIZE} أغنية",
        inline=True,
    )

    await ctx.send(embed=embed, view=self.dashboard)

async def setup(bot):
await bot.add_cog(MusicCog(bot))
