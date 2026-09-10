import os
import re
import uuid
import random
import asyncio

from datetime import timedelta

import discord
from discord.ext import commands
from discord import ui

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ReturnDocument


# =========================================================
# الإعدادات
# =========================================================

# روم أوامر العملة
ECONOMY_ROOM_ID = 1544334212734124174

# روم التحكم + الشعار
CONTROL_ROOM_ID = 1547711993568305232

# روم الشعار
BANNER_ROOM_ID = 1547711993568305232


# =========================================================
# الرتب المسموح لها باستخدام أوامر الإدارة
# =========================================================

ALLOWED_ROLE_IDS = {
    1544078469657530578,
    1544426415766896690,
    1545851911121666108
}


# =========================================================
# إعدادات المكافأة اليومية
# =========================================================

REWARD_MIN = 3000
REWARD_MAX = 4000
REWARD_COOLDOWN_HOURS = 10


# =========================================================
# إعدادات حماية -سحب
# =========================================================

# منع تكرار -سحب بسرعة
WITHDRAW_COOLDOWN_SECONDS = 2


# =========================================================
# أدوات المبالغ
# =========================================================

def parse_amount(amount_str: str):

    if not amount_str:
        return 0

    amount_str = amount_str.lower().strip()

    amount_str = (
        amount_str
        .replace("ألف", "k")
        .replace("الف", "k")
        .replace("مليون", "m")
        .replace("مليار", "b")
    )

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

    numbers = re.findall(
        r"\d+\.?\d*",
        amount_str
    )

    if not numbers:
        return 0

    try:
        return int(
            float(numbers[0]) * multiplier
        )

    except Exception:
        return 0


def format_coins(amount: int):

    if amount >= 1_000_000_000:

        return f"{amount / 1_000_000_000:.2f}b".replace(
            ".00",
            ""
        )

    elif amount >= 1_000_000:

        return f"{amount / 1_000_000:.2f}m".replace(
            ".00",
            ""
        )

    elif amount >= 1_000:

        return f"{amount / 1_000:.1f}k".replace(
            ".0",
            ""
        )

    return str(amount)


# =========================================================
# Modal الشعار
# =========================================================

class BannerModal(
    ui.Modal,
    title="🎁 تسليم شعار ومكافأة"
):

    amount_input = ui.TextInput(
        label="💰 مبلغ المكافأة",
        placeholder="مثال: 25k أو 50000",
        required=True,
        max_length=30
    )

    reason_input = ui.TextInput(
        label="📝 سبب المكافأة",
        placeholder="اكتب سبب المكافأة هنا...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000
    )

    def __init__(
        self,
        cog,
        target_member
    ):

        super().__init__()

        self.cog = cog
        self.target_member = target_member

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        member = interaction.guild.get_member(
            interaction.user.id
        )

        if not member:
            return

        if not self.cog.has_admin_role(member):
            return

        amount = parse_amount(
            self.amount_input.value
        )

        if amount <= 0:

            await interaction.response.send_message(
                "❌ المبلغ غير صحيح.\n\n"
                "مثال:\n"
                "`25k`\n"
                "`50000`\n"
                "`2 مليون`",
                ephemeral=True
            )

            return

        reason = self.reason_input.value.strip()

        if not reason:

            await interaction.response.send_message(
                "❌ يجب كتابة سبب المكافأة.",
                ephemeral=True
            )

            return

        if self.cog.rewards is None:

            await interaction.response.send_message(
                "❌ قاعدة البيانات غير متصلة.",
                ephemeral=True
            )

            return

        reward_id = str(uuid.uuid4())

        await self.cog.rewards.insert_one({
            "reward_id": reward_id,
            "user_id": self.target_member.id,
            "amount": amount,
            "reason": reason,
            "claimed": False,
            "created_by": interaction.user.id,
            "guild_id": interaction.guild.id
        })

        dm_embed = discord.Embed(
            title="🎁 لديك شعار ومكافأة جديدة!",
            description=(
                f"**السبب / التفاصيل:**\n"
                f"{reason}\n\n"
                f"💰 **قيمة المكافأة:**\n"
                f"**{format_coins(amount)} Ai**"
            ),
            color=discord.Color.gold()
        )

        dm_embed.set_footer(
            text=f"بواسطة الإدارة في سيرفر: {interaction.guild.name}"
        )

        view = ClaimRewardView(
            reward_id
        )

        try:

            await self.target_member.send(
                embed=dm_embed,
                view=view
            )

            await interaction.response.send_message(
                f"✅ تم إرسال الشعار والمكافأة إلى "
                f"{self.target_member.mention} في الخاص.\n"
                f"💰 قيمة المكافأة: "
                f"**{format_coins(amount)} Ai**",
                ephemeral=True
            )

        except discord.Forbidden:

            await self.cog.rewards.delete_one({
                "reward_id": reward_id
            })

            await interaction.response.send_message(
                f"⚠️ تعذر إرسال الخاص إلى "
                f"{self.target_member.mention} "
                f"لأن الرسائل الخاصة مغلقة.",
                ephemeral=True
            )

        except Exception:

            await self.cog.rewards.delete_one({
                "reward_id": reward_id
            })

            await interaction.response.send_message(
                "⚠️ حدث خطأ أثناء إرسال المكافأة.",
                ephemeral=True
            )


