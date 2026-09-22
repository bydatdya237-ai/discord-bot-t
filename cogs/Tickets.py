import os
import re
import asyncio
from datetime import datetime, timezone

import discord
from discord.ext import commands
from discord import ui

from pymongo import MongoClient


# =========================================================
# الإعدادات
# =========================================================

TICKET_PANEL_ROOM_ID = 1551938836962091043

PREFIX = "-"

SUPPORT_ROLE_NAME = "𓆩🛠️𓆪・الدعم الفني"

TICKET_CATEGORY_NAME = "🎫・التكتات"

LOG_CHANNEL_NAME = "📋・ticket-logs"

# MongoDB
MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    raise RuntimeError("MONGO_URI غير موجود في Environment Variables")

mongo = MongoClient(MONGO_URI)

db = mongo["discord_bot_db"]

tickets_collection = db["tickets_system"]


# =========================================================
# ألوان
# =========================================================

COLOR_MAIN = 0x8E5BFF
COLOR_SUCCESS = 0x57F287
COLOR_ERROR = 0xED4245
COLOR_WARNING = 0xFEE75C


# =========================================================
# أنواع التكتات
# =========================================================

TICKET_TYPES = {
    "support": {
        "name": "الدعم الفني",
        "emoji": "🛠️",
        "description": "للمساعدة والاستفسارات التقنية"
    },

    "complaint": {
        "name": "شكوى",
        "emoji": "📢",
        "description": "لتقديم شكوى أو بلاغ"
    },

    "finance": {
        "name": "مالية",
        "emoji": "💰",
        "description": "للمواضيع المالية والبنك"
    },

    "application": {
        "name": "تقديم",
        "emoji": "📋",
        "description": "للتقديم على وظيفة أو رتبة"
    }
}


# =========================================================
# أدوات مساعدة
# =========================================================

def now():
    return datetime.now(timezone.utc)


def clean_channel_name(name: str):
    name = name.lower()

    # تحويل المسافات إلى -
    name = name.replace(" ", "-")

    # إزالة الأشياء الغريبة
    name = re.sub(r"[^a-zA-Z0-9\u0600-\u06FF\-_]", "", name)

    # منع أكثر من -
    name = re.sub(r"-+", "-", name)

    return name[:90]


async def send_log(guild, title, description, color=COLOR_MAIN):
    """
    إرسال Log في روم الـ Logs.
    """

    config = tickets_collection.find_one({
        "guild_id": guild.id
    })

    if not config:
        return

    log_channel_id = config.get("log_channel_id")

    if not log_channel_id:
        return

    channel = guild.get_channel(log_channel_id)

    if not channel:
        return

    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=now()
    )

    embed.set_footer(text="Ticket System")

    try:
        await channel.send(embed=embed)
    except:
        pass


# =========================================================
# Modal معلومات التكت
# =========================================================

