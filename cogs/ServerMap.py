import os

import discord
from discord.ext import commands
from discord import ui
from pymongo import MongoClient


# =========================================================
# MongoDB
# =========================================================

MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    raise RuntimeError("MONGO_URI غير موجود في Environment Variables")

mongo_client = MongoClient(MONGO_URI)

db = mongo_client.discord_bot_db

collection = db["server_map_settings"]

website_collection = db["website_command_settings"]


# =========================================================
# أسماء الأوامر في الموقع
# =========================================================

CREATE_COMMAND_NAME = "خريطة-إنشاء"
SETUP_COMMAND_NAME = "خريطة-إعداد"


# =========================================================
# جلب إعداد الأمر من الموقع
# =========================================================

def get_website_command_setting(guild_id, command_name):

    guild_id_variants = [
        str(guild_id)
    ]

    try:
        guild_id_variants.append(
            int(guild_id)
        )
    except Exception:
        pass

    # =====================================================
    # الطريقة الجديدة
    # =====================================================

    setting = website_collection.find_one(
        {
            "guild_id": {
                "$in": guild_id_variants
            },
            "command_name": str(command_name)
        }
    )

    if setting:
        return setting

    # =====================================================
    # دعم البيانات القديمة
    # =====================================================

    setting = website_collection.find_one(
        {
            "guild_id": {
                "$in": guild_id_variants
            },
            "name": str(command_name)
        }
    )

    if setting:
        return setting

    # =====================================================
    # دعم command
    # =====================================================

    setting = website_collection.find_one(
        {
            "guild_id": {
                "$in": guild_id_variants
            },
            "command": str(command_name)
        }
    )

    return setting


# =========================================================
# تحويل IDs إلى Set
# =========================================================

def normalize_ids(value):

    if value is None:
        return set()

    if not isinstance(value, (list, tuple, set)):
        value = [value]

    result = set()

    for item in value:

        try:
            result.add(
                int(str(item))
            )
        except (
            ValueError,
            TypeError
        ):
            continue

    return result


# =========================================================
# التحقق من صلاحية الأمر من الموقع
#
# مطابق لنظام استدعاء:
#
# - الإعداد موجود
# - الأمر مفعّل
# - الرتبة محددة
# - العضو يملك الرتبة
# - الروم محدد
# - العضو داخل الروم المسموح
# =========================================================

def website_command_allowed(
    member,
    channel,
    command_name
):

    if member is None:
        return False

    if member.guild is None:
        return False

    setting = get_website_command_setting(
        member.guild.id,
        command_name
    )

    # =====================================================
    # لا يوجد إعداد
    # =====================================================

    if not setting:
        return False

    # =====================================================
    # الأمر غير مفعّل
    # =====================================================

    if not setting.get(
        "enabled",
        False
    ):
        return False

    # =====================================================
    # الرتب المسموحة
    # =====================================================

    role_ids = setting.get(
        "role_ids",
        []
    )

    if not role_ids:
        return False

    allowed_role_ids = {
        str(role_id)
        for role_id in role_ids
    }

    user_role_ids = {
        str(role.id)
        for role in member.roles
    }

    # =====================================================
    # العضو لا يملك الرتبة
    # =====================================================

    if not allowed_role_ids.intersection(
        user_role_ids
    ):
        return False

    # =====================================================
    # الرومات المسموحة
    # =====================================================

    channel_ids = setting.get(
        "channel_ids",
        []
    )

    if not channel_ids:
        return False

    allowed_channel_ids = {
        str(channel_id)
        for channel_id in channel_ids
    }

    # =====================================================
    # الروم الحالي غير مسموح
    # =====================================================

    if str(channel.id) not in allowed_channel_ids:
        return False

    return True


# =========================================================
# جلب إعدادات خريطة السيرفر
# =========================================================

def get_settings(guild_id):

    settings = collection.find_one(
        {
            "guild_id": guild_id
        }
    )

    if settings:
        return settings

    settings = {
        "guild_id": guild_id,
        "map_channel_id": None,
        "notification_roles": [],
        "map_channels": [],
        "rules": ""
    }

    collection.insert_one(
        settings
    )

    return settings


