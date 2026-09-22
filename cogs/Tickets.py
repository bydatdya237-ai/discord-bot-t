import os
import re
import io
from datetime import datetime, timezone

import discord
from discord.ext import commands
from discord import ui
from pymongo import MongoClient


# =========================================================
# الإعدادات
# =========================================================

PANEL_CHANNEL_ID = 1551938836962091043

SUPPORT_ROLE_NAME = "𓆩🛠️𓆪・الدعم الفني"
TICKET_CATEGORY_NAME = "🎫・التكتات"
LOG_CHANNEL_NAME = "📋・ticket-logs"

MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    raise RuntimeError("MONGO_URI غير موجود في Environment Variables")


# =========================================================
# MongoDB
# =========================================================

mongo = MongoClient(MONGO_URI)

db = mongo["discord_bot_db"]

tickets_collection = db["tickets_system"]
settings_collection = db["tickets_settings"]
ratings_collection = db["tickets_ratings"]


# =========================================================
# الألوان
# =========================================================

PURPLE = 0x8E5BFF
GREEN = 0x57F287
RED = 0xED4245
YELLOW = 0xFEE75C
BLUE = 0x3498DB


# =========================================================
# أنواع التكت
# =========================================================

TICKET_TYPES = {
    "support": {
        "name": "الدعم الفني",
        "emoji": "🛠️",
        "description": "للمساعدة والمشاكل التقنية"
    },

    "complaint": {
        "name": "شكوى",
        "emoji": "📢",
        "description": "لتقديم شكوى أو بلاغ"
    },

    "finance": {
        "name": "مالية",
        "emoji": "💰",
        "description": "للأمور المالية والبنك"
    },

    "application": {
        "name": "تقديم",
        "emoji": "📋",
        "description": "للتقديم على رتبة أو وظيفة"
    }
}


# =========================================================
# الوقت
# =========================================================

def utc_now():
    return datetime.now(timezone.utc)


# =========================================================
# تنظيف أسماء الرومات
# =========================================================

def clean_channel_name(text):

    text = text.lower()
    text = text.replace(" ", "-")

    text = re.sub(
        r"[^a-zA-Z0-9\u0600-\u06FF\-_]",
        "",
        text
    )

    text = re.sub(
        r"-+",
        "-",
        text
    )

    return text[:90]


# =========================================================
# الحصول على إعدادات السيرفر
# =========================================================

def get_settings(guild_id):

    return settings_collection.find_one({
        "guild_id": guild_id
    })


# =========================================================
# إرسال Logs
# =========================================================

async def send_log(
    guild,
    title,
    description,
    color=PURPLE
):

    settings = get_settings(guild.id)

    if not settings:
        return

    channel_id = settings.get("log_channel_id")

    if not channel_id:
        return

    channel = guild.get_channel(channel_id)

    if not channel:
        return

    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=utc_now()
    )

    embed.set_footer(
        text="Ticket System"
    )

    try:
        await channel.send(
            embed=embed
        )
    except Exception:
        pass


# =========================================================
# إنشاء Transcript
# =========================================================

async def create_transcript(channel):

    lines = []

    try:

        async for message in channel.history(
            limit=None,
            oldest_first=True
        ):

            timestamp = message.created_at.strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            content = message.content

            if not content:
                content = "[بدون نص]"

            attachments = ""

            if message.attachments:

                attachments = " | الملفات: " + ", ".join(
                    attachment.url
                    for attachment in message.attachments
                )

            lines.append(
                f"[{timestamp}] "
                f"{message.author} ({message.author.id}): "
                f"{content}{attachments}"
            )

    except Exception as e:

        lines.append(
            f"تعذر إنشاء الـ Transcript: {e}"
        )

    if not lines:
        lines.append(
            "لا توجد رسائل."
        )

    content = "\n".join(lines)

    return io.BytesIO(
        content.encode("utf-8")
    )


# =========================================================
# التحقق من الدعم
# =========================================================

def is_support_member(
    interaction
):

    guild = interaction.guild

    if not guild:
        return False

    if interaction.user.id == guild.owner_id:
        return True

    settings = get_settings(
        guild.id
    )

    if not settings:
        return False

    role_id = settings.get(
        "support_role_id"
    )

    role = guild.get_role(
        role_id
    )

    if not role:
        return False

    return role in interaction.user.roles


