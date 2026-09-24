import os
import re
import discord

from discord.ext import commands
from discord import ui
from pymongo import MongoClient


# =========================================================
# MongoDB
# =========================================================

MONGO_URI = os.getenv("MONGO_URI")

mongo_client = MongoClient(MONGO_URI)
db = mongo_client["discord_bot_db"]

# إعدادات التوب لكل سيرفر
top_settings_collection = db["top_announcement_settings"]


# =========================================================
# الجوائز الافتراضية
# =========================================================

DEFAULT_PRIZES = {
    1: {
        "gold": 450,
        "ai": 250000
    },
    2: {
        "gold": 250,
        "ai": 150000
    },
    3: {
        "gold": 100,
        "ai": 50000
    }
}


# =========================================================
# أدوات Mongo
# =========================================================

def get_settings(guild_id: int):
    settings = top_settings_collection.find_one(
        {"guild_id": guild_id}
    )

    if not settings:
        settings = {
            "guild_id": guild_id,
            "source_channel_id": None,
            "top_message_channel_id": None,
            "announcement_channel_id": None,
            "contribution_log_channel_id": None
        }

        top_settings_collection.insert_one(settings)

    return settings


def save_channel(guild_id: int, field: str, channel_id: int):
    top_settings_collection.update_one(
        {"guild_id": guild_id},
        {
            "$set": {
                field: channel_id
            }
        },
        upsert=True
    )


# =========================================================
# تحويل الأرقام
# =========================================================

def parse_amount(value):
    if value is None:
        return 0

    value = str(value).strip().lower().replace(",", "")

    try:
        if value.endswith("k"):
            return int(float(value[:-1]) * 1_000)

        if value.endswith("m"):
            return int(float(value[:-1]) * 1_000_000)

        if value.endswith("b"):
            return int(float(value[:-1]) * 1_000_000_000)

        if value.endswith("t"):
            return int(float(value[:-1]) * 1_000_000_000_000)

        return int(float(value))

    except Exception:
        return 0


# =========================================================
# استخراج نص الرسالة
# =========================================================

def get_message_text(message: discord.Message):

    parts = []

    if message.content:
        parts.append(message.content)

    for embed in message.embeds:

        if embed.title:
            parts.append(embed.title)

        if embed.description:
            parts.append(embed.description)

        if embed.author and embed.author.name:
            parts.append(embed.author.name)

        for field in embed.fields:
            if field.name:
                parts.append(field.name)

            if field.value:
                parts.append(field.value)

        if embed.footer and embed.footer.text:
            parts.append(embed.footer.text)

    return "\n".join(parts)


# =========================================================
# استخراج أفضل 3
# =========================================================

def extract_top_3(message: discord.Message):

    text = get_message_text(message)

    results = []

    # استخراج المنشنات
    mentions = re.findall(
        r"<@!?(\d+)>",
        text
    )

    for user_id in mentions:

        if user_id not in results:
            results.append(user_id)

        if len(results) >= 3:
            break

    # محاولة إضافية من الأسطر
    if len(results) < 3:

        for line in text.splitlines():

            found = re.findall(
                r"<@!?(\d+)>",
                line
            )

            for user_id in found:

                if user_id not in results:
                    results.append(user_id)

                if len(results) >= 3:
                    break

            if len(results) >= 3:
                break

    return results[:3]


# =========================================================
# جلب رسالة التوب
# =========================================================

async def get_top_message(channel: discord.TextChannel):

    try:

        async for message in channel.history(limit=30):

            text = get_message_text(message)

            if not text:
                continue

            top = extract_top_3(message)

            if len(top) >= 3:
                return message, top

    except Exception:
        return None, []

    return None, []


# =========================================================
# مودال تعديل الجائزة
# =========================================================