# =========================================================
# Modal التوزيع
# =========================================================

class DistributionModal(
    ui.Modal,
    title="💰 توزيع Ai"
):

    amount_input = ui.TextInput(
        label="💰 المبلغ لكل عضو",
        placeholder="مثال: 10k أو 5000",
        required=True,
        max_length=30
    )

    reason_input = ui.TextInput(
        label="📝 سبب التوزيع",
        placeholder="اكتب سبب التوزيع هنا...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000
    )

    def __init__(self, cog):

        super().__init__()

        self.cog = cog

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        member = interaction.guild.get_member(
            interaction.user.id
        )

        if not member:
            return

        if not self.cog.has_admin_role(member):
            return

        amount = parse_amount(
            self.amount_input.value
        )

        if amount <= 0:

            await interaction.response.send_message(
                "❌ المبلغ غير صحيح.",
                ephemeral=True
            )

            return

        reason = self.reason_input.value.strip()

        if not reason:

            await interaction.response.send_message(
                "❌ يجب كتابة سبب التوزيع.",
                ephemeral=True
            )

            return

        if self.cog.balances is None:

            await interaction.response.send_message(
                "❌ قاعدة البيانات غير متصلة.",
                ephemeral=True
            )

            return

        await interaction.response.send_message(
            "⏳ جاري توزيع Ai على أعضاء السيرفر...",
            ephemeral=True
        )

        count = 0

        for member in interaction.guild.members:

            if member.bot:
                continue

            await self.cog.update_balance(
                member.id,
                amount
            )

            count += 1

        embed = discord.Embed(
            title="💰 تم توزيع Ai",
            description=(
                f"تم توزيع **{format_coins(amount)} Ai** "
                f"على **{count}** عضو.\n\n"
                f"📝 **السبب:**\n"
                f"{reason}"
            ),
            color=discord.Color.gold()
        )

        await interaction.channel.send(
            embed=embed
        )


# =========================================================
# زر الشعار
# =========================================================

class BannerButtonView(ui.View):

    def __init__(
        self,
        cog,
        target_member
    ):

        super().__init__(
            timeout=60
        )

        self.cog = cog
        self.target_member = target_member

    @ui.button(
        label="إدخال تفاصيل الشعار",
        style=discord.ButtonStyle.blurple,
        emoji="🎁"
    )
    async def open_banner_modal(
        self,
        interaction: discord.Interaction,
        button: ui.Button
    ):

        member = interaction.guild.get_member(
            interaction.user.id
        )

        if not member:
            return

        if not self.cog.has_admin_role(member):

            await interaction.response.send_message(
                "❌ ليس لديك صلاحية استخدام هذا النظام.",
                ephemeral=True
            )

            return

        await interaction.response.send_modal(
            BannerModal(
                self.cog,
                self.target_member
            )
        )