# =========================================================
# Embed القوانين
# =========================================================

def create_rules_embed(
    rules
):

    embed = discord.Embed(
        title="📜 قوانين السيرفر",
        description=str(rules),
        color=discord.Color.blurple()
    )

    embed.set_footer(
        text="يرجى الالتزام بقوانين السيرفر."
    )

    return embed


# =========================================================
# زر عرض القوانين
# =========================================================

class RulesButtonView(
    ui.View
):

    def __init__(
        self,
        rules
    ):

        super().__init__(
            timeout=None
        )

        self.rules = rules

    @ui.button(
        label="القوانين",
        style=discord.ButtonStyle.primary,
        emoji="📜",
        custom_id="server_map_rules"
    )
    async def rules_button(
        self,
        interaction: discord.Interaction,
        button: ui.Button
    ):

        # =================================================
        # إعادة جلب القوانين من Mongo
        # حتى لو تغيرت بعد إرسال الرسالة
        # =================================================

        settings = get_settings(
            interaction.guild.id
        )

        rules = settings.get(
            "rules",
            ""
        )

        rules = str(
            rules or ""
        ).strip()

        if not rules:

            await interaction.response.send_message(
                "ℹ️ لم يتم تحديد قوانين السيرفر حاليًا.",
                ephemeral=True
            )

            return

        await interaction.response.send_message(
            embed=create_rules_embed(
                rules
            ),
            ephemeral=True
        )


# =========================================================
# تحديث خريطة السيرفر
# =========================================================

async def update_server_map(
    guild
):

    settings = get_settings(
        guild.id
    )

    map_channel_id = settings.get(
        "map_channel_id"
    )

    if not map_channel_id:
        return

    try:
        map_channel_id = int(
            map_channel_id
        )
    except (
        ValueError,
        TypeError
    ):
        return

    channel = guild.get_channel(
        map_channel_id
    )

    if channel is None:
        return

    # =====================================================
    # حذف رسائل البوت السابقة
    # =====================================================

    try:

        async for message in channel.history(
            limit=100
        ):

            if message.author.id == guild.me.id:

                try:
                    await message.delete()
                except Exception:
                    pass

    except Exception:
        pass

    # =====================================================
    # رتب الإشعارات
    # =====================================================

    notification_role_ids = normalize_ids(
        settings.get(
            "notification_roles",
            []
        )
    )

    notification_roles = []

    for role_id in notification_role_ids:

        role = guild.get_role(
            role_id
        )

        if role:
            notification_roles.append(
                role
            )

    # =====================================================
    # لا نرسل Embed رتب الإشعارات
    # إذا لم يتم تحديد أي رتبة
    # =====================================================

    if notification_roles:

        notification_embed = discord.Embed(
            title="🔔 رتب الإشعارات",
            description=(
                "اختر رتبة الإشعارات التي تريد الحصول عليها.\n\n"
                "يمكنك أيضًا إزالة رتبة حصلت عليها مسبقًا."
            ),
            color=discord.Color.blurple()
        )

        roles_text = "\n".join(
            f"• {role.mention}"
            for role in notification_roles
        )

        notification_embed.add_field(
            name="الرتب المتاحة",
            value=roles_text,
            inline=False
        )

        notification_embed.set_footer(
            text="خريطة السيرفر"
        )

        await channel.send(
            embed=notification_embed,
            view=NotificationRoleView(
                guild.id
            )
        )

    # =====================================================
    # قنوات الخريطة
    # =====================================================

    map_channel_ids = normalize_ids(
        settings.get(
            "map_channels",
            []
        )
    )

    map_channels = []

    for channel_id in map_channel_ids:

        map_item = guild.get_channel(
            channel_id
        )

        if map_item:
            map_channels.append(
                map_item
            )

    # =====================================================
    # لا نرسل Embed القنوات
    # إذا لم يتم تحديد أي قناة
    # =====================================================

    if map_channels:

        map_embed = discord.Embed(
            title="🗺️ خريطة السيرفر",
            description=(
                "هذه هي القنوات المتاحة في السيرفر."
            ),
            color=discord.Color.blurple()
        )

        channels_text = "\n".join(
            f"• {item.mention}"
            for item in map_channels
        )

        map_embed.add_field(
            name="📍 القنوات",
            value=channels_text,
            inline=False
        )

        map_embed.set_footer(
            text="خريطة السيرفر"
        )

        await channel.send(
            embed=map_embed
        )

    # =====================================================
    # القوانين
    # =====================================================

    rules = settings.get(
        "rules",
        ""
    )

    rules = str(
        rules or ""
    ).strip()

    # =====================================================
    # زر القوانين فقط إذا توجد قوانين
    # =====================================================

    if rules:

        rules_button_embed = discord.Embed(
            title="📜 قوانين السيرفر",
            description=(
                "للاطلاع على قوانين السيرفر، "
                "اضغط على الزر بالأسفل."
            ),
            color=discord.Color.blurple()
        )

        rules_button_embed.set_footer(
            text="خريطة السيرفر"
        )

        await channel.send(
            embed=rules_button_embed,
            view=RulesButtonView(
                rules
            )
        )