class TicketInfoModal(ui.Modal, title="فتح تذكرة"):

    reason = ui.TextInput(
        label="سبب فتح التذكرة",
        placeholder="اكتب سبب فتح التذكرة...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000
    )

    async def on_submit(self, interaction: discord.Interaction):

        cog = interaction.client.get_cog("Tickets")

        if not cog:
            await interaction.response.send_message(
                "❌ حدث خطأ في النظام.",
                ephemeral=True
            )
            return

        await cog.create_ticket(
            interaction,
            self.ticket_type,
            str(self.reason)
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

    async def callback(self, interaction: discord.Interaction):

        selected = self.values[0]

        modal = TicketInfoModal()

        modal.ticket_type = selected

        await interaction.response.send_modal(modal)


# =========================================================
# View لوحة فتح التكت
# =========================================================

class TicketPanelView(ui.View):

    def __init__(self):

        super().__init__(timeout=None)

        self.add_item(TicketSelect())


# =========================================================
# أزرار داخل التكت
# =========================================================

class TicketControlView(ui.View):

    def __init__(self):

        super().__init__(timeout=None)

    # -----------------------------------------------------
    # استلام التكت
    # -----------------------------------------------------

    @ui.button(
        label="استلام التكت",
        emoji="🙋",
        style=discord.ButtonStyle.primary,
        custom_id="ticket_claim"
    )
    async def claim(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        cog = interaction.client.get_cog("Tickets")

        if not cog:
            return

        if not await cog.is_support(interaction):
            await interaction.response.send_message(
                "❌ هذا الزر مخصص لفريق الدعم الفني.",
                ephemeral=True
            )
            return

        data = tickets_collection.find_one({
            "channel_id": interaction.channel.id
        })

        if not data:
            await interaction.response.send_message(
                "❌ لم يتم العثور على بيانات التكت.",
                ephemeral=True
            )
            return

        if data.get("claimed_by"):

            claimed_user = interaction.guild.get_member(
                data["claimed_by"]
            )

            name = claimed_user.mention if claimed_user else "عضو آخر"

            await interaction.response.send_message(
                f"❌ التكت مستلم بالفعل بواسطة {name}.",
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
                    "claimed_at": now()
                }
            }
        )

        await interaction.channel.send(
            f"🙋 تم استلام التكت بواسطة {interaction.user.mention}"
        )

        await send_log(
            interaction.guild,
            "🙋 استلام تكت",
            f"**التكت:** {interaction.channel.mention}\n"
            f"**المستلم:** {interaction.user.mention}",
            COLOR_MAIN
        )

        await interaction.response.send_message(
            "✅ تم استلام التكت بنجاح.",
            ephemeral=True
        )

    # -----------------------------------------------------
    # إغلاق
    # -----------------------------------------------------

    @ui.button(
        label="إغلاق التكت",
        emoji="🔒",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket_close"
    )
    async def close(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        cog = interaction.client.get_cog("Tickets")

        if not cog:
            return

        data = tickets_collection.find_one({
            "channel_id": interaction.channel.id
        })

        if not data:
            await interaction.response.send_message(
                "❌ هذه القناة ليست تكت.",
                ephemeral=True
            )
            return

        is_owner = data.get("user_id") == interaction.user.id

        is_support = await cog.is_support(interaction)

        if not is_owner and not is_support:

            await interaction.response.send_message(
                "❌ لا تملك صلاحية إغلاق هذه التذكرة.",
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
                    "closed_at": now()
                }
            }
        )

        try:

            owner = interaction.guild.get_member(
                data["user_id"]
            )

            if owner:

                await interaction.channel.set_permissions(
                    owner,
                    view_channel=True,
                    send_messages=False,
                    read_message_history=True
                )

        except:
            pass

        try:

            await interaction.channel.edit(
                name=f"closed-{interaction.channel.name}"
            )

        except:
            pass

        embed = discord.Embed(
            title="🔒 تم إغلاق التكت",
            description=(
                f"تم إغلاق التذكرة بواسطة {interaction.user.mention}.\n\n"
                "يمكن لفريق الدعم حذف التذكرة عند الانتهاء."
            ),
            color=COLOR_WARNING
        )

        await interaction.response.send_message(
            embed=embed
        )

        await send_log(
            interaction.guild,
            "🔒 إغلاق تكت",
            f"**التكت:** {interaction.channel.mention}\n"
            f"**بواسطة:** {interaction.user.mention}",
            COLOR_WARNING
        )

    # -----------------------------------------------------
    # حذف
    # -----------------------------------------------------

    @ui.button(
        label="حذف التكت",
        emoji="🗑️",
        style=discord.ButtonStyle.danger,
        custom_id="ticket_delete"
    )
    async def delete(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        cog = interaction.client.get_cog("Tickets")

        if not cog:
            return

        if not await cog.is_support(interaction):

            await interaction.response.send_message(
                "❌ حذف التكت مخصص لفريق الدعم الفني فقط.",
                ephemeral=True
            )

            return

        data = tickets_collection.find_one({
            "channel_id": interaction.channel.id
        })

        if not data:
            await interaction.response.send_message(
                "❌ لم يتم العثور على بيانات التكت.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            "🗑️ سيتم حذف التكت خلال **5 ثواني**..."
        )

        await send_log(
            interaction.guild,
            "🗑️ حذف تكت",
            f"**التكت:** #{interaction.channel.name}\n"
            f"**صاحب التكت:** <@{data['user_id']}>\n"
            f"**حذف بواسطة:** {interaction.user.mention}",
            COLOR_ERROR
        )

        tickets_collection.delete_one({
            "channel_id": interaction.channel.id
        })

        await asyncio.sleep(5)

        try:
            await interaction.channel.delete(
                reason=f"Ticket deleted by {interaction.user}"
            )
        except:
            pass


# =========================================================
# Cog
# =========================================================

class Tickets(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        # تسجيل Views حتى تعمل بعد إعادة تشغيل البوت
        bot.add_view(TicketPanelView())
        bot.add_view(TicketControlView())

    # =====================================================
    # التحقق من أن الروم هو روم لوحة التكتات
    # =====================================================

    def is_panel_channel(self, ctx):

        return ctx.channel.id == TICKET_PANEL_ROOM_ID

    # =====================================================
    # التحقق من الدعم
    # =====================================================

    async def is_support(self, interaction):

        guild = interaction.guild

        if not guild:
            return False

        # Owner السيرفر دائمًا مسموح
        if interaction.user.id == guild.owner_id:
            return True

        config = tickets_collection.find_one({
            "guild_id": guild.id
        })

        if not config:
            return False

        role_id = config.get("support_role_id")

        if not role_id:
            return False

        role = guild.get_role(role_id)

        if not role:
            return False

        return role in interaction.user.roles

    # =====================================================
    # أمر تجهيز التكتات
    # =====================================================

    @commands.command(
        name="تجهيز-التكتات"
    )
    @commands.guild_only()
    async def setup_tickets(self, ctx):

        # =================================================
        # الروم المحدد فقط
        # =================================================

        if not self.is_panel_channel(ctx):

            # تجاهل بصمت
            return

        # =================================================
        # Owner أو Support
        # =================================================

        if ctx.author.id != ctx.guild.owner_id:

            config = tickets_collection.find_one({
                "guild_id": ctx.guild.id
            })

            if not config:

                await ctx.send(
                    "❌ نظام التكتات لم يتم تجهيزه بعد.",
                    delete_after=5
                )

                return

            support_role_id = config.get(
                "support_role_id"
            )

            support_role = ctx.guild.get_role(
                support_role_id
            )

            if not support_role or support_role not in ctx.author.roles:

                await ctx.send(
                    "❌ هذا الأمر مخصص للـ Owner وفريق الدعم الفني فقط.",
                    delete_after=5
                )

                return

        await ctx.send(
            "⏳ جاري تجهيز نظام التكتات بالكامل..."
        )

        guild = ctx.guild

        # =================================================
        # إنشاء رتبة الدعم
        # =================================================

        support_role = discord.utils.get(
            guild.roles,
            name=SUPPORT_ROLE_NAME
        )

        if not support_role:

            support_role = await guild.create_role(
                name=SUPPORT_ROLE_NAME,
                permissions=discord.Permissions(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    embed_links=True,
                    attach_files=True,
                    add_reactions=True,
                    use_application_commands=True
                ),
                mentionable=False,
                reason="Ticket System Support Role"
            )

        # =================================================
        # إنشاء Category
        # =================================================

        category = discord.utils.get(
            guild.categories,
            name=TICKET_CATEGORY_NAME
        )

        if not category:

            overwrites = {

                guild.default_role:
                    discord.PermissionOverwrite(
                        view_channel=False
                    ),

                support_role:
                    discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=True,
                        read_message_history=True,
                        attach_files=True,
                        embed_links=True
                    )
            }

            category = await guild.create_category(
                name=TICKET_CATEGORY_NAME,
                overwrites=overwrites,
                reason="Ticket System Category"
            )

        else:

            try:

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

            except:
                pass

        # =================================================
        # إنشاء Logs
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

        tickets_collection.update_one(
            {
                "guild_id": guild.id
            },
            {
                "$set": {
                    "guild_id": guild.id,
                    "support_role_id": support_role.id,
                    "category_id": category.id,
                    "log_channel_id": log_channel.id,
                    "panel_channel_id": TICKET_PANEL_ROOM_ID,
                    "updated_at": now()
                }
            },
            upsert=True
        )

        # =================================================
        # حذف لوحة قديمة من الروم
        # =================================================

        try:

            async for message in ctx.channel.history(
                limit=50
            ):

                if (
                    message.author.id == self.bot.user.id
                    and message.embeds
                    and message.embeds[0].title
                    and "نظام التكتات" in message.embeds[0].title
                ):

                    try:
                        await message.delete()
                    except:
                        pass

        except:
            pass

        # =================================================
        # Embed لوحة التكتات
        # =================================================

        embed = discord.Embed(
            title="🎫 نظام التكتات",
            description=(
                "**مرحبًا بك في نظام الدعم الخاص بالسيرفر.**\n\n"
                "إذا كنت تحتاج إلى مساعدة أو لديك استفسار، "
                "اختر نوع التذكرة المناسبة من القائمة بالأسفل.\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "🛠️ **الدعم الفني**\n"
                "للمساعدة والاستفسارات التقنية.\n\n"
                "📢 **شكوى**\n"
                "لتقديم شكوى أو بلاغ.\n\n"
                "💰 **مالية**\n"
                "للمواضيع المالية والبنك.\n\n"
                "📋 **تقديم**\n"
                "للتقديم على وظيفة أو رتبة.\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "⚠️ **يرجى اختيار القسم المناسب قبل فتح التذكرة.**"
            ),
            color=COLOR_MAIN
        )

        embed.set_footer(
            text="Ticket System • Support Team"
        )

        await ctx.channel.send(
            embed=embed,
            view=TicketPanelView()
        )

        # =================================================
        # رسالة النجاح
        # =================================================

        success = discord.Embed(
            title="✅ تم تجهيز نظام التكتات",
            description=(
                f"**رتبة الدعم:** {support_role.mention}\n"
                f"**قسم التكتات:** {category.name}\n"
                f"**Logs:** {log_channel.mention}\n"
                f"**لوحة التكتات:** {ctx.channel.mention}\n\n"
                "🎫 تم إنشاء لوحة التكتات بنجاح."
            ),
            color=COLOR_SUCCESS
        )

        await ctx.send(
            embed=success,
            delete_after=10
        )

        await send_log(
            guild,
            "⚙️ تجهيز نظام التكتات",
            f"تم تجهيز النظام بواسطة {ctx.author.mention}",
            COLOR_SUCCESS
        )

    # =====================================================
    # إنشاء التكت
    # =====================================================

    async def create_ticket(
        self,
        interaction,
        ticket_type,
        reason
    ):

        guild = interaction.guild
        user = interaction.user

        # =================================================
        # التحقق من النظام
        # =================================================

        config = tickets_collection.find_one({
            "guild_id": guild.id
        })

        if not config:

            await interaction.response.send_message(
                "❌ نظام التكتات غير مجهز.",
                ephemeral=True
            )

            return

        # =================================================
        # منع فتح أكثر من تكت
        # =================================================

        existing = tickets_collection.find_one({
            "guild_id": guild.id,
            "user_id": user.id,
            "closed": False
        })

        if existing:

            channel = guild.get_channel(
                existing.get("channel_id")
            )

            if channel:

                await interaction.response.send_message(
                    f"❌ لديك تكت مفتوح بالفعل: {channel.mention}",
                    ephemeral=True
                )

                return

            else:

                tickets_collection.delete_one({
                    "_id": existing["_id"]
                })

        # =================================================
        # الحصول على الرتبة والقسم
        # =================================================

        support_role = guild.get_role(
            config["support_role_id"]
        )

        category = guild.get_channel(
            config["category_id"]
        )

        if not support_role or not category:

            await interaction.response.send_message(
                "❌ إعدادات نظام التكتات غير مكتملة.",
                ephemeral=True
            )

            return

        # =================================================
        # اسم التكت
        # =================================================

        type_name = TICKET_TYPES[ticket_type]["name"]

        channel_name = clean_channel_name(
            f"{TICKET_TYPES[ticket_type]['emoji']}-{user.name}-{type_name}"
        )

        # =================================================
        # صلاحيات التكت
        # =================================================

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

        # =================================================
        # إنشاء الروم
        # =================================================

        channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            topic=f"Ticket Owner: {user.id} | Type: {ticket_type}",
            reason="New Ticket"
        )

        # =================================================
        # حفظ التكت
        # =================================================

        tickets_collection.insert_one({

            "guild_id": guild.id,

            "channel_id": channel.id,

            "user_id": user.id,

            "username": str(user),

            "ticket_type": ticket_type,

            "reason": reason,

            "claimed_by": None,

            "closed": False,

            "created_at": now()
        })

        # =================================================
        # Embed التكت
        # =================================================

        data = TICKET_TYPES[ticket_type]

        embed = discord.Embed(
            title=f"{data['emoji']} {data['name']}",
            description=(
                f"مرحبًا {user.mention} 👋\n\n"
                "تم فتح تذكرتك بنجاح، وسيقوم فريق الدعم "
                "بمساعدتك في أقرب وقت.\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📌 **نوع التكت:** {data['name']}\n"
                f"📝 **السبب:**\n{reason}\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "🙋 **استلام:** لفريق الدعم\n"
                "🔒 **إغلاق:** لإغلاق التكت\n"
                "🗑️ **حذف:** لحذف التكت"
            ),
            color=COLOR_MAIN
        )

        embed.set_footer(
            text=f"Ticket • {user}"
        )

        await channel.send(
            content=f"{user.mention} {support_role.mention}",
            embed=embed,
            view=TicketControlView()
        )

        # =================================================
        # Log
        # =================================================

        await send_log(
            guild,
            "🎫 فتح تكت جديد",
            (
                f"**صاحب التكت:** {user.mention}\n"
                f"**النوع:** {data['name']}\n"
                f"**الروم:** {channel.mention}\n"
                f"**السبب:** {reason}"
            ),
            COLOR_SUCCESS
        )

        await interaction.response.send_message(
            f"✅ تم فتح تذكرتك بنجاح: {channel.mention}",
            ephemeral=True
        )