# =========================================================
# View تقييم
# =========================================================

class RatingView(ui.View):

    def __init__(
        self,
        ticket_id
    ):

        super().__init__(
            timeout=None
        )

        self.ticket_id = ticket_id

    async def rate(
        self,
        interaction,
        stars
    ):

        ticket = tickets_collection.find_one({
            "channel_id": self.ticket_id
        })

        if not ticket:

            await interaction.response.send_message(
                "❌ لم يتم العثور على بيانات التكت.",
                ephemeral=True
            )

            return

        existing = ratings_collection.find_one({
            "ticket_id": self.ticket_id,
            "user_id": interaction.user.id
        })

        if existing:

            await interaction.response.send_message(
                "❌ لقد قمت بتقييم هذا التكت مسبقًا.",
                ephemeral=True
            )

            return

        ratings_collection.insert_one({

            "guild_id": interaction.guild.id,

            "ticket_id": self.ticket_id,

            "user_id": interaction.user.id,

            "rating": stars,

            "created_at": utc_now()
        })

        await interaction.response.send_message(
            f"⭐ شكرًا لك! تم تسجيل تقييمك: **{stars}/5**",
            ephemeral=True
        )

    @ui.button(
        label="1",
        emoji="⭐",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket_rating_1"
    )
    async def one(
        self,
        interaction,
        button
    ):

        await self.rate(
            interaction,
            1
        )

    @ui.button(
        label="2",
        emoji="⭐",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket_rating_2"
    )
    async def two(
        self,
        interaction,
        button
    ):

        await self.rate(
            interaction,
            2
        )

    @ui.button(
        label="3",
        emoji="⭐",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket_rating_3"
    )
    async def three(
        self,
        interaction,
        button
    ):

        await self.rate(
            interaction,
            3
        )

    @ui.button(
        label="4",
        emoji="⭐",
        style=discord.ButtonStyle.primary,
        custom_id="ticket_rating_4"
    )
    async def four(
        self,
        interaction,
        button
    ):

        await self.rate(
            interaction,
            4
        )

    @ui.button(
        label="5",
        emoji="⭐",
        style=discord.ButtonStyle.success,
        custom_id="ticket_rating_5"
    )
    async def five(
        self,
        interaction,
        button
    ):

        await self.rate(
            interaction,
            5
        )


# =========================================================
# اختيار نوع التكت
# =========================================================

class TicketSelect(ui.Select):

    def __init__(self):

        options = []

        for key, data in TICKET_TYPES.items():

            options.append(
                discord.SelectOption(
                    label=data["name"],
                    description=data["description"],
                    emoji=data["emoji"],
                    value=key
                )
            )

        super().__init__(
            placeholder="🎫 اختر نوع التذكرة",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket_type_select"
        )

    async def callback(
        self,
        interaction
    ):

        ticket_type = self.values[0]

        modal = TicketReasonModal(
            ticket_type
        )

        await interaction.response.send_modal(
            modal
        )


# =========================================================
# Modal سبب التكت
# =========================================================

class TicketReasonModal(
    ui.Modal,
    title="فتح تذكرة"
):

    reason = ui.TextInput(
        label="سبب فتح التذكرة",
        placeholder="اكتب سبب فتح التذكرة...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000
    )

    def __init__(
        self,
        ticket_type
    ):

        super().__init__()

        self.ticket_type = ticket_type

    async def on_submit(
        self,
        interaction
    ):

        cog = interaction.client.get_cog(
            "Tickets"
        )

        if not cog:
            return

        await cog.create_ticket(
            interaction,
            self.ticket_type,
            str(self.reason)
        )


# =========================================================
# لوحة التكت
# =========================================================

class TicketPanelView(ui.View):

    def __init__(self):

        super().__init__(
            timeout=None
        )

        self.add_item(
            TicketSelect()
        )


# =========================================================
# أزرار التكت
# =========================================================

