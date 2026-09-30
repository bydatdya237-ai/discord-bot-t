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

db = mongo_client["discord_bot_db"]

collection = db["server_map_settings"]
website_collection = db["website_command_settings"]


# =========================================================
# الألوان
# =========================================================

EMBED_COLOR = discord.Color.from_rgb(182, 108, 255)


# =========================================================
# أسماء أوامر الموقع
# =========================================================

MAP_COMMAND_NAMES = {
    "خريطة-إنشاء",
    "خريطة-إعداد",
}


# =========================================================
# إعدادات الخريطة
# =========================================================

def get_settings(guild_id: int):

    data = collection.find_one({"guild_id": guild_id})

    if not data:

        data = {
            "guild_id": guild_id,
            "map_channel_id": None,
            "notification_roles": [],
            "map_channels": [],
            "rules": "لم يتم إضافة قوانين السيرفر حتى الآن."
        }

        collection.insert_one(data)

    return data


# =========================================================
# البحث عن إعداد الأمر في الموقع
# =========================================================

def get_website_command_setting(guild_id: int, command_name: str):

    names_to_check = {
        command_name,
        command_name.lower(),
    }

    # دعم بعض صيغ التخزين القديمة/المختلفة
    if command_name == "خريطة-إنشاء":
        names_to_check.update({
            "خريطة-إنشاء",
            "خريطة انشاء",
            "خريطة_إنشاء",
            "خريطة"
        })

    if command_name == "خريطة-إعداد":
        names_to_check.update({
            "خريطة-إعداد",
            "خريطة اعداد",
            "خريطة_إعداد"
        })

    queries = []

    for name in names_to_check:

        queries.extend([
            {
                "guild_id": guild_id,
                "command_name": name
            },
            {
                "guild_id": guild_id,
                "name": name
            },
            {
                "guild_id": guild_id,
                "command": name
            }
        ])

    for query in queries:

        data = website_collection.find_one(query)

        if data:
            return data

    return None


# =========================================================
# تحويل IDs إلى مجموعة
# =========================================================

def normalize_ids(value):

    if not value:
        return set()

    if isinstance(value, (int, str)):
        value = [value]

    result = set()

    for item in value:

        try:
            result.add(int(item))
        except:
            pass

    return result


# =========================================================
# التحقق من صلاحية الموقع
# =========================================================

def website_permission_allowed(
    member: discord.Member,
    command_name: str
):

    setting = get_website_command_setting(
        member.guild.id,
        command_name
    )

    # إذا الأمر غير موجود في الموقع = ممنوع
    if not setting:
        return False

    # -----------------------------------------------------
    # enabled
    # -----------------------------------------------------

    if setting.get("enabled") is False:
        return False

    # -----------------------------------------------------
    # الرتب
    # -----------------------------------------------------

    role_ids = normalize_ids(
        setting.get("role_ids")
        or setting.get("roles")
        or setting.get("allowed_role_ids")
        or setting.get("allowed_roles")
    )

    # -----------------------------------------------------
    # الرومات
    # -----------------------------------------------------

    channel_ids = normalize_ids(
        setting.get("channel_ids")
        or setting.get("channels")
        or setting.get("allowed_channel_ids")
        or setting.get("allowed_channels")
    )

    # إذا الموقع ما حدد أي رتبة = ممنوع
    if not role_ids:
        return False

    # إذا الموقع ما حدد أي روم = ممنوع
    if not channel_ids:
        return False

    # -----------------------------------------------------
    # فحص الرتبة
    # -----------------------------------------------------

    member_role_ids = {
        role.id
        for role in member.roles
    }

    if not (member_role_ids & role_ids):

        # Administrator لا يتجاوز إعداد الموقع
        return False

    # -----------------------------------------------------
    # فحص الروم
    # -----------------------------------------------------

    if member.guild.get_channel(member.guild.system_channel.id) \
            if member.guild.system_channel else None:
        pass

    return True


# =========================================================
# التحقق من صلاحية الموقع مع Channel
# =========================================================