# =========================================================
# اختيار رتبة إشعارات للإضافة
# =========================================================

class AddNotificationRoleSelect(
    ui.RoleSelect
):

    def __init__(
        self,
        guild_id
    ):

        super().__init__(
            placeholder="🔔 اختر رتبة الإشعارات",
            min_values=1,
            max_values=1
        )

        self.guild_id = guild_id

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        if interaction.guild is None:

            await interaction.response.send_message(
                "❌ تعذر تحديد السيرفر.",
                ephemeral=True
            )

            return

        settings = get_settings(
            self.guild_id
        )

        allowed_role_ids = normalize_ids(
            settings.get(
                "notification_roles",
                []
            )
        )

        selected_role = self.values[0]

        # =================================================
        # الرتبة ليست من الرتب المحددة
        # =================================================

        if selected_role.id not in allowed_role_ids:

            await interaction.response.send_message(
                "❌ هذه الرتبة ليست من رتب الإشعارات المتاحة.",
                ephemeral=True
            )

            return

        # =================================================
        # التحقق من رتبة البوت
        # =================================================

        me = interaction.guild.me

        if me is None:

            await interaction.response.send_message(
                "❌ تعذر تحديد البوت.",
                ephemeral=True
            )

            return

        if selected_role >= me.top_role:

            await interaction.response.send_message(
                "❌ البوت لا يستطيع إعطاء هذه الرتبة لأن رتبة البوت ليست أعلى منها.",
                ephemeral=True
            )

            return

        # =================================================
        # إضافة الرتبة
        # =================================================

        try:

            if selected_role in interaction.user.roles:

                await interaction.response.send_message(
                    "ℹ️ أنت تملك هذه الرتبة بالفعل.",
                    ephemeral=True
                )

                return

            await interaction.user.add_roles(
                selected_role,
                reason="اختيار رتبة إشعارات من خريطة السيرفر"
            )

            await interaction.response.send_message(
                f"✅ تم إعطاؤك رتبة {selected_role.mention}.",
                ephemeral=True
            )

        except discord.Forbidden:

            await interaction.response.send_message(
                "❌ البوت لا يملك صلاحية إعطاء هذه الرتبة.",
                ephemeral=True
            )

        except discord.HTTPException:

            await interaction.response.send_message(
                "❌ حدث خطأ أثناء إعطاء الرتبة.",
                ephemeral=True
            )


# =========================================================
# اختيار رتبة إشعارات للإزالة
# =========================================================

