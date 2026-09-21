import asyncio
from datetime import datetime, timezone

import discord
from discord.ext import commands
from discord import ui

from pymongo import MongoClient
import os


# =========================================================
# الإعدادات
# =========================================================

# الرتبة المسموح لها باستخدام أوامر الإرسال
ALLOWED_ROLE_ID = 1544078469657530578

# روم استقبال الأفكار والمساهمات
IDEA_CHANNEL_ID = 1550797517237518417

# اسم قاعدة البيانات
MONGO_DB_NAME = "discord_bot_db"

# اسم مجموعة الأفكار
IDEA_COLLECTION_NAME = "idea_submissions"

# تأخير بسيط بين رسائل الـ DM حتى لا يتم إرسالها بسرعة كبيرة
DM_DELAY = 0.7


# =========================================================
# MongoDB
# =========================================================

mongo_url = os.environ.get("MONGO_URI")

mongo_client = MongoClient(mongo_url)
db = mongo_client[MONGO_DB_NAME]
ideas_collection = db[IDEA_COLLECTION_NAME]


# =========================================================
# دالة التحقق من الرتبة
# =========================================================

def has_allowed_role(member: discord.Member) -> bool:
    return any(role.id == ALLOWED_ROLE_ID for role in member.roles)


# =========================================================
# Modal إرسال الفكرة
# =========================================================

