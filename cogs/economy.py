import os
import re
import uuid
import discord
from discord.ext import commands
from discord import ui
from motor.motor_asyncio import AsyncIOMotorClient


# =========================================================
# الإعدادات
# =========================================================

# الروم المسموح فيه أوامر الاقتصاد
ECONOMY_ROOM_ID = 1544334212734124174

# الروم المسموح فيه أمر الشعار
BANNER_ROOM_ID = 1547711993568305232

# الرتبة الإدارية المسموح لها بالأوامر الإدارية
ADMIN_ROLE_ID = 1544078469657530578


# =========================================================
# تحويل المبالغ
# =========================================================

def parse_amount(amount_str: str) -> int:
    if not amount_str:
        return 0

    amount_str = amount_str.lower().strip()

    # الكلمات العربية
    amount_str = (
        amount_str
        .replace("ألف", "k")
        .replace("الف", "k")
        .replace("مليون", "m")
        .replace("مليار", "b")
    )

    # إزالة المسافات
    amount_str = amount_str.replace(" ", "")

    multiplier = 1

    if "b" in amount_str:
        multiplier = 1_000_000_000
        amount_str = amount_str.replace("b", "")

    elif "m" in amount_str:
        multiplier = 1_000_000
        amount_str = amount_str.replace("m", "")

    elif "k" in amount_str:
        multiplier = 1_000
        amount_str = amount_str.replace("k", "")

    numbers = re.findall(r"\d+\.?\d*", amount_str)

    if not numbers:
        return 0

    try:
        return int(float(numbers[0]) * multiplier)
    except Exception:
        return 0


# =========================================================
# تنسيق العملة
# =========================================================

def format_coins(amount: int) -> str:
    if amount >= 1_000_000_000:
        return f"{amount / 1_000_000_000:.2f}b".replace(".00", "")

    elif amount >= 1_000_000:
        return f"{amount / 1_000_000:.2f}m".replace(".00", "")

    elif amount >= 1_000:
        return f"{amount / 1_000:.1f}k".replace(".0", "")

    return str(amount)


# =========================================================
# نظام الاقتصاد
# =========================================================

class EconomyCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

        mongo_uri = os.environ.get("MONGO_URI")

        if mongo_uri:
            self.db_client = AsyncIOMotorClient(mongo_uri)
            self.db = self.db_client.discord_bot_db

            self.balances = self.db.economy_balances
            self.rewards = self.db.economy_rewards

        else:
            self.db_client = None
            self.db = None
            self.balances = None
            self.rewards = None

    # =====================================================
    # التحقق من الروم
    # =====================================================

    def economy_room(self, ctx):
        return ctx.channel.id == ECONOMY_ROOM_ID

    def banner_room(self, ctx):
        return ctx.channel.id == BANNER_ROOM_ID

    # =====================================================
    # التحقق من الرتبة الإدارية
    # =====================================================

    def has_admin_role(self, member: discord.Member):
        return any(role.id == ADMIN_ROLE_ID for role in member.roles)

    # =====================================================
    # الرصيد
    # =====================================================

    async def get_balance(self, user_id: int) -> int:

        if self.balances is None:
            return 0

        user_data = await self.balances.find_one({
            "user_id": user_id
        })

        return user_data.get("balance", 0) if user_data else 0

    # =====================================================
    # تعديل الرصيد
    # =====================================================

    async def update_balance(self, user_id: int, amount: int):

        if self.balances is None:
            return

        await self.balances.update_one(
            {"user_id": user_id},
            {"$inc": {"balance": amount}},
            upsert=True
        )

    # =====================================================
    # أمر الشرح
    # =====================================================

    @commands.command(name="شرح")
    async def help_economy(self, ctx):

        if not self.economy_room(ctx):
            return

        embed = discord.Embed(
            title="📖 شرح أوامر نظام Ai",
            description=(
                "هذه الأوامر المتاحة لك في نظام الاقتصاد:\n\n"
                "💰 **-رصيد**\n"
                "عرض رصيدك الحالي من عملة Ai.\n\n"

                "🏆 **-توب**\n"
                "عرض أعلى 10 أعضاء من ناحية رصيد Ai.\n\n"

                "🎁 **-اعطي**\n"
                "هذا الأمر مخصص للإدارة لإعطاء Ai للأعضاء.\n\n"

                "💸 **-سحب**\n"
                "هذا الأمر مخصص للإدارة لسحب Ai من الأعضاء.\n\n"

                "💰 **-توزيع**\n"
                "هذا الأمر مخصص للإدارة لتوزيع Ai على أعضاء السيرفر."
            ),
            color=discord.Color.gold()
        )

        embed.set_footer(text="عملة السيرفر: Ai")

        await ctx.send(embed=embed)

    # =====================================================
    # أمر الرصيد
    # =====================================================

    @commands.command(name="رصيد")
    async def balance_cmd(
        self,
        ctx,
        member: discord.Member = None
    ):

        if not self.economy_room(ctx):
            return

        target = member or ctx.author

        bal = await self.get_balance(target.id)

        embed = discord.Embed(
            title="💰 رصيد Ai",
            description=(
                f"رصيد {target.mention} الحالي:\n\n"
                f"**{format_coins(bal)} Ai**"
            ),
            color=discord.Color.gold()
        )

        await ctx.send(embed=embed)

    # =====================================================
    # أمر التوب
    # =====================================================

    @commands.command(name="توب")
    async def top_cmd(self, ctx):

        if not self.economy_room(ctx):
            return

        if self.balances is None:
            await ctx.send("❌ قاعدة البيانات غير متصلة.")
            return

        cursor = (
            self.balances
            .find()
            .sort("balance", -1)
            .limit(10)
        )

        top_users = await cursor.to_list(length=10)

        if not top_users:
            await ctx.send(
                "📭 لا توجد بيانات مسجلة في التوب حتى الآن."
            )
            return

        description_lines = []

        medals = [
            "🥇 #1",
            "🥈 #2",
            "🥉 #3",
            "🔹 #4",
            "🔹 #5",
            "🔹 #6",
            "🔹 #7",
            "🔹 #8",
            "🔹 #9",
            "🔹 #10"
        ]

        for idx, doc in enumerate(top_users):

            user_id = doc.get("user_id")
            bal = doc.get("balance", 0)

            member = ctx.guild.get_member(user_id)

            if member:
                name = member.mention
            else:
                name = f"<@{user_id}> (مغادر)"

            description_lines.append(
                f"{medals[idx]} {name} — "
                f"**{format_coins(bal)} Ai**"
            )

        embed = discord.Embed(
            title="🏆 قائمة التوب",
            description="\n".join(description_lines),
            color=discord.Color.gold()
        )

        await ctx.send(embed=embed)

    # =====================================================
    # أمر الإعطاء
    # =====================================================

    @commands.command(name="اعطي")
    async def give_cmd(
        self,
        ctx,
        member: discord.Member,
        *,
        amount_str: str
    ):

        if not self.economy_room(ctx):
            return

        if not self.has_admin_role(ctx.author):
            return

        amount = parse_amount(amount_str)

        if amount <= 0:
            await ctx.send(
                "⚠️ الصيغة خاطئة.\n"
                "مثال:\n"
                "`-اعطي @الشخص 25k`\n"
                "`-اعطي @الشخص 5000`"
            )
            return

        await self.update_balance(member.id, amount)

        await ctx.send(
            f"✅ تم إضافة **{format_coins(amount)} Ai** "
            f"إلى رصيد {member.mention}"
        )

    # =====================================================
    # أمر السحب
    # =====================================================

    @commands.command(name="سحب")
    async def withdraw_cmd(
        self,
        ctx,
        member: discord.Member,
        *,
        amount_str: str
    ):

        if not self.economy_room(ctx):
            return

        if not self.has_admin_role(ctx.author):
            return

        amount = parse_amount(amount_str)

        if amount <= 0:
            await ctx.send(
                "⚠️ الصيغة خاطئة.\n"
                "مثال:\n"
                "`-سحب @الشخص 25k`\n"
                "`-سحب @الشخص 10 ألف`"
            )
            return

        current_bal = await self.get_balance(member.id)

        if current_bal <= 0:
            await ctx.send(
                f"❌ {member.mention} لا يملك أي Ai."
            )
            return

        final_amount = min(amount, current_bal)

        await self.update_balance(
            member.id,
            -final_amount
        )

        await ctx.send(
            f"✅ تم سحب **{format_coins(final_amount)} Ai** "
            f"من رصيد {member.mention}"
        )

    # =====================================================
    # أمر التوزيع
    # =====================================================

    @commands.command(name="توزيع")
    async def distribute_cmd(
        self,
        ctx,
        *,
        amount_str: str
    ):

        if not self.economy_room(ctx):
            return

        if not self.has_admin_role(ctx.author):
            return

        amount = parse_amount(amount_str)

        if amount <= 0:
            await ctx.send(
                "⚠️ يرجى تحديد مبلغ صحيح.\n"
                "مثال: `-توزيع 10k`"
            )
            return

        msg = await ctx.send(
            "⏳ جاري توزيع Ai على أعضاء السيرفر..."
        )

        count = 0

        for member in ctx.guild.members:

            if member.bot:
                continue

            await self.update_balance(
                member.id,
                amount
            )

            count += 1

        await msg.edit(
            content=(
                f"✅ تم توزيع **{format_coins(amount)} Ai** "
                f"بنجاح على **{count}** عضو!"
            )
        )

    # =====================================================
    # أمر الشعار
    # =====================================================

    @commands.command(name="شعار")
    async def banner_cmd(self, ctx):

        if not self.banner_room(ctx):
            return

        if not self.has_admin_role(ctx.author):
            return

        embed = discord.Embed(
            title="🎯 نظام إرسال الشعارات والمكافآت",
            description=(
                "اضغط على الزر أدناه لإكمال التسليم.\n\n"
                "سيتم طلب أيدي العضو وسبب الشعار، "
                "ثم إرسال المكافأة له في الخاص."
            ),
            color=discord.Color.blue()
        )

        view = BannerMainView()

        await ctx.send(
            embed=embed,
            view=view
        )

        try:
            await ctx.message.delete()
        except Exception:
            pass


