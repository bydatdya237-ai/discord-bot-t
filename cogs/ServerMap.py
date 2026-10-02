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
# أدوات عامة
# =========================================================

def normalize_ids(value):

    if value is None:
        return set()

    if not isinstance(value, (list, tuple, set)):
        value = [value]

    result = set()

    for item in value:

        try:
            result.add(int(str(item)))

        except (
            ValueError,
            TypeError
        ):
            continue

    return result


# =========================================================
# جلب إعداد الأمر من الموقع
# =========================================================

def get_website_command_setting(
    guild_id,
    command_name
):

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
# صلاحية الموقع
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

    if not setting:
        return False

    if not setting.get(
        "enabled",
        False
    ):
        return False

    # =====================================================
    # الرتب
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

    if not allowed_role_ids.intersection(
        user_role_ids
    ):
        return False

    # =====================================================
    # الرومات
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

    if str(channel.id) not in allowed_channel_ids:
        return False

    return True


# =========================================================
# إعدادات خريطة السيرفر
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

        "rules": "",

        "custom_embed_title": "",

        "custom_embed_description": "",

        "custom_embed_enabled": False
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
# Embed القنوات
# =========================================================

def create_channels_embed(
    guild,
    channel_ids
):

    channels = []

    for channel_id in normalize_ids(
        channel_ids
    ):

        channel = guild.get_channel(
            channel_id
        )

        if channel:
            channels.append(
                channel
            )

    if not channels:
        return None

    embed = discord.Embed(
        title="🗺️ خريطة السيرفر",
        description=(
            "استكشف أقسام السيرفر من خلال القنوات التالية:"
        ),
        color=discord.Color.blurple()
    )

    channels_text = "\n".join(
        f"• {channel.mention}"
        for channel in channels
    )

    embed.add_field(
        name="📍 القنوات المتاحة",
        value=channels_text,
        inline=False
    )

    embed.set_footer(
        text="خريطة السيرفر"
    )

    return embed


# =========================================================
# Embed الرتب
# =========================================================

def create_notification_roles_embed(
    guild,
    role_ids
):

    roles = []

    for role_id in normalize_ids(
        role_ids
    ):

        role = guild.get_role(
            role_id
        )

        if role:
            roles.append(
                role
            )

    if not roles:
        return None

    embed = discord.Embed(
        title="🔔 رتب الإشعارات",
        description=(
            "اختر رتبة الإشعارات التي تريد الحصول عليها."
        ),
        color=discord.Color.blurple()
    )

    roles_text = "\n".join(
        f"• {role.mention}"
        for role in roles
    )

    embed.add_field(
        name="الرتب المتاحة",
        value=roles_text,
        inline=False
    )

    embed.set_footer(
        text="يمكنك إضافة أو إزالة الرتب في أي وقت."
    )

    return embed


# =========================================================
# الحصول على رابط صورة السيرفر
# =========================================================

def get_server_icon_url(
    guild
):

    if not guild.icon:
        return None

    try:

        return str(
            guild.icon.with_size(1024).url
        )

    except Exception:

        try:

            return str(
                guild.icon.url
            )

        except Exception:

            return None


# =========================================================
# Embed الترحيب
# =========================================================

def create_welcome_embed(
    guild
):

    embed = discord.Embed(
        title=f"أهلًا بك في سيرفر {guild.name} 🌟",
        description=(
            f"أهلًا بك في **{guild.name}** 💜\n\n"
            "استكشف السيرفر من خلال الأقسام والأزرار الموجودة بالأسفل."
        ),
        color=discord.Color.blurple()
    )

    icon_url = get_server_icon_url(
        guild
    )

    if icon_url:

        embed.set_image(
            url=icon_url
        )

    embed.set_footer(
        text="نتمنى لك وقتًا ممتعًا معنا 💜"
    )

    return embed


# =========================================================
# اختيار رتبة مخصصة
# =========================================================

