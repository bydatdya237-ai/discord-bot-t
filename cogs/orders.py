import os

import discord
from discord.ext import commands
from discord import ui
from pymongo import MongoClient


# =========================================================
# MongoDB
# =========================================================

MONGO_URI = os.getenv("MONGO_URI")

mongo = MongoClient(MONGO_URI)
db = mongo["discord_bot_db"]

command_settings_collection = db["website_command_settings"]


# =========================================================
# أسماء الإعدادات في الموقع
# =========================================================

COMMAND_NAME = "طلب"

LOG_COMMAND_NAME = "طلب-سجل"


# =========================================================
# جلب إعدادات أمر معين
# =========================================================

def get_command_settings(guild_id, command_name):

    settings = command_settings_collection.find_one({
        "guild_id": str(guild_id),
        "command_name": command_name
    })

    return settings


# =========================================================
# جلب إعدادات الطلب
# =========================================================

def get_order_settings(guild_id):

    return get_command_settings(
        guild_id,
        COMMAND_NAME
    )


# =========================================================
# جلب إعدادات سجل الطلبات
# =========================================================

def get_log_settings(guild_id):

    return get_command_settings(
        guild_id,
        LOG_COMMAND_NAME
    )


# =========================================================
# التحقق من أن الأمر مفعل
# =========================================================

def is_order_enabled(guild_id):

    settings = get_order_settings(guild_id)

    if not settings:
        return False

    return settings.get("enabled", True)


# =========================================================
# التحقق من روم استخدام الأمر
# =========================================================

def is_allowed_order_channel(ctx):

    if ctx.guild is None:
        return False

    settings = get_order_settings(
        ctx.guild.id
    )

    if not settings:
        return False

    if not settings.get("enabled", True):
        return False

    channel_ids = settings.get(
        "channel_ids",
        []
    )

    allowed_channels = {
        str(channel_id)
        for channel_id in channel_ids
    }

    return str(ctx.channel.id) in allowed_channels


# =========================================================
# التحقق من الرتبة
# =========================================================

def has_allowed_role(member):

    if not isinstance(member, discord.Member):
        return False

    settings = get_order_settings(
        member.guild.id
    )

    if not settings:
        return False

    if not settings.get("enabled", True):
        return False

    role_ids = settings.get(
        "role_ids",
        []
    )

    allowed_roles = {
        str(role_id)
        for role_id in role_ids
    }

    return any(
        str(role.id) in allowed_roles
        for role in member.roles
    )


# =========================================================
# جلب روم سجل الطلبات
# =========================================================

def get_log_channel_id(guild_id):

    settings = get_log_settings(
        guild_id
    )

    if not settings:
        return None

    if not settings.get("enabled", True):
        return None

    channel_ids = settings.get(
        "channel_ids",
        []
    )

    if not channel_ids:
        return None

    # أول روم يتم تحديده من الموقع
    try:
        return int(
            str(channel_ids[0])
        )
    except (ValueError, TypeError):
        return None


# =========================================================
# جلب روم سجل الطلبات
# =========================================================

async def get_log_channel(bot, guild):

    channel_id = get_log_channel_id(
        guild.id
    )

    if channel_id is None:
        return None

    channel = bot.get_channel(
        channel_id
    )

    if channel is None:

        try:
            channel = await bot.fetch_channel(
                channel_id
            )

        except (
            discord.NotFound,
            discord.Forbidden,
            discord.HTTPException
        ):
            return None

    # التأكد أن الروم داخل نفس السيرفر
    if getattr(channel, "guild", None):

        if channel.guild.id != guild.id:
            return None

    return channel


# =========================================================
# قائمة اختيار نوع الطلب
# =========================================================

