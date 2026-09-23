import os
import re
import uuid
import random
import asyncio

from datetime import datetime, timezone, timedelta

import discord
from discord.ext import commands
from discord import ui

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ReturnDocument


# =========================================================
# الإعدادات العامة
# =========================================================

# السيرفر الوحيد الذي يسمح بأوامر الإدارة
ADMIN_GUILD_ID = 1544077828151054537

REWARD_MIN = 3000
REWARD_MAX = 4000

REWARD_COOLDOWN_HOURS = 10

LUCK_MIN = 3000
LUCK_MAX = 5000

LUCK_COOLDOWN_HOURS = 10

WITHDRAW_COOLDOWN_SECONDS = 2


# =========================================================
# تحويل المبالغ
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


# =========================================================
# تنسيق العملة
# =========================================================

def format_coins(amount: int):

    if amount >= 1_000_000_000:

        return (
            f"{amount / 1_000_000_000:.2f}b"
            .replace(".00", "")
        )

    elif amount >= 1_000_000:

        return (
            f"{amount / 1_000_000:.2f}m"
            .replace(".00", "")
        )

    elif amount >= 1_000:

        return (
            f"{amount / 1_000:.1f}k"
            .replace(".0", "")
        )

    return str(amount)


# =========================================================
# مودال الشعار
#
# الشعار أصبح متاحًا للأعضاء العاديين.
# المبلغ يتم خصمه من صاحب الأمر.
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

        if not interaction.guild:

            return

        member = interaction.guild.get_member(
            interaction.user.id
        )

        if not member:

            return

        # =============================================
        # التأكد أن الاقتصاد ما زال مفعلاً
        # =============================================

        if not await self.cog.currency_enabled(
            interaction.guild.id
        ):

            await interaction.response.send_message(
                "❌ نظام الاقتصاد غير مفعل.",
                ephemeral=True
            )

            return

        # =============================================
        # التأكد من روم الاقتصاد
        # =============================================

        economy_room_id = await self.cog.get_economy_room_id(
            interaction.guild.id
        )

        if not economy_room_id:

            await interaction.response.send_message(
                "❌ لم يتم تحديد روم الاقتصاد.",
                ephemeral=True
            )

            return

        if interaction.channel.id != economy_room_id:

            await interaction.response.send_message(
                "❌ لا يمكنك استخدام الشعار في هذا الروم.",
                ephemeral=True
            )

            return

        # =============================================
        # المبلغ
        # =============================================

        amount = parse_amount(
            self.amount_input.value
        )

        if amount <= 0:

            await interaction.response.send_message(

                "❌ المبلغ غير صحيح.\n\n"
                "أمثلة:\n"
                "`25k`\n"
                "`50000`\n"
                "`2 مليون`",

                ephemeral=True
            )

            return

        # =============================================
        # السبب
        # =============================================

        reason = self.reason_input.value.strip()

        if not reason:

            await interaction.response.send_message(
                "❌ يجب كتابة سبب المكافأة.",
                ephemeral=True
            )

            return

        if self.cog.balances is None:

            await interaction.response.send_message(
                "❌ قاعدة البيانات غير متصلة.",
                ephemeral=True
            )

            return

        if self.cog.rewards is None:

            await interaction.response.send_message(
                "❌ قاعدة البيانات غير متصلة.",
                ephemeral=True
            )

            return

        # =============================================
        # لا يمكن إرسال شعار للنفس
        # =============================================

        if self.target_member.id == interaction.user.id:

            await interaction.response.send_message(
                "❌ لا يمكنك إرسال شعار لنفسك.",
                ephemeral=True
            )

            return

        # =============================================
        # لا يمكن إرسال شعار لبوت
        # =============================================

        if self.target_member.bot:

            await interaction.response.send_message(
                "❌ لا يمكنك إرسال شعار إلى بوت.",
                ephemeral=True
            )

            return

        # =============================================
        # خصم المبلغ بشكل آمن
        #
        # لا يتم الخصم إذا كان الرصيد غير كافٍ.
        # =============================================

        deduction = await self.cog.balances.update_one(

            {
                "user_id": interaction.user.id,
                "balance": {
                    "$gte": amount
                }
            },

            {
                "$inc": {
                    "balance": -amount
                }
            }

        )

        if deduction.modified_count == 0:

            current_balance = await self.cog.get_balance(
                interaction.user.id
            )

            await interaction.response.send_message(

                f"❌ رصيدك غير كافي لإرسال الشعار.\n\n"
                f"💰 رصيدك الحالي: "
                f"**{format_coins(current_balance)} Ai**\n"
                f"💸 قيمة الشعار: "
                f"**{format_coins(amount)} Ai**",

                ephemeral=True
            )

            return

        # =============================================
        # إنشاء المكافأة
        # =============================================

        reward_id = str(
            uuid.uuid4()
        )

        try:

            await self.cog.rewards.insert_one({

                "reward_id": reward_id,

                "user_id": self.target_member.id,

                "amount": amount,

                "reason": reason,

                "claimed": False,

                "created_by": interaction.user.id,

                "guild_id": interaction.guild.id

            })

        except Exception:

            # إرجاع المبلغ إذا فشل إنشاء المكافأة

            await self.cog.update_balance(
                interaction.user.id,
                amount
            )

            await interaction.response.send_message(
                "⚠️ حدث خطأ أثناء إنشاء المكافأة، وتم إرجاع المبلغ إلى رصيدك.",
                ephemeral=True
            )

            return

        # =============================================
        # رسالة الخاص
        # =============================================

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

            text=(
                f"من {interaction.user.display_name}"
                f" في سيرفر: "
                f"{interaction.guild.name}"
            )

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
                f"{self.target_member.mention} في الخاص.\n\n"

                f"💰 قيمة الشعار: "
                f"**{format_coins(amount)} Ai**\n"

                f"💸 تم خصم المبلغ من رصيدك.",

                ephemeral=True
            )

        except discord.Forbidden:

            # حذف المكافأة
            await self.cog.rewards.delete_one({
                "reward_id": reward_id
            })

            # إرجاع المبلغ
            await self.cog.update_balance(
                interaction.user.id,
                amount
            )

            await interaction.response.send_message(

                f"⚠️ تعذر إرسال الخاص إلى "
                f"{self.target_member.mention} "
                f"لأن الرسائل الخاصة مغلقة.\n\n"

                f"💰 تم إرجاع "
                f"**{format_coins(amount)} Ai** "
                f"إلى رصيدك.",

                ephemeral=True
            )

        except Exception:

            await self.cog.rewards.delete_one({
                "reward_id": reward_id
            })

            await self.cog.update_balance(
                interaction.user.id,
                amount
            )

            await interaction.response.send_message(

                "⚠️ حدث خطأ أثناء إرسال المكافأة.\n"
                f"💰 تم إرجاع **{format_coins(amount)} Ai** إلى رصيدك.",

                ephemeral=True
            )


