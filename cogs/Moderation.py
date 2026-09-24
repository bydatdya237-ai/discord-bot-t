import os
import re
import asyncio
from datetime import timedelta

import discord
from discord.ext import commands
from discord import ui

from pymongo import MongoClient


# =========================================================
# MongoDB
# =========================================================

MONGO_URI = os.getenv("MONGO_URI")

mongo_client = MongoClient(MONGO_URI)
db = mongo_client["discord_bot_db"]

moderation_settings_collection = db["moderation_settings"]
moderation_reasons_collection = db["moderation_reasons"]
moderation_warnings_collection = db["moderation_warnings"]


# =========================================================
# الأسباب الافتراضية
# =========================================================

DEFAULT_REASONS = [
    "سب",
    "شتم",
    "إزعاج",
    "استفزاز",
    "مخالفة القوانين",
    "محتوى غير مناسب"
]


# =========================================================
# إعدادات Mongo
# =========================================================

def get_moderation_settings(guild_id: int):

    settings = moderation_settings_collection.find_one(
        {"guild_id": guild_id}
    )

    if not settings:

        settings = {
            "guild_id": guild_id
        }

        moderation_settings_collection.insert_one(
            settings
        )

    return settings


def get_reasons(guild_id: int):

    data = moderation_reasons_collection.find_one(
        {"guild_id": guild_id}
    )

    if not data:

        reasons = list(DEFAULT_REASONS)

        moderation_reasons_collection.insert_one(
            {
                "guild_id": guild_id,
                "reasons": reasons
            }
        )

        return reasons

    reasons = data.get(
        "reasons",
        []
    )

    if not reasons:

        reasons = list(DEFAULT_REASONS)

        moderation_reasons_collection.update_one(
            {"guild_id": guild_id},
            {
                "$set": {
                    "reasons": reasons
                }
            },
            upsert=True
        )

    return reasons


def add_reason(
    guild_id: int,
    reason: str
):

    reason = reason.strip()

    if not reason:
        return False

    reasons = get_reasons(
        guild_id
    )

    # منع التكرار
    if reason in reasons:
        return False

    reasons.append(reason)

    moderation_reasons_collection.update_one(
        {"guild_id": guild_id},
        {
            "$set": {
                "reasons": reasons
            }
        },
        upsert=True
    )

    return True


# =========================================================
# تحليل المدة
#
# أمثلة:
# 10s
# 100s
# 10m
# 2h
# 7d
# 1w
# =========================================================

def parse_duration(value):

    if not value:
        return None

    value = str(value).strip().lower()

    match = re.fullmatch(
        r"(\d+(?:\.\d+)?)\s*(s|sec|secs|m|min|mins|h|hr|hrs|d|day|days|w|week|weeks)",
        value
    )

    if not match:
        return None

    number = float(
        match.group(1)
    )

    unit = match.group(2)

    if number <= 0:
        return None

    if unit in (
        "s",
        "sec",
        "secs"
    ):
        seconds = number

    elif unit in (
        "m",
        "min",
        "mins"
    ):
        seconds = number * 60

    elif unit in (
        "h",
        "hr",
        "hrs"
    ):
        seconds = number * 60 * 60

    elif unit in (
        "d",
        "day",
        "days"
    ):
        seconds = number * 60 * 60 * 24

    elif unit in (
        "w",
        "week",
        "weeks"
    ):
        seconds = number * 60 * 60 * 24 * 7

    else:
        return None

    # Discord timeout maximum = 28 days
    if seconds > 28 * 24 * 60 * 60:
        return None

    return timedelta(
        seconds=seconds
    )


def format_duration(value):

    duration = parse_duration(
        value
    )

    if duration is None:
        return value

    seconds = int(
        duration.total_seconds()
    )

    if seconds < 60:
        return f"{seconds} ثانية"

    if seconds < 3600:
        return f"{seconds // 60} دقيقة"

    if seconds < 86400:
        return f"{seconds // 3600} ساعة"

    if seconds < 604800:
        return f"{seconds // 86400} يوم"

    return f"{seconds // 604800} أسبوع"


# =========================================================
# التحقق من إعدادات الموقع
#
# يستخدم نفس website_command_settings
# =========================================================