class TicketControlView(ui.View):

    def __init__(self):

        super().__init__(
            timeout=None
        )

    # =====================================================
    # استلام
    # =====================================================

    @ui.button(
        label="استلام التكت",
        emoji="🙋",
        style=discord.ButtonStyle.primary,
        custom_id="ticket_claim"
    )
    async def claim(
        self,
        interaction,
        button
    ):

        cog = interaction.client.get_cog(
            "Tickets"
        )

        if not cog:
            return

        if not is_support_member(
            interaction
        ):

            await interaction.response.send_message(
                "❌ هذا الإجراء مخصص لفريق الدعم الفني.",
                ephemeral=True
            )

            return

        ticket = tickets_collection.find_one({
            "channel_id": interaction.channel.id
        })

        if not ticket:

            await interaction.response.send_message(
                "❌ هذه القناة ليست تكت.",
                ephemeral=True
            )

            return

        if ticket.get("closed"):

            await interaction.response.send_message(
                "❌ التكت مغلق.",
                ephemeral=True
            )

            return

        if ticket.get("claimed_by"):

            member = interaction.guild.get_member(
                ticket["claimed_by"]
            )

            mention = (
                member.mention
                if member
                else "عضو آخر"
            )

            await interaction.response.send_message(
                f"❌ التكت مستلم بالفعل بواسطة {mention}.",
                ephemeral=True
            )

            return

        tickets_collection.update_one(
            {
                "channel_id": interaction.channel.id
            },
            {
                "$set": {
                    "claimed_by": interaction.user.id,
                    "claimed_at": utc_now()
                }
            }
        )

        await interaction.response.send_message(
            f"🙋 تم استلام التكت بواسطة {interaction.user.mention}."
        )

        await send_log(
            interaction.guild,
            "🙋 استلام تكت",
            (
                f"**التكت:** {interaction.channel.mention}\n"
                f"**الموظف:** {interaction.user.mention}"
            ),
            BLUE
        )

    # =====================================================
    # إغلاق
    # =====================================================

    @ui.button(
        label="إغلاق",
        emoji="🔒",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket_close"
    )
    async def close(
        self,
        interaction,
        button
    ):

        ticket = tickets_collection.find_one({
            "channel_id": interaction.channel.id
        })

        if not ticket:

            await interaction.response.send_message(
                "❌ هذه القناة ليست تكت.",
                ephemeral=True
            )

            return

        allowed = (
            interaction.user.id == ticket["user_id"]
            or is_support_member(interaction)
        )

        if not allowed:

            await interaction.response.send_message(
                "❌ لا تملك صلاحية إغلاق التكت.",
                ephemeral=True
            )

            return

        if ticket.get("closed"):

            await interaction.response.send_message(
                "❌ التكت مغلق بالفعل.",
                ephemeral=True
            )

            return

        tickets_collection.update_one(
            {
                "channel_id": interaction.channel.id
            },
            {
                "$set": {
                    "closed": True,
                    "closed_by": interaction.user.id,
                    "closed_at": utc_now()
                }
            }
        )

        owner = interaction.guild.get_member(
            ticket["user_id"]
        )

        if owner:

            try:

                await interaction.channel.set_permissions(
                    owner,
                    view_channel=True,
                    send_messages=False,
                    read_message_history=True
                )

            except Exception:
                pass

        try:

            await interaction.channel.edit(
                name=f"closed-{interaction.channel.name}"[:100]
            )

        except Exception:
            pass

        await interaction.response.send_message(
            embed=discord.Embed(
                title="🔒 تم إغلاق التكت",
                description=(
                    f"تم إغلاق التكت بواسطة "
                    f"{interaction.user.mention}.\n\n"
                    "يمكن لفريق الدعم إعادة فتحه أو حذفه."
                ),
                color=YELLOW
            )
        )

        await send_log(
            interaction.guild,
            "🔒 إغلاق تكت",
            (
                f"**التكت:** {interaction.channel.mention}\n"
                f"**بواسطة:** {interaction.user.mention}"
            ),
            YELLOW
        )

    # =====================================================
    # إعادة فتح
    # =====================================================

    @ui.button(
        label="إعادة فتح",
        emoji="🔓",
        style=discord.ButtonStyle.success,
        custom_id="ticket_reopen"
    )
    async def reopen(
        self,
        interaction,
        button
    ):

        if not is_support_member(
            interaction
        ):

            await interaction.response.send_message(
                "❌ هذا الإجراء للدعم الفني فقط.",
                ephemeral=True
            )

            return

        ticket = tickets_collection.find_one({
            "channel_id": interaction.channel.id
        })

        if not ticket:

            await interaction.response.send_message(
                "❌ هذه القناة ليست تكت.",
                ephemeral=True
            )

            return

        if not ticket.get("closed"):

            await interaction.response.send_message(
                "❌ التكت مفتوح بالفعل.",
                ephemeral=True
            )

            return

        owner = interaction.guild.get_member(
            ticket["user_id"]
        )

        if owner:

            try:

                await interaction.channel.set_permissions(
                    owner,
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    attach_files=True,
                    embed_links=True
                )

            except Exception:
                pass

        tickets_collection.update_one(
            {
                "channel_id": interaction.channel.id
            },
            {
                "$set": {
                    "closed": False,
                    "reopened_by": interaction.user.id,
                    "reopened_at": utc_now()
                }
            }
        )

        try:

            name = interaction.channel.name

            if name.startswith("closed-"):
                name = name[7:]

            await interaction.channel.edit(
                name=name[:100]
            )

        except Exception:
            pass

        await interaction.response.send_message(
            f"🔓 تم إعادة فتح التكت بواسطة {interaction.user.mention}."
        )

        await send_log(
            interaction.guild,
            "🔓 إعادة فتح تكت",
            (
                f"**التكت:** {interaction.channel.mention}\n"
                f"**بواسطة:** {interaction.user.mention}"
            ),
            GREEN
        )

    # =====================================================
    # حذف
    # =====================================================

    @ui.button(
        label="حذف",
        emoji="🗑️",
        style=discord.ButtonStyle.danger,
        custom_id="ticket_delete"
    )
    async def delete(
        self,
        interaction,
        button
    ):

        if not is_support_member(
            interaction
        ):

            await interaction.response.send_message(
                "❌ حذف التكت للدعم الفني فقط.",
                ephemeral=True
            )

            return

        ticket = tickets_collection.find_one({
            "channel_id": interaction.channel.id
        })

        if not ticket:

            await interaction.response.send_message(
                "❌ هذه القناة ليست تكت.",
                ephemeral=True
            )

            return

        await interaction.response.send_message(
            "🗑️ جاري حفظ الـ Transcript وحذف التكت..."
        )

        transcript = await create_transcript(
            interaction.channel
        )

        await send_log(
            interaction.guild,
            "🗑️ حذف تكت",
            (
                f"**صاحب التكت:** <@{ticket['user_id']}>\n"
                f"**حذف بواسطة:** {interaction.user.mention}\n"
                f"**نوع التكت:** "
                f"{TICKET_TYPES[ticket['ticket_type']]['name']}"
            ),
            RED
        )

        settings = get_settings(
            interaction.guild.id
        )

        log_channel = None

        if settings:
            log_channel = interaction.guild.get_channel(
                settings.get("log_channel_id")
            )

        if log_channel:

            file = discord.File(
                transcript,
                filename=f"transcript-{interaction.channel.id}.txt"
            )

            try:

                await log_channel.send(
                    content=(
                        f"📄 **Transcript التكت**\n"
                        f"التكت: `{interaction.channel.name}`\n"
                        f"صاحب التكت: <@{ticket['user_id']}>\n"
                        f"حذف بواسطة: {interaction.user.mention}"
                    ),
                    file=file
                )

            except Exception:
                pass

        tickets_collection.delete_one({
            "_id": ticket["_id"]
        })

        try:
            await interaction.channel.delete(
                reason="Ticket deleted"
            )
        except Exception:
            pass


