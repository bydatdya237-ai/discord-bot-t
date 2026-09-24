import asyncio
import os
from datetime import datetime, timezone

import discord
from discord.ext import commands
from discord import ui

from pymongo import MongoClient


# =========================================================
# الإعدادات العامة
# =========================================================

MONGO_DB_NAME = "discord_bot_db"

IDEA_COLLECTION_NAME = "idea_submissions"

# رتبة الإدارة المسموح لها بإعداد نظام المساهمات
SETUP_ROLE_ID = 1544078469657530578

# تأخير بين رسائل الـ DM
DM_DELAY = 0.7


# =========================================================
# MongoDB
# =========================================================

mongo_url = os.environ.get("MONGO_URI")

if not mongo_url:
    raise RuntimeError("❌ متغير MONGO_URI غير موجود.")

mongo_client = MongoClient(mongo_url)

db = mongo_client[MONGO_DB_NAME]

ideas_collection = db[IDEA_COLLECTION_NAME]

# إعدادات المساهمات لكل سيرفر
ideas_settings_collection = db["idea_settings"]


# =========================================================
# أدوات الإعدادات
# =========================================================

def get_guild_settings(guild_id: int):

    settings = ideas_settings_collection.find_one({
        "guild_id": guild_id
    })

    if not settings:
        return {}

    return settings


def get_idea_log_channel_id(guild_id: int):

    settings = get_guild_settings(guild_id)

    return settings.get("log_channel_id")


def set_idea_log_channel(
    guild_id: int,
    channel_id: int
):

    ideas_settings_collection.update_one(

        {
            "guild_id": guild_id
        },

        {
            "$set": {

                "guild_id": guild_id,

                "log_channel_id": channel_id,

                "updated_at":
                    datetime.now(timezone.utc)
            }
        },

        upsert=True
    )


# =========================================================
# التحقق من رتبة الإعداد
# =========================================================

def has_setup_role(member: discord.Member) -> bool:

    if not isinstance(member, discord.Member):
        return False

    return any(
        role.id == SETUP_ROLE_ID
        for role in member.roles
    )


# =========================================================
# Modal إرسال الفكرة
# =========================================================

