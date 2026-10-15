
import os
import re
import logging
import asyncio
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import discord
from discord.ext import commands
from pymongo import MongoClient


# =========================================================
# 1. CONFIGURATION
# =========================================================

# آيدي السيرفر المسموح للنظام بالعمل داخله فقط
ALLOWED_GUILD_ID = 1545572112134312027

# خمس رتب تجريبية — استبدلها بآيديات رتبك
AUTHORIZED_ROLE_IDS = {
    1551939466799751199,
    1551940776156725310,
    123456789012345603,
    123456789012345604,
    123456789012345605,
}

# الرومات التي تتم مراقبتها
MONITORED_CHANNEL_IDS = {
    1552446589191323709,
    1545572112692027607,
    1545572112692027606,
}

# روم طلبات مراجعة المخالفات
REQUEST_CHANNEL_ID = 1559250431467856052

# روم السجلات الأمنية
SECURITY_LOG_CHANNEL_ID = 1558805768969523272

# رومات لا تتم مراقبة رسائلها
EXEMPT_CHANNEL_IDS = {
    REQUEST_CHANNEL_ID,
    SECURITY_LOG_CHANNEL_ID,
}

# إعدادات مراقبة الرسائل
SPAM_LIMIT = 6
SPAM_WINDOW_SECONDS = 5
MENTION_LIMIT = 5
WARNING_HOURS = 24

# أضف الكلمات التي تريد مراقبتها
BAD_WORDS = {
    "كس",
}