async def website_moderation_allowed(
    member,
    command_name
):

    try:

        setting = db[
            "website_command_settings"
        ].find_one(
            {
                "guild_id": member.guild.id,
                "command_name": command_name
            }
        )

        # إذا لم يوجد إعداد في الموقع
        # نرجع إلى صلاحيات Discord الأساسية
        if not setting:
            return True

        # الأمر مغلق من الموقع
        if setting.get(
            "enabled",
            True
        ) is False:

            return False

        # التحقق من الرتب
        role_ids = setting.get(
            "role_ids",
            []
        )

        if role_ids:

            member_role_ids = {
                role.id
                for role in member.roles
            }

            if not member_role_ids.intersection(
                set(role_ids)
            ):

                return False

        # التحقق من الرومات
        channel_ids = setting.get(
            "channel_ids",
            []
        )

        if channel_ids:

            if member.guild.get_channel(
                member.guild.id
            ):
                pass

        return True

    except Exception:

        # لا نمنع النظام بالكامل بسبب خطأ في
        # إعدادات الموقع
        return True


# =========================================================
# فحص صلاحية العضو من الموقع
# مع تمرير الروم الحالي
# =========================================================

async def website_permission_for_interaction(
    member,
    command_name,
    channel_id
):

    try:

        setting = db[
            "website_command_settings"
        ].find_one(
            {
                "guild_id": member.guild.id,
                "command_name": command_name
            }
        )

        if not setting:
            return True

        if setting.get(
            "enabled",
            True
        ) is False:
            return False

        role_ids = setting.get(
            "role_ids",
            []
        )

        if role_ids:

            member_role_ids = {
                role.id
                for role in member.roles
            }

            if not member_role_ids.intersection(
                set(role_ids)
            ):
                return False

        channel_ids = setting.get(
            "channel_ids",
            []
        )

        if channel_ids:

            if channel_id not in channel_ids:
                return False

        return True

    except Exception:

        return True


# =========================================================
# حفظ التحذير
# =========================================================

def save_warning(
    guild_id,
    user_id,
    moderator_id,
    reason
):

    moderation_warnings_collection.insert_one(
        {
            "guild_id": guild_id,
            "user_id": user_id,
            "moderator_id": moderator_id,
            "reason": reason,
            "created_at": discord.utils.utcnow()
        }
    )


def get_warnings(
    guild_id,
    user_id
):

    return list(
        moderation_warnings_collection.find(
            {
                "guild_id": guild_id,
                "user_id": user_id
            }
        ).sort(
            "created_at",
            -1
        )
    )


# =========================================================
# مودال إضافة سبب
# =========================================================

class AddReasonModal(ui.Modal):

    def __init__(
        self,
        moderation_cog,
        member
    ):

        super().__init__(
            title="إضافة سبب إسكات"
        )

        self.moderation_cog = moderation_cog
        self.member = member

        self.reason_input = ui.TextInput(
            label="سبب الإسكات",
            placeholder="مثال: مخالفة القوانين",
            min_length=1,
            max_length=100,
            required=True
        )

        self.add_item(
            self.reason_input
        )

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        allowed = await website_permission_for_interaction(
            interaction.user,
            "لاتتكلم",
            interaction.channel.id
        )

        if not allowed:

            await interaction.response.send_message(
                "❌ ليس لديك صلاحية استخدام هذا الخيار.",
                ephemeral=True
            )

            return

        reason = self.reason_input.value.strip()

        if not reason:

            await interaction.response.send_message(
                "❌ اكتب سببًا صحيحًا.",
                ephemeral=True
            )

            return

        added = add_reason(
            interaction.guild.id,
            reason
        )

        if not added:

            await interaction.response.send_message(
                "⚠️ هذا السبب موجود مسبقًا.",
                ephemeral=True
            )

            return

        await interaction.response.send_message(
            "✅ تم إضافة السبب بنجاح.",
            ephemeral=True
        )

        # إظهار قائمة المدة
        await interaction.followup.send(
            "⏱️ الآن اختر مدة الإسكات:",
            view=DurationView(
                self.moderation_cog,
                self.member,
                reason
            ),
            ephemeral=True
        )


# =========================================================
# مودال مدة مخصصة
# =========================================================