# =========================================================
# Setup
# =========================================================

async def setup(bot):

    await bot.add_cog(
        Tickets(bot)
    )

مهم جدًا قبل تشغيله

في البوت الرئيسي لازم تكون عندك المكتبات:

discord.py
pymongo
dnspython
flask
groq
motor
folium

والـ "MONGO_URI" الموجود عندك يشتغل مع الكود.

وبما أن البوت سيقوم بإنشاء الرتبة والكاتيجوري والرومات، تأكد أن رتبة البوت نفسها أعلى من رتبة الدعم الفني، وأن البوت عنده:

- "Manage Channels"
- "Manage Roles"

ولا يحتاج نعطي رتبة الدعم الفني نفسها "Administrator".

طريقة التشغيل

بعد رفع "Tickets.py" وتشغيل البوت، داخل الروم:

"1551938836962091043"

اكتب:

-تجهيز-التكتات

وسيجهز لك النظام تلقائيًا.

ملاحظة: أوامر "-تجهيز-التكتات" مقفلة على الروم المحدد، وعلى Owner السيرفر أو رتبة الدعم التي ينشئها النظام. أما أزرار التكتات نفسها فتعمل داخل التكتات فقط، حتى يستطيع العضو فتح/إدارة تذكرته بالطريقة الطبيعية.

إذا أردت، أقدر في الخطوة التالية أضيف له نظام Transcript كامل + تقييم 1–5 ⭐ بعد الإغلاق + إضافة/إزالة أعضاء من التكت + نظام Claim متقدم + إحصائيات الموظفين بدون تغيير نظام الفتح الحالي.
