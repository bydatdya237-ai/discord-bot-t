import os
import re
import asyncio
import logging
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import discord
from discord.ext import commands
from pymongo import MongoClient


# =========================================================
# 1. CONFIGURATION
# =========================================================

# السيرفر الوحيد الذي يعمل فيه النظام
ALLOWED_GUILD_ID = 1545572112134312027

# الرتب المخولة بمراجعة طلبات الحماية
# استبدل أي آيدي تجريبي بالآيدي الحقيقي للرتبة
AUTHORIZED_ROLE_IDS = {
    1551939466799751199,
    1551940776156725310,
    123456789012345603,
    123456789012345604,
    123456789012345605,
}

# روم طلبات مراجعة المخالفات
REQUEST_CHANNEL_ID = 1559250431467856052

# روم السجلات الأمنية
SECURITY_LOG_CHANNEL_ID = 1558805768969523272

# رومات مستثناة من فحص الرسائل فقط
# أضف هنا أي روم لا تريد مراقبته
EXEMPT_CHANNEL_IDS = {
    REQUEST_CHANNEL_ID,
    SECURITY_LOG_CHANNEL_ID,
}

# مراقبة السبام
SPAM_LIMIT = 6
SPAM_WINDOW_SECONDS = 5

# مراقبة المنشنات الجماعية
MENTION_LIMIT = 5

# مهلة التحذير المذكورة في الرسالة فقط
WARNING_HOURS = 24

# مراقبة الانضمامات المتسارعة
JOIN_LIMIT = 8
JOIN_WINDOW_SECONDS = 30

# مدة منع تكرار طلب المخالفة نفسها للعضو
INCIDENT_COOLDOWN_SECONDS = 60

# ضع الكلمات والعبارات التي تريد رصدها
# انتبه: المطابقة الجزئية قد ترصد الكلمة داخل كلمة أطول
BAD_WORDS = {
    "تتت",
}

# نطاقات لا ترفع طلب مراجعة بسببها
# جميع النطاقات الأخرى المكتشفة ترفع طلب مراجعة
ALLOWED_DOMAINS = {
    "discord.com",
    "discord.gg",
}

# حد النصوص المحفوظة في السجلات
MAX_EVIDENCE_LENGTH = 1500

# ألوان النظام
PURPLE = discord.Color.from_rgb(182, 108, 255)
ORANGE = discord.Color.orange()
RED = discord.Color.red()
GREEN = discord.Color.green()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("security_center")


# =========================================================
# 2. HELPERS
# =========================================================

def now_utc():
    return datetime.now(timezone.utc)


def safe_text(value, limit=900):
    text = discord.utils.escape_mentions(str(value))
    return text[:limit] if text else "غير متوفر"


def has_security_role(member):
    if not isinstance(member, discord.Member):
        return False

    if member.guild.owner_id == member.id:
        return True

    return any(
        role.id in AUTHORIZED_ROLE_IDS
        for role in member.roles
    )


def is_exempt(member):
    if not isinstance(member, discord.Member):
        return True

    return (
        member.guild_permissions.administrator
        or has_security_role(member)
    )


def contains_link(text):
    return bool(
        re.search(
            r"(?:https?://|www\.)\S+",
            text,
            re.IGNORECASE,
        )
    )