class PrizeEditModal(ui.Modal):

    def __init__(self, place, parent_view):

        super().__init__(
            title=f"تعديل جائزة المركز {place}"
        )

        self.place = place
        self.parent_view = parent_view

        self.gold_input = ui.TextInput(
            label="الجولد",
            placeholder="مثال: 450",
            default=str(
                parent_view.prizes[place]["gold"]
            ),
            required=True
        )

        self.ai_input = ui.TextInput(
            label="Ai",
            placeholder="مثال: 250000",
            default=str(
                parent_view.prizes[place]["ai"]
            ),
            required=True
        )

        self.add_item(self.gold_input)
        self.add_item(self.ai_input)

    async def on_submit(self, interaction: discord.Interaction):

        gold = parse_amount(self.gold_input.value)
        ai = parse_amount(self.ai_input.value)

        if gold < 0 or ai < 0:

            await interaction.response.send_message(
                "❌ قيم الجوائز غير صحيحة.",
                ephemeral=True
            )
            return

        self.parent_view.prizes[self.place] = {
            "gold": gold,
            "ai": ai
        }

        await interaction.response.edit_message(
            embed=self.parent_view.build_embed(),
            view=self.parent_view
        )


# =========================================================
# اختيار الجائزة
# =========================================================

class PrizeSelectView(ui.View):

    def __init__(self, parent_view):

        super().__init__(timeout=180)

        self.parent_view = parent_view

        options = [
            discord.SelectOption(
                label="المركز الأول",
                value="1",
                emoji="🥇"
            ),
            discord.SelectOption(
                label="المركز الثاني",
                value="2",
                emoji="🥈"
            ),
            discord.SelectOption(
                label="المركز الثالث",
                value="3",
                emoji="🥉"
            )
        ]

        self.select = ui.Select(
            placeholder="اختر المركز لتعديل جائزته",
            options=options
        )

        self.select.callback = self.select_callback

        self.add_item(self.select)

    async def select_callback(self, interaction):

        place = int(self.select.values[0])

        await interaction.response.send_modal(
            PrizeEditModal(
                place,
                self.parent_view
            )
        )


# =========================================================
# واجهة الإعلان
# =========================================================