# =========================================================
# Cog
# =========================================================

class Tickets(commands.Cog):

    def __init__(
        self,
        bot
    ):

        self.bot = bot

        # تسجيل الـ Views بعد إعادة التشغيل
        bot.add_view(
            TicketPanelView()
        )

        bot.add_view(
            TicketControlView()
        )

    # =====================================================
    # التأكد أن الرسالة داخل تكت
    # =====================================================

    def get_ticket(
        self,
        channel_id
    ):

        return tickets_collection.find_one({
            "channel_id": channel_id
        })

    # =====================================================
    # معالجة الأوامر بدون Prefix
    # =====================================================

    @commands.Cog.listener()
    async def on_message(
        self,
        message
    ):

        if message.author.bot:
            return

        if not message.guild:
            return

        content = message.content.strip()

        if not content:
            return

        parts = content.split()

        command_name = parts[0]

        args = parts[1:]

        # =================================================
        # تجهيز التكتات
        # =================================================

        if command_name == "تجهيز-التكتات":

            # الروم المحدد فقط
            if message.channel.id != PANEL_CHANNEL_ID:
                return

            # Owner
            is_owner = (
                message.author.id ==
                message.guild.owner_id
            )

            # Support
            settings = get_settings(
                message.guild.id
            )

            is_support = False

            if settings:

                role = message.guild.get_role(
                    settings.get("support_role_id")
                )

                if role and role in message.author.roles:
                    is_support = True

            if not is_owner and not is_support:

                await message.channel.send(
                    "❌ هذا الأمر مخصص للـ Owner وفريق الدعم الفني.",
                    delete_after=5
                )

                return

            await self.setup_tickets(
                message
            )

            return

        # =================================================
        # باقي الأوامر لازم تكون داخل تكت
        # =================================================

        ticket = self.get_ticket(
            message.channel.id
        )

        if not ticket:
            return

        # =================================================
        # التحقق من الدعم
        # =================================================

        support = is_support_member_from_message(
            message
        )

        # =================================================
        # استلام التكت
        # =================================================

        if command_name == "استلام-التكت":

            if not support:
                return

            if ticket.get("claimed_by"):

                await message.channel.send(
                    "❌ التكت مستلم بالفعل."
                )

                return

            tickets_collection.update_one(
                {
                    "_id": ticket["_id"]
                },
                {
                    "$set": {
                        "claimed_by": message.author.id,
                        "claimed_at": utc_now()
                    }
                }
            )

            await message.channel.send(
                f"🙋 تم استلام التكت بواسطة {message.author.mention}."
            )

            await send_log(
                message.guild,
                "🙋 استلام تكت",
                (
                    f"**التكت:** {message.channel.mention}\n"
                    f"**الموظف:** {message.author.mention}"
                ),
                BLUE
            )

            return

        # =================================================
        # إغلاق
        # =================================================

        if command_name == "إغلاق-التكت":

            allowed = (
                message.author.id == ticket["user_id"]
                or support
            )

            if not allowed:
                return

            await self.close_ticket(
                message,
                ticket
            )

            return

        # =================================================
        # فتح
        # =================================================

        if command_name == "فتح-التكت":

            if not support:
                return

            await self.reopen_ticket(
                message,
                ticket
            )

            return

        # =================================================
        # حذف
        # =================================================

        if command_name == "حذف-التكت":

            if not support:
                return

            await self.delete_ticket(
                message,
                ticket
            )

            return

        # =================================================
        # إضافة عضو
        # =================================================

        if command_name == "إضافة-عضو":

            if not support:
                return

            member = await get_member_from_message(
                message,
                args
            )

            if not member:

                await message.channel.send(
                    "❌ استخدم الأمر بهذا الشكل:\n"
                    "`إضافة-عضو @الشخص`"
                )

                return

            await message.channel.set_permissions(
                member,
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True
            )

            await message.channel.send(
                f"✅ تمت إضافة {member.mention} إلى التكت."
            )

            await send_log(
                message.guild,
                "➕ إضافة عضو",
                (
                    f"**التكت:** {message.channel.mention}\n"
                    f"**العضو:** {member.mention}\n"
                    f"**بواسطة:** {message.author.mention}"
                ),
                GREEN
            )

            return

        # =================================================
        # إزالة عضو
        # =================================================

        if command_name == "إزالة-عضو":

            if not support:
                return

            member = await get_member_from_message(
                message,
                args
            )

            if not member:

                await message.channel.send(
                    "❌ استخدم الأمر بهذا الشكل:\n"
                    "`إزالة-عضو @الشخص`"
                )

                return

            if member.id == ticket["user_id"]:

                await message.channel.send(
                    "❌ لا يمكنك إزالة صاحب التكت."
                )

                return

            await message.channel.set_permissions(
                member,
                overwrite=None
            )

            await message.channel.send(
                f"✅ تمت إزالة {member.mention} من التكت."
            )

            await send_log(
                message.guild,
                "➖ إزالة عضو",
                (
                    f"**التكت:** {message.channel.mention}\n"
                    f"**العضو:** {member.mention}\n"
                    f"**بواسطة:** {message.author.mention}"
                ),
                RED
            )

            return

        # =================================================
        # معلومات التكت
        # =================================================

        if command_name == "معلومات-التكت":

            await self.ticket_info(
                message,
                ticket
            )

            return

    # =====================================================
    # تجهيز النظام
    # =====================================================

    async def setup_tickets(
        self,
        message
    ):

        guild = message.guild

        await message.channel.send(
            "⏳ جاري تجهيز نظام التكتات..."
        )

        # =================================================
        # رتبة الدعم
        # =================================================

        support_role = discord.utils.get(
            guild.roles,
            name=SUPPORT_ROLE_NAME
        )

        if not support_role:

            permissions = discord.Permissions(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                embed_links=True,
                attach_files=True,
                add_reactions=True,
                use_application_commands=True
            )

            support_role = await guild.create_role(
                name=SUPPORT_ROLE_NAME,
                permissions=permissions,
                mentionable=False,
                reason="Ticket System"
            )

        # =================================================
        # Category
        # =================================================

        category = discord.utils.get(
            guild.categories,
            name=TICKET_CATEGORY_NAME
        )

        if not category:

            category = await guild.create_category(
                name=TICKET_CATEGORY_NAME
            )

        await category.set_permissions(
            guild.default_role,
            view_channel=False
        )

        await category.set_permissions(
            support_role,
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            attach_files=True,
            embed_links=True
        )

        # =================================================
        # Logs
        # =================================================

        log_channel = discord.utils.get(
            guild.text_channels,
            name=LOG_CHANNEL_NAME
        )

        if not log_channel:

            log_channel = await guild.create_text_channel(
                LOG_CHANNEL_NAME,
                reason="Ticket System Logs"
            )

        # =================================================
        # حفظ الإعدادات
        # =================================================

        settings_collection.update_one(
            {
                "guild_id": guild.id
            },
            {
                "$set": {
                    "guild_id": guild.id,
                    "support_role_id": support_role.id,
                    "category_id": category.id,
                    "log_channel_id": log_channel.id,
                    "panel_channel_id": PANEL_CHANNEL_ID,
                    "updated_at": utc_now()
                }
            },
            upsert=True
        )

        # =================================================
        # إرسال لوحة التكت
        # =================================================

        embed = discord.Embed(
            title="🎫 نظام التكتات",
            description=(
                "**مرحبًا بك في نظام الدعم.**\n\n"
                "للحصول على المساعدة، اختر القسم المناسب "
                "من القائمة الموجودة بالأسفل.\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "🛠️ **الدعم الفني**\n"
                "للمشاكل والاستفسارات التقنية.\n\n"
                "📢 **شكوى**\n"
                "لتقديم شكوى أو بلاغ.\n\n"
                "💰 **مالية**\n"
                "للأمور المالية والبنك.\n\n"
                "📋 **تقديم**\n"
                "للتقديم على رتبة أو وظيفة.\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "⚠️ يرجى اختيار القسم الصحيح قبل فتح التكت."
            ),
            color=PURPLE
        )

        embed.set_footer(
            text="Ticket System • Support Team"
        )

        await message.channel.send(
            embed=embed,
            view=TicketPanelView()
        )

        await message.channel.send(
            embed=discord.Embed(
                title="✅ تم تجهيز النظام",
                description=(
                    f"**رتبة الدعم:** {support_role.mention}\n"
                    f"**Category:** `{category.name}`\n"
                    f"**Logs:** {log_channel.mention}\n\n"
                    "🎫 لوحة التكتات جاهزة الآن."
                ),
                color=GREEN
            ),
            delete_after=10
        )

        await send_log(
            guild,
            "⚙️ تجهيز نظام التكتات",
            f"تم تجهيز النظام بواسطة {message.author.mention}",
            GREEN
        )

    # =====================================================
    # إنشاء تكت
    # =====================================================

    async def create_ticket(
        self,
        interaction,
        ticket_type,
        reason
    ):

        guild = interaction.guild
        user = interaction.user

        settings = get_settings(
            guild.id
        )

        if not settings:

            await interaction.response.send_message(
                "❌ نظام التكتات غير مجهز.",
                ephemeral=True
            )

            return

        existing = tickets_collection.find_one({
            "guild_id": guild.id,
            "user_id": user.id,
            "closed": False
        })

        if existing:

            channel = guild.get_channel(
                existing["channel_id"]
            )

            if channel:

                await interaction.response.send_message(
                    f"❌ لديك تكت مفتوح بالفعل: {channel.mention}",
                    ephemeral=True
                )

                return

            tickets_collection.delete_one({
                "_id": existing["_id"]
            })

        support_role = guild.get_role(
            settings["support_role_id"]
        )

        category = guild.get_channel(
            settings["category_id"]
        )

        if not support_role or not category:

            await interaction.response.send_message(
                "❌ إعدادات التكتات غير مكتملة.",
                ephemeral=True
            )

            return

        data = TICKET_TYPES[
            ticket_type
        ]

        channel_name = clean_channel_name(
            f"{data['emoji']}-{user.name}-{data['name']}"
        )

        overwrites = {

            guild.default_role:
                discord.PermissionOverwrite(
                    view_channel=False
                ),

            user:
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    attach_files=True,
                    embed_links=True,
                    add_reactions=True
                ),

            support_role:
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    attach_files=True,
                    embed_links=True,
                    add_reactions=True
                )
        }

        channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            topic=(
                f"Ticket Owner: {user.id} | "
                f"Type: {ticket_type}"
            )
        )

        tickets_collection.insert_one({

            "guild_id": guild.id,

            "channel_id": channel.id,

            "user_id": user.id,

            "ticket_type": ticket_type,

            "reason": reason,

            "claimed_by": None,

            "closed": False,

            "created_at": utc_now()
        })

        embed = discord.Embed(
            title=f"{data['emoji']} {data['name']}",
            description=(
                f"مرحبًا {user.mention} 👋\n\n"
                "تم فتح تذكرتك بنجاح.\n"
                "سيقوم فريق الدعم بمساعدتك قريبًا.\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📌 **القسم:** {data['name']}\n"
                f"📝 **السبب:**\n{reason}\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "يمكنك استخدام الأوامر التالية داخل التكت:\n\n"
                "`إغلاق-التكت`\n"
                "`معلومات-التكت`\n\n"
                "وفريق الدعم يستطيع استخدام أوامر الإدارة."
            ),
            color=PURPLE
        )

        embed.set_footer(
            text="Ticket System"
        )

        await channel.send(
            content=f"{user.mention} {support_role.mention}",
            embed=embed,
            view=TicketControlView()
        )

        await interaction.response.send_message(
            f"✅ تم فتح التكت: {channel.mention}",
            ephemeral=True
        )

        await send_log(
            guild,
            "🎫 فتح تكت جديد",
            (
                f"**صاحب التكت:** {user.mention}\n"
                f"**النوع:** {data['name']}\n"
                f"**الروم:** {channel.mention}\n"
                f"**السبب:** {reason}"
            ),
            GREEN
        )

    # =====================================================
    # إغلاق التكت
    # =====================================================

    async def close_ticket(
        self,
        message,
        ticket
    ):

        if ticket.get("closed"):

            await message.channel.send(
                "❌ التكت مغلق بالفعل."
            )

            return

        owner = message.guild.get_member(
            ticket["user_id"]
        )

        if owner:

            await message.channel.set_permissions(
                owner,
                view_channel=True,
                send_messages=False,
                read_message_history=True
            )

        tickets_collection.update_one(
            {
                "_id": ticket["_id"]
            },
            {
                "$set": {
                    "closed": True,
                    "closed_by": message.author.id,
                    "closed_at": utc_now()
                }
            }
        )

        try:

            name = message.channel.name

            if not name.startswith("closed-"):

                await message.channel.edit(
                    name=f"closed-{name}"[:100]
                )

        except Exception:
            pass

        await message.channel.send(
            "🔒 تم إغلاق التكت."
        )

        await send_log(
            message.guild,
            "🔒 إغلاق تكت",
            (
                f"**التكت:** {message.channel.mention}\n"
                f"**بواسطة:** {message.author.mention}"
            ),
            YELLOW
        )

    # =====================================================
    # إعادة فتح
    # =====================================================

    async def reopen_ticket(
        self,
        message,
        ticket
    ):

        if not ticket.get("closed"):

            await message.channel.send(
                "❌ التكت مفتوح بالفعل."
            )

            return

        owner = message.guild.get_member(
            ticket["user_id"]
        )

        if owner:

            await message.channel.set_permissions(
                owner,
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True
            )

        tickets_collection.update_one(
            {
                "_id": ticket["_id"]
            },
            {
                "$set": {
                    "closed": False,
                    "reopened_by": message.author.id,
                    "reopened_at": utc_now()
                }
            }
        )

        try:

            name = message.channel.name

            if name.startswith("closed-"):

                name = name[7:]

            await message.channel.edit(
                name=name[:100]
            )

        except Exception:
            pass

        await message.channel.send(
            "🔓 تم إعادة فتح التكت."
        )

        await send_log(
            message.guild,
            "🔓 إعادة فتح تكت",
            (
                f"**التكت:** {message.channel.mention}\n"
                f"**بواسطة:** {message.author.mention}"
            ),
            GREEN
        )

    # =====================================================
    # حذف التكت
    # =====================================================

    async def delete_ticket(
        self,
        message,
        ticket
    ):

        await message.channel.send(
            "🗑️ جاري حفظ الـ Transcript وحذف التكت..."
        )

        transcript = await create_transcript(
            message.channel
        )

        settings = get_settings(
            message.guild.id
        )

        if settings:

            log_channel = message.guild.get_channel(
                settings.get("log_channel_id")
            )

            if log_channel:

                file = discord.File(
                    transcript,
                    filename=(
                        f"transcript-"
                        f"{message.channel.id}.txt"
                    )
                )

                await log_channel.send(
                    content=(
                        "📄 **Transcript تكت**\n"
                        f"التكت: `{message.channel.name}`\n"
                        f"صاحب التكت: <@{ticket['user_id']}>\n"
                        f"حذف بواسطة: {message.author.mention}"
                    ),
                    file=file
                )

        await send_log(
            message.guild,
            "🗑️ حذف تكت",
            (
                f"**صاحب التكت:** <@{ticket['user_id']}>\n"
                f"**حذف بواسطة:** {message.author.mention}"
            ),
            RED
        )

        tickets_collection.delete_one({
            "_id": ticket["_id"]
        })

        await message.channel.delete(
            reason="Ticket deleted"
        )

    # =====================================================
    # معلومات التكت
    # =====================================================

    async def ticket_info(
        self,
        message,
        ticket
    ):

        data = TICKET_TYPES.get(
            ticket["ticket_type"]
        )

        claimed = ticket.get(
            "claimed_by"
        )

        claimed_text = (
            f"<@{claimed}>"
            if claimed
            else "لم يتم الاستلام"
        )

        status = (
            "🔒 مغلق"
            if ticket.get("closed")
            else "🟢 مفتوح"
        )

        embed = discord.Embed(
            title="📋 معلومات التكت",
            color=PURPLE
        )

        embed.add_field(
            name="👤 صاحب التكت",
            value=f"<@{ticket['user_id']}>",
            inline=True
        )

        embed.add_field(
            name="📌 النوع",
            value=data["name"],
            inline=True
        )

        embed.add_field(
            name="📊 الحالة",
            value=status,
            inline=True
        )

        embed.add_field(
            name="🙋 المستلم",
            value=claimed_text,
            inline=True
        )

        embed.add_field(
            name="📝 السبب",
            value=ticket["reason"][:1024],
            inline=False
        )

        embed.add_field(
            name="🕐 تاريخ الإنشاء",
            value=ticket["created_at"].strftime(
                "%Y-%m-%d %H:%M:%S UTC"
            ),
            inline=False
        )

        await message.channel.send(
            embed=embed
        )


# =========================================================
# Helpers
# =========================================================

def is_support_member_from_message(
    message
):

    if message.author.id == message.guild.owner_id:
        return True

    settings = get_settings(
        message.guild.id
    )

    if not settings:
        return False

    role = message.guild.get_role(
        settings.get("support_role_id")
    )

    if not role:
        return False

    return role in message.author.roles


async def get_member_from_message(
    message,
    args
):

    if not args:
        return None

    # محاولة Mention
    if message.mentions:

        return message.mentions[0]

    # ID
    raw = args[0]

    raw = raw.strip("<@!>")

    if raw.isdigit():

        return message.guild.get_member(
            int(raw)
        )

    # اسم العضو
    lowered = raw.lower()

    for member in message.guild.members:

        if member.name.lower() == lowered:
            return member

        if member.display_name.lower() == lowered:
            return member

    return None


# =========================================================
# Setup
# =========================================================

async def setup(bot):

    await bot.add_cog(
        Tickets(bot)
    )
