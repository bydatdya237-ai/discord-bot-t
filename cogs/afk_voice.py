
import os
import asyncio
import discord
from discord.ext import commands
from pymongo import MongoClient


# ========================================================
# إعدادات قاعدة البيانات
# ========================================================

MONGO_URI = os.environ.get("MONGO_URI")

if not MONGO_URI:
    raise RuntimeError("MONGO_URI غير موجود")

mongo_client = MongoClient(MONGO_URI)
db = mongo_client["discord_bot_db"]

afk_voice_settings = db["afk_voice_settings"]


# ========================================================
# نافذة إدخال ID الروم الصوتي
# ========================================================

class AFKVoiceModal(discord.ui.Modal, title="إعداد الروم الصوتي"):

    channel_id = discord.ui.TextInput(
        label="ID الروم الصوتي",
        placeholder="أدخل ID الروم الصوتي هنا",
        required=True,
        max_length=25
    )

    async def on_submit(self, interaction: discord.Interaction):

        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ استخدم الأمر داخل السيرفر.",
                ephemeral=True
            )
            return

        raw_id = str(self.channel_id.value).strip()

        if not raw_id.isdigit():
            await interaction.response.send_message(
                "❌ ID الروم يجب أن يتكون من أرقام فقط.",
                ephemeral=True
            )
            return

        channel_id = int(raw_id)
        guild = interaction.guild

        channel = guild.get_channel(channel_id)

        if channel is None:
            try:
                channel = await guild.fetch_channel(channel_id)
            except discord.HTTPException:
                await interaction.response.send_message(
                    "❌ لم أتمكن من العثور على الروم. تأكد من الـ ID.",
                    ephemeral=True
                )
                return

        if not isinstance(channel, discord.VoiceChannel):
            await interaction.response.send_message(
                "❌ هذا ليس رومًا صوتيًا عاديًا.",
                ephemeral=True
            )
            return

        bot_member = guild.me

        if bot_member is None:
            await interaction.response.send_message(
                "❌ تعذر تحديد حساب البوت داخل السيرفر.",
                ephemeral=True
            )
            return

        permissions = channel.permissions_for(bot_member)

        if not permissions.view_channel or not permissions.connect:
            await interaction.response.send_message(
                "❌ البوت يحتاج صلاحيتَي View Channel و Connect في هذا الروم.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        # حفظ الإعداد حتى يبقى بعد إعادة التشغيل
        afk_voice_settings.update_one(
            {"guild_id": str(guild.id)},
            {
                "$set": {
                    "guild_id": str(guild.id),
                    "channel_id": str(channel.id)
                }
            },
            upsert=True
        )

        # الاتصال بالروم أو الانتقال إليه
        try:
            voice_client = guild.voice_client

            if voice_client and voice_client.is_connected():
                if voice_client.channel.id != channel.id:
                    await voice_client.move_to(channel)
            else:
                if voice_client:
                    await voice_client.disconnect(force=True)

                await channel.connect(timeout=20, reconnect=True)

            embed = discord.Embed(
                title="🔊 تم إعداد الروم الصوتي",
                description=(
                    f"**الروم:** {channel.mention}\n"
                    f"**ID:** `{channel.id}`\n\n"
                    "✅ تم حفظ الإعداد والاتصال بالروم.\n"
                    "🔇 البوت سيبقى ساكتًا دون تشغيل أي صوت."
                ),
                color=discord.Color.from_rgb(182, 108, 255)
            )

            await interaction.followup.send(
                embed=embed,
                ephemeral=True
            )

        except Exception as error:
            print(
                f"[AFK VOICE ERROR] "
                f"{type(error).__name__}: {error}"
            )

            await interaction.followup.send(
                "⚠️ تم حفظ الروم، لكن تعذر الاتصال به. "
                "تحقق من صلاحيات البوت وتثبيت PyNaCl.",
                ephemeral=True
            )


# ========================================================
# زر إعداد الروم
# ========================================================

class AFKVoiceView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(
        label="تحديد الروم الصوتي",
        style=discord.ButtonStyle.primary,
        emoji="🔊"
    )
    async def set_voice_channel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.send_modal(
            AFKVoiceModal()
        )


# ========================================================
# البوت الصوتي
# ========================================================

class AFKVoiceCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.startup_task = None

    async def cog_load(self):
        self.startup_task = asyncio.create_task(
            self.connect_saved_channels()
        )

    async def cog_unload(self):
        if self.startup_task and not self.startup_task.done():
            self.startup_task.cancel()

    async def connect_saved_channels(self):

        await self.bot.wait_until_ready()

        settings = list(afk_voice_settings.find({}))

        for setting in settings:

            try:
                guild_id = int(setting["guild_id"])
                channel_id = int(setting["channel_id"])

                guild = self.bot.get_guild(guild_id)

                if guild is None:
                    continue

                channel = guild.get_channel(channel_id)

                if channel is None:
                    try:
                        channel = await guild.fetch_channel(channel_id)
                    except discord.HTTPException:
                        continue

                if not isinstance(channel, discord.VoiceChannel):
                    continue

                voice_client = guild.voice_client

                if voice_client and voice_client.is_connected():
                    if voice_client.channel.id != channel.id:
                        await voice_client.move_to(channel)
                    continue

                if voice_client:
                    await voice_client.disconnect(force=True)

                await channel.connect(
                    timeout=20,
                    reconnect=True
                )

                print(
                    f"🔊 [AFK VOICE] Connected to "
                    f"{channel.name} in {guild.name}"
                )

            except asyncio.CancelledError:
                raise

            except Exception as error:
                print(
                    f"❌ [AFK VOICE STARTUP ERROR] "
                    f"{type(error).__name__}: {error}"
                )

    # ====================================================
    # أمر افك
    # ====================================================

    @commands.command(name="افك")
    async def afk_voice(self, ctx):

        embed = discord.Embed(
            title="🔊 إعداد الروم الصوتي",
            description=(
                "من هنا يمكنك تحديد الروم الذي سيدخل إليه البوت "
                "ويبقى فيه ساكتًا.\n\n"
                "اضغط على الزر بالأسفل، ثم أدخل ID الروم الصوتي.\n\n"
                "• يتم حفظ الإعداد في قاعدة البيانات.\n"
                "• يحاول البوت الاتصال بالروم عند تشغيله.\n"
                "• لن يشغّل موسيقى أو يصدر أي صوت."
            ),
            color=discord.Color.from_rgb(182, 108, 255)
        )

        embed.set_footer(
            text="AFK Voice • Diaa BOT"
        )

        await ctx.send(
            embed=embed,
            view=AFKVoiceView()
        )


# ========================================================
# تحميل الـ Cog
# ========================================================

async def setup(bot):
    await bot.add_cog(AFKVoiceCog(bot))