# النطاقات المسموح بها دون رفع طلب رابط
ALLOWED_DOMAINS = {
    "discord.com",
    "discord.gg",
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("security_center")


# =========================================================
# 2. HELPERS
# =========================================================

def now_utc():
    return datetime.now(timezone.utc)


def safe_text(value, limit=900):
    return discord.utils.escape_mentions(str(value))[:limit]


def has_security_role(member):
    if not isinstance(member, discord.Member):
        return False

    if member.id == member.guild.owner_id:
        return True

    return any(
        role.id in AUTHORIZED_ROLE_IDS
        for role in member.roles
    )


def is_exempt(member):
    return (
        member.guild_permissions.administrator
        or has_security_role(member)
    )


def contains_link(text):
    return bool(re.search(
        r"(?:https?://|www\.)\S+",
        text,
        re.IGNORECASE
    ))


def suspicious_link(text):
    links = re.findall(
        r"(?:https?://|www\.)[^\s<>]+",
        text,
        re.IGNORECASE
    )

    for link in links:
        link = link.rstrip(".,!?)]}")
        domain = link.split("://")[-1].split("/")[0]
        domain = domain.split("@")[-1].split(":")[0].lower()

        if domain.startswith("www."):
            domain = domain[4:]

        allowed = any(
            domain == item or domain.endswith("." + item)
            for item in ALLOWED_DOMAINS
        )

        if not allowed:
            return True

    return False


def contains_bad_word(text):
    lowered = text.casefold()

    return any(
        word.strip().casefold() in lowered
        for word in BAD_WORDS
        if word.strip()
    )


# =========================================================
# 3. REVIEW BUTTONS
# =========================================================

class SecurityRequestView(discord.ui.View):
    def __init__(self, cog, request_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.request_id = request_id

        approve = discord.ui.Button(
            label="اعتماد الطلب",
            style=discord.ButtonStyle.success,
            custom_id=f"sec:approve:{request_id}"
        )
        approve.callback = self.approve_request
        self.add_item(approve)

        reject = discord.ui.Button(
            label="رفض الطلب",
            style=discord.ButtonStyle.danger,
            custom_id=f"sec:reject:{request_id}"
        )
        reject.callback = self.reject_request
        self.add_item(reject)

    async def interaction_check(self, interaction):
        if interaction.guild_id != ALLOWED_GUILD_ID:
            await interaction.response.send_message(
                "هذا النظام غير مفعّل في هذا السيرفر.",
                ephemeral=True
            )
            return False

        if not has_security_role(interaction.user):
            await interaction.response.send_message(
                "لا تملك رتبة مخولة لمراجعة الطلبات.",
                ephemeral=True
            )
            return False

        return True

    async def approve_request(self, interaction):
        await self.cog.review_request(
            interaction, self.request_id, "approved"
        )

    async def reject_request(self, interaction):
        await self.cog.review_request(
            interaction, self.request_id, "rejected"
        )


# =========================================================
# 4. SECURITY CENTER COG
# =========================================================

class SecurityCenter(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        mongo_uri = os.getenv("MONGO_URI")
        if not mongo_uri:
            raise RuntimeError("MONGO_URI غير مضبوط.")

        self.mongo = MongoClient(
            mongo_uri,
            serverSelectionTimeoutMS=5000
        )

        db = self.mongo["discord_bot_db"]
        self.events = db["security_events"]
        self.requests = db["security_requests"]

        self.message_times = defaultdict(deque)
        self.recent_incidents = {}
        self.processing = set()

    async def cog_load(self):
        # استعادة أزرار الطلبات المفتوحة
        pending = list(self.requests.find({
            "guild_id": ALLOWED_GUILD_ID,
            "status": "pending"
        }))

        for item in pending:
            request_id = item.get("request_id")
            if request_id:
                self.bot.add_view(
                    SecurityRequestView(self, request_id)
                )

    async def get_channel(self, channel_id):
        channel = self.bot.get_channel(channel_id)

        if channel is not None:
            return channel

        try:
            return await self.bot.fetch_channel(channel_id)
        except (discord.NotFound, discord.Forbidden,
                discord.HTTPException):
            return None

    async def log_event(self, guild, event_type, details):
        # حاجز السيرفر: لا تسجّل أحداث أي سيرفر آخر
        if guild.id != ALLOWED_GUILD_ID:
            return

        self.events.insert_one({
            "guild_id": guild.id,
            "type": event_type,
            "details": details,
            "created_at": now_utc(),
        })

        channel = await self.get_channel(
            SECURITY_LOG_CHANNEL_ID
        )

        if not isinstance(channel, discord.TextChannel):
            return

        embed = discord.Embed(
            title="Security Center | سجل أمني",
            color=discord.Color.from_rgb(182, 108, 255),
            timestamp=now_utc()
        )
        embed.add_field(
            name="الحدث",
            value=safe_text(event_type),
            inline=False
        )
        embed.add_field(
            name="التفاصيل",
            value=safe_text(details),
            inline=False
        )
        embed.add_field(
            name="السيرفر",
            value=safe_text(guild.name),
            inline=False
        )

        try:
            await channel.send(
                embed=embed,
                allowed_mentions=discord.AllowedMentions.none()
            )
        except discord.HTTPException:
            logger.exception("فشل إرسال السجل")

    async def warn_member(self, member, reason):
        expiry = now_utc() + timedelta(hours=WARNING_HOURS)

        embed = discord.Embed(
            title="تنبيه أمني",
            description=(
                f"تم رصد مخالفة محتملة في سيرفر "
                f"**{safe_text(member.guild.name, 100)}**."
            ),
            color=discord.Color.orange(),
            timestamp=now_utc()
        )
        embed.add_field(
            name="السبب",
            value=safe_text(reason),
            inline=False
        )
        embed.add_field(
            name="المهلة المذكورة",
            value=f"{WARNING_HOURS} ساعة",
            inline=True
        )
        embed.add_field(
            name="موعد انتهاء المهلة",
            value=discord.utils.format_dt(expiry, style="F"),
            inline=False
        )
        embed.set_footer(
            text="تنبيه فقط؛ لا يتم تنفيذ حظر تلقائي."
        )

        try:
            await member.send(embed=embed)
            return True
        except (discord.Forbidden, discord.HTTPException):
            return False

    async def create_request(
        self, message, reason, suggested_action
    ):
        if message.guild.id != ALLOWED_GUILD_ID:
            return

        key = (
            message.guild.id,
            message.author.id,
            reason
        )
        now = now_utc()

        previous = self.recent_incidents.get(key)
        if previous and (now - previous).total_seconds() < 60:
            return

        self.recent_incidents[key] = now
        request_id = uuid4().hex[:12]

        record = {
            "request_id": request_id,
            "guild_id": message.guild.id,
            "user_id": message.author.id,
            "channel_id": message.channel.id,
            "message_id": message.id,
            "reason": reason,
            "evidence": (message.content or "")[:1500],
            "suggested_action": suggested_action,
            "status": "pending",
            "created_at": now,
            "reviewed_by": None,
            "reviewed_at": None,
        }

        self.requests.insert_one(record)

        channel = await self.get_channel(REQUEST_CHANNEL_ID)
        if not isinstance(channel, discord.TextChannel):
            await self.log_event(
                message.guild,
                "REQUEST_CHANNEL_ERROR",
                f"تعذر الوصول إلى روم الطلبات. رقم الطلب: {request_id}"
            )
            return

        embed = discord.Embed(
            title="طلب مراجعة مخالفة",
            color=discord.Color.from_rgb(182, 108, 255),
            timestamp=now
        )
        embed.add_field(
            name="رقم الطلب",
            value=f"`{request_id}`",
            inline=True
        )
        embed.add_field(
            name="العضو",
            value=f"{message.author.mention} (`{message.author.id}`)",
            inline=False
        )
        embed.add_field(
            name="الروم",
            value=message.channel.mention,
            inline=True
        )
        embed.add_field(
            name="المخالفة",
            value=safe_text(reason),
            inline=False
        )
        embed.add_field(
            name="الإجراء المقترح",
            value=safe_text(suggested_action),
            inline=False
        )
        embed.add_field(
            name="الأدلة",
            value=safe_text(message.content or "لا يوجد نص", 900),
            inline=False
        )
        embed.add_field(
            name="الرسالة الأصلية",
            value=f"[فتح الرسالة]({message.jump_url})",
            inline=False
        )
        embed.set_footer(
            text="الطلب للمراجعة فقط. لا تنفذ عقوبة تلقائيًا."
        )

        self.bot.add_view(
            SecurityRequestView(self, request_id)
        )

        try:
            await channel.send(
                embed=embed,
                view=SecurityRequestView(self, request_id),
                allowed_mentions=discord.AllowedMentions.none()
            )
        except discord.HTTPException:
            logger.exception("فشل نشر طلب المراجعة")

        await self.log_event(
            message.guild,
            "VIOLATION_DETECTED",
            f"{reason} | العضو {message.author.id} | الطلب {request_id}"
        )

    async def review_request(
        self, interaction, request_id, decision
    ):
        if interaction.guild_id != ALLOWED_GUILD_ID:
            await interaction.response.send_message(
                "السيرفر غير مسموح.",
                ephemeral=True
            )
            return

        result = self.requests.update_one(
            {
                "request_id": request_id,
                "guild_id": ALLOWED_GUILD_ID,
                "status": "pending"
            },
            {"$set": {
                "status": decision,
                "reviewed_by": interaction.user.id,
                "reviewed_at": now_utc(),
            }}
        )

        if result.modified_count == 0:
            await interaction.response.send_message(
                "الطلب غير موجود أو تمت مراجعته مسبقًا.",
                ephemeral=True
            )
            return

        label = (
            "تم اعتماد الطلب للمراجعة الإدارية"
            if decision == "approved"
            else "تم رفض الطلب"
        )

        await interaction.response.edit_message(
            content=(
                f"**{label}**\n"
                f"المراجع: {interaction.user.mention}\n"
                f"رقم الطلب: `{request_id}`"
            ),
            view=None
        )

        await self.log_event(
            interaction.guild,
            "REQUEST_REVIEWED",
            f"الطلب {request_id} | القرار {decision} | "
            f"المراجع {interaction.user.id}"
        )

    # =====================================================
    # MESSAGE MONITOR — SERVER + CHANNEL RESTRICTED
    # =====================================================

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild is None:
            return

        if message.guild.id != ALLOWED_GUILD_ID:
            return

        if message.author.bot:
            return

        if not isinstance(message.author, discord.Member):
            return

        if message.channel.id not in MONITORED_CHANNEL_IDS:
            return

        if message.channel.id in EXEMPT_CHANNEL_IDS:
            return

        if is_exempt(message.author):
            return

        content = message.content or ""
        violations = []

        if contains_link(content) and suspicious_link(content):
            violations.append((
                "رابط يحتاج إلى مراجعة",
                "مراجعة الرابط والسياق؛ تحديد الإجراء بعد المراجعة"
            ))

        if contains_bad_word(content):
            violations.append((
                "لغة مسيئة محتملة",
                "مراجعة السياق وتحديد الإجراء المناسب"
            ))

        if len(message.mentions) >= MENTION_LIMIT:
            violations.append((
                "منشن جماعي",
                "مراجعة إساءة استخدام المنشن"
            ))

        key = (message.guild.id, message.author.id)
        clock = asyncio.get_running_loop().time()
        queue = self.message_times[key]
        queue.append(clock)

        while queue and clock - queue[0] > SPAM_WINDOW_SECONDS:
            queue.popleft()

        if len(queue) >= SPAM_LIMIT:
            violations.append((
                "رسائل متكررة بسرعة",
                "مراجعة السبام وتحديد الإجراء المناسب"
            ))
            queue.clear()

        for reason, suggested in violations:
            lock_key = (message.id, reason)

            if lock_key in self.processing:
                continue

            self.processing.add(lock_key)

            try:
                sent = await self.warn_member(
                    message.author, reason
                )

                await self.create_request(
                    message, reason, suggested
                )

                await self.log_event(
                    message.guild,
                    "WARNING_SENT" if sent else "DM_FAILED",
                    f"{reason} | العضو {message.author.id}"
                )
            finally:
                self.processing.discard(lock_key)

    # =====================================================
    # AUDIT EVENTS — ONLY THE ALLOWED GUILD
    # =====================================================

    async def audit_actor(self, guild, action, target_id):
        if guild.id != ALLOWED_GUILD_ID:
            return None

        try:
            async for entry in guild.audit_logs(
                limit=6, action=action
            ):
                if (
                    getattr(entry.target, "id", None) == target_id
                    and (now_utc() - entry.created_at).total_seconds() < 30
                ):
                    return entry.user
        except (discord.Forbidden, discord.HTTPException):
            pass

        return None

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        if channel.guild.id != ALLOWED_GUILD_ID:
            return

        actor = await self.audit_actor(
            channel.guild,
            discord.AuditLogAction.channel_delete,
            channel.id
        )

        await self.log_event(
            channel.guild,
            "CHANNEL_DELETED",
            f"الروم {channel.name} ({channel.id}) | "
            f"المنفذ المحتمل: {getattr(actor, 'id', 'غير معروف')}"
        )

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        if role.guild.id != ALLOWED_GUILD_ID:
            return

        actor = await self.audit_actor(
            role.guild,
            discord.AuditLogAction.role_delete,
            role.id
        )

        await self.log_event(
            role.guild,
            "ROLE_DELETED",
            f"الرتبة {role.name} ({role.id}) | "
            f"المنفذ المحتمل: {getattr(actor, 'id', 'غير معروف')}"
        )

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel):
        if channel.guild.id != ALLOWED_GUILD_ID:
            return

        await self.log_event(
            channel.guild,
            "WEBHOOKS_CHANGED",
            f"تغيير في Webhooks للروم {channel.name} ({channel.id}). "
            "يحتاج إلى مراجعة سجل التدقيق."
        )


async def setup(bot):
    await bot.add_cog(SecurityCenter(bot))