class IdeaModal(
    ui.Modal,
    title="ساهم معنا بفعالية"
):

    idea_name = ui.TextInput(
        label="اسم الفكرة",
        placeholder="مثال: مسابقة أسبوعية...",
        style=discord.TextStyle.short,
        required=True,
        max_length=100
    )

    idea_description = ui.TextInput(
        label="شرح الفكرة",
        placeholder="اشرح فكرتك بالتفصيل...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=2000
    )

    implementation = ui.TextInput(
        label="طريقة التطبيق",
        placeholder="كيف يمكن تطبيقها داخل السيرفر؟",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=2000
    )

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        user = interaction.user

        # =====================================================
        # التأكد من وجود السيرفر
        # =====================================================

        guild = interaction.guild

        if guild is None:

            await interaction.response.send_message(
                "❌ لا يمكن إرسال المساهمة من الخاص.",
                ephemeral=True
            )

            return

        # =====================================================
        # الحصول على لوق المساهمات
        # =====================================================

        log_channel_id = get_idea_log_channel_id(
            guild.id
        )

        if not log_channel_id:

            await interaction.response.send_message(
                "❌ لم يتم تحديد روم استقبال المساهمات حتى الآن.",
                ephemeral=True
            )

            return

        idea_channel = guild.get_channel(
            int(log_channel_id)
        )

        if idea_channel is None:

            await interaction.response.send_message(
                "❌ روم استقبال المساهمات المحدد غير موجود.",
                ephemeral=True
            )

            return

        # =====================================================
        # منع إرسال فكرة ثانية أثناء المراجعة
        # =====================================================

        existing = ideas_collection.find_one({

            "guild_id": guild.id,

            "user_id": user.id,

            "status": "pending"
        })

        if existing:

            await interaction.response.send_message(

                "⚠️ لديك مساهمة قيد المراجعة بالفعل.\n"
                "انتظر حتى يتم مراجعتها من الإدارة.",

                ephemeral=True
            )

            return

        # =====================================================
        # رقم المساهمة
        # =====================================================

        last_idea = ideas_collection.find_one(

            {
                "guild_id": guild.id
            },

            sort=[
                ("idea_number", -1)
            ]
        )

        if last_idea:

            idea_number = (
                last_idea.get("idea_number", 0) + 1
            )

        else:

            idea_number = 1

        # =====================================================
        # حفظ الفكرة
        # =====================================================

        idea_data = {

            "idea_number": idea_number,

            "user_id": user.id,

            "username": str(user),

            "guild_id": guild.id,

            "idea_name": str(
                self.idea_name
            ),

            "description": str(
                self.idea_description
            ),

            "implementation": str(
                self.implementation
            ),

            "status": "pending",

            "created_at": datetime.now(
                timezone.utc
            )
        }

        result = ideas_collection.insert_one(
            idea_data
        )

        # =====================================================
        # Embed الفكرة
        # =====================================================

        embed = discord.Embed(

            title="💡 مساهمة جديدة",

            description=(

                f"**رقم المساهمة:** "
                f"`#{idea_number:03d}`\n\n"

                f"**صاحب الفكرة:** "
                f"{user.mention}\n\n"

                f"### 📝 اسم الفكرة\n"
                f"{self.idea_name}\n\n"

                f"### 📖 شرح الفكرة\n"
                f"{self.idea_description}\n\n"

                f"### 🛠️ طريقة التطبيق\n"
                f"{self.implementation}"
            ),

            color=discord.Color.blurple(),

            timestamp=datetime.now(
                timezone.utc
            )
        )

        embed.set_footer(
            text="🟡 حالة المساهمة: قيد المراجعة"
        )

        # =====================================================
        # أزرار المراجعة
        # =====================================================

        review_view = IdeaReviewView()

        try:

            review_message = await idea_channel.send(

                embed=embed,

                view=review_view,

                allowed_mentions=
                discord.AllowedMentions.none()
            )

            # حفظ رسالة المراجعة
            ideas_collection.update_one(

                {
                    "_id": result.inserted_id
                },

                {
                    "$set": {

                        "review_message_id":
                            review_message.id,

                        "log_channel_id":
                            idea_channel.id
                    }
                }
            )

        except Exception as e:

            ideas_collection.delete_one({

                "_id": result.inserted_id
            })

            print(
                f"❌ خطأ أثناء إرسال المساهمة: {e}"
            )

            await interaction.response.send_message(

                "❌ حدث خطأ أثناء إرسال مساهمتك.",

                ephemeral=True
            )

            return

        # =====================================================
        # الرد لصاحب الفكرة
        # =====================================================

        await interaction.response.send_message(

            f"✅ **تم إرسال مساهمتك بنجاح!**\n\n"

            f"💡 الفكرة: **{self.idea_name}**\n"

            f"📌 رقم المساهمة: "
            f"`#{idea_number:03d}`\n\n"

            f"🟡 سيتم مراجعتها من الإدارة.",

            ephemeral=True
        )


# =========================================================
# رسالة الـ DM
# =========================================================