def website_command_allowed(
    member: discord.Member,
    channel: discord.abc.GuildChannel,
    command_name: str
):

    setting = get_website_command_setting(
        member.guild.id,
        command_name
    )

    if not setting:
        return False

    if setting.get("enabled") is False:
        return False

    role_ids = normalize_ids(
        setting.get("role_ids")
        or setting.get("roles")
        or setting.get("allowed_role_ids")
        or setting.get("allowed_roles")
    )

    channel_ids = normalize_ids(
        setting.get("channel_ids")
        or setting.get("channels")
        or setting.get("allowed_channel_ids")
        or setting.get("allowed_channels")
    )

    # لازم الموقع يكون محدد رتبة
    if not role_ids:
        return False

    # لازم الموقع يكون محدد روم
    if not channel_ids:
        return False

    member_role_ids = {
        role.id
        for role in member.roles
    }

    if not (member_role_ids & role_ids):
        return False

    if channel.id not in channel_ids:
        return False

    return True


# =========================================================
# إرسال رسالة صلاحية
# =========================================================

async def permission_denied(interaction):

    await interaction.response.send_message(
        "❌ لا تملك الصلاحية لاستخدام هذا النظام.",
        ephemeral=True
    )


# =========================================================
# تحديث خريطة السيرفر
# =========================================================

async def update_server_map(guild: discord.Guild):

    data = get_settings(guild.id)

    map_channel_id = data.get("map_channel_id")

    if not map_channel_id:
        return

    channel = guild.get_channel(map_channel_id)

    if not isinstance(channel, discord.TextChannel):
        return

    # =====================================================
    # حذف رسائل البوت القديمة
    # =====================================================

    try:

        async for message in channel.history(limit=100):

            if message.author.id == guild.me.id:

                try:
                    await message.delete()
                except:
                    pass

    except:
        pass

    # =====================================================
    # إيمبد رتب الإشعارات
    # =====================================================

    roles_embed = discord.Embed(
        title="🔔 رتب الإشعارات",
        description=(
            "اختر رتب الإشعارات التي تريد استلامها.\n\n"
            "عند اختيار رتبة، سيقوم البوت بإضافتها لك تلقائيًا.\n"
            "ولإزالة رتبة استخدم زر **➖ إزالة رتبة**."
        ),
        color=EMBED_COLOR
    )

    notification_roles = data.get(
        "notification_roles",
        []
    )

    role_lines = []

    for role_id in notification_roles:

        role = guild.get_role(role_id)

        if role:
            role_lines.append(
                f"🔔 {role.mention}"
            )

    if role_lines:

        roles_embed.add_field(
            name="الرتب المتاحة",
            value="\n".join(role_lines),
            inline=False
        )

    else:

        roles_embed.add_field(
            name="الرتب",
            value="لم يتم تحديد رتب إشعارات حتى الآن.",
            inline=False
        )

    roles_embed.set_footer(
        text=f"{guild.name} • نظام خريطة السيرفر"
    )

    await channel.send(
        embed=roles_embed,
        view=NotificationRoleView(guild.id)
    )

    # =====================================================
    # خريطة السيرفر
    # =====================================================

    map_embed = discord.Embed(
        title="🗺️ خريطة السيرفر",
        description=(
            f"أهلاً بك في **{guild.name}** 👋\n\n"
            "هنا تقدر تتعرف على أهم أقسام ورومات السيرفر."
        ),
        color=EMBED_COLOR
    )

    map_channels = data.get(
        "map_channels",
        []
    )

    if map_channels:

        for channel_id in map_channels:

            channel_obj = guild.get_channel(
                channel_id
            )

            if not channel_obj:
                continue

            map_embed.add_field(
                name=f"📍 {channel_obj.name}",
                value=channel_obj.mention,
                inline=True
            )

    else:

        map_embed.add_field(
            name="الرومات",
            value="لم يتم تحديد رومات الخريطة حتى الآن.",
            inline=False
        )

    map_embed.set_footer(
        text="🗺️ خريطة السيرفر"
    )

    await channel.send(
        embed=map_embed
    )

    # =====================================================
    # القوانين
    # =====================================================

    rules = data.get(
        "rules",
        "لم يتم إضافة قوانين السيرفر حتى الآن."
    )

    rules_embed = discord.Embed(
        title="📜 قوانين السيرفر",
        description=rules,
        color=EMBED_COLOR
    )

    rules_embed.set_footer(
        text=f"{guild.name} • يرجى الالتزام بالقوانين"
    )

    await channel.send(
        embed=rules_embed
    )