class NotificationRoleSelect(
    ui.Select
):

    def __init__(
        self,
        guild
    ):

        self.guild_id = guild.id

        settings = get_settings(
            guild.id
        )

        allowed_role_ids = normalize_ids(
            settings.get(
                "notification_roles",
                []
            )
        )

        options = []

        for role_id in allowed_role_ids:

            role = guild.get_role(
                role_id
            )

            if role is None:
                continue

            options.append(
                discord.SelectOption(
                    label=role.name[:100],
                    value=str(role.id),
                    description=(
                        f"اختيار رتبة {role.name[:80]}"
                    ),
                    emoji="🔔"
                )
            )

        if not options:

            options.append(
                discord.SelectOption(
                    label="لا توجد رتب متاحة",
                    value="none",
                    description="لم يتم تحديد رتب إشعارات",
                    emoji="ℹ️"
                )
            )

        super().__init__(
            placeholder="🔔 اختر رتبة الإشعارات",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="server_map_notification_role_select"
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        if interaction.guild is None:
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

        selected_value = self.values[0]

        if selected_value == "none":

            await interaction.response.send_message(
                "ℹ️ لا توجد رتب إشعارات محددة حاليًا.",
                ephemeral=True
            )

            return

        try:

            role_id = int(
                selected_value
            )

        except Exception:

            await interaction.response.send_message(
                "❌ تعذر تحديد الرتبة.",
                ephemeral=True
            )

            return

        if role_id not in allowed_role_ids:

            await interaction.response.send_message(
                "❌ هذه الرتبة ليست من الرتب المحددة للإشعارات.",
                ephemeral=True
            )

            return

        role = interaction.guild.get_role(
            role_id
        )

        if role is None:

            await interaction.response.send_message(
                "❌ هذه الرتبة لم تعد موجودة.",
                ephemeral=True
            )

            return

        me = interaction.guild.me

        if me is None:

            await interaction.response.send_message(
                "❌ تعذر تحديد البوت.",
                ephemeral=True
            )

            return

        if role >= me.top_role:

            await interaction.response.send_message(
                "❌ البوت لا يستطيع إعطاء هذه الرتبة لأن رتبة البوت ليست أعلى منها.",
                ephemeral=True
            )

            return

        if role in interaction.user.roles:

            await interaction.response.send_message(
                "ℹ️ أنت تملك هذه الرتبة بالفعل.",
                ephemeral=True
            )

            return

        try:

            await interaction.user.add_roles(
                role,
                reason="اختيار رتبة إشعارات من خريطة السيرفر"
            )

            await interaction.response.send_message(
                f"✅ تم إعطاؤك رتبة {role.mention}.",
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
# اختيار رتبة للإزالة
# =========================================================

class RemoveNotificationRoleSelect(
    ui.Select
):

    def __init__(
        self,
        guild
    ):

        self.guild_id = guild.id

        settings = get_settings(
            guild.id
        )

        allowed_role_ids = normalize_ids(
            settings.get(
                "notification_roles",
                []
            )
        )

        options = []

        for role_id in allowed_role_ids:

            role = guild.get_role(
                role_id
            )

            if role is None:
                continue

            options.append(
                discord.SelectOption(
                    label=role.name[:100],
                    value=str(role.id),
                    description=(
                        f"إزالة رتبة {role.name[:80]}"
                    ),
                    emoji="🗑️"
                )
            )

        if not options:

            options.append(
                discord.SelectOption(
                    label="لا توجد رتب متاحة",
                    value="none",
                    description="لم يتم تحديد رتب إشعارات",
                    emoji="ℹ️"
                )
            )

        super().__init__(
            placeholder="🗑️ اختر رتبة لإزالتها",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="server_map_remove_role_select"
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        if interaction.guild is None:
            return

        selected_value = self.values[0]

        if selected_value == "none":

            await interaction.response.send_message(
                "ℹ️ لا توجد رتب إشعارات محددة حاليًا.",
                ephemeral=True
            )

            return

        try:

            role_id = int(
                selected_value
            )

        except Exception:

            await interaction.response.send_message(
                "❌ تعذر تحديد الرتبة.",
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

        if role_id not in allowed_role_ids:

            await interaction.response.send_message(
                "❌ هذه الرتبة ليست من الرتب المحددة للإشعارات.",
                ephemeral=True
            )

            return

        role = interaction.guild.get_role(
            role_id
        )

        if role is None:

            await interaction.response.send_message(
                "❌ هذه الرتبة لم تعد موجودة.",
                ephemeral=True
            )

            return

        if role not in interaction.user.roles:

            await interaction.response.send_message(
                "ℹ️ أنت لا تملك هذه الرتبة.",
                ephemeral=True
            )

            return

        try:

            await interaction.user.remove_roles(
                role,
                reason="إزالة رتبة إشعارات من خريطة السيرفر"
            )

            await interaction.response.send_message(
                f"✅ تم إزالة رتبة {role.mention} منك.",
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
# View اختيار رتب الإشعارات
# =========================================================

class NotificationRoleMenuView(
    ui.View
):

    def __init__(
        self,
        guild
    ):

        super().__init__(
            timeout=60
        )

        self.add_item(
            NotificationRoleSelect(
                guild
            )
        )


# =========================================================
# View إزالة رتب الإشعارات
# =========================================================

class RemoveNotificationRoleMenuView(
    ui.View
):

    def __init__(
        self,
        guild
    ):

        super().__init__(
            timeout=60
        )

        self.add_item(
            RemoveNotificationRoleSelect(
                guild
            )
        )


# =========================================================
# زر القوانين
# =========================================================

class RulesButton(
    ui.Button
):

    def __init__(self):

        super().__init__(
            label="القوانين",
            style=discord.ButtonStyle.primary,
            emoji="📜",
            custom_id="server_map_rules"
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        if interaction.guild is None:
            return

        settings = get_settings(
            interaction.guild.id
        )

        rules = str(
            settings.get(
                "rules",
                ""
            ) or ""
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
# زر خريطة السيرفر
# =========================================================

class MapButton(
    ui.Button
):

    def __init__(self):

        super().__init__(
            label="خريطة السيرفر",
            style=discord.ButtonStyle.primary,
            emoji="🗺️",
            custom_id="server_map_channels"
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        if interaction.guild is None:
            return

        settings = get_settings(
            interaction.guild.id
        )

        embed = create_channels_embed(
            interaction.guild,
            settings.get(
                "map_channels",
                []
            )
        )

        if embed is None:

            await interaction.response.send_message(
                "ℹ️ لم يتم تحديد قنوات في خريطة السيرفر حاليًا.",
                ephemeral=True
            )

            return

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )


# =========================================================
# زر رتب الإشعارات
# =========================================================

class NotificationButton(
    ui.Button
):

    def __init__(self):

        super().__init__(
            label="رتب الإشعارات",
            style=discord.ButtonStyle.primary,
            emoji="🔔",
            custom_id="server_map_notifications"
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        if interaction.guild is None:
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

        if not allowed_role_ids:

            await interaction.response.send_message(
                "ℹ️ لم يتم تحديد رتب إشعارات حاليًا.",
                ephemeral=True
            )

            return

        embed = create_notification_roles_embed(
            interaction.guild,
            allowed_role_ids
        )

        if embed is None:

            await interaction.response.send_message(
                "ℹ️ لم تعد رتب الإشعارات المحددة موجودة.",
                ephemeral=True
            )

            return

        view = NotificationRoleMenuView(
            interaction.guild
        )

        await interaction.response.send_message(
            embed=embed,
            view=view,
            ephemeral=True
        )


# =========================================================
# زر الإيمبد المخصص
# =========================================================

class CustomEmbedButton(
    ui.Button
):

    def __init__(
        self,
        title=""
    ):

        title = str(
            title or ""
        ).strip()

        if not title:
            title = "معلومات السيرفر"

        button_label = title[:80]

        super().__init__(
            label=button_label,
            style=discord.ButtonStyle.secondary,
            emoji="ℹ️",
            custom_id="server_map_custom_embed"
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        if interaction.guild is None:
            return

        settings = get_settings(
            interaction.guild.id
        )

        enabled = settings.get(
            "custom_embed_enabled",
            False
        )

        title = str(
            settings.get(
                "custom_embed_title",
                ""
            ) or ""
        ).strip()

        description = str(
            settings.get(
                "custom_embed_description",
                ""
            ) or ""
        ).strip()

        if not enabled or not description:

            await interaction.response.send_message(
                "ℹ️ لم يتم إعداد هذا القسم حاليًا.",
                ephemeral=True
            )

            return

        if not title:
            title = "معلومات السيرفر"

        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.blurple()
        )

        embed.set_footer(
            text=interaction.guild.name
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )


# =========================================================
# View خريطة السيرفر الرئيسية
# =========================================================

class ServerMapMainView(
    ui.View
):

    def __init__(
        self,
        guild
    ):

        super().__init__(
            timeout=None
        )

        settings = get_settings(
            guild.id
        )

        # =================================================
        # زر الرتب فقط إذا فيه رتب
        # =================================================

        role_ids = normalize_ids(
            settings.get(
                "notification_roles",
                []
            )
        )

        valid_roles = [
            guild.get_role(role_id)
            for role_id in role_ids
        ]

        valid_roles = [
            role
            for role in valid_roles
            if role is not None
        ]

        if valid_roles:

            self.add_item(
                NotificationButton()
            )

        # =================================================
        # زر الخريطة فقط إذا فيه قنوات
        # =================================================

        channel_ids = normalize_ids(
            settings.get(
                "map_channels",
                []
            )
        )

        valid_channels = [
            guild.get_channel(channel_id)
            for channel_id in channel_ids
        ]

        valid_channels = [
            channel
            for channel in valid_channels
            if channel is not None
        ]

        if valid_channels:

            self.add_item(
                MapButton()
            )

        # =================================================
        # زر القوانين فقط إذا فيه قوانين
        # =================================================

        rules = str(
            settings.get(
                "rules",
                ""
            ) or ""
        ).strip()

        if rules:

            self.add_item(
                RulesButton()
            )

        # =================================================
        # الإيمبد المخصص
        # =================================================

        custom_enabled = settings.get(
            "custom_embed_enabled",
            False
        )

        custom_title = str(
            settings.get(
                "custom_embed_title",
                ""
            ) or ""
        ).strip()

        custom_description = str(
            settings.get(
                "custom_embed_description",
                ""
            ) or ""
        ).strip()

        if custom_enabled and custom_description:

            self.add_item(
                CustomEmbedButton(
                    custom_title
                )
            )


# =========================================================
# Persistent View لخريطة السيرفر
#
# هذه الـ View لا تعتمد على إعدادات سيرفر محدد.
# أزرارها تستخدم interaction.guild لمعرفة السيرفر.
# =========================================================

class PersistentServerMapView(
    ui.View
):

    def __init__(self):

        super().__init__(
            timeout=None
        )

        # =================================================
        # جميع الأزرار الممكنة
        #
        # حتى لو كانت الرسالة القديمة تحتوي على زر واحد
        # فقط، Discord سيجد الـ custom_id الصحيح.
        # =================================================

        self.add_item(
            NotificationButton()
        )

        self.add_item(
            MapButton()
        )

        self.add_item(
            RulesButton()
        )

        self.add_item(
            CustomEmbedButton()
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

        me = guild.me

        if me:

            async for message in channel.history(
                limit=100
            ):

                if message.author.id == me.id:

                    try:
                        await message.delete()

                    except Exception:
                        pass

    except Exception:
        pass

    # =====================================================
    # Embed الترحيب
    # =====================================================

    welcome_embed = create_welcome_embed(
        guild
    )

    # =====================================================
    # View
    # =====================================================

    view = ServerMapMainView(
        guild
    )

    # =====================================================
    # إرسال الإيمبد
    # =====================================================

    try:

        await channel.send(
            embed=welcome_embed,
            view=view
        )

    except discord.HTTPException as error:

        print(
            f"[ServerMap] Failed to send server map: {repr(error)}"
        )

        # =================================================
        # محاولة إرسال الإيمبد بدون الصورة
        # =================================================

        try:

            welcome_embed.set_image(
                url=None
            )

            await channel.send(
                embed=welcome_embed,
                view=view
            )

        except Exception as fallback_error:

            print(
                f"[ServerMap] Fallback send failed: {repr(fallback_error)}"
            )


# =========================================================
# إعداد رتب الإشعارات من الأدمن
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
            "✅ تم حفظ رتب الإشعارات المحددة.",
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
# Modal إنشاء الإيمبد المخصص
# =========================================================

class CustomEmbedModal(
    ui.Modal,
    title="📝 الإيمبد المخصص"
):

    title_input = ui.TextInput(
        label="عنوان الإيمبد",
        placeholder="مثال: معلومات مهمة",
        required=False,
        max_length=256
    )

    description_input = ui.TextInput(
        label="محتوى الإيمبد",
        placeholder="اكتب أي شيء تريده هنا...",
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

        title = str(
            self.title_input.value or ""
        ).strip()

        description = str(
            self.description_input.value or ""
        ).strip()

        if not title:
            title = "معلومات السيرفر"

        collection.update_one(
            {
                "guild_id": self.guild_id
            },
            {
                "$set": {
                    "custom_embed_title": title,
                    "custom_embed_description": description,
                    "custom_embed_enabled": True
                }
            },
            upsert=True
        )

        await interaction.response.send_message(
            f"✅ تم حفظ الإيمبد باسم **{title}**.\n"
            "🔄 اضغط تحديث الخريطة حتى تظهر التغييرات.",
            ephemeral=True
        )


# =========================================================
# Modal تعديل الإيمبد المخصص
# =========================================================

class EditCustomEmbedModal(
    ui.Modal,
    title="✏️ تعديل الإيمبد المخصص"
):

    title_input = ui.TextInput(
        label="عنوان الإيمبد",
        placeholder="اكتب عنوان الإيمبد...",
        required=False,
        max_length=256
    )

    description_input = ui.TextInput(
        label="محتوى الإيمبد",
        placeholder="اكتب محتوى الإيمبد...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=4000
    )

    def __init__(
        self,
        guild_id,
        current_title,
        current_description
    ):

        super().__init__()

        self.guild_id = guild_id

        current_title = str(
            current_title or ""
        ).strip()

        current_description = str(
            current_description or ""
        ).strip()

        if not current_title:
            current_title = "معلومات السيرفر"

        self.title_input.default = current_title
        self.description_input.default = current_description

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

        title = str(
            self.title_input.value or ""
        ).strip()

        description = str(
            self.description_input.value or ""
        ).strip()

        if not title:
            title = "معلومات السيرفر"

        if not description:

            await interaction.response.send_message(
                "❌ لا يمكن حفظ إيمبد بدون محتوى.",
                ephemeral=True
            )

            return

        collection.update_one(
            {
                "guild_id": self.guild_id
            },
            {
                "$set": {
                    "custom_embed_title": title,
                    "custom_embed_description": description,
                    "custom_embed_enabled": True
                }
            },
            upsert=True
        )

        await interaction.response.send_message(
            f"✅ تم تعديل الإيمبد **{title}** بنجاح.\n"
            "🔄 اضغط تحديث الخريطة حتى تظهر التغييرات.",
            ephemeral=True
        )


# =========================================================
# View تأكيد حذف الإيمبد
# =========================================================

class DeleteCustomEmbedConfirmView(
    ui.View
):

    def __init__(
        self,
        guild_id
    ):

        super().__init__(
            timeout=60
        )

        self.guild_id = guild_id

    # =====================================================
    # تأكيد الحذف
    # =====================================================

    @ui.button(
        label="نعم، احذف الإيمبد",
        style=discord.ButtonStyle.danger,
        emoji="🗑️"
    )
    async def confirm_delete(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if interaction.guild is None:
            return

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

        collection.update_one(
            {
                "guild_id": self.guild_id
            },
            {
                "$set": {
                    "custom_embed_title": "",
                    "custom_embed_description": "",
                    "custom_embed_enabled": False
                }
            },
            upsert=True
        )

        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(
            content=(
                "✅ تم حذف الإيمبد المخصص بنجاح.\n"
                "🔄 اضغط **تحديث الخريطة** حتى يختفي زر الإيمبد من الخريطة."
            ),
            view=self
        )

    # =====================================================
    # إلغاء الحذف
    # =====================================================

    @ui.button(
        label="إلغاء",
        style=discord.ButtonStyle.secondary,
        emoji="↩️"
    )
    async def cancel_delete(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(
            content="ℹ️ تم إلغاء حذف الإيمبد.",
            view=self
        )


# =========================================================
# View إعداد الخريطة
# =========================================================

class ServerMapSetupView(
    ui.View
):

    def __init__(
        self,
        guild_id=None
    ):

        # =================================================
        # أصبحت Persistent حتى تبقى لوحة الإعداد تعمل
        # بعد Restart / Redeploy
        # =================================================

        super().__init__(
            timeout=None
        )

        self.guild_id = guild_id

    # =====================================================
    # الحصول على Guild ID
    # =====================================================

    def get_guild_id(
        self,
        interaction
    ):

        if interaction.guild is None:
            return None

        if self.guild_id:
            return self.guild_id

        return interaction.guild.id

    # =====================================================
    # التحقق من الصلاحية
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
        row=0,
        custom_id="server_map_setup_roles"
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

        guild_id = self.get_guild_id(
            interaction
        )

        if guild_id is None:
            return

        view = ui.View(
            timeout=60
        )

        view.add_item(
            NotificationAdminRoleSelect(
                guild_id
            )
        )

        await interaction.response.send_message(
            "🔔 اختر الرتب التي تريد إتاحتها كرتب إشعارات.\n"
            "ملاحظة: هذه الرتب فقط هي التي ستظهر للأعضاء.",
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
        row=0,
        custom_id="server_map_setup_channels"
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

        guild_id = self.get_guild_id(
            interaction
        )

        if guild_id is None:
            return

        view = ui.View(
            timeout=60
        )

        view.add_item(
            MapChannelSelect(
                guild_id
            )
        )

        await interaction.response.send_message(
            "🗺️ اختر القنوات التي تريد ظهورها في الخريطة.",
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
        row=1,
        custom_id="server_map_setup_rules"
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

        guild_id = self.get_guild_id(
            interaction
        )

        if guild_id is None:
            return

        await interaction.response.send_modal(
            RulesModal(
                guild_id
            )
        )

    # =====================================================
    # إنشاء إيمبد مخصص
    # =====================================================

    @ui.button(
        label="إيمبد مخصص",
        style=discord.ButtonStyle.secondary,
        emoji="📝",
        row=1,
        custom_id="server_map_setup_custom_embed"
    )
    async def custom_embed_button(
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

        guild_id = self.get_guild_id(
            interaction
        )

        if guild_id is None:
            return

        await interaction.response.send_modal(
            CustomEmbedModal(
                guild_id
            )
        )

    # =====================================================
    # تعديل الإيمبد
    # =====================================================

    @ui.button(
        label="تعديل الإيمبد",
        style=discord.ButtonStyle.secondary,
        emoji="✏️",
        row=2,
        custom_id="server_map_setup_edit_embed"
    )
    async def edit_custom_embed_button(
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

        guild_id = self.get_guild_id(
            interaction
        )

        if guild_id is None:
            return

        settings = get_settings(
            guild_id
        )

        enabled = settings.get(
            "custom_embed_enabled",
            False
        )

        title = str(
            settings.get(
                "custom_embed_title",
                ""
            ) or ""
        ).strip()

        description = str(
            settings.get(
                "custom_embed_description",
                ""
            ) or ""
        ).strip()

        if not enabled or not description:

            await interaction.response.send_message(
                "ℹ️ لا يوجد إيمبد مخصص لتعديله حاليًا.",
                ephemeral=True
            )

            return

        await interaction.response.send_modal(
            EditCustomEmbedModal(
                guild_id,
                title,
                description
            )
        )

    # =====================================================
    # حذف الإيمبد المخصص
    # =====================================================

    @ui.button(
        label="حذف الإيمبد المخصص",
        style=discord.ButtonStyle.danger,
        emoji="🗑️",
        row=2,
        custom_id="server_map_setup_delete_embed"
    )
    async def delete_custom_embed_button(
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

        guild_id = self.get_guild_id(
            interaction
        )

        if guild_id is None:
            return

        settings = get_settings(
            guild_id
        )

        enabled = settings.get(
            "custom_embed_enabled",
            False
        )

        description = str(
            settings.get(
                "custom_embed_description",
                ""
            ) or ""
        ).strip()

        if not enabled or not description:

            await interaction.response.send_message(
                "ℹ️ لا يوجد إيمبد مخصص لحذفه حاليًا.",
                ephemeral=True
            )

            return

        await interaction.response.send_message(
            "⚠️ هل أنت متأكد أنك تريد حذف الإيمبد المخصص؟\n\n"
            "سيتم حذف العنوان والمحتوى المحفوظين.",
            view=DeleteCustomEmbedConfirmView(
                guild_id
            ),
            ephemeral=True
        )

    # =====================================================
    # تحديث الخريطة
    # =====================================================

    @ui.button(
        label="تحديث الخريطة",
        style=discord.ButtonStyle.success,
        emoji="🔄",
        row=3,
        custom_id="server_map_setup_refresh"
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

        if interaction.guild is None:
            return

        await interaction.response.defer(
            ephemeral=True
        )

        await update_server_map(
            interaction.guild
        )

        await interaction.followup.send(
            "✅ تم تحديث خريطة السيرفر بالإعدادات الجديدة.",
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
    # تسجيل Persistent Views
    #
    # يتم تنفيذها عند تحميل الـ Cog.
    #
    # هذا هو الجزء الذي يجعل الأزرار القديمة تعمل
    # بعد Restart / Redeploy.
    # =====================================================

    async def cog_load(
        self
    ):

        try:

            # =================================================
            # View خريطة السيرفر
            # =================================================

            self.bot.add_view(
                PersistentServerMapView()
            )

            # =================================================
            # View إعداد الخريطة
            # =================================================

            self.bot.add_view(
                ServerMapSetupView()
            )

            print(
                "[ServerMap] Persistent Views registered successfully."
            )

        except Exception as error:

            print(
                f"[ServerMap] Failed to register Persistent Views: {repr(error)}"
            )

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

        if not website_command_allowed(
            ctx.author,
            ctx.channel,
            CREATE_COMMAND_NAME
        ):

            return

        map_channel = discord.utils.get(
            ctx.guild.text_channels,
            name="🗺️・خريطة-السيرفر"
        )

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

        if not website_command_allowed(
            ctx.author,
            ctx.channel,
            SETUP_COMMAND_NAME
        ):

            return

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

        await update_server_map(
            ctx.guild
        )

        embed = discord.Embed(
            title="🗺️ إعداد خريطة السيرفر",
            description=(
                "من هنا تقدر تتحكم في محتوى خريطة السيرفر.\n\n"

                "🔔 **رتب الإشعارات**\n"
                "حدد الرتب التي يستطيع الأعضاء اختيارها.\n\n"

                "🗺️ **قنوات الخريطة**\n"
                "حدد القنوات التي ستظهر للأعضاء.\n\n"

                "📜 **القوانين**\n"
                "اكتب قوانين السيرفر.\n\n"

                "📝 **إيمبد مخصص**\n"
                "أنشئ إيمبد مخصص وسيظهر في خريطة السيرفر.\n\n"

                "✏️ **تعديل الإيمبد**\n"
                "عدل عنوان أو محتوى الإيمبد المخصص الحالي.\n\n"

                "🗑️ **حذف الإيمبد المخصص**\n"
                "احذف الإيمبد المخصص الحالي من خريطة السيرفر.\n\n"

                "🔄 **تحديث الخريطة**\n"
                "يعيد بناء رسالة الخريطة بالإعدادات الحالية."
            ),
            color=discord.Color.blurple()
        )

        if ctx.guild.icon:

            embed.set_thumbnail(
                url=ctx.guild.icon.url
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

        print(
            f"[ServerMap] Setup Error: {repr(error)}"
        )


# =========================================================
# تشغيل الـ Cog
# =========================================================

async def setup(
    bot
):

    await bot.add_cog(
        ServerMapCog(bot)
    )