class IdeaDMView(ui.View):

    def __init__(self):

        super().__init__(
            timeout=None
        )

    @ui.button(
        label="ساهم بفكرتك",
        style=discord.ButtonStyle.primary,
        emoji="💡",
        custom_id="ideas:open_modal"
    )
    async def open_modal(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.send_modal(
            IdeaModal()
        )


# =========================================================
# Modal سبب الرفض
# =========================================================

class RejectReasonModal(
    ui.Modal,
    title="سبب رفض المساهمة"
):

    reason = ui.TextInput(

        label="سبب الرفض",

        placeholder="اكتب سبب رفض الفكرة...",

        style=discord.TextStyle.paragraph,

        required=True,

        max_length=1500
    )

    def __init__(
        self,
        idea
    ):

        super().__init__()

        self.idea = idea

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        idea = self.idea

        if idea.get("status") != "pending":

            await interaction.response.send_message(

                "⚠️ تمت معالجة هذه المساهمة مسبقًا.",

                ephemeral=True
            )

            return

        reason_text = str(
            self.reason
        )

        # =====================================================
        # تحديث قاعدة البيانات
        # =====================================================

        ideas_collection.update_one(

            {
                "_id": idea["_id"]
            },

            {
                "$set": {

                    "status": "rejected",

                    "rejection_reason":
                        reason_text,

                    "reviewed_by":
                        interaction.user.id,

                    "reviewed_at":
                        datetime.now(
                            timezone.utc
                        )
                }
            }
        )

        # =====================================================
        # تعديل الرسالة
        # =====================================================

        if interaction.message:

            if interaction.message.embeds:

                old_embed = (
                    interaction.message.embeds[0]
                )

                embed = old_embed.copy()

                embed.color = (
                    discord.Color.red()
                )

                embed.set_footer(

                    text=(
                        f"🔴 حالة المساهمة: مرفوضة "
                        f"• بواسطة {interaction.user}"
                    )
                )

                await interaction.message.edit(

                    embed=embed,

                    view=IdeaReviewView(
                        disabled=True
                    )
                )

        # =====================================================
        # إرسال سبب الرفض
        # =====================================================

        try:

            user = await interaction.client.fetch_user(
                idea["user_id"]
            )

            dm_embed = discord.Embed(

                title="📩 تحديث على مساهمتك",

                description=(

                    f"تمت مراجعة فكرتك:\n"
                    f"**{idea['idea_name']}**\n\n"

                    f"📌 رقم المساهمة: "
                    f"`#{idea['idea_number']:03d}`\n\n"

                    f"🔴 **حالة المساهمة: مرفوضة**\n\n"

                    f"### 📝 سبب الرفض\n"
                    f"{reason_text}"
                ),

                color=discord.Color.red()
            )

            await user.send(
                embed=dm_embed
            )

        except Exception as e:

            print(
                f"⚠️ تعذر إرسال سبب الرفض: {e}"
            )

        await interaction.response.send_message(

            "❌ تم رفض المساهمة وإرسال سبب الرفض لصاحبها.",

            ephemeral=True
        )


# =========================================================
# Modal طلب تعديل
# =========================================================

class EditRequestModal(
    ui.Modal,
    title="طلب تعديل على الفكرة"
):

    changes = ui.TextInput(

        label="ما المطلوب تعديله؟",

        placeholder="اكتب التعديلات أو الملاحظات المطلوبة...",

        style=discord.TextStyle.paragraph,

        required=True,

        max_length=1500
    )

    def __init__(
        self,
        idea
    ):

        super().__init__()

        self.idea = idea

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        idea = self.idea

        if idea.get("status") != "pending":

            await interaction.response.send_message(

                "⚠️ تمت معالجة هذه المساهمة مسبقًا.",

                ephemeral=True
            )

            return

        changes = str(
            self.changes
        )

        # =====================================================
        # تحديث الحالة
        # =====================================================

        ideas_collection.update_one(

            {
                "_id": idea["_id"]
            },

            {
                "$set": {

                    "status": "needs_edit",

                    "edit_request":
                        changes,

                    "reviewed_by":
                        interaction.user.id,

                    "reviewed_at":
                        datetime.now(
                            timezone.utc
                        )
                }
            }
        )

        # =====================================================
        # تعديل Embed
        # =====================================================

        if interaction.message:

            if interaction.message.embeds:

                old_embed = (
                    interaction.message.embeds[0]
                )

                embed = old_embed.copy()

                embed.color = (
                    discord.Color.orange()
                )

                embed.set_footer(

                    text=(
                        f"🟠 حالة المساهمة: تحتاج تعديل "
                        f"• بواسطة {interaction.user}"
                    )
                )

                await interaction.message.edit(

                    embed=embed,

                    view=IdeaReviewView(
                        disabled=True
                    )
                )

        # =====================================================
        # إرسال الطلب لصاحب الفكرة
        # =====================================================

        try:

            user = await interaction.client.fetch_user(
                idea["user_id"]
            )

            dm_embed = discord.Embed(

                title="📝 مطلوب تعديل على مساهمتك",

                description=(

                    f"تمت مراجعة فكرتك:\n"
                    f"**{idea['idea_name']}**\n\n"

                    f"📌 رقم المساهمة: "
                    f"`#{idea['idea_number']:03d}`\n\n"

                    f"الإدارة ترغب بتعديل بعض التفاصيل "
                    f"قبل اعتماد الفكرة.\n\n"

                    f"### 🛠️ المطلوب تعديله\n"
                    f"{changes}"
                ),

                color=discord.Color.orange()
            )

            await user.send(
                embed=dm_embed
            )

        except Exception as e:

            print(
                f"⚠️ تعذر إرسال طلب التعديل: {e}"
            )

        await interaction.response.send_message(

            "🟠 تم إرسال طلب التعديل لصاحبها.",

            ephemeral=True
        )


# =========================================================
# أزرار مراجعة الأفكار
# =========================================================

class IdeaReviewView(ui.View):

    def __init__(
        self,
        disabled=False
    ):

        super().__init__(
            timeout=None
        )

        for child in self.children:

            if isinstance(
                child,
                discord.ui.Button
            ):

                child.disabled = disabled

    # =====================================================
    # قبول
    # =====================================================

    @ui.button(
        label="قبول",
        style=discord.ButtonStyle.success,
        emoji="✅",
        custom_id="ideas:accept"
    )
    async def accept_idea(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not has_setup_role(
            interaction.user
        ):

            await interaction.response.send_message(

                "❌ ليس لديك صلاحية استخدام هذا الزر.",

                ephemeral=True
            )

            return

        idea = ideas_collection.find_one({

            "review_message_id":
                interaction.message.id
        })

        if not idea:

            await interaction.response.send_message(

                "❌ لم يتم العثور على بيانات المساهمة.",

                ephemeral=True
            )

            return

        if idea.get("status") != "pending":

            await interaction.response.send_message(

                "⚠️ تمت معالجة هذه المساهمة مسبقًا.",

                ephemeral=True
            )

            return

        # =====================================================
        # تحديث
        # =====================================================

        ideas_collection.update_one(

            {
                "_id": idea["_id"]
            },

            {
                "$set": {

                    "status": "accepted",

                    "reviewed_by":
                        interaction.user.id,

                    "reviewed_at":
                        datetime.now(
                            timezone.utc
                        )
                }
            }
        )

        # =====================================================
        # تعديل Embed
        # =====================================================

        old_embed = (
            interaction.message.embeds[0]
        )

        embed = old_embed.copy()

        embed.color = (
            discord.Color.green()
        )

        embed.set_footer(

            text=(
                f"🟢 حالة المساهمة: مقبولة "
                f"• بواسطة {interaction.user}"
            )
        )

        await interaction.message.edit(

            embed=embed,

            view=IdeaReviewView(
                disabled=True
            )
        )

        # =====================================================
        # DM
        # =====================================================

        try:

            user = await interaction.client.fetch_user(
                idea["user_id"]
            )

            dm_embed = discord.Embed(

                title="🎉 تم قبول مساهمتك!",

                description=(

                    f"تم قبول فكرتك:\n"
                    f"**{idea['idea_name']}**\n\n"

                    f"📌 رقم المساهمة: "
                    f"`#{idea['idea_number']:03d}`\n\n"

                    f"الرجاء التوجه إلى **التكت** "
                    f"للتواصل مع الإدارة واستكمال التفاصيل."
                ),

                color=discord.Color.green()
            )

            await user.send(
                embed=dm_embed
            )

        except Exception as e:

            print(
                f"⚠️ تعذر إرسال رسالة القبول: {e}"
            )

        await interaction.response.send_message(

            "✅ تم قبول المساهمة وإبلاغ صاحبها.",

            ephemeral=True
        )

    # =====================================================
    # رفض
    # =====================================================

    @ui.button(
        label="رفض",
        style=discord.ButtonStyle.danger,
        emoji="❌",
        custom_id="ideas:reject"
    )
    async def reject_idea(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not has_setup_role(
            interaction.user
        ):

            await interaction.response.send_message(

                "❌ ليس لديك صلاحية استخدام هذا الزر.",

                ephemeral=True
            )

            return

        idea = ideas_collection.find_one({

            "review_message_id":
                interaction.message.id
        })

        if not idea:

            await interaction.response.send_message(

                "❌ لم يتم العثور على بيانات المساهمة.",

                ephemeral=True
            )

            return

        if idea.get("status") != "pending":

            await interaction.response.send_message(

                "⚠️ تمت معالجة هذه المساهمة مسبقًا.",

                ephemeral=True
            )

            return

        await interaction.response.send_modal(
            RejectReasonModal(idea)
        )

    # =====================================================
    # طلب تعديل
    # =====================================================

    @ui.button(
        label="طلب تعديل",
        style=discord.ButtonStyle.secondary,
        emoji="📝",
        custom_id="ideas:edit"
    )
    async def request_edit(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not has_setup_role(
            interaction.user
        ):

            await interaction.response.send_message(

                "❌ ليس لديك صلاحية استخدام هذا الزر.",

                ephemeral=True
            )

            return

        idea = ideas_collection.find_one({

            "review_message_id":
                interaction.message.id
        })

        if not idea:

            await interaction.response.send_message(

                "❌ لم يتم العثور على بيانات المساهمة.",

                ephemeral=True
            )

            return

        if idea.get("status") != "pending":

            await interaction.response.send_message(

                "⚠️ تمت معالجة هذه المساهمة مسبقًا.",

                ephemeral=True
            )

            return

        await interaction.response.send_modal(
            EditRequestModal(idea)
        )


# =========================================================
# تأكيد الإرسال للجميع
# =========================================================

class BroadcastConfirmView(ui.View):

    def __init__(
        self,
        cog,
        guild_id
    ):

        super().__init__(
            timeout=60
        )

        self.cog = cog

        self.guild_id = guild_id

    # =====================================================
    # تأكيد
    # =====================================================

    @ui.button(
        label="نعم، إرسال للجميع",
        style=discord.ButtonStyle.success,
        emoji="📢"
    )
    async def confirm(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not has_setup_role(
            interaction.user
        ):

            await interaction.response.send_message(

                "❌ ليس لديك صلاحية استخدام هذا الزر.",

                ephemeral=True
            )

            return

        guild = interaction.client.get_guild(
            self.guild_id
        )

        if guild is None:

            await interaction.response.send_message(

                "❌ تعذر العثور على السيرفر.",

                ephemeral=True
            )

            return

        # تعطيل الأزرار

        for child in self.children:

            if isinstance(
                child,
                discord.ui.Button
            ):

                child.disabled = True

        await interaction.response.edit_message(

            content=(
                "⏳ **جاري إرسال رسالة «ساهم معنا بفعالية»...**\n\n"
                "سيتم إرسالها للأعضاء واحدًا تلو الآخر."
            ),

            embed=None,

            view=self
        )

        # =====================================================
        # الإرسال
        # =====================================================

        sent, failed = (
            await self.cog.broadcast_to_server(
                guild
            )
        )

        await interaction.edit_original_response(

            content=(

                "✅ **انتهى إرسال فعالية المساهمات!**\n\n"

                f"📨 تم الإرسال بنجاح: `{sent}`\n"

                f"⚠️ تعذر الإرسال: `{failed}`\n\n"

                "يمكن الآن للأعضاء الضغط على زر "
                "**ساهم بفكرتك** وإرسال مساهماتهم."
            ),

            view=None
        )

    # =====================================================
    # إلغاء
    # =====================================================

    @ui.button(
        label="إلغاء",
        style=discord.ButtonStyle.danger,
        emoji="🛑"
    )
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not has_setup_role(
            interaction.user
        ):

            await interaction.response.send_message(

                "❌ ليس لديك صلاحية استخدام هذا الزر.",

                ephemeral=True
            )

            return

        await interaction.response.edit_message(

            content=(
                "🛑 **تم إلغاء الإرسال.**\n\n"
                "لم يتم إرسال أي رسالة للأعضاء."
            ),

            embed=None,

            view=None
        )


# =========================================================
# Cog
# =========================================================

class IdeasCog(commands.Cog):

    def __init__(
        self,
        bot
    ):

        self.bot = bot

    # =====================================================
    # عند تحميل الـ Cog
    # =====================================================

    async def cog_load(self):

        self.bot.add_view(
            IdeaDMView()
        )

        self.bot.add_view(
            IdeaReviewView()
        )

    # =====================================================
    # تحديد لوق المساهمات
    #
    # الاستخدام المطلوب:
    #
    # تحديد لوق المساهمات
    #
    # داخل الروم نفسه الذي تريد جعله لوق.
    # =====================================================

    async def handle_set_idea_log(
        self,
        message
    ):

        if message.guild is None:
            return

        # =====================================================
        # التحقق من الرتبة
        # =====================================================

        if not has_setup_role(
            message.author
        ):
            return

        # =====================================================
        # حفظ نفس الروم الذي أرسل فيه الأمر
        # =====================================================

        set_idea_log_channel(

            message.guild.id,

            message.channel.id
        )

        try:

            await message.channel.send(

                "✅ **تم تحديد هذا الروم كلوق للمساهمات بنجاح!**\n\n"
                f"📥 روم المساهمات: {message.channel.mention}",

                allowed_mentions=
                discord.AllowedMentions.none()
            )

        except Exception as e:

            print(
                f"❌ خطأ أثناء تأكيد لوق المساهمات: {e}"
            )

    # =====================================================
    # استقبال الأمر بدون بادئة
    #
    # تحديد لوق المساهمات
    # =====================================================

    @commands.Cog.listener()
    async def on_message(
        self,
        message
    ):

        # =====================================================
        # تجاهل البوتات
        # =====================================================

        if message.author.bot:
            return

        content = message.content.strip()

        # =====================================================
        # الأمر الأساسي بدون أي بادئة
        # =====================================================

        normalized = (
            content
            .replace("ـ", "")
            .replace("  ", " ")
            .strip()
        )

        if normalized == "تحديد لوق المساهمات":

            await self.handle_set_idea_log(
                message
            )

            return

        # =====================================================
        # صيغة إضافية:
        #
        # تحديد-لوق-المساهمات
        #
        # أيضًا تجعل نفس الروم هو اللوق
        # =====================================================

        if normalized == "تحديد-لوق-المساهمات":

            await self.handle_set_idea_log(
                message
            )

            return

    # =====================================================
    # الأمر القديم مع تحديد الروم
    #
    # تحديد-لوق-المساهمات #الروم
    # =====================================================

    @commands.command(
        name="تحديد-لوق-المساهمات"
    )
    async def set_idea_log(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel = None
    ):

        if not has_setup_role(
            ctx.author
        ):

            return

        # =====================================================
        # إذا لم يتم تحديد روم
        #
        # نستخدم نفس الروم الحالي
        # =====================================================

        if channel is None:

            set_idea_log_channel(

                ctx.guild.id,

                ctx.channel.id
            )

            await ctx.send(

                "✅ **تم تحديد هذا الروم كلوق للمساهمات بنجاح!**\n\n"
                f"📥 روم المساهمات: {ctx.channel.mention}",

                allowed_mentions=
                discord.AllowedMentions.none()
            )

            return

        # =====================================================
        # إذا تم تحديد روم يدويًا
        # =====================================================

        set_idea_log_channel(

            ctx.guild.id,

            channel.id
        )

        await ctx.send(

            "✅ **تم تحديد لوق المساهمات بنجاح!**\n\n"
            f"📥 روم استقبال المساهمات: {channel.mention}",

            allowed_mentions=
            discord.AllowedMentions.none()
        )

    # =====================================================
    # عرض لوق المساهمات
    # =====================================================

    @commands.command(
        name="لوق-المساهمات"
    )
    async def show_idea_log(
        self,
        ctx
    ):

        if not has_setup_role(
            ctx.author
        ):

            return

        channel_id = get_idea_log_channel_id(
            ctx.guild.id
        )

        if not channel_id:

            await ctx.send(
                "⚠️ لم يتم تحديد لوق المساهمات لهذا السيرفر."
            )

            return

        channel = ctx.guild.get_channel(
            int(channel_id)
        )

        if channel is None:

            await ctx.send(
                "❌ الروم المحفوظ للمساهمات لم يعد موجودًا."
            )

            return

        await ctx.send(

            "📥 **لوق المساهمات الحالي:**\n"
            f"{channel.mention}",

            allowed_mentions=
            discord.AllowedMentions.none()
        )

    # =====================================================
    # أمر ساهم
    # =====================================================

    @commands.command(
        name="ساهم"
    )
    async def send_idea_message(
        self,
        ctx: commands.Context,
        *args
    ):

        # =====================================================
        # التأكد من السيرفر
        # =====================================================

        if ctx.guild is None:
            return

        # =====================================================
        # التأكد من وجود اللوق
        # =====================================================

        log_channel_id = get_idea_log_channel_id(
            ctx.guild.id
        )

        if not log_channel_id:

            await ctx.send(

                "❌ لم يتم تحديد **لوق المساهمات** لهذا السيرفر.\n"
                "يجب على الإدارة تحديده أولًا."
            )

            return

        # =====================================================
        # أكثر من منشن
        # =====================================================

        if len(ctx.message.mentions) > 1:

            await ctx.send(

                "❌ **طريقة الاستخدام خاطئة.**\n\n"

                "استخدم أحد الشكلين:\n\n"

                "📢 إرسال للجميع:\n"
                "`ساهم`\n\n"

                "🧪 إرسال لشخص واحد للتجربة:\n"
                "`ساهم @الشخص`"
            )

            return

        # =====================================================
        # كلام إضافي بدون منشن
        # =====================================================

        if (
            len(args) > 0
            and len(ctx.message.mentions) == 0
        ):

            await ctx.send(

                "❌ **طريقة الاستخدام خاطئة.**\n\n"

                "📢 لإرسال فعالية المساهمات للجميع:\n"
                "`ساهم`\n\n"

                "🧪 لإرسالها لشخص واحد للتجربة:\n"
                "`ساهم @الشخص`\n\n"

                "⚠️ لا تكتب أي نص إضافي بعد الأمر."
            )

            return

        # =====================================================
        # شخص واحد
        # =====================================================

        if len(ctx.message.mentions) == 1:

            member = ctx.message.mentions[0]

            if member.bot:

                await ctx.send(
                    "❌ لا يمكن إرسال فعالية المساهمات إلى بوت."
                )

                return

            success = await self.send_dm(
                member
            )

            if success:

                await ctx.send(

                    f"✅ تم إرسال رسالة **ساهم معنا بفعالية** "
                    f"إلى {member.mention}.",

                    allowed_mentions=
                    discord.AllowedMentions.none()
                )

            else:

                await ctx.send(

                    f"❌ تعذر إرسال الرسالة إلى "
                    f"{member.mention}.",

                    allowed_mentions=
                    discord.AllowedMentions.none()
                )

            return

        # =====================================================
        # إرسال للجميع
        # =====================================================

        embed = discord.Embed(

            title="📢 تأكيد إرسال فعالية المساهمات",

            description=(

                "هل أنت متأكد من إرسال رسالة:\n"
                "**«ساهم معنا بفعالية»**\n"
                "إلى جميع أعضاء السيرفر؟\n\n"

                "⚠️ سيتم تجاهل البوتات.\n"
                "⚠️ الأعضاء الذين أغلقوا الخاص لن تصلهم الرسالة.\n\n"

                "لن يتم الإرسال إلا بعد الضغط على "
                "**نعم، إرسال للجميع**."
            ),

            color=discord.Color.orange()
        )

        await ctx.send(

            embed=embed,

            view=BroadcastConfirmView(
                self,
                ctx.guild.id
            )
        )

    # =====================================================
    # إرسال DM لشخص
    # =====================================================

    async def send_dm(
        self,
        member: discord.Member
    ):

        if member.bot:
            return False

        embed = discord.Embed(

            title="ساهم معنا بفعالية",

            description=(

                "💡 **عندك فكرة؟ شاركنا فيها!**\n\n"

                "نرحب بأفكاركم واقتراحاتكم "
                "لتطوير السيرفر وإضافة فعاليات "
                "وتجارب جديدة.\n\n"

                "اضغط على الزر بالأسفل، "
                "واكتب لنا فكرتك وكيف تتوقع تطبيقها."
            ),

            color=discord.Color.blurple()
        )

        embed.add_field(

            name="📝 ماذا نحتاج منك؟",

            value=(

                "• اسم الفكرة\n"
                "• شرح الفكرة\n"
                "• طريقة تطبيقها"
            ),

            inline=False
        )

        embed.add_field(

            name="💜 ساهم معنا",

            value=(

                "فكرتك قد تكون الفعالية القادمة "
                "في السيرفر!"
            ),

            inline=False
        )

        embed.set_footer(
            text="ساهم معنا بفعالية"
        )

        try:

            await member.send(

                embed=embed,

                view=IdeaDMView()
            )

            return True

        except discord.Forbidden:

            return False

        except discord.HTTPException:

            return False

        except Exception as e:

            print(
                f"❌ خطأ DM مع {member}: {e}"
            )

            return False

    # =====================================================
    # إرسال للجميع
    # =====================================================

    async def broadcast_to_server(
        self,
        guild: discord.Guild
    ):

        members = [

            member

            for member in guild.members

            if not member.bot
        ]

        sent = 0

        failed = 0

        for member in members:

            success = await self.send_dm(
                member
            )

            if success:

                sent += 1

            else:

                failed += 1

            await asyncio.sleep(
                DM_DELAY
            )

        return sent, failed

    # =====================================================
    # إحصائيات المساهمات
    # =====================================================

    @commands.command(
        name="حالة-المساهمات"
    )
    async def ideas_status(
        self,
        ctx
    ):

        if not has_setup_role(
            ctx.author
        ):

            return

        guild_filter = {

            "guild_id": ctx.guild.id
        }

        pending = ideas_collection.count_documents({

            **guild_filter,

            "status": "pending"
        })

        accepted = ideas_collection.count_documents({

            **guild_filter,

            "status": "accepted"
        })

        rejected = ideas_collection.count_documents({

            **guild_filter,

            "status": "rejected"
        })

        needs_edit = ideas_collection.count_documents({

            **guild_filter,

            "status": "needs_edit"
        })

        total = ideas_collection.count_documents(
            guild_filter
        )

        embed = discord.Embed(

            title="📊 إحصائيات المساهمات",

            color=discord.Color.blurple()
        )

        embed.add_field(

            name="📚 إجمالي المساهمات",

            value=f"`{total}`",

            inline=True
        )

        embed.add_field(

            name="🟡 قيد المراجعة",

            value=f"`{pending}`",

            inline=True
        )

        embed.add_field(

            name="🟢 مقبولة",

            value=f"`{accepted}`",

            inline=True
        )

        embed.add_field(

            name="🔴 مرفوضة",

            value=f"`{rejected}`",

            inline=True
        )

        embed.add_field(

            name="🟠 تحتاج تعديل",

            value=f"`{needs_edit}`",

            inline=True
        )

        await ctx.send(
            embed=embed
        )


# =========================================================
# setup
# =========================================================

async def setup(bot):

    await bot.add_cog(
        IdeasCog(bot)
    )