class RemoveNotificationRoleSelect(
    ui.RoleSelect
):

    def __init__(
        self,
        guild_id
    ):

        super().__init__(
            placeholder="🗑️ اختر رتبة الإشعارات لإزالتها",
            min_values=1,
            max_values=1
        )

        self.guild_id = guild_id

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        if interaction.guild is None:

            await interaction.response.send_message(
                "❌ تعذر تحديد السيرفر.",
                ephemeral=True
            )

            return

        settings = get_settings(
            self.guild_id
        )

        allowed_role_ids = normalize_ids(
            settings.get(
                "notification_roles",
                []
            )
        )

        selected_role = self.values[0]

        # =================================================
        # الرتبة ليست من الرتب المحددة
        # =================================================

        if selected_role.id not in allowed_role_ids:

            await interaction.response.send_message(
                "❌ هذه الرتبة ليست من رتب الإشعارات المتاحة.",
                ephemeral=True
            )

            return

        # =================================================
        # المستخدم لا يملك الرتبة
        # =================================================

        if selected_role not in interaction.user.roles:

            await interaction.response.send_message(
                "ℹ️ أنت لا تملك هذه الرتبة.",
                ephemeral=True
            )

            return

        # =================================================
        # إزالة الرتبة
        # =================================================

        try:

            await interaction.user.remove_roles(
                selected_role,
                reason="إزالة رتبة إشعارات من خريطة السيرفر"
            )

            await interaction.response.send_message(
                f"✅ تم إزالة رتبة {selected_role.mention} منك.",
                ephemeral=True
            )

        except discord.Forbidden:

            await interaction.response.send_message(
                "❌ البوت لا يملك صلاحية إزالة هذه الرتبة.",
                ephemeral=True
            )

        except discord.HTTPException:

            await interaction.response.send_message(
                "❌ حدث خطأ أثناء إزالة الرتبة.",
                ephemeral=True
            )


# =========================================================
# View رتب الإشعارات
# =========================================================

class NotificationRoleView(
    ui.View
):

    def __init__(
        self,
        guild_id
    ):

        super().__init__(
            timeout=None
        )

        self.guild_id = guild_id

    # =====================================================
    # اختيار رتبة
    # =====================================================

    @ui.button(
        label="اختيار رتبة",
        style=discord.ButtonStyle.primary,
        emoji="🔔",
        custom_id="server_map_add_role"
    )
    async def add_role_button(
        self,
        interaction: discord.Interaction,
        button: ui.Button
    ):

        if interaction.guild is None:

            await interaction.response.send_message(
                "❌ تعذر تحديد السيرفر.",
                ephemeral=True
            )

            return

        settings = get_settings(
            interaction.guild.id
        )

        allowed_role_ids = normalize_ids(
            settings.get(
                "notification_roles",
                []
            )
        )

        # =================================================
        # إذا لم تعد هناك رتب محددة
        # =================================================

        if not allowed_role_ids:

            await interaction.response.send_message(
                "ℹ️ لا توجد رتب إشعارات محددة حاليًا.",
                ephemeral=True
            )

            return

        view = ui.View(
            timeout=60
        )

        view.add_item(
            AddNotificationRoleSelect(
                interaction.guild.id
            )
        )

        await interaction.response.send_message(
            "🔔 اختر رتبة الإشعارات التي تريد الحصول عليها:",
            view=view,
            ephemeral=True
        )

    # =====================================================
    # إزالة رتبة
    # =====================================================

    @ui.button(
        label="إزالة رتبة",
        style=discord.ButtonStyle.secondary,
        emoji="🗑️",
        custom_id="server_map_remove_role"
    )
    async def remove_role_button(
        self,
        interaction: discord.Interaction,
        button: ui.Button
    ):

        if interaction.guild is None:

            await interaction.response.send_message(
                "❌ تعذر تحديد السيرفر.",
                ephemeral=True
            )

            return

        settings = get_settings(
            interaction.guild.id
        )

        allowed_role_ids = normalize_ids(
            settings.get(
                "notification_roles",
                []
            )
        )

        # =================================================
        # إذا لم تعد هناك رتب محددة
        # =================================================

        if not allowed_role_ids:

            await interaction.response.send_message(
                "ℹ️ لا توجد رتب إشعارات محددة حاليًا.",
                ephemeral=True
            )

            return

        view = ui.View(
            timeout=60
        )

        view.add_item(
            RemoveNotificationRoleSelect(
                interaction.guild.id
            )
        )

        await interaction.response.send_message(
            "🗑️ اختر رتبة الإشعارات التي تريد إزالتها:",
            view=view,
            ephemeral=True
        )