# =========================================================
# زر التوزيع
# =========================================================

class DistributionButtonView(ui.View):

    def __init__(self, cog):

        super().__init__(
            timeout=60
        )

        self.cog = cog

    @ui.button(
        label="إدخال تفاصيل التوزيع",
        style=discord.ButtonStyle.green,
        emoji="💰"
    )
    async def open_distribution_modal(
        self,
        interaction: discord.Interaction,
        button: ui.Button
    ):

        member = interaction.guild.get_member(
            interaction.user.id
        )

        if not member:
            return

        if not self.cog.has_admin_role(member):

            await interaction.response.send_message(
                "❌ ليس لديك صلاحية استخدام هذا النظام.",
                ephemeral=True
            )

            return

        await interaction.response.send_modal(
            DistributionModal(
                self.cog
            )
        )


# =========================================================
# زر استلام المكافأة
# =========================================================

class ClaimRewardView(ui.View):

    def __init__(
        self,
        reward_id: str
    ):

        super().__init__(
            timeout=None
        )

        button = ui.Button(
            label="إستلام المكافأة",
            style=discord.ButtonStyle.blurple,
            emoji="💰",
            custom_id=f"claim_reward:{reward_id}"
        )

        self.add_item(
            button
        )


# =========================================================
# نظام الاقتصاد
# =========================================================