class OrderSelect(ui.Select):

    def __init__(
        self,
        target_user
    ):

        self.target_user = target_user

        options = [

            discord.SelectOption(
                label="رفع طلب عملة",
                description="رفع طلب خاص بالعملة",
                emoji="💰"
            ),

            discord.SelectOption(
                label="رفع طلب رتبة",
                description="رفع طلب خاص بالرتبة",
                emoji="👑"
            ),

            discord.SelectOption(
                label="رفع طلب بنك",
                description="رفع طلب خاص بالبنك",
                emoji="🏦"
            ),

        ]

        super().__init__(
            placeholder="اختر نوع الطلب...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(
        self,
        interaction
    ):

        # =================================================
        # التأكد من أن الإعدادات ما زالت مفعلة
        # =================================================

        if interaction.guild is None:

            await interaction.response.send_message(
                "❌ تعذر تحديد السيرفر.",
                ephemeral=True
            )

            return

        if not is_order_enabled(
            interaction.guild.id
        ):

            await interaction.response.send_message(
                "❌ نظام الطلبات غير مفعل حاليًا.",
                ephemeral=True
            )

            return

        if not has_allowed_role(
            interaction.user
        ):

            await interaction.response.send_message(
                "❌ ليس لديك صلاحية استخدام نظام الطلبات.",
                ephemeral=True
            )

            return

        # =================================================
        # فتح نافذة السبب
        # =================================================

        modal = OrderModal(
            order_type=self.values[0],
            target_user=self.target_user
        )

        await interaction.response.send_modal(
            modal
        )


# =========================================================
# View اختيار نوع الطلب
# =========================================================

class OrderSelectView(ui.View):

    def __init__(
        self,
        target_user
    ):

        super().__init__(
            timeout=300
        )

        self.add_item(
            OrderSelect(
                target_user
            )
        )


# =========================================================
# نافذة كتابة السبب
# =========================================================

class OrderModal(
    ui.Modal,
    title="تقديم طلب جديد"
):

    def __init__(
        self,
        order_type,
        target_user
    ):

        super().__init__()

        self.order_type = order_type
        self.target_user = target_user

        self.reason_input = ui.TextInput(
            label="السبب / التفاصيل",
            style=discord.TextStyle.paragraph,
            placeholder="اكتب تفاصيل أو سبب طلبك هنا...",
            required=True,
            max_length=1000
        )

        self.add_item(
            self.reason_input
        )

    async def on_submit(
        self,
        interaction
    ):

        # =================================================
        # التأكد من السيرفر
        # =================================================

        if interaction.guild is None:

            await interaction.response.send_message(
                "❌ تعذر تحديد السيرفر.",
                ephemeral=True
            )

            return

        # =================================================
        # التأكد من تفعيل النظام
        # =================================================

        if not is_order_enabled(
            interaction.guild.id
        ):

            await interaction.response.send_message(
                "❌ نظام الطلبات غير مفعل حاليًا.",
                ephemeral=True
            )

            return

        # =================================================
        # التأكد من صلاحية مقدم الطلب
        # =================================================

        if not has_allowed_role(
            interaction.user
        ):

            await interaction.response.send_message(
                "❌ ليس لديك صلاحية استخدام نظام الطلبات.",
                ephemeral=True
            )

            return

        # =================================================
        # جلب روم السجل من الموقع
        # =================================================

        log_channel = await get_log_channel(
            self._get_bot(interaction),
            interaction.guild
        )

        if not log_channel:

            await interaction.response.send_message(
                "❌ لم يتم تحديد روم سجل الطلبات من الموقع.",
                ephemeral=True
            )

            return

        # =================================================
        # إنشاء الطلب
        # =================================================

        embed = discord.Embed(
            title="📋 طلب جديد",
            color=discord.Color.gold()
        )

        embed.add_field(
            name="نوع الطلب",
            value=self.order_type,
            inline=False
        )

        embed.add_field(
            name="العضو المطلوب له الطلب",
            value=self.target_user.mention,
            inline=True
        )

        embed.add_field(
            name="ايدي العضو",
            value=str(self.target_user.id),
            inline=True
        )

        embed.add_field(
            name="السبب",
            value=self.reason_input.value,
            inline=False
        )

        embed.add_field(
            name="مقدم الطلب",
            value=interaction.user.mention,
            inline=False
        )

        embed.add_field(
            name="حالة الطلب",
            value="⏳ قيد المراجعة",
            inline=False
        )

        # =================================================
        # إرسال الطلب
        # =================================================

        try:

            await log_channel.send(
                embed=embed,
                view=OrderActionView()
            )

        except discord.Forbidden:

            await interaction.response.send_message(
                "❌ البوت لا يملك صلاحية إرسال الرسائل في روم سجل الطلبات.",
                ephemeral=True
            )

            return

        except discord.HTTPException:

            await interaction.response.send_message(
                "❌ حدث خطأ أثناء إرسال الطلب.",
                ephemeral=True
            )

            return

        # =================================================
        # نجاح
        # =================================================

        await interaction.response.send_message(
            f"✅ تم إرسال الطلب بنجاح للعضو "
            f"{self.target_user.mention}",
            ephemeral=True
        )

    def _get_bot(self, interaction):

        return interaction.client