# =========================================================
# اختيار رتب الإشعارات من إعداد الخريطة
# =========================================================

class NotificationAdminRoleSelect(
    ui.RoleSelect
):

    def __init__(
        self,
        guild_id
    ):

        super().__init__(
            placeholder="🔔 اختر رتب الإشعارات",
            min_values=1,
            max_values=10
        )

        self.guild_id = guild_id

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        if not website_command_allowed(
            interaction.user,
            interaction.channel,
            SETUP_COMMAND_NAME
        ):

            await interaction.response.send_message(
                "❌ لم تعد تملك صلاحية إعداد خريطة السيرفر.",
                ephemeral=True
            )

            return

        role_ids = [
            role.id
            for role in self.values
        ]

        collection.update_one(
            {
                "guild_id": self.guild_id
            },
            {
                "$set": {
                    "notification_roles": role_ids
                }
            },
            upsert=True
        )

        await interaction.response.send_message(
            "✅ تم حفظ رتب الإشعارات.",
            ephemeral=True
        )


# =========================================================
# اختيار قنوات الخريطة
# =========================================================

class MapChannelSelect(
    ui.ChannelSelect
):

    def __init__(
        self,
        guild_id
    ):

        super().__init__(
            placeholder="🗺️ اختر القنوات التي ستظهر في الخريطة",
            min_values=1,
            max_values=25,
            channel_types=[
                discord.ChannelType.text,
                discord.ChannelType.news
            ]
        )

        self.guild_id = guild_id

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        if not website_command_allowed(
            interaction.user,
            interaction.channel,
            SETUP_COMMAND_NAME
        ):

            await interaction.response.send_message(
                "❌ لم تعد تملك صلاحية إعداد خريطة السيرفر.",
                ephemeral=True
            )

            return

        channel_ids = [
            channel.id
            for channel in self.values
        ]

        collection.update_one(
            {
                "guild_id": self.guild_id
            },
            {
                "$set": {
                    "map_channels": channel_ids
                }
            },
            upsert=True
        )

        await interaction.response.send_message(
            "✅ تم حفظ قنوات خريطة السيرفر.",
            ephemeral=True
        )


# =========================================================
# Modal القوانين
# =========================================================

class RulesModal(
    ui.Modal,
    title="📜 قوانين السيرفر"
):

    rules = ui.TextInput(
        label="قوانين السيرفر",
        placeholder="اكتب قوانين السيرفر هنا...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=4000
    )

    def __init__(
        self,
        guild_id
    ):

        super().__init__()

        self.guild_id = guild_id

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        if not website_command_allowed(
            interaction.user,
            interaction.channel,
            SETUP_COMMAND_NAME
        ):

            await interaction.response.send_message(
                "❌ لم تعد تملك صلاحية إعداد خريطة السيرفر.",
                ephemeral=True
            )

            return

        rules = str(
            self.rules.value or ""
        ).strip()

        collection.update_one(
            {
                "guild_id": self.guild_id
            },
            {
                "$set": {
                    "rules": rules
                }
            },
            upsert=True
        )

        await interaction.response.send_message(
            "✅ تم حفظ قوانين السيرفر.",
            ephemeral=True
        )


# =========================================================
# View إعداد خريطة السيرفر
# =========================================================