# =========================================================
# مودال التوزيع
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

        if not interaction.guild:

            return

        member = interaction.guild.get_member(
            interaction.user.id
        )

        if not member:

            return

        allowed = await self.cog.has_admin_permission(
            interaction.guild.id,
            member,
            "توزيع",
            interaction.channel.id
        )

        if not allowed:

            await interaction.response.send_message(
                "❌ ليس لديك صلاحية استخدام هذا النظام.",
                ephemeral=True
            )

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

        for guild_member in interaction.guild.members:

            if guild_member.bot:
                continue

            await self.cog.update_balance(
                guild_member.id,
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
        button
    ):

        if not interaction.guild:

            return

        member = interaction.guild.get_member(
            interaction.user.id
        )

        if not member:

            return

        if not await self.cog.currency_enabled(
            interaction.guild.id
        ):

            await interaction.response.send_message(
                "❌ نظام الاقتصاد غير مفعل.",
                ephemeral=True
            )

            return

        economy_room_id = await self.cog.get_economy_room_id(
            interaction.guild.id
        )

        if not economy_room_id:

            await interaction.response.send_message(
                "❌ لم يتم تحديد روم الاقتصاد.",
                ephemeral=True
            )

            return

        if interaction.channel.id != economy_room_id:

            await interaction.response.send_message(
                "❌ لا يمكنك استخدام الشعار في هذا الروم.",
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
        button
    ):

        if not interaction.guild:

            return

        member = interaction.guild.get_member(
            interaction.user.id
        )

        if not member:

            return

        allowed = await self.cog.has_admin_permission(
            interaction.guild.id,
            member,
            "توزيع",
            interaction.channel.id
        )

        if not allowed:

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

            custom_id=(
                f"claim_reward:{reward_id}"
            )

        )

        self.add_item(
            button
        )