class CustomDurationModal(ui.Modal):

    def __init__(
        self,
        moderation_cog,
        member,
        reason
    ):

        super().__init__(
            title="مدة مخصصة"
        )

        self.moderation_cog = moderation_cog
        self.member = member
        self.reason = reason

        self.duration_input = ui.TextInput(
            label="المدة",
            placeholder="مثال: 100s أو 10m أو 2h أو 7d",
            required=True,
            max_length=30
        )

        self.add_item(
            self.duration_input
        )

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        duration_text = (
            self.duration_input.value
            .strip()
            .lower()
        )

        duration = parse_duration(
            duration_text
        )

        if duration is None:

            await interaction.response.send_message(
                "❌ المدة غير صحيحة.\n"
                "أمثلة: `100s` أو `10m` أو `2h` أو `7d`.",
                ephemeral=True
            )

            return

        await self.moderation_cog.apply_timeout(
            interaction,
            self.member,
            duration,
            self.reason
        )


# =========================================================
# قائمة مدة الإسكات
# =========================================================

class DurationView(ui.View):

    def __init__(
        self,
        moderation_cog,
        member,
        reason
    ):

        super().__init__(
            timeout=180
        )

        self.moderation_cog = moderation_cog
        self.member = member
        self.reason = reason

    @ui.button(
        label="10 ثواني",
        style=discord.ButtonStyle.secondary
    )
    async def ten_seconds(
        self,
        interaction,
        button
    ):

        await self.moderation_cog.apply_timeout(
            interaction,
            self.member,
            timedelta(seconds=10),
            self.reason
        )

    @ui.button(
        label="1 دقيقة",
        style=discord.ButtonStyle.secondary
    )
    async def one_minute(
        self,
        interaction,
        button
    ):

        await self.moderation_cog.apply_timeout(
            interaction,
            self.member,
            timedelta(minutes=1),
            self.reason
        )

    @ui.button(
        label="10 دقائق",
        style=discord.ButtonStyle.primary
    )
    async def ten_minutes(
        self,
        interaction,
        button
    ):

        await self.moderation_cog.apply_timeout(
            interaction,
            self.member,
            timedelta(minutes=10),
            self.reason
        )

    @ui.button(
        label="1 ساعة",
        style=discord.ButtonStyle.primary
    )
    async def one_hour(
        self,
        interaction,
        button
    ):

        await self.moderation_cog.apply_timeout(
            interaction,
            self.member,
            timedelta(hours=1),
            self.reason
        )

    @ui.button(
        label="يوم",
        style=discord.ButtonStyle.success
    )
    async def one_day(
        self,
        interaction,
        button
    ):

        await self.moderation_cog.apply_timeout(
            interaction,
            self.member,
            timedelta(days=1),
            self.reason
        )

    @ui.button(
        label="مدة مخصصة",
        style=discord.ButtonStyle.success
    )
    async def custom(
        self,
        interaction,
        button
    ):

        await interaction.response.send_modal(
            CustomDurationModal(
                self.moderation_cog,
                self.member,
                self.reason
            )
        )


# =========================================================
# قائمة الأسباب
# =========================================================

class ReasonSelectView(ui.View):

    def __init__(
        self,
        moderation_cog,
        member
    ):

        super().__init__(
            timeout=180
        )

        self.moderation_cog = moderation_cog
        self.member = member

        reasons = get_reasons(
            member.guild.id
        )

        options = []

        for index, reason in enumerate(
            reasons[:24]
        ):

            options.append(
                discord.SelectOption(
                    label=reason[:100],
                    value=str(index)
                )
            )

        if not options:

            options.append(
                discord.SelectOption(
                    label="لا توجد أسباب",
                    value="none"
                )
            )

        self.select = ui.Select(
            placeholder="اختر سبب الإسكات",
            options=options
        )

        self.select.callback = (
            self.reason_callback
        )

        self.add_item(
            self.select
        )

        # زر إضافة سبب
        self.add_item(
            AddReasonButton(
                moderation_cog,
                member
            )
        )

    async def reason_callback(
        self,
        interaction
    ):

        value = self.select.values[0]

        if value == "none":

            await interaction.response.send_message(
                "❌ لا توجد أسباب متاحة.",
                ephemeral=True
            )

            return

        reasons = get_reasons(
            self.member.guild.id
        )

        try:
            reason = reasons[
                int(value)
            ]

        except Exception:

            await interaction.response.send_message(
                "❌ تعذر العثور على السبب.",
                ephemeral=True
            )

            return

        await interaction.response.send_message(
            f"⏱️ سبب الإسكات: **{reason}**\nاختر المدة:",
            view=DurationView(
                self.moderation_cog,
                self.member,
                reason
            ),
            ephemeral=True
        )