class ServerMapSetupView(
    ui.View
):

    def __init__(
        self,
        guild_id
    ):

        super().__init__(
            timeout=300
        )

        self.guild_id = guild_id

    # =====================================================
    # فحص الصلاحية
    # =====================================================

    async def check_permission(
        self,
        interaction
    ):

        if interaction.guild is None:
            return False

        return website_command_allowed(
            interaction.user,
            interaction.channel,
            SETUP_COMMAND_NAME
        )

    # =====================================================
    # رتب الإشعارات
    # =====================================================

    @ui.button(
        label="رتب الإشعارات",
        style=discord.ButtonStyle.primary,
        emoji="🔔",
        row=0
    )
    async def notification_roles_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not await self.check_permission(
            interaction
        ):

            await interaction.response.send_message(
                "❌ لم تعد تملك صلاحية إعداد خريطة السيرفر.",
                ephemeral=True
            )

            return

        view = ui.View(
            timeout=60
        )

        view.add_item(
            NotificationAdminRoleSelect(
                self.guild_id
            )
        )

        await interaction.response.send_message(
            "🔔 اختر رتب الإشعارات التي تريد إتاحتها للأعضاء:",
            view=view,
            ephemeral=True
        )

    # =====================================================
    # قنوات الخريطة
    # =====================================================

    @ui.button(
        label="قنوات الخريطة",
        style=discord.ButtonStyle.primary,
        emoji="🗺️",
        row=0
    )
    async def map_channels_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not await self.check_permission(
            interaction
        ):

            await interaction.response.send_message(
                "❌ لم تعد تملك صلاحية إعداد خريطة السيرفر.",
                ephemeral=True
            )

            return

        view = ui.View(
            timeout=60
        )

        view.add_item(
            MapChannelSelect(
                self.guild_id
            )
        )

        await interaction.response.send_message(
            "🗺️ اختر القنوات التي تريد ظهورها في خريطة السيرفر:",
            view=view,
            ephemeral=True
        )

    # =====================================================
    # القوانين
    # =====================================================

    @ui.button(
        label="القوانين",
        style=discord.ButtonStyle.primary,
        emoji="📜",
        row=1
    )
    async def rules_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not await self.check_permission(
            interaction
        ):

            await interaction.response.send_message(
                "❌ لم تعد تملك صلاحية إعداد خريطة السيرفر.",
                ephemeral=True
            )

            return

        await interaction.response.send_modal(
            RulesModal(
                self.guild_id
            )
        )

    # =====================================================
    # تحديث الخريطة
    # =====================================================

    @ui.button(
        label="تحديث الخريطة",
        style=discord.ButtonStyle.success,
        emoji="🔄",
        row=1
    )
    async def refresh_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not await self.check_permission(
            interaction
        ):

            await interaction.response.send_message(
                "❌ لم تعد تملك صلاحية إعداد خريطة السيرفر.",
                ephemeral=True
            )

            return

        await interaction.response.defer(
            ephemeral=True
        )

        await update_server_map(
            interaction.guild
        )

        await interaction.followup.send(
            "✅ تم تحديث خريطة السيرفر.",
            ephemeral=True
        )


# =========================================================
# Cog خريطة السيرفر
# =========================================================

