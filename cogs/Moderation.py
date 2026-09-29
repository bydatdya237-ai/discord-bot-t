import os
import re
import asyncio
from datetime import timedelta

import discord
from discord.ext import commands
from discord import ui
from pymongo import MongoClient
from motor.motor_asyncio import AsyncIOMotorClient


# =========================================================
# MongoDB
# =========================================================

MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    raise RuntimeError("MONGO_URI غير موجود في Environment Variables.")

mongo_client = MongoClient(MONGO_URI)
db = mongo_client["discord_bot_db"]

moderation_reasons_collection = db["moderation_reasons"]
moderation_warnings_collection = db["moderation_warnings"]
moderation_mutes_collection = db["moderation_mutes"]

# تخزين إعدادات قفل الرومات المؤقتة
moderation_channel_locks_collection = db["moderation_channel_locks"]


# =========================================================
# MongoDB Async لنظام الموقع
# =========================================================

if MONGO_URI:

    website_mongo_client = AsyncIOMotorClient(
        MONGO_URI
    )

    website_db = website_mongo_client.discord_bot_db

    website_command_settings = (
        website_db.website_command_settings
    )

else:

    website_mongo_client = None
    website_db = None
    website_command_settings = None


# =========================================================
# الأسباب الافتراضية
# =========================================================

DEFAULT_REASONS = [
    "سب",
    "شتم",
    "إزعاج",
    "استفزاز",
    "مخالفة القوانين",
    "محتوى غير مناسب",
]


# =========================================================
# أسماء الأوامر
# =========================================================

COMMAND_MUTE = "لاتتكلم"
COMMAND_UNMUTE = "احكي"
COMMAND_BAN = "باند"
COMMAND_UNBAN = "انتهاء-التسفير"
COMMAND_KICK = "طرد"
COMMAND_WARN = "تحذير"
COMMAND_WARNS = "تحذيرات"
COMMAND_CLEAR_WARNS = "مسح-تحذيرات"
COMMAND_MUTES = "اسكاتات"
COMMAND_CLEAR = "مسح"

COMMAND_LOCK = "قفل"
COMMAND_UNLOCK = "فتح"
COMMAND_HIDE = "اخفاء"
COMMAND_SHOW = "اظهار"


# =========================================================
# دعم guild_id كـ String أو Integer
# =========================================================

def guild_id_variants(guild_id):

    variants = [
        str(guild_id)
    ]

    try:

        variants.append(
            int(guild_id)
        )

    except Exception:
        pass

    return variants


# =========================================================
# جلب إعدادات أمر من الموقع
# =========================================================

async def get_command_setting(
    guild_id,
    command_name
):

    if website_command_settings is None:
        return None

    guild_ids = guild_id_variants(
        guild_id
    )

    setting = await website_command_settings.find_one(
        {
            "guild_id": {
                "$in": guild_ids
            },
            "command_name": str(command_name)
        }
    )

    if setting:
        return setting

    setting = await website_command_settings.find_one(
        {
            "guild_id": {
                "$in": guild_ids
            },
            "name": str(command_name)
        }
    )

    return setting


# =========================================================
# نظام صلاحيات الموقع
# =========================================================