# =========================================================
# لوحة الشعار
# =========================================================

class BannerMainView(ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(
        label="إكمال التسليم",
        style=discord.ButtonStyle.green,
        emoji="📋",
        custom_id="banner_start_delivery"
    )
    async def start_delivery(
        self,
        interaction: discord.Interaction,
        button: ui.Button
    ):

        # التأكد من الرتبة
        member = interaction.guild.get_member(
            interaction.user.id
        )

        if not member:
            return

        if not any(
            role.id == ADMIN_ROLE_ID
            for role in member.roles
        ):
            await interaction.response.send_message(
                "❌ ليس لديك صلاحية استخدام هذا النظام.",
                ephemeral=True
            )
            return

        modal = BannerModal()

        await interaction.response.send_modal(modal)


# =========================================================
# نافذة تفاصيل الشعار
# =========================================================

class BannerModal(ui.Modal, title="تفاصيل تسليم الشعار"):

    def __init__(self):
        super().__init__()

        self.user_id_input = ui.TextInput(
            label="أيدي العضو",
            placeholder="اكتب أيدي العضو هنا...",
            required=True,
            max_length=30
        )

        self.reason_input = ui.TextInput(
            label="سبب الشعار / التفاصيل",
            style=discord.TextStyle.paragraph,
            placeholder="اكتب سبب أو تفاصيل الشعار هنا...",
            required=True,
            max_length=1000
        )

        self.add_item(self.user_id_input)
        self.add_item(self.reason_input)

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        # التأكد من الرتبة مرة ثانية
        member = interaction.guild.get_member(
            interaction.user.id
        )

        if not member:
            return

        if not any(
            role.id == ADMIN_ROLE_ID
            for role in member.roles
        ):
            await interaction.response.send_message(
                "❌ ليس لديك صلاحية استخدام هذا النظام.",
                ephemeral=True
            )
            return

        raw_id = self.user_id_input.value.strip()

        if not raw_id.isdigit():
            await interaction.response.send_message(
                "❌ الأيدي غير صحيح. اكتب أرقام فقط.",
                ephemeral=True
            )
            return

        target_id = int(raw_id)

        target_member = interaction.guild.get_member(
            target_id
        )

        if not target_member:
            await interaction.response.send_message(
                "❌ لم يتم العثور على هذا العضو داخل السيرفر.",
                ephemeral=True
            )
            return

        reason = self.reason_input.value

        # مبلغ المكافأة
        reward_amount = 5000

        # ID فريد للمكافأة
        reward_id = str(uuid.uuid4())

        # حفظ المكافأة في MongoDB
        mongo_uri = os.environ.get("MONGO_URI")

        if not mongo_uri:
            await interaction.response.send_message(
                "❌ قاعدة البيانات غير متصلة.",
                ephemeral=True
            )
            return

        client = AsyncIOMotorClient(mongo_uri)
        db = client.discord_bot_db
        rewards = db.economy_rewards

        await rewards.insert_one({
            "reward_id": reward_id,
            "user_id": target_member.id,
            "amount": reward_amount,
            "reason": reason,
            "claimed": False,
            "created_by": interaction.user.id,
            "guild_id": interaction.guild.id
        })

        # رسالة الخاص
        dm_embed = discord.Embed(
            title="🎁 لديك شعار ومكافأة جديدة!",
            description=(
                f"**السبب / التفاصيل:**\n"
                f"{reason}\n\n"
                f"💰 قيمة المكافأة: "
                f"**{format_coins(reward_amount)} Ai**"
            ),
            color=discord.Color.gold()
        )

        dm_embed.set_footer(
            text=f"بواسطة الإدارة في سيرفر: {interaction.guild.name}"
        )

        view = ClaimRewardView(reward_id)

        try:

            await target_member.send(
                embed=dm_embed,
                view=view
            )

            await interaction.response.send_message(
                f"✅ تم إرسال الشعار والمكافأة إلى "
                f"{target_member.mention} في الخاص.",
                ephemeral=True
            )

        except Exception:

            # إذا فشل إرسال الخاص نحذف المكافأة المحفوظة
            await rewards.delete_one({
                "reward_id": reward_id
            })

            await interaction.response.send_message(
                "⚠️ تعذر إرسال رسالة خاصة للعضو. "
                "تأكد أن الخاص مفتوح لديه.",
                ephemeral=True
            )

        finally:
            client.close()


# =========================================================
# زر استلام المكافأة
# =========================================================

class ClaimRewardView(ui.View):

    def __init__(self, reward_id: str):
        super().__init__(timeout=None)

        self.reward_id = reward_id

        button = ui.Button(
            label="إستلام المكافأة",
            style=discord.ButtonStyle.blurple,
            emoji="💰",
            custom_id=f"claim_reward:{reward_id}"
        )

        self.add_item(button)


# =========================================================
# التعامل مع زر الاستلام
# =========================================================

class RewardInteractionCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

        mongo_uri = os.environ.get("MONGO_URI")

        if mongo_uri:
            self.db_client = AsyncIOMotorClient(mongo_uri)
            self.db = self.db_client.discord_bot_db
            self.balances = self.db.economy_balances
            self.rewards = self.db.economy_rewards
        else:
            self.db_client = None
            self.db = None
            self.balances = None
            self.rewards = None

    @commands.Cog.listener()
    async def on_interaction(
        self,
        interaction: discord.Interaction
    ):

        if interaction.type != discord.InteractionType.component:
            return

        custom_id = interaction.data.get("custom_id")

        if not custom_id:
            return

        if not custom_id.startswith("claim_reward:"):
            return

        if self.rewards is None:
            await interaction.response.send_message(
                "❌ قاعدة البيانات غير متصلة.",
                ephemeral=True
            )
            return

        reward_id = custom_id.split(
            "claim_reward:",
            1
        )[1]

        # محاولة استلام المكافأة بشكل ذري
        reward = await self.rewards.find_one_and_update(
            {
                "reward_id": reward_id,
                "user_id": interaction.user.id,
                "claimed": False
            },
            {
                "$set": {
                    "claimed": True,
                    "claimed_at": discord.utils.utcnow()
                }
            },
            return_document=True
        )

        # لا توجد مكافأة قابلة للاستلام
        if not reward:

            await interaction.response.send_message(
                "❌ هذه المكافأة تم استلامها مسبقاً "
                "أو أنها ليست مخصصة لك.",
                ephemeral=True
            )

            return

        reward_amount = reward["amount"]

        # إضافة Ai إلى الرصيد
        await self.balances.update_one(
            {"user_id": interaction.user.id},
            {
                "$inc": {
                    "balance": reward_amount
                }
            },
            upsert=True
        )

        # تعطيل الزر
        view = discord.ui.View(timeout=None)

        disabled_button = discord.ui.Button(
            label="تم الاستلام بنجاح",
            style=discord.ButtonStyle.green,
            emoji="✅",
            custom_id=f"claimed_reward:{reward_id}",
            disabled=True
        )

        view.add_item(disabled_button)

        # تحديث رسالة المكافأة
        await interaction.response.edit_message(
            view=view
        )

        # رسالة خاصة للمستلم
        await interaction.followup.send(
            f"🎉 مبروك! تمت إضافة "
            f"**{format_coins(reward_amount)} Ai** "
            f"إلى رصيدك.",
            ephemeral=True
        )


# =========================================================
# تشغيل الـ Cogs
# =========================================================

async def setup(bot):
    await bot.add_cog(EconomyCog(bot))
    await bot.add_cog(RewardInteractionCog(bot))