class ServerMapCog(
    commands.Cog
):

    def __init__(
        self,
        bot
    ):

        self.bot = bot

    # =====================================================
    # خريطة-إنشاء
    # =====================================================

    @commands.command(
        name="خريطة-إنشاء"
    )
    async def create_server_map(
        self,
        ctx
    ):

        if ctx.guild is None:
            return

        # =================================================
        # صلاحية الموقع
        # =================================================

        allowed = website_command_allowed(
            ctx.author,
            ctx.channel,
            CREATE_COMMAND_NAME
        )

        if not allowed:
            return

        # =================================================
        # البحث عن الروم
        # =================================================

        map_channel = discord.utils.get(
            ctx.guild.text_channels,
            name="🗺️・خريطة-السيرفر"
        )

        # =================================================
        # إنشاء الروم
        # =================================================

        if map_channel is None:

            try:

                map_channel = await ctx.guild.create_text_channel(
                    "🗺️・خريطة-السيرفر",
                    reason="إنشاء خريطة السيرفر"
                )

            except discord.Forbidden:

                await ctx.send(
                    "❌ البوت لا يملك صلاحية إنشاء الرومات."
                )

                return

            except discord.HTTPException:

                await ctx.send(
                    "❌ حدث خطأ أثناء إنشاء روم خريطة السيرفر."
                )

                return

        # =================================================
        # حفظ روم الخريطة
        # =================================================

        collection.update_one(
            {
                "guild_id": ctx.guild.id
            },
            {
                "$set": {
                    "map_channel_id": map_channel.id
                }
            },
            upsert=True
        )

        # =================================================
        # تحديث الخريطة
        # =================================================

        await update_server_map(
            ctx.guild
        )

        await ctx.send(
            f"✅ تم إنشاء خريطة السيرفر بنجاح.\n"
            f"🗺️ {map_channel.mention}"
        )

    # =====================================================
    # خريطة-إعداد
    # =====================================================

    @commands.command(
        name="خريطة-إعداد"
    )
    async def setup_server_map(
        self,
        ctx
    ):

        if ctx.guild is None:
            return

        # =================================================
        # صلاحية الموقع
        # =================================================

        allowed = website_command_allowed(
            ctx.author,
            ctx.channel,
            SETUP_COMMAND_NAME
        )

        if not allowed:
            return

        # =================================================
        # التأكد من وجود الخريطة
        # =================================================

        settings = get_settings(
            ctx.guild.id
        )

        if not settings.get(
            "map_channel_id"
        ):

            await ctx.send(
                "⚠️ قم باستخدام خريطة-إنشاء أولًا."
            )

            return

        # =================================================
        # Embed الإعداد
        # =================================================

        embed = discord.Embed(
            title="🗺️ إعداد خريطة السيرفر",
            description=(
                "من هنا يمكنك إعداد محتوى خريطة السيرفر.\n\n"
                "🔔 **رتب الإشعارات**\n"
                "حدد الرتب التي يستطيع الأعضاء اختيارها.\n\n"
                "🗺️ **قنوات الخريطة**\n"
                "حدد القنوات التي ستظهر داخل الخريطة.\n\n"
                "📜 **القوانين**\n"
                "حدد قوانين السيرفر.\n\n"
                "🔄 **تحديث الخريطة**\n"
                "إعادة إرسال الخريطة بالإعدادات الجديدة."
            ),
            color=discord.Color.blurple()
        )

        embed.set_footer(
            text="إعداد خريطة السيرفر"
        )

        await ctx.send(
            embed=embed,
            view=ServerMapSetupView(
                ctx.guild.id
            )
        )

    # =====================================================
    # أخطاء خريطة-إنشاء
    # =====================================================

    @create_server_map.error
    async def create_server_map_error(
        self,
        ctx,
        error
    ):

        if ctx.guild is None:
            return

        setting = get_website_command_setting(
            ctx.guild.id,
            CREATE_COMMAND_NAME
        )

        if not setting:
            return

        if not setting.get(
            "enabled",
            False
        ):
            return

        channel_ids = setting.get(
            "channel_ids",
            []
        )

        allowed_channel_ids = {
            str(channel_id)
            for channel_id in channel_ids
        }

        if str(ctx.channel.id) not in allowed_channel_ids:
            return

        if isinstance(
            error,
            commands.CheckFailure
        ):
            return

        print(
            f"[ServerMap] Create Error: {repr(error)}"
        )

    # =====================================================
    # أخطاء خريطة-إعداد
    # =====================================================

    @setup_server_map.error
    async def setup_server_map_error(
        self,
        ctx,
        error
    ):

        if ctx.guild is None:
            return

        setting = get_website_command_setting(
            ctx.guild.id,
            SETUP_COMMAND_NAME
        )

        if not setting:
            return

        if not setting.get(
            "enabled",
            False
        ):
            return

        channel_ids = setting.get(
            "channel_ids",
            []
        )

        allowed_channel_ids = {
            str(channel_id)
            for channel_id in channel_ids
        }

        if str(ctx.channel.id) not in allowed_channel_ids:
            return

        print(
            f"[ServerMap] Setup Error: {repr(error)}"
        )


# =========================================================
# تشغيل الـ Cog
# =========================================================

async def setup(bot):

    await bot.add_cog(
        ServerMapCog(bot)
    )