class IdeaModal(ui.Modal, title="ساهم معنا بفعالية"):

    idea_name = ui.TextInput(
        label="اسم الفكرة",
        placeholder="اكتب اسم الفكرة هنا...",
        style=discord.TextStyle.short,
        required=True,
        max_length=100
    )

    idea_description = ui.TextInput(
        label="شرح الفكرة",
        placeholder="اشرح لنا فكرتك بالتفصيل...",
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

        # البحث عن فكرة معلقة مسبقًا لنفس الشخص
        existing = ideas_collection.find_one({
            "user_id": user.id,
            "status": "pending"
        })

        if existing:
            await interaction.response.send_message(
                "⚠️ لديك فكرة قيد المراجعة بالفعل، انتظر حتى يتم مراجعتها من الإدارة.",
                ephemeral=True
            )
            return

        # إنشاء رقم للفكرة
        last_idea = ideas_collection.find_one(
            {},
            sort=[("idea_number", -1)]
        )

        if last_idea:
            idea_number = last_idea.get("idea_number", 0) + 1
        else:
            idea_number = 1

        # البحث عن السيرفر
        guild = None

        for g in interaction.client.guilds:
            member = g.get_member(user.id)

            if member:
                guild = g
                break

        if guild is None:
            await interaction.response.send_message(
                "❌ تعذر العثور على السيرفر.",
                ephemeral=True
            )
            return

        idea_channel = guild.get_channel(IDEA_CHANNEL_ID)

        if idea_channel is None:
            await interaction.response.send_message(
                "❌ تعذر العثور على روم استقبال الأفكار.",
                ephemeral=True
            )
            return

        # تسجيل الفكرة في MongoDB
        idea_data = {
            "idea_number": idea_number,
            "user_id": user.id,
            "username": str(user),
            "guild_id": guild.id,
            "idea_name": str(self.idea_name),
            "description": str(self.idea_description),
            "implementation": str(self.implementation),
            "status": "pending",
            "created_at": datetime.now(timezone.utc)
        }

        result = ideas_collection.insert_one(idea_data)

        # =====================================================
        # Embed الفكرة في روم الأفكار
        # =====================================================

        embed = discord.Embed(
            title="💡 مساهمة جديدة",
            description=(
                f"**رقم المساهمة:** `#{idea_number:03d}`\n"
                f"**صاحب الفكرة:** {user.mention}\n\n"
                f"### 📝 اسم الفكرة\n"
                f"{self.idea_name}\n\n"
                f"### 📖 شرح الفكرة\n"
                f"{self.idea_description}\n\n"
                f"### 🛠️ طريقة التطبيق\n"
                f"{self.implementation}"
            ),
            color=discord.Color.blurple(),
            timestamp=datetime.now(timezone.utc)
        )

        embed.set_footer(
            text="حالة المساهمة: قيد المراجعة"
        )

        review_view = IdeaReviewView(
            idea_id=str(result.inserted_id)
        )

        try:
            review_message = await idea_channel.send(
                embed=embed,
                view=review_view,
                allowed_mentions=discord.AllowedMentions.none()
            )

            # حفظ رسالة المراجعة
            ideas_collection.update_one(
                {"_id": result.inserted_id},
                {
                    "$set": {
                        "review_message_id": review_message.id
                    }
                }
            )

        except Exception as e:

            ideas_collection.delete_one({
                "_id": result.inserted_id
            })

            print(f"❌ خطأ أثناء إرسال الفكرة للروم: {e}")

            await interaction.response.send_message(
                "❌ حدث خطأ أثناء إرسال فكرتك، حاول مرة أخرى.",
                ephemeral=True
            )
            return

        # الرد للشخص
        await interaction.response.send_message(
            f"✅ **تم إرسال مساهمتك بنجاح!**\n\n"
            f"رقم المساهمة: `#{idea_number:03d}`\n"
            f"سيتم مراجعتها من الإدارة.",
            ephemeral=True
        )


# =========================================================
# زر فتح نموذج الفكرة
# =========================================================

class IdeaDMView(ui.View):

    def __init__(self):
        super().__init__(timeout=None)

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
# View مراجعة الأفكار
# =========================================================

class IdeaReviewView(ui.View):

    def __init__(self, idea_id=None, disabled=False):
        super().__init__(timeout=None)

        self.idea_id = idea_id

        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = disabled

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

        if not has_allowed_role(interaction.user):
            await interaction.response.send_message(
                "❌ ليس لديك صلاحية استخدام هذا الزر.",
                ephemeral=True
            )
            return

        idea = ideas_collection.find_one({
            "review_message_id": interaction.message.id
        })

        if not idea:
            await interaction.response.send_message(
                "❌ لم يتم العثور على بيانات هذه المساهمة.",
                ephemeral=True
            )
            return

        if idea.get("status") != "pending":
            await interaction.response.send_message(
                "⚠️ تمت معالجة هذه المساهمة مسبقًا.",
                ephemeral=True
            )
            return

        ideas_collection.update_one(
            {"_id": idea["_id"]},
            {
                "$set": {
                    "status": "accepted",
                    "reviewed_by": interaction.user.id,
                    "reviewed_at": datetime.now(timezone.utc)
                }
            }
        )

        # تعديل الرسالة
        old_embed = interaction.message.embeds[0]

        embed = old_embed.copy()

        embed.color = discord.Color.green()
        embed.set_footer(
            text=f"حالة المساهمة: مقبولة • بواسطة {interaction.user}"
        )

        await interaction.message.edit(
            embed=embed,
            view=IdeaReviewView(disabled=True)
        )

        # إرسال DM لصاحب الفكرة
        try:

            user = await interaction.client.fetch_user(
                idea["user_id"]
            )

            dm_embed = discord.Embed(
                title="🎉 تم قبول مساهمتك!",
                description=(
                    f"تم قبول فكرتك **{idea['idea_name']}** "
                    f"بنجاح.\n\n"
                    f"📌 رقم المساهمة: `#{idea['idea_number']:03d}`\n\n"
                    f"الرجاء التوجه إلى **التكت** "
                    f"للتواصل مع الإدارة واستكمال التفاصيل."
                ),
                color=discord.Color.green()
            )

            await user.send(embed=dm_embed)

        except Exception as e:
            print(f"⚠️ تعذر إرسال رسالة القبول لصاحب الفكرة: {e}")

        await interaction.response.send_message(
            "✅ تم قبول المساهمة وإبلاغ صاحبها.",
            ephemeral=True
        )

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

        if not has_allowed_role(interaction.user):
            await interaction.response.send_message(
                "❌ ليس لديك صلاحية استخدام هذا الزر.",
                ephemeral=True
            )
            return

        idea = ideas_collection.find_one({
            "review_message_id": interaction.message.id
        })

        if not idea:
            await interaction.response.send_message(
                "❌ لم يتم العثور على بيانات هذه المساهمة.",
                ephemeral=True
            )
            return

        if idea.get("status") != "pending":
            await interaction.response.send_message(
                "⚠️ تمت معالجة هذه المساهمة مسبقًا.",
                ephemeral=True
            )
            return

        ideas_collection.update_one(
            {"_id": idea["_id"]},
            {
                "$set": {
                    "status": "rejected",
                    "reviewed_by": interaction.user.id,
                    "reviewed_at": datetime.now(timezone.utc)
                }
            }
        )

        old_embed = interaction.message.embeds[0]

        embed = old_embed.copy()

        embed.color = discord.Color.red()
        embed.set_footer(
            text=f"حالة المساهمة: مرفوضة • بواسطة {interaction.user}"
        )

        await interaction.message.edit(
            embed=embed,
            view=IdeaReviewView(disabled=True)
        )

        # إبلاغ صاحب الفكرة
        try:

            user = await interaction.client.fetch_user(
                idea["user_id"]
            )

            dm_embed = discord.Embed(
                title="📩 تحديث على مساهمتك",
                description=(
                    f"تمت مراجعة فكرتك **{idea['idea_name']}**.\n\n"
                    f"حالة المساهمة: ❌ **مرفوضة**\n\n"
                    f"رقم المساهمة: `#{idea['idea_number']:03d}`"
                ),
                color=discord.Color.red()
            )

            await user.send(embed=dm_embed)

        except Exception as e:
            print(f"⚠️ تعذر إرسال رسالة الرفض: {e}")

        await interaction.response.send_message(
            "❌ تم رفض المساهمة وإبلاغ صاحبها.",
            ephemeral=True
        )


# =========================================================
# Cog
# =========================================================

class IdeasCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):

        # يجعل زر "ساهم بفكرتك" يعمل حتى بعد إعادة تشغيل البوت
        self.bot.add_view(
            IdeaDMView()
        )

        # يجعل أزرار قبول/رفض الأفكار تعمل بعد إعادة التشغيل
        self.bot.add_view(
            IdeaReviewView()
        )

    # =====================================================
    # إرسال لشخص محدد - اختبار
    # =====================================================

    @commands.command(name="ساهم")
    async def send_idea_message(
        self,
        ctx: commands.Context,
        member: discord.Member = None
    ):

        # التحقق من الرتبة
        if not has_allowed_role(ctx.author):
            return

        # =================================================
        # إذا لم يتم تحديد شخص
        # يرسل للجميع
        # =================================================

        if member is None:

            # رسالة تأكيد قبل الإرسال للجميع
            confirm_view = BroadcastConfirmView(
                self,
                ctx.guild.id
            )

            embed = discord.Embed(
                title="📢 إرسال فعالية المساهمات",
                description=(
                    "هل أنت متأكد من إرسال رسالة **ساهم معنا بفعالية** "
                    "إلى جميع أعضاء السيرفر؟\n\n"
                    "⚠️ سيتم تجاهل البوتات والأعضاء الذين لا يمكن استقبال "
                    "رسائل خاصة منهم."
                ),
                color=discord.Color.orange()
            )

            await ctx.send(
                embed=embed,
                view=confirm_view
            )

            return

        # =================================================
        # إرسال لشخص واحد للاختبار
        # =================================================

        success = await self.send_dm(member)

        if success:

            await ctx.send(
                f"✅ تم إرسال رسالة **ساهم معنا بفعالية** إلى {member.mention}.",
                allowed_mentions=discord.AllowedMentions.none()
            )

        else:

            await ctx.send(
                f"❌ لم أتمكن من إرسال الرسالة إلى {member.mention}.",
                allowed_mentions=discord.AllowedMentions.none()
            )

    # =====================================================
    # إرسال DM
    # =====================================================

    async def send_dm(self, member: discord.Member):

        if member.bot:
            return False

        embed = discord.Embed(
            title="ساهم معنا بفعالية",
            description=(
                "💡 **عندك فكرة؟ شاركنا فيها!**\n\n"
                "نرحب بأفكاركم واقتراحاتكم لتطوير السيرفر "
                "وإضافة فعاليات وتجارب جديدة.\n\n"
                "اضغط على الزر بالأسفل، واكتب لنا فكرتك "
                "وكيف تتوقع تطبيقها."
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

        embed.set_footer(
            text="ساهم معنا • فكرتك قد تصبح فعالية داخل السيرفر!"
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
            print(f"❌ خطأ DM مع {member}: {e}")
            return False

    # =====================================================
    # إرسال للجميع
    # =====================================================

    async def broadcast_to_server(self, guild: discord.Guild):

        members = [
            member
            for member in guild.members
            if not member.bot
        ]

        sent = 0
        failed = 0

        for member in members:

            success = await self.send_dm(member)

            if success:
                sent += 1
            else:
                failed += 1

            await asyncio.sleep(DM_DELAY)

        return sent, failed


# =========================================================
# تأكيد الإرسال للجميع
# =========================================================

class BroadcastConfirmView(ui.View):

    def __init__(self, cog, guild_id):
        super().__init__(timeout=60)

        self.cog = cog
        self.guild_id = guild_id

    @ui.button(
        label="إرسال للجميع",
        style=discord.ButtonStyle.success,
        emoji="📢"
    )
    async def confirm(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not has_allowed_role(interaction.user):
            await interaction.response.send_message(
                "❌ ليس لديك صلاحية استخدام هذا الأمر.",
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

        await interaction.response.edit_message(
            content="⏳ جاري إرسال رسالة **ساهم معنا بفعالية** للأعضاء...",
            embed=None,
            view=None
        )

        sent, failed = await self.cog.broadcast_to_server(
            guild
        )

        await interaction.edit_original_response(
            content=(
                "✅ **انتهى الإرسال!**\n\n"
                f"📨 تم الإرسال بنجاح: `{sent}`\n"
                f"⚠️ تعذر الإرسال: `{failed}`"
            )
        )

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

        if not has_allowed_role(interaction.user):
            await interaction.response.send_message(
                "❌ ليس لديك صلاحية استخدام هذا الزر.",
                ephemeral=True
            )
            return

        await interaction.response.edit_message(
            content="🛑 تم إلغاء إرسال الرسالة.",
            embed=None,
            view=None
        )


# =========================================================
# setup
# =========================================================

async def setup(bot):
    await bot.add_cog(
        IdeasCog(bot)
    )