# =========================================================
# اختيار رتبة الإضافة
# =========================================================

class AddNotificationRoleSelect(ui.RoleSelect):

    def __init__(self, guild_id):

        self.guild_id = guild_id

        super().__init__(
            placeholder="🔔 اختر رتبة لإضافتها لك",
            min_values=1,
            max_values=1
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        member = interaction.user

        data = get_settings(
            self.guild_id
        )

        allowed_role_ids = {
            int(role_id)
            for role_id in data.get(
                "notification_roles",
                []
            )
        }

        selected_role = self.values[0]

        # -------------------------------------------------
        # حماية: لا يمكن اختيار رتبة غير موجودة بالإعدادات
        # -------------------------------------------------

        if selected_role.id not in allowed_role_ids:

            await interaction.response.send_message(
                "❌ هذه الرتبة غير متاحة للاشتراك.",
                ephemeral=True
            )

            return

        # -------------------------------------------------
        # حماية: البوت لازم يقدر يدير الرتبة
        # -------------------------------------------------

        bot_member = interaction.guild.me

        if not bot_member:

            await interaction.response.send_message(
                "❌ لم أستطع التحقق من صلاحيات البوت.",
                ephemeral=True
            )

            return

        if selected_role >= bot_member.top_role:

            await interaction.response.send_message(
                "❌ لا أستطيع إعطاء هذه الرتبة لأن رتبة البوت ليست أعلى منها.",
                ephemeral=True
            )

            return

        # -------------------------------------------------
        # إذا عنده الرتبة
        # -------------------------------------------------

        if selected_role in member.roles:

            await interaction.response.send_message(
                f"ℹ️ أنت تملك رتبة {selected_role.mention} بالفعل.",
                ephemeral=True
            )

            return

        try:

            await member.add_roles(
                selected_role,
                reason="Server Map notification role"
            )

        except discord.Forbidden:

            await interaction.response.send_message(
                "❌ البوت لا يملك صلاحية إعطاء هذه الرتبة.",
                ephemeral=True
            )

            return

        except discord.HTTPException:

            await interaction.response.send_message(
                "❌ حدث خطأ أثناء إضافة الرتبة.",
                ephemeral=True
            )

            return

        await interaction.response.send_message(
            f"✅ تم إعطاؤك رتبة {selected_role.mention}.",
            ephemeral=True
        )


# =========================================================
# اختيار رتبة الإزالة
# =========================================================

class RemoveNotificationRoleSelect(ui.RoleSelect):

    def __init__(self, guild_id):

        self.guild_id = guild_id

        super().__init__(
            placeholder="➖ اختر رتبة لإزالتها منك",
            min_values=1,
            max_values=1
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        member = interaction.user

        data = get_settings(
            self.guild_id
        )

        allowed_role_ids = {
            int(role_id)
            for role_id in data.get(
                "notification_roles",
                []
            )
        }

        selected_role = self.values[0]

        # -------------------------------------------------
        # حماية
        # -------------------------------------------------

        if selected_role.id not in allowed_role_ids:

            await interaction.response.send_message(
                "❌ هذه الرتبة ليست من رتب الإشعارات.",
                ephemeral=True
            )

            return

        # -------------------------------------------------
        # العضو لا يملك الرتبة
        # -------------------------------------------------

        if selected_role not in member.roles:

            await interaction.response.send_message(
                f"ℹ️ أنت لا تملك رتبة {selected_role.mention}.",
                ephemeral=True
            )

            return

        # -------------------------------------------------
        # حماية ترتيب الرتبة
        # -------------------------------------------------

        bot_member = interaction.guild.me

        if bot_member and selected_role >= bot_member.top_role:

            await interaction.response.send_message(
                "❌ لا أستطيع إزالة هذه الرتبة لأن رتبة البوت ليست أعلى منها.",
                ephemeral=True
            )

            return

        try:

            await member.remove_roles(
                selected_role,
                reason="Server Map notification role removal"
            )

        except discord.Forbidden:

            await interaction.response.send_message(
                "❌ البوت لا يملك صلاحية إزالة هذه الرتبة.",
                ephemeral=True
            )

            return

        except discord.HTTPException:

            await interaction.response.send_message(
                "❌ حدث خطأ أثناء إزالة الرتبة.",
                ephemeral=True
            )

            return

        await interaction.response.send_message(
            f"✅ تمت إزالة رتبة {selected_role.mention} منك.",
            ephemeral=True
        )


# =========================================================
# View إضافة الرتبة
# =========================================================

class AddNotificationRoleView(ui.View):

    def __init__(self, guild_id):

        super().__init__(
            timeout=180
        )

        self.add_item(
            AddNotificationRoleSelect(
                guild_id
            )
        )


# =========================================================
# View إزالة الرتبة
# =========================================================

class RemoveNotificationRoleView(ui.View):

    def __init__(self, guild_id):

        super().__init__(
            timeout=180
        )

        self.add_item(
            RemoveNotificationRoleSelect(
                guild_id
            )
        )


# =========================================================
# View الرئيسية لرتب الإشعارات
# =========================================================

class NotificationRoleView(ui.View):

    def __init__(self, guild_id):

        super().__init__(
            timeout=None
        )

        self.guild_id = guild_id

    # -----------------------------------------------------
    # إضافة رتبة
    # -----------------------------------------------------

    @ui.button(
        label="اختيار رتبة",
        emoji="🔔",
        style=discord.ButtonStyle.success,
        custom_id="server_map_add_role"
    )
    async def add_role(
        self,
        interaction: discord.Interaction,
        button: ui.Button
    ):

        view = AddNotificationRoleView(
            self.guild_id
        )

        await interaction.response.send_message(
            "🔔 اختر رتبة الإشعارات التي تريد إضافتها لك:",
            view=view,
            ephemeral=True
        )

    # -----------------------------------------------------
    # إزالة رتبة
    # -----------------------------------------------------

    @ui.button(
        label="إزالة رتبة",
        emoji="➖",
        style=discord.ButtonStyle.danger,
        custom_id="server_map_remove_role"
    )
    async def remove_role(
        self,
        interaction: discord.Interaction,
        button: ui.Button
    ):

        view = RemoveNotificationRoleView(
            self.guild_id
        )

        await interaction.response.send_message(
            "➖ اختر رتبة الإشعارات التي تريد إزالتها منك:",
            view=view,
            ephemeral=True
        )


# =========================================================
# اختيار رومات الخريطة للإدارة
# =========================================================

class MapChannelSelect(ui.ChannelSelect):

    def __init__(self, guild_id):

        self.guild_id = guild_id

        super().__init__(
            placeholder="🗺️ اختر رومات الخريطة",
            channel_types=[
                discord.ChannelType.text,
                discord.ChannelType.news
            ],
            min_values=1,
            max_values=25
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        member = interaction.user

        if not website_command_allowed(
            member,
            interaction.channel,
            "خريطة-إعداد"
        ):

            await permission_denied(
                interaction
            )

            return

        channel_ids = [
            channel.id
            for channel in self.values
        ]

        collection.update_one(
            {"guild_id": self.guild_id},
            {
                "$set": {
                    "map_channels": channel_ids
                }
            },
            upsert=True
        )

        await interaction.response.send_message(
            "✅ تم حفظ رومات خريطة السيرفر.",
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
        label="اكتب قوانين السيرفر",
        placeholder=(
            "مثال:\n"
            "1- احترام الجميع\n"
            "2- ممنوع السبام\n"
            "3- ممنوع نشر الروابط"
        ),
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=4000
    )

    def __init__(self, guild_id):

        super().__init__()

        self.guild_id = guild_id

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        if not website_command_allowed(
            interaction.user,
            interaction.channel,
            "خريطة-إعداد"
        ):

            await permission_denied(
                interaction
            )

            return

        collection.update_one(
            {"guild_id": self.guild_id},
            {
                "$set": {
                    "rules": self.rules.value
                }
            },
            upsert=True
        )

        await interaction.response.send_message(
            "✅ تم حفظ قوانين السيرفر.",
            ephemeral=True
        )


# =========================================================
# لوحة إعداد الخريطة
# =========================================================

class ServerMapSetupView(ui.View):

    def __init__(self, guild_id):

        super().__init__(
            timeout=300
        )

        self.guild_id = guild_id

    # -----------------------------------------------------
    # رتب الإشعارات
    # -----------------------------------------------------

    @ui.button(
        label="رتب الإشعارات",
        emoji="🔔",
        style=discord.ButtonStyle.primary
    )
    async def notification_roles(
        self,
        interaction: discord.Interaction,
        button: ui.Button
    ):

        if not website_command_allowed(
            interaction.user,
            interaction.channel,
            "خريطة-إعداد"
        ):

            await permission_denied(
                interaction
            )

            return

        view = ui.View(
            timeout=180
        )

        view.add_item(
            NotificationAdminRoleSelect(
                self.guild_id
            )
        )

        await interaction.response.send_message(
            "🔔 اختر رتب الإشعارات التي تريد إظهارها للأعضاء:",
            view=view,
            ephemeral=True
        )

    # -----------------------------------------------------
    # رومات الخريطة
    # -----------------------------------------------------

    @ui.button(
        label="رومات الخريطة",
        emoji="🗺️",
        style=discord.ButtonStyle.primary
    )
    async def map_channels(
        self,
        interaction: discord.Interaction,
        button: ui.Button
    ):

        if not website_command_allowed(
            interaction.user,
            interaction.channel,
            "خريطة-إعداد"
        ):

            await permission_denied(
                interaction
            )

            return

        view = ui.View(
            timeout=180
        )

        view.add_item(
            MapChannelSelect(
                self.guild_id
            )
        )

        await interaction.response.send_message(
            "🗺️ اختر الرومات التي تريد ظهورها في خريطة السيرفر:",
            view=view,
            ephemeral=True
        )

    # -----------------------------------------------------
    # القوانين
    # -----------------------------------------------------

    @ui.button(
        label="القوانين",
        emoji="📜",
        style=discord.ButtonStyle.primary
    )
    async def rules(
        self,
        interaction: discord.Interaction,
        button: ui.Button
    ):

        if not website_command_allowed(
            interaction.user,
            interaction.channel,
            "خريطة-إعداد"
        ):

            await permission_denied(
                interaction
            )

            return

        await interaction.response.send_modal(
            RulesModal(
                self.guild_id
            )
        )

    # -----------------------------------------------------
    # تحديث
    # -----------------------------------------------------

    @ui.button(
        label="تحديث الخريطة",
        emoji="🔄",
        style=discord.ButtonStyle.success
    )
    async def refresh(
        self,
        interaction: discord.Interaction,
        button: ui.Button
    ):

        if not website_command_allowed(
            interaction.user,
            interaction.channel,
            "خريطة-إعداد"
        ):

            await permission_denied(
                interaction
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
# اختيار رتب الإشعارات من لوحة الإدارة
# =========================================================

class NotificationAdminRoleSelect(ui.RoleSelect):

    def __init__(self, guild_id):

        self.guild_id = guild_id

        super().__init__(
            placeholder="🔔 اختر رتب الإشعارات",
            min_values=1,
            max_values=10
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        if not website_command_allowed(
            interaction.user,
            interaction.channel,
            "خريطة-إعداد"
        ):

            await permission_denied(
                interaction
            )

            return

        role_ids = [
            role.id
            for role in self.values
        ]

        collection.update_one(
            {"guild_id": self.guild_id},
            {
                "$set": {
                    "notification_roles": role_ids
                }
            },
            upsert=True
        )

        await interaction.response.send_message(
            "✅ تم حفظ رتب الإشعارات.\n"
            "الأعضاء الآن يستطيعون اختيار هذه الرتب من خريطة السيرفر.",
            ephemeral=True
        )


# =========================================================
# Cog
# =========================================================

class ServerMapCog(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

    # =====================================================
    # إنشاء الخريطة
    # =====================================================

    @commands.command(name="خريطة-إنشاء")
    async def create_map(
        self,
        ctx
    ):

        if not isinstance(
            ctx.author,
            discord.Member
        ):
            return

        # -------------------------------------------------
        # الموقع هو المتحكم
        # -------------------------------------------------

        if not website_command_allowed(
            ctx.author,
            ctx.channel,
            "خريطة-إنشاء"
        ):

            return

        guild = ctx.guild

        data = get_settings(
            guild.id
        )

        existing_channel = None

        # -------------------------------------------------
        # الروم المحفوظ
        # -------------------------------------------------

        if data.get("map_channel_id"):

            existing_channel = guild.get_channel(
                data["map_channel_id"]
            )

        # -------------------------------------------------
        # إذا موجود
        # -------------------------------------------------

        if existing_channel:

            await ctx.send(
                f"ℹ️ خريطة السيرفر موجودة بالفعل هنا: "
                f"{existing_channel.mention}"
            )

            return

        # -------------------------------------------------
        # البحث عن روم قديم
        # -------------------------------------------------

        for channel in guild.text_channels:

            if channel.name == "🗺️・خريطة-السيرفر":

                existing_channel = channel

                break

        # -------------------------------------------------
        # إنشاء الروم
        # -------------------------------------------------

        if not existing_channel:

            existing_channel = await guild.create_text_channel(
                "🗺️・خريطة-السيرفر"
            )

        # -------------------------------------------------
        # حفظ ID
        # -------------------------------------------------

        collection.update_one(
            {"guild_id": guild.id},
            {
                "$set": {
                    "map_channel_id": existing_channel.id
                }
            },
            upsert=True
        )

        # -------------------------------------------------
        # تحديث
        # -------------------------------------------------

        await update_server_map(
            guild
        )

        await ctx.send(
            f"✅ تم إنشاء خريطة السيرفر بنجاح!\n"
            f"📍 {existing_channel.mention}"
        )

    # =====================================================
    # إعداد الخريطة
    # =====================================================

    @commands.command(name="خريطة-إعداد")
    async def setup_map(
        self,
        ctx
    ):

        if not isinstance(
            ctx.author,
            discord.Member
        ):
            return

        # -------------------------------------------------
        # الموقع هو المتحكم
        # -------------------------------------------------

        if not website_command_allowed(
            ctx.author,
            ctx.channel,
            "خريطة-إعداد"
        ):

            return

        embed = discord.Embed(
            title="🗺️ إعداد خريطة السيرفر",
            description=(
                "من هنا تقدر تتحكم في محتوى خريطة السيرفر.\n\n"

                "🔔 **رتب الإشعارات**\n"
                "حدد الرتب التي يستطيع الأعضاء اختيارها.\n\n"

                "🗺️ **رومات الخريطة**\n"
                "حدد الرومات التي تظهر في الخريطة.\n\n"

                "📜 **القوانين**\n"
                "اكتب قوانين السيرفر.\n\n"

                "🔄 **تحديث الخريطة**\n"
                "يعيد بناء الإيمبدات بالمعلومات الجديدة."
            ),
            color=EMBED_COLOR
        )

        embed.set_footer(
            text="لوحة إدارة خريطة السيرفر"
        )

        await ctx.send(
            embed=embed,
            view=ServerMapSetupView(
                ctx.guild.id
            )
        )


# =========================================================
# Setup
# =========================================================

async def setup(bot):

    await bot.add_cog(
        ServerMapCog(bot)
    )