# =========================================================
# أزرار التحكم بالطلب
# =========================================================

class OrderActionView(ui.View):

    def __init__(self):

        super().__init__(
            timeout=None
        )

    # =====================================================
    # تم التسليم
    # =====================================================

    @ui.button(
        label="تم التسليم",
        style=discord.ButtonStyle.green,
        emoji="✅"
    )
    async def accept_order(
        self,
        interaction,
        button
    ):

        if not isinstance(
            interaction.user,
            discord.Member
        ):
            return

        # =================================================
        # التحقق من رتبة التحكم من الموقع
        # =================================================

        if not has_allowed_role(
            interaction.user
        ):

            await interaction.response.send_message(
                "❌ ليس لديك صلاحية للتحكم بالطلبات!",
                ephemeral=True
            )

            return

        # =================================================
        # التأكد من وجود Embed
        # =================================================

        if not interaction.message.embeds:

            await interaction.response.send_message(
                "❌ تعذر قراءة بيانات الطلب.",
                ephemeral=True
            )

            return

        embed = interaction.message.embeds[0]

        embed.color = discord.Color.green()

        for i, field in enumerate(
            embed.fields
        ):

            if field.name == "حالة الطلب":

                embed.set_field_at(
                    i,
                    name="حالة الطلب",
                    value=(
                        f"✅ تم التسليم\n"
                        f"بواسطة: {interaction.user.mention}"
                    ),
                    inline=False
                )

        try:

            await interaction.message.edit(
                embed=embed,
                view=None
            )

        except discord.HTTPException:

            await interaction.response.send_message(
                "❌ حدث خطأ أثناء تحديث الطلب.",
                ephemeral=True
            )

            return

        await interaction.response.send_message(
            f"✅ تم قبول الطلب بواسطة "
            f"{interaction.user.mention}",
            ephemeral=True
        )

    # =====================================================
    # لم يتم التسليم
    # =====================================================

    @ui.button(
        label="لم يتم التسليم",
        style=discord.ButtonStyle.red,
        emoji="❌"
    )
    async def reject_order(
        self,
        interaction,
        button
    ):

        if not isinstance(
            interaction.user,
            discord.Member
        ):
            return

        # =================================================
        # التحقق من رتبة التحكم من الموقع
        # =================================================

        if not has_allowed_role(
            interaction.user
        ):

            await interaction.response.send_message(
                "❌ ليس لديك صلاحية للتحكم بالطلبات!",
                ephemeral=True
            )

            return

        # =================================================
        # التأكد من وجود Embed
        # =================================================

        if not interaction.message.embeds:

            await interaction.response.send_message(
                "❌ تعذر قراءة بيانات الطلب.",
                ephemeral=True
            )

            return

        embed = interaction.message.embeds[0]

        embed.color = discord.Color.red()

        for i, field in enumerate(
            embed.fields
        ):

            if field.name == "حالة الطلب":

                embed.set_field_at(
                    i,
                    name="حالة الطلب",
                    value=(
                        f"❌ لم يتم التسليم\n"
                        f"بواسطة: {interaction.user.mention}"
                    ),
                    inline=False
                )

        try:

            await interaction.message.edit(
                embed=embed,
                view=None
            )

        except discord.HTTPException:

            await interaction.response.send_message(
                "❌ حدث خطأ أثناء تحديث الطلب.",
                ephemeral=True
            )

            return

        await interaction.response.send_message(
            f"❌ تم رفض الطلب بواسطة "
            f"{interaction.user.mention}",
            ephemeral=True
        )