async def website_permission_allowed(
    member: discord.Member,
    command_name: str,
    channel_id: int
):

    if member is None:
        return False

    if member.guild is None:
        return False

    setting = await get_command_setting(
        member.guild.id,
        command_name
    )

    if not setting:
        return False

    if not setting.get(
        "enabled",
        False
    ):
        return False

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

    if not allowed_role_ids.intersection(
        user_role_ids
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

    if str(channel_id) not in allowed_channel_ids:
        return False

    return True


# =========================================================
# جلب رتب الموقع الخاصة بأمر معين
# =========================================================

async def get_website_role_ids(
    guild_id,
    command_name
):

    setting = await get_command_setting(
        guild_id,
        command_name
    )

    if not setting:
        return []

    if not setting.get(
        "enabled",
        False
    ):
        return []

    role_ids = setting.get(
        "role_ids",
        []
    )

    if not role_ids:
        return []

    result = set()

    for role_id in role_ids:

        try:

            result.add(
                int(role_id)
            )

        except (
            TypeError,
            ValueError
        ):

            pass

    return result


# =========================================================
# قفل الروم
#
# يحفظ الـ Override القديم حتى نقدر نرجعه عند فتح الروم
# =========================================================

async def lock_channel(
    channel: discord.abc.GuildChannel,
    allowed_role_ids
):

    guild = channel.guild

    existing_lock = (
        moderation_channel_locks_collection.find_one(
            {
                "guild_id": guild.id,
                "channel_id": channel.id
            }
        )
    )

    # =====================================================
    # إذا الروم مقفول مسبقًا
    # نستخدم الحالة الموجودة
    # =====================================================

    if existing_lock:

        everyone_previous = existing_lock.get(
            "everyone_send_messages"
        )

        role_previous = existing_lock.get(
            "role_send_messages",
            {}
        )

    else:

        everyone_overwrite = channel.overwrites_for(
            guild.default_role
        )

        everyone_previous = (
            everyone_overwrite.send_messages
        )

        role_previous = {}

    # =====================================================
    # حفظ الحالة الأصلية للرتب الجديدة
    # =====================================================

    for role_id in allowed_role_ids:

        role = guild.get_role(
            role_id
        )

        if role is None:
            continue

        role_key = str(
            role.id
        )

        if role_key not in role_previous:

            overwrite = channel.overwrites_for(
                role
            )

            role_previous[role_key] = (
                overwrite.send_messages
            )

    # =====================================================
    # قفل @everyone
    # =====================================================

    everyone_overwrite = channel.overwrites_for(
        guild.default_role
    )

    everyone_overwrite.send_messages = False

    await channel.set_permissions(
        guild.default_role,
        overwrite=everyone_overwrite,
        reason="قفل الروم"
    )

    # =====================================================
    # السماح للرتب المحددة من الموقع
    # =====================================================

    for role_id in allowed_role_ids:

        role = guild.get_role(
            role_id
        )

        if role is None:
            continue

        try:

            overwrite = channel.overwrites_for(
                role
            )

            overwrite.send_messages = True

            await channel.set_permissions(
                role,
                overwrite=overwrite,
                reason="السماح لرتبة محددة بعد قفل الروم"
            )

        except (
            discord.Forbidden,
            discord.HTTPException
        ):

            pass

    # =====================================================
    # حفظ حالة القفل
    # =====================================================

    moderation_channel_locks_collection.update_one(
        {
            "guild_id": guild.id,
            "channel_id": channel.id
        },
        {
            "$set": {
                "guild_id": guild.id,
                "channel_id": channel.id,
                "everyone_send_messages": everyone_previous,
                "role_send_messages": role_previous,
                "allowed_role_ids": list(
                    allowed_role_ids
                )
            }
        },
        upsert=True
    )


# =========================================================
# فتح الروم
# =========================================================

async def unlock_channel(
    channel: discord.abc.GuildChannel
):

    guild = channel.guild

    lock_data = (
        moderation_channel_locks_collection.find_one(
            {
                "guild_id": guild.id,
                "channel_id": channel.id
            }
        )
    )

    # =====================================================
    # استرجاع Override @everyone الأصلي
    # =====================================================

    if lock_data:

        everyone_previous = lock_data.get(
            "everyone_send_messages"
        )

        everyone_overwrite = channel.overwrites_for(
            guild.default_role
        )

        everyone_overwrite.send_messages = (
            everyone_previous
        )

        await channel.set_permissions(
            guild.default_role,
            overwrite=everyone_overwrite,
            reason="فتح الروم"
        )

        # =================================================
        # استرجاع Overrides الرتب التي عدلها القفل
        # =================================================

        role_previous = lock_data.get(
            "role_send_messages",
            {}
        )

        for role_id, previous_value in role_previous.items():

            try:

                role = guild.get_role(
                    int(role_id)
                )

            except (
                TypeError,
                ValueError
            ):

                continue

            if role is None:
                continue

            try:

                overwrite = channel.overwrites_for(
                    role
                )

                overwrite.send_messages = (
                    previous_value
                )

                await channel.set_permissions(
                    role,
                    overwrite=overwrite,
                    reason="استرجاع صلاحيات ما قبل القفل"
                )

            except (
                discord.Forbidden,
                discord.HTTPException
            ):

                pass

        moderation_channel_locks_collection.delete_one(
            {
                "guild_id": guild.id,
                "channel_id": channel.id
            }
        )

        return

    # =====================================================
    # لو ما فيه حالة محفوظة
    # نفتح @everyone
    # =====================================================

    overwrite = channel.overwrites_for(
        guild.default_role
    )

    overwrite.send_messages = True

    await channel.set_permissions(
        guild.default_role,
        overwrite=overwrite,
        reason="فتح الروم"
    )


# =========================================================
# إخفاء الروم
# =========================================================

async def hide_channel(
    channel: discord.abc.GuildChannel,
    allowed_role_ids
):

    guild = channel.guild

    await channel.set_permissions(
        guild.default_role,
        view_channel=False,
        reason="إخفاء الروم"
    )

    for role_id in allowed_role_ids:

        role = guild.get_role(
            role_id
        )

        if role is None:
            continue

        try:

            await channel.set_permissions(
                role,
                view_channel=True,
                reason="السماح لرتبة محددة برؤية الروم"
            )

        except (
            discord.Forbidden,
            discord.HTTPException
        ):

            pass


# =========================================================
# إظهار الروم
# =========================================================

async def show_channel(
    channel: discord.abc.GuildChannel
):

    guild = channel.guild

    await channel.set_permissions(
        guild.default_role,
        view_channel=True,
        reason="إظهار الروم"
    )


# =========================================================
# الأسباب
# =========================================================

def get_reasons(guild_id: int):

    data = moderation_reasons_collection.find_one(
        {
            "guild_id": guild_id
        }
    )

    if not data:

        reasons = DEFAULT_REASONS.copy()

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
        return DEFAULT_REASONS.copy()

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

    normalized_existing = {
        str(item).strip().lower()
        for item in reasons
    }

    if reason.lower() in normalized_existing:
        return False

    moderation_reasons_collection.update_one(
        {
            "guild_id": guild_id
        },
        {
            "$setOnInsert": {
                "guild_id": guild_id
            },
            "$push": {
                "reasons": reason
            }
        },
        upsert=True
    )

    return True


# =========================================================
# تحويل المدة
# =========================================================

def parse_duration(value: str):

    if not value:
        return None

    value = value.strip().lower()

    if not value:
        return None

    pattern = re.compile(
        r"(\d+(?:\.\d+)?)\s*"
        r"(w|week|weeks|"
        r"d|day|days|"
        r"h|hr|hrs|hour|hours|"
        r"m|min|mins|minute|minutes|"
        r"s|sec|secs|second|seconds)"
    )

    matches = list(
        pattern.finditer(value)
    )

    if not matches:
        return None

    rebuilt = "".join(
        match.group(0)
        for match in matches
    )

    normalized_input = re.sub(
        r"\s+",
        "",
        value
    )

    normalized_rebuilt = re.sub(
        r"\s+",
        "",
        rebuilt
    )

    if normalized_input != normalized_rebuilt:
        return None

    total_seconds = 0.0

    for match in matches:

        amount = float(
            match.group(1)
        )

        unit = match.group(2)

        if amount <= 0:
            return None

        if unit in {
            "w",
            "week",
            "weeks"
        }:

            total_seconds += (
                amount * 7 * 24 * 60 * 60
            )

        elif unit in {
            "d",
            "day",
            "days"
        }:

            total_seconds += (
                amount * 24 * 60 * 60
            )

        elif unit in {
            "h",
            "hr",
            "hrs",
            "hour",
            "hours"
        }:

            total_seconds += (
                amount * 60 * 60
            )

        elif unit in {
            "m",
            "min",
            "mins",
            "minute",
            "minutes"
        }:

            total_seconds += (
                amount * 60
            )

        elif unit in {
            "s",
            "sec",
            "secs",
            "second",
            "seconds"
        }:

            total_seconds += amount

        else:

            return None

    max_seconds = 28 * 24 * 60 * 60

    if total_seconds > max_seconds:
        return None

    if total_seconds <= 0:
        return None

    return timedelta(
        seconds=total_seconds
    )


# =========================================================
# عرض المدة
# =========================================================

def format_duration(
    duration: timedelta
):

    total_seconds = int(
        duration.total_seconds()
    )

    days = total_seconds // 86400

    total_seconds %= 86400

    hours = total_seconds // 3600

    total_seconds %= 3600

    minutes = total_seconds // 60

    seconds = total_seconds % 60

    parts = []

    if days:
        parts.append(
            f"{days} يوم"
        )

    if hours:
        parts.append(
            f"{hours} ساعة"
        )

    if minutes:
        parts.append(
            f"{minutes} دقيقة"
        )

    if seconds:
        parts.append(
            f"{seconds} ثانية"
        )

    return (
        " و ".join(parts)
        if parts
        else "0 ثانية"
    )


# =========================================================
# فحص إمكانية الإشراف
# =========================================================

def can_moderate(
    moderator: discord.Member,
    target: discord.Member
):

    if target.id == moderator.id:

        return (
            False,
            "❌ ما تقدر تستخدم الأمر على نفسك."
        )

    if target.id == moderator.guild.owner_id:

        return (
            False,
            "❌ ما تقدر تستخدم الأمر على صاحب السيرفر."
        )

    if moderator.id != moderator.guild.owner_id:

        if target.top_role >= moderator.top_role:

            return (
                False,
                "❌ ما تقدر تستخدم الأمر على شخص رتبته مساوية أو أعلى من رتبتك."
            )

    bot_member = moderator.guild.me

    if bot_member is None:

        return (
            False,
            "❌ ما قدرت أحدد رتبة البوت."
        )

    if target.top_role >= bot_member.top_role:

        return (
            False,
            "❌ رتبة الشخص أعلى من رتبة البوت أو مساوية لها."
        )

    return True, None


# =========================================================
# الإنذارات
# =========================================================

def save_warning(
    guild_id: int,
    user_id: int,
    moderator_id: int,
    reason: str
):

    result = moderation_warnings_collection.insert_one(
        {
            "guild_id": guild_id,
            "user_id": user_id,
            "moderator_id": moderator_id,
            "reason": reason,
            "created_at": discord.utils.utcnow()
        }
    )

    return result.inserted_id


def get_warnings(
    guild_id: int,
    user_id: int
):

    return list(
        moderation_warnings_collection.find(
            {
                "guild_id": guild_id,
                "user_id": user_id
            }
        ).sort(
            [
                ("created_at", -1)
            ]
        )
    )


# =========================================================
# الإسكاتات
# =========================================================

def save_mute(
    guild_id: int,
    user_id: int,
    moderator_id: int,
    reason: str,
    duration: timedelta
):

    now = discord.utils.utcnow()

    expires_at = now + duration

    result = moderation_mutes_collection.insert_one(
        {
            "guild_id": guild_id,
            "user_id": user_id,
            "moderator_id": moderator_id,
            "reason": reason,
            "duration_seconds": int(
                duration.total_seconds()
            ),
            "created_at": now,
            "expires_at": expires_at
        }
    )

    return result.inserted_id


def get_mutes(
    guild_id: int,
    user_id: int
):

    return list(
        moderation_mutes_collection.find(
            {
                "guild_id": guild_id,
                "user_id": user_id
            }
        ).sort(
            [
                ("created_at", -1)
            ]
        )
    )


# =========================================================
# نظام صفحات التحذيرات والإسكاتات
# =========================================================

class ModerationPagesView(ui.View):

    def __init__(
        self,
        member,
        records,
        command_name
    ):

        super().__init__(
            timeout=300
        )

        self.member = member
        self.records = records
        self.command_name = command_name
        self.current_page = 0

        self.previous_button = ui.Button(
            label="السابق",
            emoji="⬅️",
            style=discord.ButtonStyle.secondary
        )

        self.next_button = ui.Button(
            label="التالي",
            emoji="➡️",
            style=discord.ButtonStyle.primary
        )

        self.delete_button = ui.Button(
            label="حذف السجل",
            emoji="🗑️",
            style=discord.ButtonStyle.danger
        )

        self.previous_button.callback = (
            self.previous_page
        )

        self.next_button.callback = (
            self.next_page
        )

        self.delete_button.callback = (
            self.delete_current
        )

        self.add_item(
            self.previous_button
        )

        self.add_item(
            self.next_button
        )

        self.add_item(
            self.delete_button
        )

        self.update_buttons()

    # =====================================================
    # تحديث الأزرار
    # =====================================================

    def update_buttons(self):

        self.previous_button.disabled = (
            self.current_page <= 0
        )

        self.next_button.disabled = (
            self.current_page >= len(self.records) - 1
        )

        self.delete_button.disabled = (
            len(self.records) == 0
        )

    # =====================================================
    # بناء Embed
    # =====================================================

    def build_embed(self):

        record = self.records[
            self.current_page
        ]

        record_type = record.get(
            "_record_type",
            "warning"
        )

        guild = self.member.guild

        moderator = guild.get_member(
            record.get("moderator_id")
        )

        moderator_name = (
            moderator.mention
            if moderator
            else f"`{record.get('moderator_id')}`"
        )

        reason = record.get(
            "reason",
            "لا يوجد سبب"
        )

        created_at = record.get(
            "created_at"
        )

        if created_at:

            created_text = discord.utils.format_dt(
                created_at,
                style="R"
            )

        else:

            created_text = "غير معروف"

        # =================================================
        # تحذير
        # =================================================

        if record_type == "warning":

            embed = discord.Embed(
                title="⚠️ سجل التحذيرات",
                description=(
                    f"👤 **الشخص:** {self.member.mention}\n\n"
                    f"📝 **السبب:** {reason}\n"
                    f"👮 **بواسطة:** {moderator_name}\n"
                    f"🕐 **الوقت:** {created_text}"
                ),
                color=discord.Color.orange()
            )

        # =================================================
        # إسكات
        # =================================================

        else:

            duration_seconds = record.get(
                "duration_seconds",
                0
            )

            duration = timedelta(
                seconds=int(
                    duration_seconds
                )
            )

            expires_at = record.get(
                "expires_at"
            )

            if expires_at:

                expires_text = discord.utils.format_dt(
                    expires_at,
                    style="R"
                )

            else:

                expires_text = "غير معروف"

            embed = discord.Embed(
                title="🔇 سجل الإسكاتات",
                description=(
                    f"👤 **الشخص:** {self.member.mention}\n\n"
                    f"📝 **السبب:** {reason}\n"
                    f"⏱️ **المدة:** {format_duration(duration)}\n"
                    f"👮 **بواسطة:** {moderator_name}\n"
                    f"🕐 **بدأ:** {created_text}\n"
                    f"⏳ **ينتهي:** {expires_text}"
                ),
                color=discord.Color.red()
            )

        embed.set_footer(
            text=(
                f"الصفحة {self.current_page + 1}"
                f" من {len(self.records)}"
            )
        )

        return embed

    # =====================================================
    # التحقق من الصلاحية
    # =====================================================

    async def interaction_check(
        self,
        interaction: discord.Interaction
    ):

        allowed = await website_permission_allowed(
            interaction.user,
            self.command_name,
            interaction.channel.id
        )

        if not allowed:

            await interaction.response.send_message(
                "❌ ما عندك صلاحية استخدام هذا الأمر.",
                ephemeral=True
            )

            return False

        return True

    # =====================================================
    # السابق
    # =====================================================

    async def previous_page(
        self,
        interaction: discord.Interaction
    ):

        if self.current_page > 0:

            self.current_page -= 1

        self.update_buttons()

        await interaction.response.edit_message(
            embed=self.build_embed(),
            view=self
        )

    # =====================================================
    # التالي
    # =====================================================

    async def next_page(
        self,
        interaction: discord.Interaction
    ):

        if self.current_page < len(self.records) - 1:

            self.current_page += 1

        self.update_buttons()

        await interaction.response.edit_message(
            embed=self.build_embed(),
            view=self
        )

    # =====================================================
    # حذف السجل الحالي
    # =====================================================

    async def delete_current(
        self,
        interaction: discord.Interaction
    ):

        if not self.records:
            return

        record = self.records[
            self.current_page
        ]

        record_type = record.get(
            "_record_type",
            "warning"
        )

        record_id = record.get(
            "_id"
        )

        if record_type == "warning":

            collection = (
                moderation_warnings_collection
            )

        else:

            collection = (
                moderation_mutes_collection
            )

        result = collection.delete_one(
            {
                "_id": record_id,
                "guild_id": interaction.guild.id,
                "user_id": self.member.id
            }
        )

        if result.deleted_count == 0:

            await interaction.response.send_message(
                "⚠️ هذا السجل محذوف مسبقًا.",
                ephemeral=True
            )

            return

        # =================================================
        # إذا كان إسكاتًا
        # =================================================

        if record_type == "mute":

            member = interaction.guild.get_member(
                self.member.id
            )

            if member:

                try:

                    await member.timeout(
                        None,
                        reason="حذف سجل الإسكات"
                    )

                except (
                    discord.Forbidden,
                    discord.HTTPException
                ):

                    pass

        # =================================================
        # حذف من القائمة الحالية
        # =================================================

        self.records.pop(
            self.current_page
        )

        if not self.records:

            self.stop()

            await interaction.response.edit_message(
                content="✅ تم حذف آخر سجل.",
                embed=None,
                view=None
            )

            return

        if self.current_page >= len(
            self.records
        ):

            self.current_page = (
                len(self.records) - 1
            )

        self.update_buttons()

        await interaction.response.edit_message(
            embed=self.build_embed(),
            view=self
        )

    # =====================================================
    # انتهاء مدة الأزرار
    # =====================================================

    async def on_timeout(self):

        for child in self.children:

            child.disabled = True

        try:

            if hasattr(self, "message") and self.message:

                await self.message.edit(
                    view=self
                )

        except (
            discord.NotFound,
            discord.HTTPException
        ):

            pass


# =========================================================
# مودال إضافة سبب
# =========================================================

class AddReasonModal(ui.Modal):

    def __init__(
        self,
        target: discord.Member
    ):

        super().__init__(
            title="إضافة سبب إسكات"
        )

        self.target = target

        self.reason_input = ui.TextInput(
            label="السبب الجديد",
            placeholder="اكتب سبب الإسكات...",
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

        if interaction.guild is None:

            await interaction.response.send_message(
                "❌ تعذر تحديد السيرفر.",
                ephemeral=True
            )

            return

        allowed = await website_permission_allowed(
            interaction.user,
            COMMAND_MUTE,
            interaction.channel.id
        )

        if not allowed:

            await interaction.response.send_message(
                "❌ ما عندك صلاحية استخدام إضافة أسباب الإسكات.",
                ephemeral=True
            )

            return

        reason = self.reason_input.value.strip()

        if not reason:

            await interaction.response.send_message(
                "❌ اكتب سبب صحيح.",
                ephemeral=True
            )

            return

        added = add_reason(
            interaction.guild.id,
            reason
        )

        if not added:

            await interaction.response.send_message(
                "❌ هذا السبب موجود مسبقًا.",
                ephemeral=True
            )

            return

        await interaction.response.send_message(
            f"✅ تمت إضافة السبب **{reason}**.",
            ephemeral=True
        )

        try:

            await interaction.followup.send(
                f"اختر مدة إسكات {self.target.mention}:",
                view=DurationView(
                    moderator=interaction.user,
                    target=self.target,
                    reason=reason
                ),
                ephemeral=True
            )

        except Exception:
            pass


# =========================================================
# مودال المدة المخصصة
# =========================================================

class CustomDurationModal(ui.Modal):

    def __init__(
        self,
        moderator,
        target,
        reason
    ):

        super().__init__(
            title="مدة مخصصة"
        )

        self.moderator = moderator
        self.target = target
        self.reason = reason

        self.duration_input = ui.TextInput(
            label="المدة",
            placeholder="مثال: 5m20s أو 1h30m أو 2d5h",
            max_length=50,
            required=True
        )

        self.add_item(
            self.duration_input
        )

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        if interaction.guild is None:

            await interaction.response.send_message(
                "❌ تعذر تحديد السيرفر.",
                ephemeral=True
            )

            return

        allowed = await website_permission_allowed(
            interaction.user,
            COMMAND_MUTE,
            interaction.channel.id
        )

        if not allowed:

            await interaction.response.send_message(
                "❌ ما عندك صلاحية استخدام أمر الإسكات.",
                ephemeral=True
            )

            return

        duration = parse_duration(
            self.duration_input.value
        )

        if duration is None:

            await interaction.response.send_message(
                "❌ المدة غير صحيحة.\n\n"
                "أمثلة:\n"
                "`5m20s`\n"
                "`1h30m`\n"
                "`2d5h20m10s`\n"
                "`1w2d3h4m5s`\n\n"
                "الحد الأقصى 28 يوم.",
                ephemeral=True
            )

            return

        cog = interaction.client.get_cog(
            "ModerationCog"
        )

        if cog is None:

            await interaction.response.send_message(
                "❌ تعذر الوصول لنظام الحماية.",
                ephemeral=True
            )

            return

        await cog.apply_timeout(
            interaction,
            self.target,
            duration,
            self.reason
        )


# =========================================================
# قائمة المدة
# =========================================================

class DurationView(ui.View):

    def __init__(
        self,
        moderator,
        target,
        reason
    ):

        super().__init__(
            timeout=120
        )

        self.moderator = moderator
        self.target = target
        self.reason = reason

    async def interaction_check(
        self,
        interaction: discord.Interaction
    ):

        if interaction.user.id != self.moderator.id:

            await interaction.response.send_message(
                "❌ هذه القائمة ليست لك.",
                ephemeral=True
            )

            return False

        allowed = await website_permission_allowed(
            interaction.user,
            COMMAND_MUTE,
            interaction.channel.id
        )

        if not allowed:

            await interaction.response.send_message(
                "❌ ما عندك صلاحية استخدام أمر الإسكات.",
                ephemeral=True
            )

            return False

        return True

    async def apply(
        self,
        interaction,
        seconds,
        label
    ):

        duration = timedelta(
            seconds=seconds
        )

        cog = interaction.client.get_cog(
            "ModerationCog"
        )

        if cog is None:

            await interaction.response.send_message(
                "❌ تعذر الوصول لنظام الحماية.",
                ephemeral=True
            )

            return

        await cog.apply_timeout(
            interaction,
            self.target,
            duration,
            self.reason
        )

    @ui.button(
        label="10 ثواني",
        style=discord.ButtonStyle.secondary
    )
    async def ten_seconds(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await self.apply(
            interaction,
            10,
            "10 ثواني"
        )

    @ui.button(
        label="1 دقيقة",
        style=discord.ButtonStyle.primary
    )
    async def one_minute(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await self.apply(
            interaction,
            60,
            "1 دقيقة"
        )

    @ui.button(
        label="10 دقائق",
        style=discord.ButtonStyle.primary
    )
    async def ten_minutes(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await self.apply(
            interaction,
            600,
            "10 دقائق"
        )

    @ui.button(
        label="1 ساعة",
        style=discord.ButtonStyle.primary
    )
    async def one_hour(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await self.apply(
            interaction,
            3600,
            "1 ساعة"
        )

    @ui.button(
        label="1 يوم",
        style=discord.ButtonStyle.primary
    )
    async def one_day(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await self.apply(
            interaction,
            86400,
            "1 يوم"
        )

    @ui.button(
        label="مدة مخصصة",
        style=discord.ButtonStyle.success,
        row=2
    )
    async def custom_duration(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.send_modal(
            CustomDurationModal(
                moderator=interaction.user,
                target=self.target,
                reason=self.reason
            )
        )


# =========================================================
# قائمة الأسباب
# =========================================================

class ReasonSelect(ui.Select):

    def __init__(
        self,
        target: discord.Member
    ):

        self.target = target

        reasons = get_reasons(
            target.guild.id
        )

        options = []

        for index, reason in enumerate(
            reasons[:24]
        ):

            options.append(
                discord.SelectOption(
                    label=str(reason)[:100],
                    value=str(index)
                )
            )

        super().__init__(
            placeholder="اختر سبب الإسكات...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        if interaction.guild is None:

            await interaction.response.send_message(
                "❌ تعذر تحديد السيرفر.",
                ephemeral=True
            )

            return

        allowed = await website_permission_allowed(
            interaction.user,
            COMMAND_MUTE,
            interaction.channel.id
        )

        if not allowed:

            await interaction.response.send_message(
                "❌ ما عندك صلاحية استخدام أمر الإسكات.",
                ephemeral=True
            )

            return

        reasons = get_reasons(
            self.target.guild.id
        )

        index = int(
            self.values[0]
        )

        if index >= len(reasons):

            await interaction.response.send_message(
                "❌ السبب غير موجود.",
                ephemeral=True
            )

            return

        reason = reasons[index]

        await interaction.response.send_message(
            f"تم اختيار السبب: **{reason}**\n"
            f"الآن اختر مدة الإسكات:",
            view=DurationView(
                moderator=interaction.user,
                target=self.target,
                reason=reason
            ),
            ephemeral=True
        )


# =========================================================
# زر إضافة سبب
# =========================================================

class AddReasonButton(ui.Button):

    def __init__(
        self,
        target: discord.Member
    ):

        super().__init__(
            label="إضافة سبب",
            style=discord.ButtonStyle.success,
            row=1
        )

        self.target = target

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        if interaction.guild is None:

            await interaction.response.send_message(
                "❌ تعذر تحديد السيرفر.",
                ephemeral=True
            )

            return

        allowed = await website_permission_allowed(
            interaction.user,
            COMMAND_MUTE,
            interaction.channel.id
        )

        if not allowed:

            await interaction.response.send_message(
                "❌ ما عندك صلاحية إضافة أسباب.",
                ephemeral=True
            )

            return

        await interaction.response.send_modal(
            AddReasonModal(
                target=self.target
            )
        )


# =========================================================
# View الأسباب
# =========================================================

class ReasonView(ui.View):

    def __init__(
        self,
        target: discord.Member
    ):

        super().__init__(
            timeout=120
        )

        self.add_item(
            ReasonSelect(target)
        )

        self.add_item(
            AddReasonButton(target)
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
    # تطبيق الإسكات
    # =====================================================

    async def apply_timeout(
        self,
        interaction: discord.Interaction,
        target: discord.Member,
        duration: timedelta,
        reason: str
    ):

        moderator = interaction.user

        allowed, error = can_moderate(
            moderator,
            target
        )

        if not allowed:

            await interaction.response.send_message(
                error,
                ephemeral=True
            )

            return

        try:

            await target.timeout(
                duration,
                reason=reason
            )

        except discord.Forbidden:

            await interaction.response.send_message(
                "❌ البوت ما عنده صلاحية إسكات هذا الشخص، أو رتبة البوت أقل منه.",
                ephemeral=True
            )

            return

        except discord.HTTPException:

            await interaction.response.send_message(
                "❌ حصل خطأ أثناء تنفيذ الإسكات.",
                ephemeral=True
            )

            return

        save_mute(
            guild_id=interaction.guild.id,
            user_id=target.id,
            moderator_id=moderator.id,
            reason=reason,
            duration=duration
        )

        await interaction.response.send_message(
            f"🔇 تم إسكات {target.mention}\n"
            f"**المدة:** {format_duration(duration)}\n"
            f"**السبب:** {reason}",
            ephemeral=False
        )

    # =====================================================
    # قفل
    # =====================================================

    @commands.command(
        name=COMMAND_LOCK
    )
    async def lock_command(
        self,
        ctx
    ):

        if not await website_permission_allowed(
            ctx.author,
            COMMAND_LOCK,
            ctx.channel.id
        ):

            return

        if not ctx.guild:
            return

        permissions = ctx.channel.permissions_for(
            ctx.guild.me
        )

        if not permissions.manage_channels:

            await ctx.send(
                "❌ البوت ما عنده صلاحية **Manage Channels** في هذا الروم."
            )

            return

        try:

            allowed_role_ids = await get_website_role_ids(
                ctx.guild.id,
                COMMAND_LOCK
            )

            await lock_channel(
                ctx.channel,
                allowed_role_ids
            )

        except discord.Forbidden:

            await ctx.send(
                "❌ البوت ما عنده صلاحية تعديل صلاحيات هذا الروم."
            )

            return

        except discord.HTTPException:

            await ctx.send(
                "❌ حصل خطأ أثناء قفل الروم."
            )

            return

        await ctx.send(
            "🔒 تم قفل الروم."
        )

    # =====================================================
    # فتح
    # =====================================================

    @commands.command(
        name=COMMAND_UNLOCK
    )
    async def unlock_command(
        self,
        ctx
    ):

        if not await website_permission_allowed(
            ctx.author,
            COMMAND_UNLOCK,
            ctx.channel.id
        ):

            return

        if not ctx.guild:
            return

        permissions = ctx.channel.permissions_for(
            ctx.guild.me
        )

        if not permissions.manage_channels:

            await ctx.send(
                "❌ البوت ما عنده صلاحية **Manage Channels** في هذا الروم."
            )

            return

        try:

            await unlock_channel(
                ctx.channel
            )

        except discord.Forbidden:

            await ctx.send(
                "❌ البوت ما عنده صلاحية تعديل صلاحيات هذا الروم."
            )

            return

        except discord.HTTPException:

            await ctx.send(
                "❌ حصل خطأ أثناء فتح الروم."
            )

            return

        await ctx.send(
            "🔓 تم فتح الروم للجميع."
        )

    # =====================================================
    # اخفاء
    # =====================================================

    @commands.command(
        name=COMMAND_HIDE
    )
    async def hide_command(
        self,
        ctx
    ):

        if not await website_permission_allowed(
            ctx.author,
            COMMAND_HIDE,
            ctx.channel.id
        ):

            return

        if not ctx.guild:
            return

        permissions = ctx.channel.permissions_for(
            ctx.guild.me
        )

        if not permissions.manage_channels:

            await ctx.send(
                "❌ البوت ما عنده صلاحية **Manage Channels** في هذا الروم."
            )

            return

        try:

            allowed_role_ids = await get_website_role_ids(
                ctx.guild.id,
                COMMAND_HIDE
            )

            await hide_channel(
                ctx.channel,
                allowed_role_ids
            )

        except discord.Forbidden:

            await ctx.send(
                "❌ البوت ما عنده صلاحية تعديل صلاحيات هذا الروم."
            )

            return

        except discord.HTTPException:

            await ctx.send(
                "❌ حصل خطأ أثناء إخفاء الروم."
            )

            return

        await ctx.send(
            "👻 تم إخفاء الروم."
        )

    # =====================================================
    # اظهار
    # =====================================================

    @commands.command(
        name=COMMAND_SHOW
    )
    async def show_command(
        self,
        ctx
    ):

        if not await website_permission_allowed(
            ctx.author,
            COMMAND_SHOW,
            ctx.channel.id
        ):

            return

        if not ctx.guild:
            return

        permissions = ctx.channel.permissions_for(
            ctx.guild.me
        )

        if not permissions.manage_channels:

            await ctx.send(
                "❌ البوت ما عنده صلاحية **Manage Channels** في هذا الروم."
            )

            return

        try:

            await show_channel(
                ctx.channel
            )

        except discord.Forbidden:

            await ctx.send(
                "❌ البوت ما عنده صلاحية تعديل صلاحيات هذا الروم."
            )

            return

        except discord.HTTPException:

            await ctx.send(
                "❌ حصل خطأ أثناء إظهار الروم."
            )

            return

        await ctx.send(
            "👁️ تم إظهار الروم للجميع."
        )

    # =====================================================
    # لاتتكلم
    # =====================================================

    @commands.command(
        name="لاتتكلم"
    )
    async def mute_command(
        self,
        ctx,
        member: discord.Member = None,
        duration_text: str = None
    ):

        if not await website_permission_allowed(
            ctx.author,
            COMMAND_MUTE,
            ctx.channel.id
        ):

            return

        if member is None:

            await ctx.send(
                "❌ استخدم الأمر هكذا:\n"
                "`-لاتتكلم @الشخص 10m`"
            )

            return

        allowed, error = can_moderate(
            ctx.author,
            member
        )

        if not allowed:

            await ctx.send(
                error
            )

            return

        if duration_text:

            duration = parse_duration(
                duration_text
            )

            if duration is None:

                await ctx.send(
                    "❌ المدة غير صحيحة.\n\n"
                    "أمثلة:\n"
                    "`10s`\n"
                    "`5m20s`\n"
                    "`1h30m`\n"
                    "`2d5h20m10s`\n"
                    "`1w2d3h`\n\n"
                    "الحد الأقصى 28 يوم."
                )

                return

            try:

                await member.timeout(
                    duration,
                    reason="إسكات يدوي"
                )

            except discord.Forbidden:

                await ctx.send(
                    "❌ البوت ما يقدر يسكت هذا الشخص. "
                    "تأكد أن رتبة البوت أعلى منه."
                )

                return

            except discord.HTTPException:

                await ctx.send(
                    "❌ حصل خطأ أثناء تنفيذ الإسكات."
                )

                return

            save_mute(
                guild_id=ctx.guild.id,
                user_id=member.id,
                moderator_id=ctx.author.id,
                reason="إسكات يدوي",
                duration=duration
            )

            await ctx.send(
                f"🔇 تم إسكات {member.mention}\n"
                f"**المدة:** {format_duration(duration)}\n"
                f"**السبب:** إسكات يدوي"
            )

            return

        await ctx.send(
            f"🔇 اختر سبب إسكات {member.mention}:",
            view=ReasonView(member)
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

        if not await website_permission_allowed(
            ctx.author,
            COMMAND_UNMUTE,
            ctx.channel.id
        ):

            return

        if member is None:

            await ctx.send(
                "❌ استخدم الأمر هكذا:\n"
                "`-احكي @الشخص`"
            )

            return

        allowed, error = can_moderate(
            ctx.author,
            member
        )

        if not allowed:

            await ctx.send(
                error
            )

            return

        try:

            await member.timeout(
                None,
                reason="إلغاء الإسكات"
            )

        except discord.Forbidden:

            await ctx.send(
                "❌ البوت ما عنده صلاحية فك الإسكات."
            )

            return

        except discord.HTTPException:

            await ctx.send(
                "❌ حصل خطأ أثناء فك الإسكات."
            )

            return

        await ctx.send(
            f"🔊 تم فك الإسكات عن {member.mention}."
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

        if not await website_permission_allowed(
            ctx.author,
            COMMAND_BAN,
            ctx.channel.id
        ):

            return

        if member is None:

            await ctx.send(
                "❌ استخدم الأمر هكذا:\n"
                "`-باند @الشخص السبب`"
            )

            return

        allowed, error = can_moderate(
            ctx.author,
            member
        )

        if not allowed:

            await ctx.send(
                error
            )

            return

        try:

            await member.ban(
                reason=reason,
                delete_message_days=0
            )

        except discord.Forbidden:

            await ctx.send(
                "❌ البوت ما عنده صلاحية تبنيد هذا الشخص."
            )

            return

        except discord.HTTPException:

            await ctx.send(
                "❌ حصل خطأ أثناء التبنيد."
            )

            return

        await ctx.send(
            f"🔨 تم تبنيد {member.mention}\n"
            f"**السبب:** {reason}"
        )

    # =====================================================
    # انتهاء التسفير
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
        user_input: str = None
    ):

        if not await website_permission_allowed(
            ctx.author,
            COMMAND_UNBAN,
            ctx.channel.id
        ):

            return

        if not user_input:

            await ctx.send(
                "❌ استخدم الأمر هكذا:\n"
                "`-انتهاء-التسفير ID`"
            )

            return

        user_id_match = re.search(
            r"\d{15,25}",
            user_input
        )

        if not user_id_match:

            await ctx.send(
                "❌ ما قدرت أتعرف على ID الشخص."
            )

            return

        user_id = int(
            user_id_match.group()
        )

        try:

            user = await self.bot.fetch_user(
                user_id
            )

        except discord.NotFound:

            await ctx.send(
                "❌ هذا المستخدم غير موجود."
            )

            return

        except discord.HTTPException:

            await ctx.send(
                "❌ حصل خطأ أثناء جلب المستخدم."
            )

            return

        try:

            await ctx.guild.unban(
                user,
                reason=f"فك الباند بواسطة {ctx.author}"
            )

        except discord.NotFound:

            await ctx.send(
                "❌ هذا الشخص غير موجود في قائمة المبندين."
            )

            return

        except discord.Forbidden:

            await ctx.send(
                "❌ البوت ما عنده صلاحية فك الباند."
            )

            return

        except discord.HTTPException:

            await ctx.send(
                "❌ حصل خطأ أثناء فك الباند."
            )

            return

        await ctx.send(
            f"🔓 تم فك الباند عن **{user}**."
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

        if not await website_permission_allowed(
            ctx.author,
            COMMAND_KICK,
            ctx.channel.id
        ):

            return

        if member is None:

            await ctx.send(
                "❌ استخدم الأمر هكذا:\n"
                "`-طرد @الشخص السبب`"
            )

            return

        allowed, error = can_moderate(
            ctx.author,
            member
        )

        if not allowed:

            await ctx.send(
                error
            )

            return

        try:

            await member.kick(
                reason=reason
            )

        except discord.Forbidden:

            await ctx.send(
                "❌ البوت ما عنده صلاحية طرد هذا الشخص."
            )

            return

        except discord.HTTPException:

            await ctx.send(
                "❌ حصل خطأ أثناء الطرد."
            )

            return

        await ctx.send(
            f"👢 تم طرد {member.mention}\n"
            f"**السبب:** {reason}"
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

        if not await website_permission_allowed(
            ctx.author,
            COMMAND_WARN,
            ctx.channel.id
        ):

            return

        if member is None:

            await ctx.send(
                "❌ استخدم الأمر هكذا:\n"
                "`-تحذير @الشخص السبب`"
            )

            return

        allowed, error = can_moderate(
            ctx.author,
            member
        )

        if not allowed:

            await ctx.send(
                error
            )

            return

        save_warning(
            guild_id=ctx.guild.id,
            user_id=member.id,
            moderator_id=ctx.author.id,
            reason=reason
        )

        try:

            await member.send(
                f"⚠️ تم تحذيرك في سيرفر **{ctx.guild.name}**.\n"
                f"**السبب:** {reason}"
            )

        except discord.HTTPException:

            pass

        warnings = get_warnings(
            ctx.guild.id,
            member.id
        )

        await ctx.send(
            f"⚠️ تم تحذير {member.mention}.\n"
            f"**السبب:** {reason}\n"
            f"**عدد التحذيرات:** {len(warnings)}"
        )

    # =====================================================
    # تحذيرات - صفحات
    # =====================================================

    @commands.command(
        name="تحذيرات"
    )
    async def warnings_command(
        self,
        ctx,
        member: discord.Member = None
    ):

        if not await website_permission_allowed(
            ctx.author,
            COMMAND_WARNS,
            ctx.channel.id
        ):

            return

        if member is None:

            await ctx.send(
                "❌ استخدم الأمر هكذا:\n"
                "`تحذيرات @الشخص`"
            )

            return

        warnings = get_warnings(
            ctx.guild.id,
            member.id
        )

        if not warnings:

            await ctx.send(
                f"✅ {member.mention} ما عليه أي تحذيرات."
            )

            return

        # =================================================
        # تحديد نوع كل سجل
        # =================================================

        for warning in warnings:

            warning["_record_type"] = "warning"

        view = ModerationPagesView(
            member=member,
            records=warnings,
            command_name=COMMAND_WARNS
        )

        message = await ctx.send(
            embed=view.build_embed(),
            view=view
        )

        view.message = message

    # =====================================================
    # اسكاتات - صفحات
    # =====================================================

    @commands.command(
        name="اسكاتات"
    )
    async def mutes_command(
        self,
        ctx,
        member: discord.Member = None
    ):

        if not await website_permission_allowed(
            ctx.author,
            COMMAND_MUTES,
            ctx.channel.id
        ):

            return

        if member is None:

            await ctx.send(
                "❌ استخدم الأمر هكذا:\n"
                "`اسكاتات @الشخص`"
            )

            return

        warnings = get_warnings(
            ctx.guild.id,
            member.id
        )

        mutes = get_mutes(
            ctx.guild.id,
            member.id
        )

        if not warnings and not mutes:

            await ctx.send(
                f"✅ {member.mention} ما عليه أي "
                "تحذيرات أو إسكاتات محفوظة."
            )

            return

        # =================================================
        # تحويل السجلات إلى نظام موحد
        # =================================================

        records = []

        for warning in warnings:

            warning["_record_type"] = "warning"

            records.append(
                warning
            )

        for mute in mutes:

            mute["_record_type"] = "mute"

            records.append(
                mute
            )

        # =================================================
        # ترتيب كل السجلات من الأحدث إلى الأقدم
        # =================================================

        records.sort(
            key=lambda record: (
                record.get("created_at").timestamp()
                if record.get("created_at")
                else 0
            ),
            reverse=True
        )

        view = ModerationPagesView(
            member=member,
            records=records,
            command_name=COMMAND_MUTES
        )

        message = await ctx.send(
            embed=view.build_embed(),
            view=view
        )

        view.message = message

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

        if not await website_permission_allowed(
            ctx.author,
            COMMAND_CLEAR_WARNS,
            ctx.channel.id
        ):

            return

        if member is None:

            await ctx.send(
                "❌ استخدم الأمر هكذا:\n"
                "`-مسح-تحذيرات @الشخص`"
            )

            return

        deleted = moderation_warnings_collection.delete_many(
            {
                "guild_id": ctx.guild.id,
                "user_id": member.id
            }
        )

        await ctx.send(
            f"🧹 تم مسح **{deleted.deleted_count}** "
            f"تحذير عن {member.mention}."
        )

    # =====================================================
    # مسح الرسائل
    # =====================================================

    @commands.command(
        name="مسح"
    )
    async def clear_messages_command(
        self,
        ctx,
        amount: int = None
    ):

        if not await website_permission_allowed(
            ctx.author,
            COMMAND_CLEAR,
            ctx.channel.id
        ):

            return

        if amount is None:

            await ctx.send(
                "❌ استخدم الأمر هكذا:\n"
                "`مسح 100`"
            )

            return

        if amount <= 0:

            await ctx.send(
                "❌ لازم تكتب رقم أكبر من 0."
            )

            return

        if not ctx.channel.permissions_for(
            ctx.guild.me
        ).manage_messages:

            await ctx.send(
                "❌ البوت ما عنده صلاحية **Manage Messages** في هذا الروم."
            )

            return

        amount = min(
            amount,
            100000
        )

        status_message = await ctx.send(
            f"🧹 جاري مسح **{amount:,}** رسالة..."
        )

        try:

            messages = []

            async for message in ctx.channel.history(
                limit=amount
            ):

                messages.append(
                    message
                )

            if not messages:

                await status_message.edit(
                    content="ℹ️ ما لقيت أي رسائل لمسحها."
                )

                return

            now = discord.utils.utcnow()

            fourteen_days = timedelta(
                days=14
            )

            recent_messages = []
            old_messages = []

            for message in messages:

                age = now - message.created_at

                if age < fourteen_days:

                    recent_messages.append(
                        message
                    )

                else:

                    old_messages.append(
                        message
                    )

            deleted_count = 0

            for index in range(
                0,
                len(recent_messages),
                100
            ):

                chunk = recent_messages[
                    index:index + 100
                ]

                if not chunk:
                    continue

                try:

                    if len(chunk) == 1:

                        await chunk[0].delete()

                    else:

                        await ctx.channel.delete_messages(
                            chunk
                        )

                    deleted_count += len(
                        chunk
                    )

                except discord.HTTPException:

                    for message in chunk:

                        try:

                            await message.delete()

                            deleted_count += 1

                        except (
                            discord.NotFound,
                            discord.Forbidden,
                            discord.HTTPException
                        ):

                            pass

            for message in old_messages:

                try:

                    await message.delete()

                    deleted_count += 1

                except (
                    discord.NotFound,
                    discord.Forbidden,
                    discord.HTTPException
                ):

                    pass

            try:

                if ctx.message.id not in {
                    message.id
                    for message in messages
                }:

                    await ctx.message.delete()

            except (
                discord.NotFound,
                discord.Forbidden,
                discord.HTTPException
            ):

                pass

            await status_message.edit(
                content=(
                    f"🧹 **تم الانتهاء من المسح!**\n\n"
                    f"🗑️ تم حذف: **{deleted_count:,}** رسالة."
                )
            )

            try:

                await asyncio.sleep(
                    5
                )

                await status_message.delete()

            except (
                discord.NotFound,
                discord.Forbidden,
                discord.HTTPException
            ):

                pass

        except discord.Forbidden:

            await status_message.edit(
                content=(
                    "❌ البوت ما عنده صلاحية حذف الرسائل."
                )
            )

        except discord.HTTPException:

            await status_message.edit(
                content=(
                    "❌ حصل خطأ من Discord أثناء مسح الرسائل.\n"
                    "إذا كان العدد ضخم جدًا حاول تقسيمه على أكثر من عملية."
                )
            )

        except Exception as error:

            print(
                f"[CLEAR ERROR] {error}"
            )

            await status_message.edit(
                content=(
                    "❌ حصل خطأ غير متوقع أثناء مسح الرسائل."
                )
            )


# =========================================================
# Setup
# =========================================================

async def setup(bot):

    await bot.add_cog(
        ModerationCog(bot)
    )