# =========================================================
# زر إضافة سبب
# =========================================================

class AddReasonButton(
    ui.Button
):

    def __init__(
        self,
        moderation_cog,
        member
    ):

        super().__init__(
            label="إضافة سبب",
            style=discord.ButtonStyle.success,
            emoji="➕"
        )

        self.moderation_cog = moderation_cog
        self.member = member

    async def callback(
        self,
        interaction
    ):

        allowed = await website_permission_for_interaction(
            interaction.user,
            "لاتتكلم",
            interaction.channel.id
        )

        if not allowed:

            await interaction.response.send_message(
                "❌ ليس لديك صلاحية إضافة أسباب من الموقع.",
                ephemeral=True
            )

            return

        await interaction.response.send_modal(
            AddReasonModal(
                self.moderation_cog,
                self.member
            )
        )


# =========================================================
# Cog
# =========================================================

class ModerationCog(commands.Cog):

    def __init__(
        self,
        bot
    ):

        self.bot = bot

    # =====================================================
    # فحص العضو المستهدف
    # =====================================================

    def can_moderate(
        self,
        ctx,
        member
    ):

        if member.id == ctx.author.id:
            return False

        if member.id == ctx.guild.owner_id:
            return False

        if member.top_role >= ctx.author.top_role:
            return False

        if member.top_role >= ctx.guild.me.top_role:
            return False

        return True

    # =====================================================
    # تطبيق الإسكات
    # =====================================================

    async def apply_timeout(
        self,
        interaction,
        member,
        duration,
        reason
    ):

        try:

            await member.timeout(
                duration,
                reason=(
                    f"{reason} | "
                    f"بواسطة {interaction.user}"
                )
            )

            seconds = int(
                duration.total_seconds()
            )

            if seconds < 60:

                duration_text = (
                    f"{seconds} ثانية"
                )

            elif seconds < 3600:

                duration_text = (
                    f"{seconds // 60} دقيقة"
                )

            elif seconds < 86400:

                duration_text = (
                    f"{seconds // 3600} ساعة"
                )

            else:

                duration_text = (
                    f"{seconds // 86400} يوم"
                )

            await interaction.response.send_message(
                (
                    f"🔇 تم إسكات {member.mention}\n"
                    f"📝 السبب: **{reason}**\n"
                    f"⏱️ المدة: **{duration_text}**"
                ),
                ephemeral=False
            )

        except discord.Forbidden:

            await interaction.response.send_message(
                "❌ البوت لا يملك صلاحية إسكات هذا العضو.",
                ephemeral=True
            )

        except Exception as e:

            await interaction.response.send_message(
                f"❌ حدث خطأ:\n`{e}`",
                ephemeral=True
            )

    # =====================================================
    # لاتتكلم
    #
    # الاستخدام:
    # -لاتتكلم @الشخص
    # -لاتتكلم @الشخص 10m
    # =====================================================

    @commands.command(
        name="لاتتكلم"
    )
    async def mute_command(
        self,
        ctx,
        member: discord.Member = None,
        duration: str = None
    ):

        if member is None:

            await ctx.send(
                "❌ استخدم:\n"
                "`-لاتتكلم @الشخص 10m`"
            )

            return

        if not self.can_moderate(
            ctx,
            member
        ):

            await ctx.send(
                "❌ لا يمكنك تطبيق العقوبة على هذا العضو."
            )

            return

        # مدة مكتوبة مباشرة
        if duration:

            parsed = parse_duration(
                duration
            )

            if parsed is None:

                await ctx.send(
                    "❌ المدة غير صحيحة.\n"
                    "مثال: `100s` أو `10m` أو `2h` أو `7d`."
                )

                return

            reason = "إسكات يدوي"

            await member.timeout(
                parsed,
                reason=(
                    f"{reason} | "
                    f"بواسطة {ctx.author}"
                )
            )

            await ctx.send(
                f"🔇 تم إسكات {member.mention} لمدة **{format_duration(duration)}**."
            )

            return

        # بدون مدة → قائمة الأسباب
        embed = discord.Embed(
            title="🔇 إسكات عضو",
            description=(
                f"العضو: {member.mention}\n\n"
                "اختر سبب الإسكات من القائمة."
            ),
            color=discord.Color.orange()
        )

        await ctx.send(
            embed=embed,
            view=ReasonSelectView(
                self,
                member
            )
        )

    # =====================================================
    # احكي
    # =====================================================

    @commands.command(
        name="احكي"
    )
    async def unmute_command(
        self,
        ctx,
        member: discord.Member = None
    ):

        if member is None:

            await ctx.send(
                "❌ استخدم:\n"
                "`-احكي @الشخص`"
            )

            return

        if not self.can_moderate(
            ctx,
            member
        ):

            await ctx.send(
                "❌ لا يمكنك إزالة العقوبة عن هذا العضو."
            )

            return

        try:

            await member.timeout(
                None,
                reason=(
                    f"إزالة الإسكات بواسطة {ctx.author}"
                )
            )

            await ctx.send(
                f"🔊 تم رفع الإسكات عن {member.mention}."
            )

        except discord.Forbidden:

            await ctx.send(
                "❌ البوت لا يملك صلاحية إزالة الإسكات."
            )

        except Exception as e:

            await ctx.send(
                f"❌ حدث خطأ:\n`{e}`"
            )

    # =====================================================
    # باند
    # =====================================================

    @commands.command(
        name="باند"
    )
    async def ban_command(
        self,
        ctx,
        member: discord.Member = None,
        *,
        reason: str = "لا يوجد سبب"
    ):

        if member is None:

            await ctx.send(
                "❌ استخدم:\n"
                "`-باند @الشخص السبب`"
            )

            return

        if not self.can_moderate(
            ctx,
            member
        ):

            await ctx.send(
                "❌ لا يمكنك حظر هذا العضو."
            )

            return

        try:

            await member.ban(
                reason=(
                    f"{reason} | "
                    f"بواسطة {ctx.author}"
                )
            )

            await ctx.send(
                f"🔨 تم حظر {member.mention}.\n"
                f"📝 السبب: **{reason}**"
            )

        except discord.Forbidden:

            await ctx.send(
                "❌ البوت لا يملك صلاحية حظر هذا العضو."
            )

        except Exception as e:

            await ctx.send(
                f"❌ حدث خطأ:\n`{e}`"
            )

    # =====================================================
    # انتهاء التسفير / فك الباند
    #
    # يقبل ID أو منشن
    # =====================================================

    @commands.command(
        name="انتهاء-التسفير",
        aliases=[
            "فك-الباند",
            "انتهاء-الباند"
        ]
    )
    async def unban_command(
        self,
        ctx,
        user_id: str = None
    ):

        if not user_id:

            await ctx.send(
                "❌ استخدم:\n"
                "`-انتهاء-التسفير ID`"
            )

            return

        # استخراج ID من المنشن
        mention_match = re.fullmatch(
            r"<@!?(\d+)>",
            user_id
        )

        if mention_match:
            user_id = mention_match.group(1)

        try:

            user_id = int(
                user_id
            )

        except ValueError:

            await ctx.send(
                "❌ الـ ID غير صحيح."
            )

            return

        try:

            user = await self.bot.fetch_user(
                user_id
            )

            await ctx.guild.unban(
                user,
                reason=(
                    f"فك الحظر بواسطة {ctx.author}"
                )
            )

            await ctx.send(
                f"✅ تم فك حظر **{user}**."
            )

        except discord.NotFound:

            await ctx.send(
                "❌ هذا العضو غير موجود ضمن قائمة المحظورين."
            )

        except discord.Forbidden:

            await ctx.send(
                "❌ البوت لا يملك صلاحية فك الحظر."
            )

        except Exception as e:

            await ctx.send(
                f"❌ حدث خطأ:\n`{e}`"
            )

    # =====================================================
    # طرد
    # =====================================================

    @commands.command(
        name="طرد"
    )
    async def kick_command(
        self,
        ctx,
        member: discord.Member = None,
        *,
        reason: str = "لا يوجد سبب"
    ):

        if member is None:

            await ctx.send(
                "❌ استخدم:\n"
                "`-طرد @الشخص السبب`"
            )

            return

        if not self.can_moderate(
            ctx,
            member
        ):

            await ctx.send(
                "❌ لا يمكنك طرد هذا العضو."
            )

            return

        try:

            await member.kick(
                reason=(
                    f"{reason} | "
                    f"بواسطة {ctx.author}"
                )
            )

            await ctx.send(
                f"👢 تم طرد {member.mention}.\n"
                f"📝 السبب: **{reason}**"
            )

        except discord.Forbidden:

            await ctx.send(
                "❌ البوت لا يملك صلاحية طرد هذا العضو."
            )

        except Exception as e:

            await ctx.send(
                f"❌ حدث خطأ:\n`{e}`"
            )

    # =====================================================
    # تحذير
    # =====================================================

    @commands.command(
        name="تحذير"
    )
    async def warn_command(
        self,
        ctx,
        member: discord.Member = None,
        *,
        reason: str = "لا يوجد سبب"
    ):

        if member is None:

            await ctx.send(
                "❌ استخدم:\n"
                "`-تحذير @الشخص السبب`"
            )

            return

        if not self.can_moderate(
            ctx,
            member
        ):

            await ctx.send(
                "❌ لا يمكنك تحذير هذا العضو."
            )

            return

        save_warning(
            ctx.guild.id,
            member.id,
            ctx.author.id,
            reason
        )

        await ctx.send(
            f"⚠️ تم تحذير {member.mention}.\n"
            f"📝 السبب: **{reason}**"
        )

        try:

            await member.send(
                (
                    f"⚠️ تم تحذيرك في سيرفر **{ctx.guild.name}**.\n"
                    f"📝 السبب: **{reason}**"
                )
            )

        except Exception:
            pass

    # =====================================================
    # عرض التحذيرات
    # =====================================================

    @commands.command(
        name="تحذيرات"
    )
    async def warnings_command(
        self,
        ctx,
        member: discord.Member = None
    ):

        if member is None:
            member = ctx.author

        warnings = get_warnings(
            ctx.guild.id,
            member.id
        )

        if not warnings:

            await ctx.send(
                f"📋 {member.mention} ليس لديه تحذيرات."
            )

            return

        embed = discord.Embed(
            title=f"⚠️ تحذيرات {member}",
            color=discord.Color.orange()
        )

        for index, warning in enumerate(
            warnings[:10],
            start=1
        ):

            moderator = warning.get(
                "moderator_id"
            )

            reason = warning.get(
                "reason",
                "لا يوجد سبب"
            )

            created_at = warning.get(
                "created_at"
            )

            if created_at:

                date_text = discord.utils.format_dt(
                    created_at,
                    style="R"
                )

            else:

                date_text = "غير معروف"

            embed.add_field(
                name=f"التحذير #{index}",
                value=(
                    f"📝 السبب: {reason}\n"
                    f"👮 بواسطة: <@{moderator}>\n"
                    f"🕒 {date_text}"
                ),
                inline=False
            )

        await ctx.send(
            embed=embed
        )

    # =====================================================
    # مسح التحذيرات
    # =====================================================

    @commands.command(
        name="مسح-تحذيرات"
    )
    async def clear_warnings_command(
        self,
        ctx,
        member: discord.Member = None
    ):

        if member is None:

            await ctx.send(
                "❌ استخدم:\n"
                "`-مسح-تحذيرات @الشخص`"
            )

            return

        if not self.can_moderate(
            ctx,
            member
        ):

            await ctx.send(
                "❌ لا يمكنك مسح تحذيرات هذا العضو."
            )

            return

        result = moderation_warnings_collection.delete_many(
            {
                "guild_id": ctx.guild.id,
                "user_id": member.id
            }
        )

        await ctx.send(
            f"✅ تم مسح **{result.deleted_count}** تحذيرًا عن {member.mention}."
        )


# =========================================================
# Setup
# =========================================================

async def setup(bot):

    await bot.add_cog(
        ModerationCog(bot)
    )