class EconomyCog(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        # قفل لمنع إرسال -مكافاة مرتين بنفس اللحظة
        self.reward_locks = {}

        # =================================================
        # حماية -سحب
        # =================================================

        # قفل لكل إداري لمنع تنفيذ عمليتي سحب بنفس اللحظة
        self.withdraw_locks = {}

        # آخر وقت تم فيه تنفيذ -سحب لكل إداري
        self.withdraw_cooldowns = {}

        mongo_uri = os.environ.get(
            "MONGO_URI"
        )

        if mongo_uri:

            self.db_client = AsyncIOMotorClient(
                mongo_uri
            )

            self.db = (
                self.db_client.discord_bot_db
            )

            self.balances = (
                self.db.economy_balances
            )

            self.rewards = (
                self.db.economy_rewards
            )

            self.settings = (
                self.db.economy_settings
            )

            # تخزين وقت آخر مكافأة لكل لاعب
            self.reward_cooldowns = (
                self.db.economy_reward_cooldowns
            )

        else:

            self.db_client = None
            self.db = None
            self.balances = None
            self.rewards = None
            self.settings = None
            self.reward_cooldowns = None

    # =====================================================
    # الرتب
    # =====================================================

    def has_admin_role(
        self,
        member: discord.Member
    ):

        return any(
            role.id in ALLOWED_ROLE_IDS
            for role in member.roles
        )

    # =====================================================
    # التحقق من الإدارة
    # =====================================================

    def is_admin(
        self,
        ctx
    ):

        return (
            isinstance(ctx.author, discord.Member)
            and self.has_admin_role(ctx.author)
        )

    # =====================================================
    # الرومات
    # =====================================================

    def economy_room(self, ctx):

        return (
            ctx.channel.id ==
            ECONOMY_ROOM_ID
        )

    def control_room(self, ctx):

        return (
            ctx.channel.id ==
            CONTROL_ROOM_ID
        )

    def banner_room(self, ctx):

        return (
            ctx.channel.id ==
            BANNER_ROOM_ID
        )

    # =====================================================
    # حالة العملة
    # =====================================================

    async def currency_enabled(
        self,
        guild_id: int
    ):

        if self.settings is None:
            return True

        data = await self.settings.find_one({
            "guild_id": guild_id
        })

        if not data:
            return True

        return data.get(
            "currency_enabled",
            True
        )

    async def set_currency_enabled(
        self,
        guild_id: int,
        enabled: bool
    ):

        if self.settings is None:
            return

        await self.settings.update_one(
            {
                "guild_id": guild_id
            },
            {
                "$set": {
                    "currency_enabled": enabled
                }
            },
            upsert=True
        )

    # =====================================================
    # الرصيد
    # =====================================================

    async def get_balance(
        self,
        user_id: int
    ):

        if self.balances is None:
            return 0

        user_data = await self.balances.find_one({
            "user_id": user_id
        })

        return (
            user_data.get(
                "balance",
                0
            )
            if user_data
            else 0
        )

    async def update_balance(
        self,
        user_id: int,
        amount: int
    ):

        if self.balances is None:
            return

        await self.balances.update_one(
            {
                "user_id": user_id
            },
            {
                "$inc": {
                    "balance": amount
                }
            },
            upsert=True
        )

    # =====================================================
    # قفل مكافأة المستخدم
    # =====================================================

    def get_reward_lock(
        self,
        guild_id: int,
        user_id: int
    ):

        key = (
            guild_id,
            user_id
        )

        if key not in self.reward_locks:

            self.reward_locks[key] = (
                asyncio.Lock()
            )

        return self.reward_locks[key]

    # =====================================================
    # قفل سحب المستخدم
    # =====================================================

    def get_withdraw_lock(
        self,
        guild_id: int,
        user_id: int
    ):

        key = (
            guild_id,
            user_id
        )

        if key not in self.withdraw_locks:

            self.withdraw_locks[key] = (
                asyncio.Lock()
            )

        return self.withdraw_locks[key]

    # =====================================================
    # حماية تكرار -سحب
    # =====================================================

    def withdraw_is_on_cooldown(
        self,
        guild_id: int,
        user_id: int
    ):

        key = (
            guild_id,
            user_id
        )

        now = asyncio.get_running_loop().time()

        last_time = self.withdraw_cooldowns.get(
            key,
            0
        )

        if (
            now - last_time
            < WITHDRAW_COOLDOWN_SECONDS
        ):

            return True

        self.withdraw_cooldowns[key] = now

        return False

    # =====================================================
    # -تعطيل
    # =====================================================

    @commands.command(name="تعطيل")
    async def disable_currency(
        self,
        ctx
    ):

        if not self.control_room(ctx):
            return

        if not self.is_admin(ctx):
            return

        await self.set_currency_enabled(
            ctx.guild.id,
            False
        )

        embed = discord.Embed(
            title="🔴 تم تعطيل العملة",
            description=(
                "تم تعطيل **أوامر العملة فقط**.\n\n"
                "يمكن إعادة تشغيلها باستخدام:\n"
                "`-تفعيل`"
            ),
            color=discord.Color.red()
        )

        await ctx.send(
            embed=embed
        )

    # =====================================================
    # -تفعيل
    # =====================================================

    @commands.command(name="تفعيل")
    async def enable_currency(
        self,
        ctx
    ):

        if not self.control_room(ctx):
            return

        if not self.is_admin(ctx):
            return

        await self.set_currency_enabled(
            ctx.guild.id,
            True
        )

        embed = discord.Embed(
            title="🟢 تم تفعيل العملة",
            description=(
                "تم تفعيل **أوامر العملة** من جديد.\n\n"
                "جميع أوامر الاقتصاد أصبحت متاحة الآن."
            ),
            color=discord.Color.green()
        )

        await ctx.send(
            embed=embed
        )

    # =====================================================
    # -شرح
    # =====================================================

    @commands.command(name="شرح")
    async def help_economy(
        self,
        ctx
    ):

        if not self.economy_room(ctx):
            return

        if not await self.currency_enabled(
            ctx.guild.id
        ):
            return

        embed = discord.Embed(
            title="📖 شرح أوامر نظام Ai",
            description=(
                "💰 **-رصيد**\n"
                "عرض رصيدك الحالي.\n\n"

                "🏆 **-توب [رقم الصفحة]**\n"
                "عرض أعلى الأعضاء.\n"
                "مثال: `-توب 1`\n\n"

                "🎁 **-مكافاة**\n"
                "الحصول على مكافأة عشوائية "
                "من 3000 إلى 4000 Ai "
                "مرة كل 10 ساعات.\n\n"

                "🎁 **-اعطي @العضو المبلغ**\n"
                "إعطاء Ai لعضو — للإدارة فقط.\n\n"

                "💸 **-سحب @العضو المبلغ**\n"
                "سحب Ai من عضو — للإدارة فقط.\n"
                "ويمكن استخدام `كل` لسحب كامل رصيده.\n\n"

                "💰 **-توزيع**\n"
                "فتح قائمة التوزيع — للإدارة فقط.\n\n"

                "🎖️ **-شعار @العضو**\n"
                "إرسال شعار ومكافأة — للإدارة فقط.\n\n"

                "🧹 **-تصفير كل**\n"
                "تصفير أرصدة جميع اللاعبين — للإدارة فقط."
            ),
            color=discord.Color.gold()
        )

        embed.set_footer(
            text="عملة السيرفر: Ai"
        )

        await ctx.send(
            embed=embed
        )

    # =====================================================
    # -رصيد
    # =====================================================

    @commands.command(name="رصيد")
    async def balance_cmd(
        self,
        ctx,
        member: discord.Member = None
    ):

        if not self.economy_room(ctx):
            return

        if not await self.currency_enabled(
            ctx.guild.id
        ):
            return

        target = member or ctx.author

        bal = await self.get_balance(
            target.id
        )

        embed = discord.Embed(
            title="💰 رصيد Ai",
            description=(
                f"رصيد {target.mention} الحالي:\n\n"
                f"**{format_coins(bal)} Ai**"
            ),
            color=discord.Color.gold()
        )

        await ctx.send(
            embed=embed
        )

    # =====================================================
    # -توب
    # =====================================================

    @commands.command(name="توب")
    async def top_cmd(
        self,
        ctx,
        page_str: str = None
    ):

        if not self.economy_room(ctx):
            return

        if page_str is None:

            page = 1

        else:

            if not page_str.isdigit():

                await ctx.send(
                    "❌ **طريقة الاستعمال:**\n"
                    "`-توب [رقم الصفحة]`\n\n"
                    "مثال:\n"
                    "`-توب 1`"
                )

                return

            page = int(page_str)

        if page < 1:

            await ctx.send(
                "❌ **طريقة الاستعمال:**\n"
                "`-توب [رقم الصفحة]`\n\n"
                "مثال:\n"
                "`-توب 1`"
            )

            return

        if not await self.currency_enabled(
            ctx.guild.id
        ):
            return

        if self.balances is None:

            await ctx.send(
                "❌ قاعدة البيانات غير متصلة."
            )

            return

        per_page = 10

        skip = (
            page - 1
        ) * per_page

        cursor = (
            self.balances
            .find()
            .sort("balance", -1)
            .skip(skip)
            .limit(per_page)
        )

        top_users = await cursor.to_list(
            length=per_page
        )

        if not top_users:

            await ctx.send(
                f"📭 لا توجد نتائج في الصفحة "
                f"**{page}**."
            )

            return

        description_lines = []

        medals = [
            "🥇",
            "🥈",
            "🥉",
            "🔹",
            "🔹",
            "🔹",
            "🔹",
            "🔹",
            "🔹",
            "🔹"
        ]

        for idx, doc in enumerate(top_users):

            user_id = doc.get(
                "user_id"
            )

            bal = doc.get(
                "balance",
                0
            )

            member = ctx.guild.get_member(
                user_id
            )

            if member:

                name = member.mention

            else:

                name = (
                    f"<@{user_id}> "
                    f"(مغادر)"
                )

            rank = (
                skip +
                idx +
                1
            )

            description_lines.append(
                f"{medals[idx]} "
                f"**#{rank}** "
                f"{name} — "
                f"**{format_coins(bal)} Ai**"
            )

        embed = discord.Embed(
            title="🏆 قائمة التوب",
            description="\n".join(
                description_lines
            ),
            color=discord.Color.gold()
        )

        embed.set_footer(
            text=f"صفحة التوب: {page}"
        )

        await ctx.send(
            embed=embed
        )

    # =====================================================
    # -مكافاة
    # =====================================================

    @commands.command(name="مكافاة")
    async def reward_cmd(
        self,
        ctx
    ):

        if not self.economy_room(ctx):
            return

        if not await self.currency_enabled(
            ctx.guild.id
        ):
            return

        if self.balances is None or self.reward_cooldowns is None:

            await ctx.send(
                "❌ قاعدة البيانات غير متصلة."
            )

            return

        # منع تنفيذ المكافأة مرتين بنفس اللحظة
        lock = self.get_reward_lock(
            ctx.guild.id,
            ctx.author.id
        )

        async with lock:

            now = discord.utils.utcnow()

            cooldown_data = await (
                self.reward_cooldowns.find_one({
                    "guild_id": ctx.guild.id,
                    "user_id": ctx.author.id
                })
            )

            if cooldown_data:

                last_claim = cooldown_data.get(
                    "last_claim"
                )

                if last_claim:

                    next_claim = (
                        last_claim
                        + timedelta(
                            hours=REWARD_COOLDOWN_HOURS
                        )
                    )

                    if now < next_claim:

                        remaining_seconds = int(
                            (
                                next_claim - now
                            ).total_seconds()
                        )

                        hours = (
                            remaining_seconds
                            // 3600
                        )

                        minutes = (
                            (
                                remaining_seconds
                                % 3600
                            )
                            // 60
                        )

                        if hours > 0:

                            if minutes > 0:

                                time_text = (
                                    f"**{hours} ساعة "
                                    f"و {minutes} دقيقة**"
                                )

                            else:

                                time_text = (
                                    f"**{hours} ساعة**"
                                )

                        else:

                            time_text = (
                                f"**{max(minutes, 1)} دقيقة**"
                            )

                        await ctx.send(
                            f"⏳ {ctx.author.mention}\n\n"
                            f"لقد أخذت المكافأة مسبقًا.\n"
                            f"🎁 المكافأة القادمة متاحة بعد "
                            f"{time_text}."
                        )

                        return

            # تسجيل وقت المكافأة قبل إعطاء الرصيد
            await self.reward_cooldowns.update_one(
                {
                    "guild_id": ctx.guild.id,
                    "user_id": ctx.author.id
                },
                {
                    "$set": {
                        "last_claim": now
                    }
                },
                upsert=True
            )

            # مبلغ عشوائي من 3000 إلى 4000
            amount = random.randint(
                REWARD_MIN,
                REWARD_MAX
            )

            await self.update_balance(
                ctx.author.id,
                amount
            )

        embed = discord.Embed(
            title="🎁 حصلت على مكافأة!",
            description=(
                f"مبروك {ctx.author.mention}!\n\n"
                f"💰 المكافأة:\n"
                f"**{format_coins(amount)} Ai**\n\n"
                f"⏳ يمكنك أخذ المكافأة مرة أخرى "
                f"بعد **10 ساعات**."
            ),
            color=discord.Color.gold()
        )

        await ctx.send(
            embed=embed
        )

    # =====================================================
    # -اعطي
    # =====================================================

    @commands.command(name="اعطي")
    async def give_cmd(
        self,
        ctx,
        member: discord.Member = None,
        *,
        amount_str: str = None
    ):

        if not self.economy_room(ctx):
            return

        if not self.is_admin(ctx):
            return

        if member is None or not amount_str:

            await ctx.send(
                "❌ **طريقة الاستعمال:**\n"
                "`-اعطي @العضو المبلغ`\n\n"
                "مثال:\n"
                "`-اعطي @ضياء 25k`"
            )

            return

        if not await self.currency_enabled(
            ctx.guild.id
        ):
            return

        amount = parse_amount(
            amount_str
        )

        if amount <= 0:

            await ctx.send(
                "❌ **طريقة الاستعمال:**\n"
                "`-اعطي @العضو المبلغ`\n\n"
                "مثال:\n"
                "`-اعطي @ضياء 25k`"
            )

            return

        await self.update_balance(
            member.id,
            amount
        )

        await ctx.send(
            f"✅ تم إضافة "
            f"**{format_coins(amount)} Ai** "
            f"إلى رصيد {member.mention}"
        )

    # =====================================================
    # -سحب
    # =====================================================

    @commands.command(name="سحب")
    async def withdraw_cmd(
        self,
        ctx,
        member: discord.Member = None,
        *,
        amount_str: str = None
    ):

        if not self.economy_room(ctx):
            return

        if not self.is_admin(ctx):
            return

        # =================================================
        # حماية السبام
        # =================================================

        # إذا تم إرسال الأمر عدة مرات خلال ثانيتين
        # يتم تجاهل التكرار بدون إرسال أي رسالة.
        if self.withdraw_is_on_cooldown(
            ctx.guild.id,
            ctx.author.id
        ):

            return

        # =================================================
        # قفل السحب
        # =================================================

        lock = self.get_withdraw_lock(
            ctx.guild.id,
            ctx.author.id
        )

        async with lock:

            if member is None or not amount_str:

                await ctx.send(
                    "❌ **طريقة الاستعمال:**\n"
                    "`-سحب @العضو المبلغ`\n"
                    "أو\n"
                    "`-سحب @العضو كل`\n\n"
                    "مثال:\n"
                    "`-سحب @ضياء 25k`\n"
                    "`-سحب @ضياء كل`"
                )

                return

            if not await self.currency_enabled(
                ctx.guild.id
            ):
                return

            # =================================================
            # سحب كامل الرصيد
            # =================================================

            if amount_str.strip() == "كل":

                current_bal = await self.get_balance(
                    member.id
                )

                if current_bal <= 0:

                    await ctx.send(
                        f"❌ {member.mention} "
                        f"لا يملك أي Ai."
                    )

                    return

                await self.update_balance(
                    member.id,
                    -current_bal
                )

                await ctx.send(
                    f"✅ تم سحب كامل رصيد "
                    f"{member.mention}.\n"
                    f"💸 المبلغ المسحوب: "
                    f"**{format_coins(current_bal)} Ai**"
                )

                return

            # =================================================
            # السحب بمبلغ محدد
            # =================================================

            amount = parse_amount(
                amount_str
            )

            if amount <= 0:

                await ctx.send(
                    "❌ **طريقة الاستعمال:**\n"
                    "`-سحب @العضو المبلغ`\n"
                    "أو\n"
                    "`-سحب @العضو كل`\n\n"
                    "مثال:\n"
                    "`-سحب @ضياء 25k`\n"
                    "`-سحب @ضياء كل`"
                )

                return

            current_bal = await self.get_balance(
                member.id
            )

            if current_bal <= 0:

                await ctx.send(
                    f"❌ {member.mention} "
                    f"لا يملك أي Ai."
                )

                return

            final_amount = min(
                amount,
                current_bal
            )

            await self.update_balance(
                member.id,
                -final_amount
            )

            await ctx.send(
                f"✅ تم سحب "
                f"**{format_coins(final_amount)} Ai** "
                f"من رصيد {member.mention}"
            )

    # =====================================================
    # -تصفير كل
    # =====================================================

    @commands.command(name="تصفير")
    async def reset_cmd(
        self,
        ctx,
        option: str = None
    ):

        if not self.economy_room(ctx):
            return

        # الإدارة فقط
        if not self.is_admin(ctx):
            return

        if option != "كل":

            await ctx.send(
                "❌ **طريقة الاستعمال:**\n"
                "`-تصفير كل`\n\n"
                "هذا الأمر يقوم بتصفير أرصدة جميع اللاعبين."
            )

            return

        if not await self.currency_enabled(
            ctx.guild.id
        ):
            return

        if self.balances is None:

            await ctx.send(
                "❌ قاعدة البيانات غير متصلة."
            )

            return

        result = await self.balances.update_many(
            {},
            {
                "$set": {
                    "balance": 0
                }
            }
        )

        await ctx.send(
            "🧹 **تم تصفير جميع أرصدة اللاعبين.**\n\n"
            f"👥 عدد الحسابات التي تم تصفيرها: "
            f"**{result.modified_count}**\n"
            "💰 جميع الأرصدة أصبحت **0 Ai**."
        )

    # =====================================================
    # -توزيع
    # =====================================================

    @commands.command(name="توزيع")
    async def distribute_cmd(
        self,
        ctx
    ):

        if not self.economy_room(ctx):
            return

        if not self.is_admin(ctx):
            return

        if not await self.currency_enabled(
            ctx.guild.id
        ):
            return

        view = DistributionButtonView(
            self
        )

        await ctx.send(
            "📋 اضغط الزر التالي لإدخال "
            "المبلغ والسبب:",
            view=view
        )

    # =====================================================
    # -شعار
    # =====================================================

    @commands.command(name="شعار")
    async def banner_cmd(
        self,
        ctx,
        member: discord.Member = None
    ):

        if not self.banner_room(ctx):
            return

        if not self.is_admin(ctx):
            return

        if member is None:

            await ctx.send(
                "❌ **طريقة الاستعمال:**\n"
                "`-شعار @العضو`\n\n"
                "مثال:\n"
                "`-شعار @ضياء`"
            )

            return

        if not await self.currency_enabled(
            ctx.guild.id
        ):
            return

        await ctx.send(
            f"🎁 إعداد مكافأة لـ "
            f"{member.mention}\n"
            f"اضغط الزر لإدخال المبلغ والسبب:",
            view=BannerButtonView(
                self,
                member
            )
        )


# =========================================================
# نظام استلام المكافآت
# =========================================================

class RewardInteractionCog(
    commands.Cog
):

    def __init__(self, bot):

        self.bot = bot

        mongo_uri = os.environ.get(
            "MONGO_URI"
        )

        if mongo_uri:

            self.db_client = (
                AsyncIOMotorClient(
                    mongo_uri
                )
            )

            self.db = (
                self.db_client.discord_bot_db
            )

            self.balances = (
                self.db.economy_balances
            )

            self.rewards = (
                self.db.economy_rewards
            )

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

        if (
            interaction.type !=
            discord.InteractionType.component
        ):
            return

        if not interaction.data:
            return

        custom_id = interaction.data.get(
            "custom_id"
        )

        if not custom_id:
            return

        if not custom_id.startswith(
            "claim_reward:"
        ):
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

        reward = await (
            self.rewards.find_one_and_update(
                {
                    "reward_id": reward_id,
                    "user_id": interaction.user.id,
                    "claimed": False
                },
                {
                    "$set": {
                        "claimed": True,
                        "claimed_at":
                            discord.utils.utcnow()
                    }
                },
                return_document=
                    ReturnDocument.AFTER
            )
        )

        if not reward:

            await interaction.response.send_message(
                "❌ هذه المكافأة تم استلامها مسبقاً "
                "أو أنها ليست مخصصة لك.",
                ephemeral=True
            )

            return

        reward_amount = reward["amount"]

        await self.balances.update_one(
            {
                "user_id":
                    interaction.user.id
            },
            {
                "$inc": {
                    "balance":
                        reward_amount
                }
            },
            upsert=True
        )

        view = discord.ui.View(
            timeout=None
        )

        disabled_button = discord.ui.Button(
            label="تم الاستلام بنجاح",
            style=discord.ButtonStyle.green,
            emoji="✅",
            custom_id=
                f"claimed_reward:{reward_id}",
            disabled=True
        )

        view.add_item(
            disabled_button
        )

        await interaction.response.edit_message(
            view=view
        )

        await interaction.followup.send(
            f"🎉 مبروك!\n"
            f"تمت إضافة "
            f"**{format_coins(reward_amount)} Ai** "
            f"إلى رصيدك.",
            ephemeral=True
        )


# =========================================================
# تشغيل الـ Cogs
# =========================================================

async def setup(bot):

    await bot.add_cog(
        EconomyCog(bot)
    )

    await bot.add_cog(
        RewardInteractionCog(bot)
    )