# =========================================================
# Economy Cog
# =========================================================

class EconomyCog(commands.Cog):

    def __init__(
        self,
        bot
    ):

        self.bot = bot

        self.reward_locks = {}

        self.withdraw_locks = {}

        self.withdraw_cooldowns = {}

        self.transfer_locks = {}

        self.luck_locks = {}

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

            self.settings = (
                self.db.economy_settings
            )

            self.reward_cooldowns = (
                self.db.economy_reward_cooldowns
            )

            self.luck_cooldowns = (
                self.db.economy_luck_cooldowns
            )

            self.website_command_settings = (
                self.db.website_command_settings
            )

        else:

            self.db_client = None
            self.db = None
            self.balances = None
            self.rewards = None
            self.settings = None
            self.reward_cooldowns = None
            self.luck_cooldowns = None
            self.website_command_settings = None


    # =====================================================
    # إعدادات الموقع
    # =====================================================

    async def get_command_setting(
        self,
        guild_id,
        command_name
    ):

        if self.website_command_settings is None:

            return None

        guild_ids = [
            guild_id,
            str(guild_id)
        ]

        setting = await self.website_command_settings.find_one({

            "guild_id": {
                "$in": guild_ids
            },

            "command_name": command_name

        })

        if setting:

            return setting

        # دعم النسخ القديمة التي تستخدم name

        setting = await self.website_command_settings.find_one({

            "guild_id": {
                "$in": guild_ids
            },

            "name": command_name

        })

        return setting


    async def has_admin_permission(
        self,
        guild_id,
        member,
        command_name,
        channel_id=None
    ):

        # =================================================
        # أوامر الإدارة لا تعمل إلا في السيرفر المحدد
        # =================================================

        if guild_id != ADMIN_GUILD_ID:

            return False

        if not member:

            return False

        setting = await self.get_command_setting(
            guild_id,
            command_name
        )

        if not setting:

            return False

        if not setting.get(
            "enabled",
            False
        ):

            return False

        # =================================================
        # الرتب
        # =================================================

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

        if not (
            allowed_role_ids
            & user_role_ids
        ):

            return False

        # =================================================
        # الروم
        # =================================================

        if channel_id is not None:

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

            if str(channel_id) not in allowed_channel_ids:

                return False

        return True


    async def command_channel_allowed(
        self,
        guild_id,
        command_name,
        channel_id
    ):

        if guild_id != ADMIN_GUILD_ID:

            return False

        setting = await self.get_command_setting(
            guild_id,
            command_name
        )

        if not setting:

            return False

        if not setting.get(
            "enabled",
            False
        ):

            return False

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

        return str(channel_id) in allowed_channel_ids


    # =====================================================
    # روم الاقتصاد
    # =====================================================

    async def get_economy_room_id(
        self,
        guild_id
    ):

        if self.settings is None:

            return None

        guild_ids = [
            guild_id,
            str(guild_id)
        ]

        data = await self.settings.find_one({

            "guild_id": {
                "$in": guild_ids
            }

        })

        if not data:

            return None

        room_id = data.get(
            "economy_room_id"
        )

        if not room_id:

            return None

        try:

            return int(room_id)

        except Exception:

            return None


    async def economy_room(
        self,
        ctx
    ):

        if not ctx.guild:

            return False

        room_id = await self.get_economy_room_id(
            ctx.guild.id
        )

        if not room_id:

            return False

        return ctx.channel.id == room_id


    # =====================================================
    # العملة
    # =====================================================

    async def currency_enabled(
        self,
        guild_id
    ):

        if self.settings is None:

            return False

        guild_ids = [
            guild_id,
            str(guild_id)
        ]

        data = await self.settings.find_one({

            "guild_id": {
                "$in": guild_ids
            }

        })

        if not data:

            return False

        return data.get(
            "currency_enabled",
            False
        )


    async def set_currency_enabled(
        self,
        guild_id,
        enabled
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
    # فحص توفر الاقتصاد
    # =====================================================

    async def economy_available(
        self,
        ctx
    ):

        if not ctx.guild:

            return False

        if not await self.currency_enabled(
            ctx.guild.id
        ):

            return False

        if not await self.economy_room(
            ctx
        ):

            return False

        return True


    # =====================================================
    # الرصيد
    #
    # الرصيد مربوط بـ user_id فقط
    # كما كان في النظام السابق.
    # =====================================================

    async def get_balance(
        self,
        user_id
    ):

        if self.balances is None:

            return 0

        user_data = await self.balances.find_one({

            "user_id": user_id

        })

        if not user_data:

            return 0

        return user_data.get(
            "balance",
            0
        )


    async def update_balance(
        self,
        user_id,
        amount
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
    # أقفال المكافأة
    # =====================================================

    def get_reward_lock(
        self,
        guild_id,
        user_id
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
    # أقفال السحب
    # =====================================================

    def get_withdraw_lock(
        self,
        guild_id,
        user_id
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


    def withdraw_is_on_cooldown(
        self,
        guild_id,
        user_id
    ):

        key = (
            guild_id,
            user_id
        )

        now = (
            asyncio.get_running_loop().time()
        )

        last_time = (
            self.withdraw_cooldowns.get(
                key,
                0
            )
        )

        if (
            now - last_time
            < WITHDRAW_COOLDOWN_SECONDS
        ):

            return True

        self.withdraw_cooldowns[key] = now

        return False


    # =====================================================
    # أقفال التحويل
    # =====================================================

    def get_transfer_lock(
        self,
        guild_id,
        user_id
    ):

        key = (
            guild_id,
            user_id
        )

        if key not in self.transfer_locks:

            self.transfer_locks[key] = (
                asyncio.Lock()
            )

        return self.transfer_locks[key]


    # =====================================================
    # أقفال الحظ
    # =====================================================

    def get_luck_lock(
        self,
        guild_id,
        user_id
    ):

        key = (
            guild_id,
            user_id
        )

        if key not in self.luck_locks:

            self.luck_locks[key] = (
                asyncio.Lock()
            )

        return self.luck_locks[key]


    # =====================================================
    # تعطيل العملة
    # =====================================================

    @commands.command(name="تعطيل")
    async def disable_currency(
        self,
        ctx
    ):

        if not ctx.guild:

            return

        if ctx.guild.id != ADMIN_GUILD_ID:

            return

        allowed = await self.has_admin_permission(

            ctx.guild.id,

            ctx.author,

            "تعطيل",

            ctx.channel.id

        )

        if not allowed:

            return

        await self.set_currency_enabled(

            ctx.guild.id,

            False

        )

        embed = discord.Embed(

            title="🔴 تم تعطيل العملة",

            description=(

                "تم تعطيل **أوامر العملة فقط**.\n\n"

                "يمكن إعادة تفعيل النظام من "
                "لوحة تحكم الموقع."

            ),

            color=discord.Color.red()

        )

        await ctx.send(
            embed=embed
        )


    # =====================================================
    # شرح
    # =====================================================

    @commands.command(name="شرح")
    async def help_economy(
        self,
        ctx
    ):

        if not await self.economy_available(
            ctx
        ):

            return

        embed = discord.Embed(

            title="📖 شرح أوامر نظام Ai",

            description=(

                "💰 **رصيد**\n"
                "عرض رصيدك الحالي.\n\n"

                "🏆 **توب [رقم الصفحة]**\n"
                "عرض أعلى الأعضاء.\n"
                "مثال: `توب 1`\n\n"

                "🎁 **مكافاة**\n"
                "الحصول على مكافأة عشوائية "
                "من 3000 إلى 4000 Ai "
                "مرة كل 10 ساعات.\n\n"

                "🎲 **حظ**\n"
                "الحصول على مبلغ عشوائي "
                "من 3000 إلى 5000 Ai "
                "مرة كل 10 ساعات.\n\n"

                "💸 **تحويل @العضو المبلغ**\n"
                "تحويل Ai من رصيدك إلى عضو آخر.\n"
                "يمكنك استخدام مبلغ مثل `25k`.\n"
                "أو `ربع` / `نص` / `نصف` / `كامل`.\n\n"

                "🎁 **اعطي @العضو المبلغ**\n"
                "إعطاء Ai لعضو — للإدارة فقط.\n\n"

                "💸 **سحب @العضو المبلغ**\n"
                "سحب Ai من عضو — للإدارة فقط.\n"
                "ويمكن استخدام `كل` لسحب كامل رصيده.\n\n"

                "💰 **توزيع**\n"
                "فتح قائمة التوزيع — للإدارة فقط.\n\n"

                "🎖️ **شعار @العضو**\n"
                "إرسال شعار ومكافأة، "
                "ويتم خصم قيمة الشعار من رصيد المرسل.\n\n"

                "🧹 **تصفير كل**\n"
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
    # الرصيد
    # =====================================================

    @commands.command(name="رصيد")
    async def balance_cmd(
        self,
        ctx,
        member: discord.Member = None
    ):

        if not await self.economy_available(
            ctx
        ):

            return

        target = (
            member
            or ctx.author
        )

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
    # التوب
    # =====================================================

    @commands.command(name="توب")
    async def top_cmd(
        self,
        ctx,
        page_str: str = None
    ):

        if not await self.economy_available(
            ctx
        ):

            return

        if page_str is None:

            page = 1

        else:

            if not page_str.isdigit():

                await ctx.send(

                    "❌ **طريقة الاستعمال:**\n"
                    "`توب [رقم الصفحة]`\n\n"
                    "مثال:\n"
                    "`توب 1`"

                )

                return

            page = int(
                page_str
            )

        if page < 1:

            await ctx.send(

                "❌ **طريقة الاستعمال:**\n"
                "`توب [رقم الصفحة]`\n\n"
                "مثال:\n"
                "`توب 1`"

            )

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
                f"📭 لا توجد نتائج في الصفحة **{page}**."
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

        for idx, doc in enumerate(
            top_users
        ):

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
                    f"<@{user_id}> (مغادر)"
                )

            rank = (
                skip + idx + 1
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
    # المكافأة
    # =====================================================

    @commands.command(name="مكافاة")
    async def reward_cmd(
        self,
        ctx
    ):

        if not await self.economy_available(
            ctx
        ):

            return

        if (
            self.balances is None
            or self.reward_cooldowns is None
        ):

            await ctx.send(
                "❌ قاعدة البيانات غير متصلة."
            )

            return

        lock = self.get_reward_lock(

            ctx.guild.id,
            ctx.author.id

        )

        async with lock:

            now = datetime.now(
                timezone.utc
            )

            cooldown_data = (
                await self.reward_cooldowns.find_one({

                    "guild_id": ctx.guild.id,

                    "user_id": ctx.author.id

                })
            )

            if cooldown_data:

                last_claim = cooldown_data.get(
                    "last_claim"
                )

                if last_claim:

                    if last_claim.tzinfo is None:

                        last_claim = (
                            last_claim.replace(
                                tzinfo=timezone.utc
                            )
                        )

                    else:

                        last_claim = (
                            last_claim.astimezone(
                                timezone.utc
                            )
                        )

                    next_claim = (

                        last_claim
                        + timedelta(
                            hours=REWARD_COOLDOWN_HOURS
                        )

                    )

                    if now < next_claim:

                        remaining_seconds = int(

                            (
                                next_claim
                                - now
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
    # الحظ
    # =====================================================

    @commands.command(name="حظ")
    async def luck_cmd(
        self,
        ctx
    ):

        if not await self.economy_available(
            ctx
        ):

            return

        if (
            self.balances is None
            or self.luck_cooldowns is None
        ):

            await ctx.send(
                "❌ قاعدة البيانات غير متصلة."
            )

            return

        lock = self.get_luck_lock(

            ctx.guild.id,
            ctx.author.id

        )

        async with lock:

            now = datetime.now(
                timezone.utc
            )

            cooldown_data = (
                await self.luck_cooldowns.find_one({

                    "guild_id": ctx.guild.id,

                    "user_id": ctx.author.id

                })
            )

            if cooldown_data:

                last_claim = cooldown_data.get(
                    "last_claim"
                )

                if last_claim:

                    if last_claim.tzinfo is None:

                        last_claim = (
                            last_claim.replace(
                                tzinfo=timezone.utc
                            )
                        )

                    else:

                        last_claim = (
                            last_claim.astimezone(
                                timezone.utc
                            )
                        )

                    next_claim = (

                        last_claim
                        + timedelta(
                            hours=LUCK_COOLDOWN_HOURS
                        )

                    )

                    if now < next_claim:

                        remaining_seconds = int(

                            (
                                next_claim
                                - now
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
                            f"لقد استخدمت الحظ مسبقًا.\n"
                            f"🎲 المحاولة القادمة متاحة بعد "
                            f"{time_text}."

                        )

                        return

            amount = random.randint(

                LUCK_MIN,
                LUCK_MAX

            )

            await self.luck_cooldowns.update_one(

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

            await self.update_balance(

                ctx.author.id,
                amount

            )

        embed = discord.Embed(

            title="🎲 حظك اليوم!",

            description=(

                f"مبروك {ctx.author.mention}!\n\n"

                f"🍀 حصلت على:\n"
                f"**{format_coins(amount)} Ai**\n\n"

                f"⏳ يمكنك استخدام `حظ` مرة أخرى "
                f"بعد **10 ساعات**."

            ),

            color=discord.Color.gold()

        )

        await ctx.send(
            embed=embed
        )


    # =====================================================
    # التحويل
    # =====================================================

    @commands.command(name="تحويل")
    async def transfer_cmd(
        self,
        ctx,
        member: discord.Member = None,
        *,
        amount_str: str = None
    ):

        if not await self.economy_available(
            ctx
        ):

            return

        if self.balances is None:

            await ctx.send(
                "❌ قاعدة البيانات غير متصلة."
            )

            return

        if member is None or not amount_str:

            await ctx.send(

                "❌ **طريقة الاستعمال:**\n"
                "`تحويل @العضو المبلغ`\n\n"

                "أمثلة:\n"
                "`تحويل @ضياء 25k`\n"
                "`تحويل @ضياء ربع`\n"
                "`تحويل @ضياء نص`\n"
                "`تحويل @ضياء كامل`"

            )

            return

        if member.id == ctx.author.id:

            await ctx.send(
                "❌ لا يمكنك تحويل Ai لنفسك."
            )

            return

        if member.bot:

            await ctx.send(
                "❌ لا يمكنك تحويل Ai إلى بوت."
            )

            return

        amount_text = (
            amount_str
            .strip()
            .lower()
        )

        lock = self.get_transfer_lock(

            ctx.guild.id,
            ctx.author.id

        )

        async with lock:

            sender_balance = (
                await self.get_balance(
                    ctx.author.id
                )
            )

            if amount_text in (
                "كامل",
                "كل"
            ):

                amount = sender_balance

            elif amount_text in (
                "نص",
                "نصف"
            ):

                amount = (
                    sender_balance // 2
                )

            elif amount_text == "ربع":

                amount = (
                    sender_balance // 4
                )

            elif amount_text in (
                "ثلاث ارباع",
                "ثلاثة ارباع",
                "ثلاث ارباعه",
                "ثلاثة أرباع"
            ):

                amount = (
                    sender_balance * 3
                ) // 4

            else:

                amount = parse_amount(
                    amount_str
                )

            if amount <= 0:

                await ctx.send(

                    f"❌ لا يمكن تحويل هذا المبلغ.\n\n"
                    f"💰 رصيدك الحالي: "
                    f"**{format_coins(sender_balance)} Ai**"

                )

                return

            if sender_balance < amount:

                await ctx.send(

                    f"❌ {ctx.author.mention}\n\n"

                    f"رصيدك غير كافي لإتمام التحويل.\n"

                    f"💰 رصيدك الحالي: "
                    f"**{format_coins(sender_balance)} Ai**\n"

                    f"💸 المبلغ المطلوب: "
                    f"**{format_coins(amount)} Ai**"

                )

                return

            await self.update_balance(

                ctx.author.id,
                -amount

            )

            await self.update_balance(

                member.id,
                amount

            )

        embed = discord.Embed(

            title="💸 تم التحويل بنجاح",

            description=(

                f"👤 **المرسل:**\n"
                f"{ctx.author.mention}\n\n"

                f"📥 **المستلم:**\n"
                f"{member.mention}\n\n"

                f"💰 **المبلغ المحول:**\n"
                f"**{format_coins(amount)} Ai**"

            ),

            color=discord.Color.gold()

        )

        await ctx.send(
            embed=embed
        )


    # =====================================================
    # إعطاء
    # =====================================================

    @commands.command(name="اعطي")
    async def give_cmd(
        self,
        ctx,
        member: discord.Member = None,
        *,
        amount_str: str = None
    ):

        if not ctx.guild:

            return

        if not await self.economy_available(
            ctx
        ):

            return

        allowed = await self.has_admin_permission(

            ctx.guild.id,

            ctx.author,

            "اعطي",

            ctx.channel.id

        )

        if not allowed:

            return

        if member is None or not amount_str:

            await ctx.send(

                "❌ **طريقة الاستعمال:**\n"
                "`اعطي @العضو المبلغ`\n\n"

                "مثال:\n"
                "`اعطي @ضياء 25k`"

            )

            return

        amount = parse_amount(
            amount_str
        )

        if amount <= 0:

            await ctx.send(

                "❌ **طريقة الاستعمال:**\n"
                "`اعطي @العضو المبلغ`\n\n"

                "مثال:\n"
                "`اعطي @ضياء 25k`"

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
    # سحب
    # =====================================================

    @commands.command(name="سحب")
    async def withdraw_cmd(
        self,
        ctx,
        member: discord.Member = None,
        *,
        amount_str: str = None
    ):

        if not ctx.guild:

            return

        if not await self.economy_available(
            ctx
        ):

            return

        allowed = await self.has_admin_permission(

            ctx.guild.id,

            ctx.author,

            "سحب",

            ctx.channel.id

        )

        if not allowed:

            return

        if self.withdraw_is_on_cooldown(

            ctx.guild.id,
            ctx.author.id

        ):

            return

        lock = self.get_withdraw_lock(

            ctx.guild.id,
            ctx.author.id

        )

        async with lock:

            if member is None or not amount_str:

                await ctx.send(

                    "❌ **طريقة الاستعمال:**\n"
                    "`سحب @العضو المبلغ`\n"
                    "أو\n"
                    "`سحب @العضو كل`\n\n"

                    "مثال:\n"
                    "`سحب @ضياء 25k`\n"
                    "`سحب @ضياء كل`"

                )

                return

            if amount_str.strip() == "كل":

                current_bal = (
                    await self.get_balance(
                        member.id
                    )
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

            amount = parse_amount(
                amount_str
            )

            if amount <= 0:

                await ctx.send(

                    "❌ **طريقة الاستعمال:**\n"
                    "`سحب @العضو المبلغ`\n"
                    "أو\n"
                    "`سحب @العضو كل`"

                )

                return

            current_bal = (
                await self.get_balance(
                    member.id
                )
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
    # تصفير
    # =====================================================

    @commands.command(name="تصفير")
    async def reset_cmd(
        self,
        ctx,
        option: str = None
    ):

        if not ctx.guild:

            return

        if not await self.economy_available(
            ctx
        ):

            return

        allowed = await self.has_admin_permission(

            ctx.guild.id,

            ctx.author,

            "تصفير",

            ctx.channel.id

        )

        if not allowed:

            return

        if option != "كل":

            await ctx.send(

                "❌ **طريقة الاستعمال:**\n"
                "`تصفير كل`\n\n"

                "هذا الأمر يقوم بتصفير "
                "أرصدة جميع اللاعبين."

            )

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
    # توزيع
    # =====================================================

    @commands.command(name="توزيع")
    async def distribute_cmd(
        self,
        ctx
    ):

        if not ctx.guild:

            return

        if not await self.economy_available(
            ctx
        ):

            return

        allowed = await self.has_admin_permission(

            ctx.guild.id,

            ctx.author,

            "توزيع",

            ctx.channel.id

        )

        if not allowed:

            return

        await ctx.send(

            "📋 اضغط الزر التالي "
            "لإدخال المبلغ والسبب:",

            view=DistributionButtonView(
                self
            )

        )


    # =====================================================
    # شعار
    #
    # متاح لأي عضو.
    # قيمة الشعار تخصم من رصيد صاحب الأمر.
    # =====================================================

    @commands.command(name="شعار")
    async def banner_cmd(
        self,
        ctx,
        member: discord.Member = None
    ):

        if not ctx.guild:

            return

        if not await self.economy_available(
            ctx
        ):

            return

        if member is None:

            await ctx.send(

                "❌ **طريقة الاستعمال:**\n"
                "`شعار @العضو`\n\n"

                "مثال:\n"
                "`شعار @ضياء`\n\n"

                "💡 سيتم خصم قيمة المكافأة "
                "من رصيدك."

            )

            return

        if member.id == ctx.author.id:

            await ctx.send(
                "❌ لا يمكنك إرسال شعار لنفسك."
            )

            return

        if member.bot:

            await ctx.send(
                "❌ لا يمكنك إرسال شعار إلى بوت."
            )

            return

        await ctx.send(

            f"🎁 إعداد مكافأة لـ "
            f"{member.mention}\n\n"

            f"اضغط الزر لإدخال "
            f"المبلغ والسبب.\n"

            f"💰 **سيتم خصم قيمة المكافأة "
            f"من رصيدك.**",

            view=BannerButtonView(

                self,

                member

            )

        )


# =========================================================
# تفاعل استلام المكافأة
# =========================================================

class RewardInteractionCog(
    commands.Cog
):

    def __init__(
        self,
        bot
    ):

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
            interaction.type
            != discord.InteractionType.component
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

        if self.balances is None:

            await interaction.response.send_message(

                "❌ قاعدة البيانات غير متصلة.",

                ephemeral=True

            )

            return

        reward_id = custom_id.split(

            "claim_reward:",
            1

        )[1]

        reward = (
            await self.rewards.find_one_and_update(

                {
                    "reward_id": reward_id,

                    "user_id": interaction.user.id,

                    "claimed": False

                },

                {
                    "$set": {

                        "claimed": True,

                        "claimed_at": datetime.now(
                            timezone.utc
                        )

                    }
                },

                return_document=ReturnDocument.AFTER

            )
        )

        if not reward:

            await interaction.response.send_message(

                "❌ هذه المكافأة تم استلامها مسبقاً "
                "أو أنها ليست مخصصة لك.",

                ephemeral=True

            )

            return

        reward_amount = reward[
            "amount"
        ]

        view = discord.ui.View(
            timeout=None
        )

        disabled_button = discord.ui.Button(

            label="تم الاستلام بنجاح",

            style=discord.ButtonStyle.green,

            emoji="✅",

            custom_id=(
                f"claimed_reward:{reward_id}"
            ),

            disabled=True

        )

        view.add_item(
            disabled_button
        )

        await interaction.response.edit_message(
            view=view
        )

        await self.balances.update_one(

            {
                "user_id": interaction.user.id
            },

            {
                "$inc": {
                    "balance": reward_amount
                }
            },

            upsert=True

        )

        await interaction.followup.send(

            f"🎉 مبروك!\n\n"

            f"تمت إضافة "
            f"**{format_coins(reward_amount)} Ai** "
            f"إلى رصيدك.",

            ephemeral=True

        )


# =========================================================
# Setup
# =========================================================

async def setup(bot):

    await bot.add_cog(
        EconomyCog(bot)
    )

    await bot.add_cog(
        RewardInteractionCog(bot)
    )