class AnnouncementView(ui.View):

    def __init__(
        self,
        cog,
        guild_id,
        top_users
    ):

        super().__init__(timeout=300)

        self.cog = cog
        self.guild_id = guild_id
        self.top_users = top_users

        self.prizes = {
            1: dict(DEFAULT_PRIZES[1]),
            2: dict(DEFAULT_PRIZES[2]),
            3: dict(DEFAULT_PRIZES[3])
        }

    # -----------------------------------------------------
    # Embed
    # -----------------------------------------------------

    def build_embed(self):

        embed = discord.Embed(
            title="🏆 إعلان أفضل 3",
            description="راجع الجوائز قبل إرسال الإعلان.",
            color=discord.Color.purple()
        )

        medals = {
            1: "🥇",
            2: "🥈",
            3: "🥉"
        }

        for place in range(1, 4):

            user_id = self.top_users[place - 1]

            prize = self.prizes[place]

            embed.add_field(
                name=f"{medals[place]} المركز {place}",
                value=(
                    f"<@{user_id}>\n"
                    f"💰 Gold: `{prize['gold']:,}`\n"
                    f"💎 Ai: `{prize['ai']:,}`"
                ),
                inline=False
            )

        return embed

    # -----------------------------------------------------
    # تعديل الجوائز
    # -----------------------------------------------------

    @ui.button(
        label="تعديل الجوائز",
        style=discord.ButtonStyle.primary,
        emoji="✏️"
    )
    async def edit_prizes(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.send_message(
            "اختر المركز الذي تريد تعديل جائزته:",
            view=PrizeSelectView(self),
            ephemeral=True
        )

    # -----------------------------------------------------
    # معاينة
    # -----------------------------------------------------

    @ui.button(
        label="معاينة",
        style=discord.ButtonStyle.secondary,
        emoji="👀"
    )
    async def preview(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.send_message(
            embed=self.build_embed(),
            ephemeral=True
        )

    # -----------------------------------------------------
    # إعلان
    # -----------------------------------------------------

    @ui.button(
        label="إعلان",
        style=discord.ButtonStyle.success,
        emoji="📢"
    )
    async def announce_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        settings = get_settings(
            self.guild_id
        )

        announcement_channel_id = settings.get(
            "announcement_channel_id"
        )

        if not announcement_channel_id:

            await interaction.response.send_message(
                "❌ لم يتم تحديد روم إعلان التوب.\n"
                "استخدم الأمر `-اعلان-التوب` داخل الروم المطلوب.",
                ephemeral=True
            )
            return

        channel = interaction.guild.get_channel(
            announcement_channel_id
        )

        if channel is None:

            await interaction.response.send_message(
                "❌ روم إعلان التوب المحفوظ غير موجود أو البوت لا يستطيع الوصول إليه.",
                ephemeral=True
            )
            return

        await interaction.response.defer(
            ephemeral=True
        )

        medals = {
            1: "🥇",
            2: "🥈",
            3: "🥉"
        }

        description = (
            "## 🏆 أفضل 3\n\n"
        )

        for place in range(1, 4):

            user_id = self.top_users[place - 1]

            prize = self.prizes[place]

            description += (
                f"{medals[place]} **المركز {place}**\n"
                f"👤 <@{user_id}>\n"
                f"💰 Gold: `{prize['gold']:,}`\n"
                f"💎 Ai: `{prize['ai']:,}`\n\n"
            )

        embed = discord.Embed(
            title="🏆 نتائج التوب",
            description=description,
            color=discord.Color.gold()
        )

        try:

            await channel.send(
                content=(
                    "@everyone\n"
                    f"<@&{self.cog.member_role_id}>"
                ),
                embed=embed,
                allowed_mentions=discord.AllowedMentions(
                    everyone=True,
                    roles=True,
                    users=True
                )
            )

            await interaction.followup.send(
                "✅ تم إرسال إعلان أفضل 3 بنجاح.",
                ephemeral=True
            )

            self.stop()

        except Exception as e:

            await interaction.followup.send(
                f"❌ حدث خطأ أثناء إرسال الإعلان:\n`{e}`",
                ephemeral=True
            )

    # -----------------------------------------------------
    # إلغاء
    # -----------------------------------------------------

    @ui.button(
        label="إلغاء",
        style=discord.ButtonStyle.danger,
        emoji="❌"
    )
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        self.stop()

        await interaction.response.edit_message(
            content="❌ تم إلغاء الإعلان.",
            embed=None,
            view=None
        )


# =========================================================
# Cog
# =========================================================

class AnnouncementCog(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        # رتبة العضو التي يتم منشنها في الإعلان
        self.member_role_id = 1544078847253811331

    # =====================================================
    # التحقق من صلاحية إعداد الرومات
    # =====================================================

    async def can_manage_top(self, ctx):

        if ctx.guild is None:
            return False

        # صاحب السيرفر
        if ctx.guild.owner_id == ctx.author.id:
            return True

        # Administrator / Manage Guild
        permissions = ctx.author.guild_permissions

        if permissions.administrator:
            return True

        if permissions.manage_guild:
            return True

        return False

    # =====================================================
    # سحب أفضل 3
    # يحفظ الروم الحالي كروم مصدر التوب
    # =====================================================

    @commands.command(
        name="سحب-افضل-3"
    )
    async def get_top_room(
        self,
        ctx
    ):

        if not await self.can_manage_top(ctx):
            return

        save_channel(
            ctx.guild.id,
            "source_channel_id",
            ctx.channel.id
        )

        await ctx.send(
            f"✅ تم حفظ {ctx.channel.mention} كروم مصدر التوب.\n"
            "الآن أي أمر `-اعلن` سيبحث عن رسالة التوب في هذا الروم."
        )

    # =====================================================
    # تحديد رسالة التوب
    # يحفظ الروم الحالي كمكان لرسالة التوب
    # =====================================================

    @commands.command(
        name="تحديد-رسالة-التوب"
    )
    async def set_top_message_room(
        self,
        ctx
    ):

        if not await self.can_manage_top(ctx):
            return

        save_channel(
            ctx.guild.id,
            "top_message_channel_id",
            ctx.channel.id
        )

        await ctx.send(
            f"✅ تم تحديد {ctx.channel.mention} كروم رسالة التوب."
        )

    # =====================================================
    # إعلان التوب
    # يحفظ الروم الحالي كروم الإعلان
    # =====================================================

    @commands.command(
        name="اعلان-التوب"
    )
    async def set_announcement_room(
        self,
        ctx
    ):

        if not await self.can_manage_top(ctx):
            return

        save_channel(
            ctx.guild.id,
            "announcement_channel_id",
            ctx.channel.id
        )

        await ctx.send(
            f"✅ تم تحديد {ctx.channel.mention} كروم إعلان أفضل 3."
        )

    # =====================================================
    # تحديد لوق المساهمات
    # يحفظ الروم فقط
    # =====================================================

    @commands.command(
        name="تحديد-لوق-المساهمات"
    )
    async def set_contribution_log(
        self,
        ctx
    ):

        if not await self.can_manage_top(ctx):
            return

        save_channel(
            ctx.guild.id,
            "contribution_log_channel_id",
            ctx.channel.id
        )

        await ctx.send(
            f"✅ تم تحديد {ctx.channel.mention} كلوق للمساهمات."
        )

    # =====================================================
    # إعلان
    # =====================================================

    @commands.command(
        name="اعلن"
    )
    async def announce(
        self,
        ctx
    ):

        if not await self.can_manage_top(ctx):
            return

        settings = get_settings(
            ctx.guild.id
        )

        source_channel_id = settings.get(
            "source_channel_id"
        )

        if not source_channel_id:

            await ctx.send(
                "❌ لم يتم تحديد روم سحب أفضل 3.\n"
                "استخدم `-سحب-افضل-3` داخل روم رسالة التوب."
            )

            return

        source_channel = ctx.guild.get_channel(
            source_channel_id
        )

        if source_channel is None:

            await ctx.send(
                "❌ روم مصدر التوب المحفوظ غير موجود أو لا أستطيع الوصول إليه."
            )

            return

        # ---------------------------------------------
        # البحث عن رسالة التوب
        # ---------------------------------------------

        message, top_users = await get_top_message(
            source_channel
        )

        if not message or len(top_users) < 3:

            await ctx.send(
                "❌ لم أجد رسالة توب تحتوي على أفضل 3 في الروم المحفوظ."
            )

            return

        # ---------------------------------------------
        # إرسال نسخة التوب إلى روم تحديد رسالة التوب
        # ---------------------------------------------

        top_message_channel_id = settings.get(
            "top_message_channel_id"
        )

        if top_message_channel_id:

            top_message_channel = ctx.guild.get_channel(
                top_message_channel_id
            )

            if top_message_channel:

                try:

                    top_text = (
                        "🏆 **أفضل 3**\n\n"
                        f"🥇 <@{top_users[0]}>\n"
                        f"🥈 <@{top_users[1]}>\n"
                        f"🥉 <@{top_users[2]}>"
                    )

                    await top_message_channel.send(
                        top_text,
                        allowed_mentions=discord.AllowedMentions(
                            users=True
                        )
                    )

                except Exception:
                    pass

        # ---------------------------------------------
        # واجهة الجوائز القديمة
        # ---------------------------------------------

        embed = discord.Embed(
            title="🏆 تجهيز إعلان أفضل 3",
            description=(
                "تم سحب أفضل 3 بنجاح.\n\n"
                "يمكنك الآن تعديل الجوائز أو معاينة الإعلان "
                "قبل إرساله."
            ),
            color=discord.Color.purple()
        )

        view = AnnouncementView(
            self,
            ctx.guild.id,
            top_users
        )

        await ctx.send(
            embed=embed,
            view=view
        )


# =========================================================
# Setup
# =========================================================

async def setup(bot):

    await bot.add_cog(
        AnnouncementCog(bot)
    )