def suspicious_link(text):
    links = re.findall(
        r"(?:https?://|www\.)[^\s<>]+",
        text,
        re.IGNORECASE,
    )

    for link in links:
        link = link.rstrip(".,!?)]}\"'")

        if link.lower().startswith("www."):
            host = link.split("/", 1)[0]
        else:
            host = link.split("://", 1)[-1].split("/", 1)[0]

        host = host.split("?", 1)[0]
        host = host.split("#", 1)[0]
        host = host.split("@")[-1]
        host = host.split(":")[0].lower().rstrip(".")

        if host.startswith("www."):
            host = host[4:]

        allowed = any(
            host == domain or host.endswith("." + domain)
            for domain in ALLOWED_DOMAINS
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


def is_exempt_channel(channel):
    channel_id = getattr(channel, "id", None)
    parent_id = getattr(channel, "parent_id", None)

    return (
        channel_id in EXEMPT_CHANNEL_IDS
        or parent_id in EXEMPT_CHANNEL_IDS
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
            emoji="✅",
            style=discord.ButtonStyle.success,
            custom_id=f"sec:approve:{request_id}",
        )
        approve.callback = self.approve_request
        self.add_item(approve)

        reject = discord.ui.Button(
            label="رفض الطلب",
            emoji="❌",
            style=discord.ButtonStyle.danger,
            custom_id=f"sec:reject:{request_id}",
        )
        reject.callback = self.reject_request
        self.add_item(reject)

    async def interaction_check(self, interaction):
        if interaction.guild_id != ALLOWED_GUILD_ID:
            await interaction.response.send_message(
                "هذا النظام غير مفعّل في هذا السيرفر.",
                ephemeral=True,
            )
            return False

        if not has_security_role(interaction.user):
            await interaction.response.send_message(
                "لا تملك رتبة مخولة لمراجعة الطلبات.",
                ephemeral=True,
            )
            return False

        return True

    async def approve_request(self, interaction):
        await self.cog.review_request(
            interaction,
            self.request_id,
            "approved",
        )

    async def reject_request(self, interaction):
        await self.cog.review_request(
            interaction,
            self.request_id,
            "rejected",
        )


# =========================================================
# 4. SECURITY CENTER
# =========================================================

class SecurityCenter(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        mongo_uri = os.getenv("MONGO_URI")
        if not mongo_uri:
            raise RuntimeError(
                "متغير البيئة MONGO_URI غير مضبوط."
            )

        self.mongo = MongoClient(
            mongo_uri,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
        )

        db = self.mongo["discord_bot_db"]

        self.events = db["security_events"]
        self.requests = db["security_requests"]

        # طوابير السبام لكل عضو
        self.message_times = defaultdict(deque)

        # آخر وقت لإنشاء طلب لكل عضو ونوع مخالفة
        self.recent_incidents = {}

        # منع معالجة الحدث نفسه بالتزامن
        self.processing = set()

        # مراقبة الانضمامات
        self.join_times = defaultdict(deque)
        self.raid_alert_times = {}

    async def cog_load(self):
        # استعادة أزرار الطلبات المفتوحة عند إعادة تشغيل البوت
        try:
            pending = await asyncio.to_thread(
                lambda: list(
                    self.requests.find({
                        "guild_id": ALLOWED_GUILD_ID,
                        "status": "pending",
                    })
                )
            )

            for item in pending:
                request_id = item.get("request_id")

                if request_id:
                    self.bot.add_view(
                        SecurityRequestView(self, request_id)
                    )

            logger.info(
                "Security Center loaded. Pending requests: %s",
                len(pending),
            )

        except Exception:
            logger.exception(
                "تعذر استعادة الطلبات المفتوحة من MongoDB"
            )

    def cog_unload(self):
        try:
            self.mongo.close()
        except Exception:
            logger.exception("تعذر إغلاق اتصال MongoDB")

    async def get_channel(self, channel_id):
        channel = self.bot.get_channel(channel_id)

        if channel is not None:
            return channel

        try:
            return await self.bot.fetch_channel(channel_id)

        except (
            discord.NotFound,
            discord.Forbidden,
            discord.HTTPException,
        ):
            logger.warning(
                "تعذر الوصول إلى القناة %s",
                channel_id,
            )
            return None

    async def send_log_embed(self, guild, embed):
        if guild.id != ALLOWED_GUILD_ID:
            return

        channel = await self.get_channel(
            SECURITY_LOG_CHANNEL_ID
        )

        if not isinstance(channel, discord.TextChannel):
            logger.error(
                "روم السجلات الأمنية غير متاح: %s",
                SECURITY_LOG_CHANNEL_ID,
            )
            return

        try:
            await channel.send(
                embed=embed,
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except discord.HTTPException:
            logger.exception("فشل إرسال السجل الأمني")

    async def log_event(self, guild, event_type, details):
        if guild is None or guild.id != ALLOWED_GUILD_ID:
            return

        try:
            await asyncio.to_thread(
                self.events.insert_one,
                {
                    "guild_id": guild.id,
                    "type": event_type,
                    "details": str(details)[:3000],
                    "created_at": now_utc(),
                },
            )
        except Exception:
            logger.exception("فشل حفظ الحدث في MongoDB")

        embed = discord.Embed(
            title="Security Center | سجل أمني",
            color=PURPLE,
            timestamp=now_utc(),
        )
        embed.add_field(
            name="الحدث",
            value=safe_text(event_type),
            inline=False,
        )
        embed.add_field(
            name="التفاصيل",
            value=safe_text(details),
            inline=False,
        )
        embed.add_field(
            name="السيرفر",
            value=safe_text(guild.name, 200),
            inline=False,
        )

        await self.send_log_embed(guild, embed)

    async def warn_member(self, member, reason):
        expiry = now_utc() + timedelta(
            hours=WARNING_HOURS
        )

        embed = discord.Embed(
            title="⚠️ تنبيه أمني",
            description=(
                f"تم رصد مخالفة محتملة في سيرفر "
                f"**{safe_text(member.guild.name, 100)}**."
            ),
            color=ORANGE,
            timestamp=now_utc(),
        )
        embed.add_field(
            name="السبب",
            value=safe_text(reason),
            inline=False,
        )
        embed.add_field(
            name="المهلة المذكورة",
            value=f"{WARNING_HOURS} ساعة",
            inline=True,
        )
        embed.add_field(
            name="موعد انتهاء المهلة",
            value=discord.utils.format_dt(
                expiry,
                style="F",
            ),
            inline=False,
        )
        embed.set_footer(
            text="تنبيه فقط؛ لا توجد عقوبة تلقائية عند انتهاء المهلة."
        )

        try:
            await member.send(
                embed=embed,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return True

        except discord.Forbidden:
            logger.info(
                "تعذر إرسال الخاص إلى العضو %s",
                member.id,
            )
            return False

        except discord.HTTPException:
            logger.exception(
                "فشل إرسال التحذير إلى العضو %s",
                member.id,
            )
            return False

    # =====================================================
    # CREATE REVIEW REQUEST
    # =====================================================

    async def create_request(
        self,
        message,
        reason,
        suggested_action,
    ):
        guild = message.guild

        if guild is None or guild.id != ALLOWED_GUILD_ID:
            return False

        key = (
            guild.id,
            message.author.id,
            reason,
        )
        current_time = now_utc()

        previous = self.recent_incidents.get(key)

        if (
            previous
            and (
                current_time - previous
            ).total_seconds() < INCIDENT_COOLDOWN_SECONDS
        ):
            return False

        self.recent_incidents[key] = current_time

        # تنظيف البيانات القديمة حتى لا تكبر الذاكرة باستمرار
        stale_keys = [
            old_key
            for old_key, old_time in self.recent_incidents.items()
            if (
                current_time - old_time
            ).total_seconds() > INCIDENT_COOLDOWN_SECONDS * 5
        ]

        for old_key in stale_keys:
            self.recent_incidents.pop(old_key, None)

        request_id = uuid4().hex[:12]

        record = {
            "request_id": request_id,
            "guild_id": guild.id,
            "user_id": message.author.id,
            "channel_id": message.channel.id,
            "message_id": message.id,
            "reason": reason,
            "evidence": (
                message.content or ""
            )[:MAX_EVIDENCE_LENGTH],
            "suggested_action": suggested_action,
            "status": "pending",
            "created_at": current_time,
            "reviewed_by": None,
            "reviewed_at": None,
        }

        try:
            await asyncio.to_thread(
                self.requests.insert_one,
                record,
            )
        except Exception:
            logger.exception(
                "تعذر حفظ طلب المراجعة %s",
                request_id,
            )
            return False

        channel = await self.get_channel(
            REQUEST_CHANNEL_ID
        )

        if not isinstance(channel, discord.TextChannel):
            await self.log_event(
                guild,
                "REQUEST_CHANNEL_ERROR",
                f"تعذر الوصول إلى روم الطلبات. رقم الطلب: {request_id}",
            )
            return True

        embed = discord.Embed(
            title="🚨 طلب مراجعة مخالفة",
            description=(
                "تم رصد مخالفة محتملة. "
                "يرجى مراجعة الأدلة قبل اتخاذ القرار."
            ),
            color=PURPLE,
            timestamp=current_time,
        )

        embed.add_field(
            name="رقم الطلب",
            value=f"`{request_id}`",
            inline=True,
        )
        embed.add_field(
            name="الحالة",
            value="بانتظار المراجعة",
            inline=True,
        )
        embed.add_field(
            name="العضو",
            value=(
                f"{message.author.mention}\n"
                f"`{message.author.id}`"
            ),
            inline=False,
        )
        embed.add_field(
            name="الروم",
            value=f"<#{message.channel.id}>",
            inline=True,
        )
        embed.add_field(
            name="المخالفة",
            value=safe_text(reason),
            inline=False,
        )
        embed.add_field(
            name="الإجراء المقترح",
            value=safe_text(suggested_action),
            inline=False,
        )
        embed.add_field(
            name="الأدلة",
            value=safe_text(
                message.content or "لا يوجد نص",
                900,
            ),
            inline=False,
        )
        embed.add_field(
            name="الرسالة الأصلية",
            value=f"[فتح الرسالة]({message.jump_url})",
            inline=False,
        )
        embed.set_footer(
            text="القرار للإدارة فقط؛ لا تنفذ عقوبة تلقائية."
        )

        view = SecurityRequestView(self, request_id)

        # تسجيل الـ View لاستمرار الأزرار بعد إعادة التشغيل
        self.bot.add_view(
            SecurityRequestView(self, request_id)
        )

        try:
            await channel.send(
                embed=embed,
                view=view,
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except discord.HTTPException:
            logger.exception(
                "فشل نشر طلب المراجعة %s",
                request_id,
            )

            await self.log_event(
                guild,
                "REQUEST_SEND_FAILED",
                f"تعذر إرسال الطلب {request_id} إلى روم المراجعة.",
            )

        await self.log_event(
            guild,
            "VIOLATION_DETECTED",
            (
                f"{reason} | العضو {message.author.id} "
                f"| الطلب {request_id}"
            ),
        )

        return True

    # =====================================================
    # REVIEW REQUEST
    # =====================================================

    async def review_request(
        self,
        interaction,
        request_id,
        decision,
    ):
        if interaction.guild_id != ALLOWED_GUILD_ID:
            await interaction.response.send_message(
                "السيرفر غير مسموح.",
                ephemeral=True,
            )
            return

        if not has_security_role(interaction.user):
            await interaction.response.send_message(
                "ليست لديك صلاحية مراجعة الطلبات.",
                ephemeral=True,
            )
            return

        try:
            result = await asyncio.to_thread(
                self.requests.update_one,
                {
                    "request_id": request_id,
                    "guild_id": ALLOWED_GUILD_ID,
                    "status": "pending",
                },
                {
                    "$set": {
                        "status": decision,
                        "reviewed_by": interaction.user.id,
                        "reviewed_at": now_utc(),
                    }
                },
            )
        except Exception:
            logger.exception(
                "فشل تحديث طلب المراجعة %s",
                request_id,
            )
            await interaction.response.send_message(
                "تعذر حفظ القرار بسبب مشكلة في قاعدة البيانات.",
                ephemeral=True,
            )
            return

        if result.modified_count == 0:
            await interaction.response.send_message(
                "الطلب غير موجود أو تمت مراجعته مسبقًا.",
                ephemeral=True,
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
                f"رقم الطلب: `{request_id}`\n\n"
                "لم ينفذ النظام حظرًا أو عقوبة تلقائية."
            ),
            view=None,
        )

        await self.log_event(
            interaction.guild,
            "REQUEST_REVIEWED",
            (
                f"الطلب {request_id} | القرار {decision} "
                f"| المراجع {interaction.user.id}"
            ),
        )

    # =====================================================
    # MESSAGE ANALYSIS
    # =====================================================

    async def inspect_message(self, message):
        if message.guild is None:
            return

        if message.guild.id != ALLOWED_GUILD_ID:
            return

        if message.author.bot:
            return

        if not isinstance(message.author, discord.Member):
            return

        # كل الرومات مراقبة تلقائيًا، باستثناء المستثناة
        if is_exempt_channel(message.channel):
            return

        if is_exempt(message.author):
            return

        content = message.content or ""
        violations = []

        # 1. الروابط الخارجية
        if contains_link(content) and suspicious_link(content):
            violations.append((
                "رابط يحتاج إلى مراجعة",
                "مراجعة الرابط والسياق وتحديد الإجراء المناسب",
            ))

        # 2. الكلمات المسيئة
        if contains_bad_word(content):
            violations.append((
                "لغة مسيئة محتملة",
                "مراجعة السياق وتحديد الإجراء المناسب",
            ))

        # 3. المنشنات الجماعية
        if (
            len(message.mentions) >= MENTION_LIMIT
            or message.mention_everyone
        ):
            violations.append((
                "منشن جماعي",
                "مراجعة إساءة استخدام المنشنات",
            ))

        # 4. السبام السريع
        key = (
            message.guild.id,
            message.author.id,
        )

        clock = asyncio.get_running_loop().time()
        queue = self.message_times[key]

        queue.append(clock)

        while (
            queue
            and clock - queue[0] > SPAM_WINDOW_SECONDS
        ):
            queue.popleft()

        if len(queue) >= SPAM_LIMIT:
            violations.append((
                "رسائل متكررة بسرعة",
                "مراجعة السبام وتحديد الإجراء المناسب",
            ))
            queue.clear()

        # 5. معالجة المخالفات وإنشاء طلبات المراجعة
        for reason, suggested in violations:
            lock_key = (
                message.guild.id,
                message.id,
                reason,
            )

            if lock_key in self.processing:
                continue

            self.processing.add(lock_key)

            try:
                created = await self.create_request(
                    message,
                    reason,
                    suggested,
                )

                # لا نرسل تحذيرات متكررة إذا منع التكرار الطلب
                if created:
                    sent = await self.warn_member(
                        message.author,
                        reason,
                    )

                    await self.log_event(
                        message.guild,
                        "WARNING_SENT" if sent else "DM_FAILED",
                        (
                            f"{reason} | العضو "
                            f"{message.author.id}"
                        ),
                    )

            finally:
                self.processing.discard(lock_key)

    @commands.Cog.listener()
    async def on_message(self, message):
        await self.inspect_message(message)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.content == after.content:
            return

        # فحص التعديلات أيضًا، لمنع تجاوز الفحص بتعديل الرسالة
        await self.inspect_message(after)

    # =====================================================
    # JOIN MONITOR
    # =====================================================

    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild = member.guild

        if guild.id != ALLOWED_GUILD_ID:
            return

        await self.log_event(
            guild,
            "MEMBER_JOINED",
            (
                f"العضو {member} "
                f"({member.id}) انضم إلى السيرفر."
            ),
        )

        clock = asyncio.get_running_loop().time()
        queue = self.join_times[guild.id]

        queue.append(clock)

        while (
            queue
            and clock - queue[0] > JOIN_WINDOW_SECONDS
        ):
            queue.popleft()

        if len(queue) < JOIN_LIMIT:
            return

        last_alert = self.raid_alert_times.get(guild.id, 0)

        if clock - last_alert < JOIN_WINDOW_SECONDS:
            return

        self.raid_alert_times[guild.id] = clock

        await self.log_event(
            guild,
            "POSSIBLE_JOIN_RAID",
            (
                f"انضم {len(queue)} أعضاء خلال "
                f"{JOIN_WINDOW_SECONDS} ثانية. "
                "هذا تنبيه للمراجعة وليس إثباتًا لهجوم."
            ),
        )

    # =====================================================
    # AUDIT LOG HELPERS
    # =====================================================

    async def audit_actor(self, guild, action, target_id):
        if guild.id != ALLOWED_GUILD_ID:
            return None

        try:
            async for entry in guild.audit_logs(
                limit=10,
                action=action,
            ):
                target = getattr(entry.target, "id", None)

                age = (
                    now_utc() - entry.created_at
                ).total_seconds()

                if target == target_id and age < 30:
                    return entry.user

        except discord.Forbidden:
            logger.warning(
                "البوت لا يملك View Audit Log في السيرفر %s",
                guild.id,
            )

        except discord.HTTPException:
            logger.exception("فشل قراءة سجل التدقيق")

        return None

    # =====================================================
    # CHANNEL DELETE MONITOR
    # =====================================================

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        guild = channel.guild

        if guild.id != ALLOWED_GUILD_ID:
            return

        actor = await self.audit_actor(
            guild,
            discord.AuditLogAction.channel_delete,
            channel.id,
        )

        await self.log_event(
            guild,
            "CHANNEL_DELETED",
            (
                f"الروم {channel.name} ({channel.id}) "
                f"| المنفذ المحتمل: "
                f"{getattr(actor, 'id', 'غير معروف')}"
            ),
        )

    # =====================================================
    # ROLE DELETE MONITOR
    # =====================================================

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        guild = role.guild

        if guild.id != ALLOWED_GUILD_ID:
            return

        actor = await self.audit_actor(
            guild,
            discord.AuditLogAction.role_delete,
            role.id,
        )

        await self.log_event(
            guild,
            "ROLE_DELETED",
            (
                f"الرتبة {role.name} ({role.id}) "
                f"| المنفذ المحتمل: "
                f"{getattr(actor, 'id', 'غير معروف')}"
            ),
        )

    # =====================================================
    # WEBHOOK MONITOR
    # =====================================================

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel):
        guild = channel.guild

        if guild.id != ALLOWED_GUILD_ID:
            return

        await self.log_event(
            guild,
            "WEBHOOKS_CHANGED",
            (
                f"تغيير في Webhooks للروم "
                f"{channel.name} ({channel.id}). "
                "راجع سجل التدقيق لمعرفة التفاصيل."
            ),
        )


# =========================================================
# 5. EXTENSION SETUP
# =========================================================

async def setup(bot):
    await bot.add_cog(SecurityCenter(bot))
