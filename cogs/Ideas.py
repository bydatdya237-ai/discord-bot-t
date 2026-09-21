import asyncio
import os
from datetime import datetime, timezone

import discord
from discord.ext import commands
from discord import ui

from pymongo import MongoClient


# =========================================================
# الإعدادات
# =========================================================

# الرتبة المسموح لها باستخدام أوامر المساهمات
ALLOWED_ROLE_ID = 1544078469657530578

# روم استقبال الأفكار
IDEA_CHANNEL_ID = 1550797517237518417

# قاعدة البيانات
MONGO_DB_NAME = "discord_bot_db"

# Collection خاصة بالمساهمات فقط
IDEA_COLLECTION_NAME = "idea_submissions"

# تأخير بسيط بين الـ DM والـ DM
# حتى لا يتم إرسال كمية ضخمة بنفس اللحظة
DM_DELAY = 0.7


# =========================================================
# MongoDB
# =========================================================

mongo_url = os.environ.get("MONGO_URI")

mongo_client = MongoClient(mongo_url)

db = mongo_client[MONGO_DB_NAME]

ideas_collection = db[IDEA_COLLECTION_NAME]


# =========================================================
# التحقق من الرتبة
# =========================================================

def has_allowed_role(member: discord.Member) -> bool:
    return any(
        role.id == ALLOWED_ROLE_ID
        for role in member.roles
    )


# =========================================================
# Modal إرسال الفكرة
# =========================================================

class IdeaModal(ui.Modal, title="ساهم معنا بفعالية"):

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
        placeholder="كيف يمكن تطبيق الفكرة داخل السيرفر؟",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=2000
    )

    async def on_submit(self, interaction: discord.Interaction):

        user = interaction.user

        # =====================================================
        # منع إرسال فكرة ثانية أثناء وجود فكرة قيد المراجعة
        # =====================================================

        existing = ideas_collection.find_one({
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
        # رقم الفكرة
        # =====================================================

        last_idea = ideas_collection.find_one(
            {},
            sort=[("idea_number", -1)]
        )

        if last_idea:
            idea_number = last_idea.get(
                "idea_number",
                0
            ) + 1
        else:
            idea_number = 1

        # =====================================================
        # العثور على السيرفر
        # =====================================================

        guild = None

        for g in interaction.client.guilds:

            if g.get_member(user.id):
                guild = g
                break

        if guild is None:

            await interaction.response.send_message(
                "❌ تعذر العثور على السيرفر.",
                ephemeral=True
            )

            return

        # =====================================================
        # روم الأفكار
        # =====================================================

        idea_channel = guild.get_channel(
            IDEA_CHANNEL_ID
        )

        if idea_channel is None:

            await interaction.response.send_message(
                "❌ تعذر العثور على روم استقبال الأفكار.",
                ephemeral=True
            )

            return

        # =====================================================
        # حفظ الفكرة
        # =====================================================

        idea_data = {

            "idea_number": idea_number,

            "user_id": user.id,

            "username": str(user),

            "guild_id": guild.id,

            "idea_name": str(self.idea_name),

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

            # حفظ رقم رسالة المراجعة
            ideas_collection.update_one(

                {
                    "_id": result.inserted_id
                },

                {
                    "$set": {
                        "review_message_id":
                            review_message.id
                    }
                }
            )

        except Exception as e:

            ideas_collection.delete_one({
                "_id": result.inserted_id
            })

            print(
                f"❌ خطأ أثناء إرسال الفكرة: {e}"
            )

            await interaction.response.send_message(
                "❌ حدث خطأ أثناء إرسال فكرتك.",
                ephemeral=True
            )

            return

        # =====================================================
        # الرد لصاحب الفكرة
        # =====================================================

        await interaction.response.send_message(

            f"✅ **تم إرسال مساهمتك بنجاح!**\n\n"
            f"💡 الفكرة: **{self.idea_name}**\n"
            f"📌 رقم المساهمة: `#{idea_number:03d}`\n\n"
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

    def __init__(self, idea):

        super().__init__()

        self.idea = idea

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        idea = self.idea

        # التأكد أن الفكرة ما زالت قيد المراجعة
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
        # تعديل رسالة الفكرة
        # =====================================================

        if interaction.message:

            old_embed = interaction.message.embeds[0]

            embed = old_embed.copy()

            embed.color = discord.Color.red()

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
        # إرسال سبب الرفض لصاحب الفكرة
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

    def __init__(self, idea):

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

            old_embed = interaction.message.embeds[0]

            embed = old_embed.copy()

            embed.color = discord.Color.orange()

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
            "🟠 تم إرسال طلب التعديل لصاحب الفكرة.",
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

        if not has_allowed_role(
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

        # =================================================
        # تحديث قاعدة البيانات
        # =================================================

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

        # =================================================
        # تعديل Embed
        # =================================================

        old_embed = interaction.message.embeds[0]

        embed = old_embed.copy()

        embed.color = discord.Color.green()

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

        # =================================================
        # DM لصاحب الفكرة
        # =================================================

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

        if not has_allowed_role(
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

        # فتح Modal سبب الرفض
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

        if not has_allowed_role(
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

        if not has_allowed_role(
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

        # =================================================
        # بدء الإرسال
        # =================================================

        sent, failed = await self.cog.broadcast_to_server(
            guild
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

        if not has_allowed_role(
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

        # زر الـ DM
        self.bot.add_view(
            IdeaDMView()
        )

        # أزرار مراجعة الأفكار
        self.bot.add_view(
            IdeaReviewView()
        )

    # =====================================================
    # أمر -ساهم
    # =====================================================

    @commands.command(
        name="ساهم"
    )
    async def send_idea_message(
        self,
        ctx: commands.Context,
        *args
    ):

        # =================================================
        # التحقق من الرتبة
        # =================================================

        if not has_allowed_role(
            ctx.author
        ):
            return

        # =================================================
        # أكثر من منشن
        # =================================================

        if len(ctx.message.mentions) > 1:

            await ctx.send(
                "❌ **طريقة الاستخدام خاطئة.**\n\n"

                "استخدم أحد الشكلين:\n\n"

                "📢 إرسال للجميع:\n"
                "`-ساهم`\n\n"

                "🧪 إرسال لشخص واحد للتجربة:\n"
                "`-ساهم @الشخص`"
            )

            return

        # =================================================
        # إذا كتب كلام بعد الأمر بدون منشن
        # =================================================

        if len(args) > 0 and len(
            ctx.message.mentions
        ) == 0:

            await ctx.send(
                "❌ **طريقة الاستخدام خاطئة.**\n\n"

                "📢 لإرسال فعالية المساهمات للجميع:\n"
                "`-ساهم`\n\n"

                "🧪 لإرسالها لشخص واحد للتجربة:\n"
                "`-ساهم @الشخص`\n\n"

                "⚠️ لا تكتب أي نص إضافي بعد الأمر."
            )

            return

        # =================================================
        # شخص واحد
        # =================================================

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

        # =================================================
        # -ساهم لوحده
        # =================================================

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

            # تأخير بين الرسائل
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

        if not has_allowed_role(
            ctx.author
        ):
            return

        pending = ideas_collection.count_documents({
            "status": "pending"
        })

        accepted = ideas_collection.count_documents({
            "status": "accepted"
        })

        rejected = ideas_collection.count_documents({
            "status": "rejected"
        })

        needs_edit = ideas_collection.count_documents({
            "status": "needs_edit"
        })

        total = ideas_collection.count_documents({})

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