# =========================================================
# Cog
# =========================================================

class OrdersCog(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

    # =====================================================
    # أمر -طلب
    # =====================================================

    @commands.command(
        name="طلب"
    )
    async def order_cmd(
        self,
        ctx,
        member: discord.Member = None
    ):

        # =================================================
        # يجب أن يكون داخل سيرفر
        # =================================================

        if ctx.guild is None:
            return

        # =================================================
        # التحقق من إعدادات الموقع
        # =================================================

        settings = get_order_settings(
            ctx.guild.id
        )

        if not settings:
            return

        if not settings.get(
            "enabled",
            True
        ):
            return

        # =================================================
        # التحقق من الروم
        # =================================================

        if not is_allowed_order_channel(
            ctx
        ):
            return

        # =================================================
        # التحقق من الرتبة
        # =================================================

        if not has_allowed_role(
            ctx.author
        ):

            return

        # =================================================
        # إذا لم يتم تحديد شخص
        # =================================================

        if member is None:

            await ctx.send(
                "❌ **خطأ في الاستخدام**\n"
                "يجب تحديد العضو المطلوب بالمنشن.\n\n"
                "📝 **مثال:**\n"
                "`-طلب @الشخص`",
                delete_after=10
            )

            try:

                await ctx.message.delete()

            except discord.HTTPException:
                pass

            return

        # =================================================
        # منع البوتات
        # =================================================

        if member.bot:

            await ctx.send(
                "❌ لا يمكن تقديم طلبات للبوتات.",
                delete_after=10
            )

            try:

                await ctx.message.delete()

            except discord.HTTPException:
                pass

            return

        # =================================================
        # رسالة اختيار نوع الطلب
        # =================================================

        embed = discord.Embed(
            title="📄 رفع طلب",
            description=(
                f"**العضو:** {member.mention}\n\n"
                "اختر نوع الطلب من القائمة بالأسفل."
            ),
            color=discord.Color.gold()
        )

        await ctx.send(
            embed=embed,
            view=OrderSelectView(
                member
            )
        )

        # =================================================
        # حذف أمر -طلب
        # =================================================

        try:

            await ctx.message.delete()

        except discord.HTTPException:
            pass


# =========================================================
# Setup
# =========================================================

async def setup(bot):

    await bot.add_cog(
        OrdersCog(bot)
    )

[/writing]

ملاحظة مهمة جدًا

في النسخة الأصلية كان عندك روم واحد فقط:

COMMAND_ROOM_ID

و:

LOG_CHANNEL_ID

الآن صار التحكم من الموقع، لذلك تحتاج في الموقع إعدادين:

1. أمر "طلب"

- "channel_ids" = الروم الذي يسمح باستخدام "-طلب"
- "role_ids" = الرتب المسموح لها باستخدامه
- "enabled" = تشغيل/إيقاف

2. أمر "طلب-سجل"

- "channel_ids" = روم استقبال الطلبات
- "enabled" = تشغيل/إيقاف

وبكذا كل سيرفر يقدر يختار الروم والرتب بنفسه، وما فيه IDs ثابتة مرتبطة بسيرفرك أنت.
