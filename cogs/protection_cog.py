
import os
import asyncio
from datetime import datetime, timedelta, timezone
from collections import defaultdict

import discord
from discord.ext import commands
from pymongo import MongoClient, DESCENDING


# =========================================================
# SERVER CONFIGURATION
# غيّر هذا الرقم إلى ID السيرفر الحقيقي
# =========================================================

SERVER_ID = 1545572112134312027

MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    raise RuntimeError("MONGO_URI is missing from environment variables.")

mongo_client = MongoClient(
    MONGO_URI,
    serverSelectionTimeoutMS=10000
)

db = mongo_client["discord_bot_db"]

SETTINGS_COLLECTION = db["protection_settings"]
EVENTS_COLLECTION = db["protection_events"]


# =========================================================
# DEFAULT SETTINGS
# =========================================================

DEFAULT_SETTINGS = {
    "guild_id": SERVER_ID,
    "enabled": False,
    "spam_log_channel_id": None,
    "security_log_channel_id": None,
    "spam_threshold": 5,
    "spam_window_seconds": 8,
    "whitelist_user_ids": [],
}


class ProtectionCog(commands.Cog):
    """حماية مقيّدة بسيرفر واحد."""

    def __init__(self, bot):
        self.bot = bot

        # تتبع الرسائل مؤقتًا لاكتشاف السبام
        self.message_history = defaultdict(list)
        self.last_spam_notice = {}

        # تتبع أحداث التخريب في الذاكرة
        self.action_history = defaultdict(list)

    # =====================================================
    # SERVER LOCK
    # كل أوامر هذا الـ Cog تمر من هذا الفحص
    # =====================================================

    async def cog_check(self, ctx):
        return (
            ctx.guild is not None
            and ctx.guild.id == SERVER_ID
        )

    def is_target_guild(self, guild):
        return guild is not None and guild.id == SERVER_ID

    # =====================================================
    # DATABASE SETTINGS
    # =====================================================

    def get_settings(self):
        SETTINGS_COLLECTION.update_one(
            {"guild_id": SERVER_ID},
            {"$setOnInsert": DEFAULT_SETTINGS.copy()},
            upsert=True
        )

        settings = SETTINGS_COLLECTION.find_one(
            {"guild_id": SERVER_ID}
        ) or DEFAULT_SETTINGS.copy()

        # قيم افتراضية لأي إعداد جديد أضيف مستقبلًا
        for key, value in DEFAULT_SETTINGS.items():
            settings.setdefault(key, value)

        return settings

    def update_settings(self, **changes):
        SETTINGS_COLLECTION.update_one(
            {"guild_id": SERVER_ID},
            {
                "$setOnInsert": DEFAULT_SETTINGS.copy(),
                "$set": changes,
            },
            upsert=True
        )

    # =====================================================
    # PERMISSIONS
    # =====================================================

    async def require_admin(self, ctx):
        if ctx.guild is None or ctx.guild.id != SERVER_ID:
            return False

        if ctx.author.id == ctx.guild.owner_id:
            return True

        permissions = ctx.author.guild_permissions

        if permissions.administrator or permissions.manage_guild:
            return True

        await ctx.send(
            "❌ تحتاج صلاحية **Manage Server** أو **Administrator** "
            "لاستخدام أمر إعدادات الحماية."
        )
        return False

    def is_whitelisted(self, user_id):
        settings = self.get_settings()
        return int(user_id) in [
            int(uid)
            for uid in settings.get("whitelist_user_ids", [])
        ]

    # =====================================================
    # LOGGING
    # =====================================================

    async def send_log(self, kind, title, description, color=None):
        # لا نرسل سجلات لهذا الـ Cog خارج السيرفر المحدد
        guild = self.bot.get_guild(SERVER_ID)

        if not self.is_target_guild(guild):
            return

        settings = self.get_settings()

        if kind == "spam":
            channel_id = settings.get("spam_log_channel_id")
        else:
            channel_id = settings.get("security_log_channel_id")

        # تسجيل الحدث في MongoDB حتى لو لم يتم تحديد روم
        try:
            EVENTS_COLLECTION.insert_one({
                "guild_id": SERVER_ID,
                "kind": kind,
                "title": title,
                "description": str(description)[:1500],
                "created_at": datetime.now(timezone.utc),
            })
        except Exception as exc:
            print(f"[PROTECTION DB ERROR] {exc}")

        if not channel_id:
            return

        channel = guild.get_channel(int(channel_id))

        if channel is None:
            return

        embed = discord.Embed(
            title=title,
            description=str(description)[:4000],
            color=color or discord.Color.purple(),
            timestamp=datetime.now(timezone.utc),
        )

        try:
            await channel.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException) as exc:
            print(f"[PROTECTION LOG ERROR] {exc}")

    # =====================================================
    # HELPERS: AUDIT LOG
    # =====================================================

    async def find_audit_executor(
        self, guild, action, target_id
    ):
        if not self.is_target_guild(guild):
            return None

        try:
            async for entry in guild.audit_logs(
                limit=10,
                action=action
            ):
                target = entry.target

                if target is None:
                    continue

                if int(getattr(target, "id", 0)) != int(target_id):
                    continue

                age = (
                    datetime.now(timezone.utc) - entry.created_at
                ).total_seconds()

                if 0 <= age <= 15:
                    return entry.user

        except (discord.Forbidden, discord.HTTPException) as exc:
            print(f"[AUDIT LOG ERROR] {exc}")

        return None

    async def process_audit_action(
        self,
        guild,
        action,
        target,
        action_name,
        destructive=False,
        high_risk=False,
    ):
        if not self.is_target_guild(guild):
            return

        settings = self.get_settings()

        if not settings.get("enabled", False):
            return

        executor = await self.find_audit_executor(
            guild,
            action,
            target.id
        )

        if executor is None:
            await self.send_log(
                "security",
                "⚠️ حدث أمني غير محدد المنفّذ",
                f"الحدث: {action_name}\n"
                f"الهدف: {target}\n"
                "تعذر تحديد المنفّذ من سجل تدقيق Discord. "
                "يرجى مراجعة Audit Log يدويًا.",
                discord.Color.orange(),
            )
            return

        if executor.bot and executor.id == self.bot.user.id:
            return

        await self.send_log(
            "security",
            f"🛡️ {action_name}",
            f"المنفّذ: {executor.mention} (`{executor.id}`)\n"
            f"الهدف: {target}\n"
            f"الحدث عالي الخطورة: {'نعم' if high_risk else 'لا'}",
            discord.Color.orange(),
        )

        # الأحداث الحساسة مثل الإنشاء المتكرر أو عمليات الحظر:
        # تسجيل وتنبيه فقط؛ لا نتخذ إجراء عقابيًا تلقائيًا.
        if high_risk:
            return

        if not destructive:
            return

        # لا نعاقب مالك السيرفر أو الحسابات المستثناة
        if executor.id == guild.owner_id:
            return

        if self.is_whitelisted(executor.id):
            return

        now = datetime.now(timezone.utc).timestamp()
        key = (executor.id, action_name)

        self.action_history[key] = [
            timestamp
            for timestamp in self.action_history[key]
            if now - timestamp <= 10
        ]

        self.action_history[key].append(now)

        # حذف 3 رومات أو رتب خلال 10 ثوانٍ:
        # إجراء تلقائي مشروط، مع بقاء سجل الحدث.
        if len(self.action_history[key]) < 3:
            return

        self.action_history[key].clear()

        member = guild.get_member(executor.id)

        if member is None:
            try:
                member = await guild.fetch_member(executor.id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                member = None

        if member is None:
            await self.send_log(
                "security",
                "🚨 يلزم تدخل الإدارة",
                f"تم رصد تكرار خطير لحدث: {action_name}\n"
                f"المنفّذ: {executor.mention}\n"
                "تعذر العثور على العضو لتطبيق التهدئة. "
                "راجع سجل التدقيق.",
                discord.Color.red(),
            )
            return

        if member.id == guild.owner_id:
            return

        bot_member = guild.me

        if (
            bot_member is None
            or not bot_member.guild_permissions.moderate_members
            or member.top_role >= bot_member.top_role
        ):
            await self.send_log(
                "security",
                "🚨 يلزم تدخل الإدارة",
                f"تم رصد تكرار خطير لحدث: {action_name}\n"
                f"المنفّذ: {member.mention}\n"
                "لم يتمكن البوت من تطبيق التهدئة بسبب الصلاحيات "
                "أو ترتيب الرتب.",
                discord.Color.red(),
            )
            return

        try:
            await member.timeout(
                timedelta(minutes=10),
                reason=(
                    "حماية السيرفر: تكرار حذف الرومات أو الرتب "
                    "خلال فترة قصيرة."
                ),
            )

            await self.send_log(
                "security",
                "🚨 تم تطبيق تهدئة تلقائية",
                f"العضو: {member.mention} (`{member.id}`)\n"
                f"السبب: تكرار حدث **{action_name}** "
                "3 مرات خلال 10 ثوانٍ.\n"
                "المدة: 10 دقائق.",
                discord.Color.red(),
            )

        except (discord.Forbidden, discord.HTTPException) as exc:
            await self.send_log(
                "security",
                "🚨 فشل الإجراء التلقائي",
                f"العضو: {member.mention}\n"
                f"الحدث: {action_name}\n"
                f"الخطأ: {type(exc).__name__}\n"
                "يرجى مراجعة سجل التدقيق والتدخل يدويًا.",
                discord.Color.red(),
            )

    # =====================================================
    # SPAM DETECTION: LOG ONLY, NO PUNISHMENT
    # =====================================================

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild is None:
            return

        if message.guild.id != SERVER_ID:
            return

        if message.author.bot:
            return

        settings = self.get_settings()

        if not settings.get("enabled", False):
            return

        if message.author.id == message.guild.owner_id:
            return

        now = datetime.now(timezone.utc).timestamp()
        threshold = max(
            3,
            min(20, int(settings.get("spam_threshold", 5)))
        )
        window = max(
            3,
            min(30, int(settings.get("spam_window_seconds", 8)))
        )

        key = (message.guild.id, message.channel.id, message.author.id)

        history = [
            item
            for item in self.message_history[key]
            if now - item <= window
        ]
        history.append(now)
        self.message_history[key] = history

        # إشعار واحد كل 60 ثانية لكل عضو وروم لتقليل إزعاج السجلات
        last_notice = self.last_spam_notice.get(key, 0)

        if len(history) >= threshold and now - last_notice >= 60:
            self.last_spam_notice[key] = now

            await self.send_log(
                "spam",
                "⚠️ رصد نشاط يشبه السبام",
                f"العضو: {message.author.mention} "
                f"(`{message.author.id}`)\n"
                f"الروم: {message.channel.mention}\n"
                f"عدد الرسائل: {len(history)} خلال {window} ثوانٍ.\n"
                "الإجراء: تسجيل وتنبيه فقط، دون حذف أو عقوبة.",
                discord.Color.orange(),
            )

    # =====================================================
    # ANTI-NUKE EVENTS
    # =====================================================

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        if channel.guild.id != SERVER_ID:
            return

        await self.process_audit_action(
            channel.guild,
            discord.AuditLogAction.channel_delete,
            channel,
            "حذف روم",
            destructive=True,
        )

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        if role.guild.id != SERVER_ID:
            return

        await self.process_audit_action(
            role.guild,
            discord.AuditLogAction.role_delete,
            role,
            "حذف رتبة",
            destructive=True,
        )

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        if channel.guild.id != SERVER_ID:
            return

        await self.process_audit_action(
            channel.guild,
            discord.AuditLogAction.channel_create,
            channel,
            "إنشاء روم",
            high_risk=True,
        )

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        if role.guild.id != SERVER_ID:
            return

        await self.process_audit_action(
            role.guild,
            discord.AuditLogAction.role_create,
            role,
            "إنشاء رتبة",
            high_risk=True,
        )

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        if member.guild.id != SERVER_ID:
            return

        # مغادرة العضو العادية لا تُعتبر تخريبًا.
        # نبحث عن حدث طرد أو حظر مطابق في سجل التدقيق.
        executor = await self.find_audit_executor(
            member.guild,
            discord.AuditLogAction.kick,
            member.id,
        )

        action = discord.AuditLogAction.kick
        action_name = "طرد عضو"

        if executor is None:
            executor = await self.find_audit_executor(
                member.guild,
                discord.AuditLogAction.ban,
                member.id,
            )
            action = discord.AuditLogAction.ban
            action_name = "حظر عضو"

        if executor is None:
            return

        await self.process_audit_action(
            member.guild,
            action,
            member,
            action_name,
            high_risk=True,
        )

    # =====================================================
    # COMMANDS
    # =====================================================

    @commands.command(name="حماية-مساعدة")
    async def protection_help(self, ctx):
        embed = discord.Embed(
            title="🛡️ أوامر الحماية",
            description=(
                "`حماية-حالة` — عرض الحالة والإعدادات\n"
                "`حماية-تفعيل` — تشغيل الحماية\n"
                "`حماية-تعطيل` — إيقاف المراقبة\n"
                "`لوق-السبام #الروم` — تحديد سجل السبام\n"
                "`لوق-الحماية #الروم` — تحديد سجل الحماية\n"
                "`سبام-حد 5` — تحديد عدد الرسائل لرصد السبام\n"
                "`حماية-استثناء @عضو` — استثناء عضو من التهدئة التلقائية\n"
                "`حماية-إلغاء-استثناء @عضو` — إزالة الاستثناء\n"
                "`حماية-اختبار` — اختبار إرسال السجلات\n"
                "`حماية-سجل` — عرض آخر أحداث الحماية المسجلة"
            ),
            color=discord.Color.purple(),
        )
        await ctx.send(embed=embed)

    @commands.command(name="حماية-حالة")
    async def protection_status(self, ctx):
        settings = self.get_settings()

        spam_channel = settings.get("spam_log_channel_id")
        security_channel = settings.get("security_log_channel_id")

        embed = discord.Embed(
            title="🛡️ حالة الحماية",
            color=(
                discord.Color.green()
                if settings.get("enabled")
                else discord.Color.red()
            ),
        )

        embed.add_field(
            name="الحالة",
            value="مفعّلة" if settings.get("enabled") else "معطّلة",
            inline=True,
        )
        embed.add_field(
            name="حد السبام",
            value=(
                f"{settings.get('spam_threshold', 5)} رسائل خلال "
                f"{settings.get('spam_window_seconds', 8)} ثوانٍ"
            ),
            inline=False,
        )
        embed.add_field(
            name="سجل السبام",
            value=f"<#{spam_channel}>" if spam_channel else "غير محدد",
            inline=True,
        )
        embed.add_field(
            name="سجل الحماية",
            value=f"<#{security_channel}>" if security_channel else "غير محدد",
            inline=True,
        )

        await ctx.send(embed=embed)

    @commands.command(name="حماية-تفعيل")
    async def protection_enable(self, ctx):
        if not await self.require_admin(ctx):
            return

        self.update_settings(enabled=True)
        await ctx.send(
            "✅ تم تفعيل الحماية في السيرفر المحدد فقط."
        )

    @commands.command(name="حماية-تعطيل")
    async def protection_disable(self, ctx):
        if not await self.require_admin(ctx):
            return

        self.update_settings(enabled=False)
        await ctx.send(
            "⏸️ تم تعطيل المراقبة. إعداداتك وسجلاتك المحفوظة "
            "في MongoDB لم تُحذف."
        )

    @commands.command(name="لوق-السبام")
    async def set_spam_log(self, ctx, channel: discord.TextChannel = None):
        if not await self.require_admin(ctx):
            return

        if channel is None:
            await ctx.send("الاستخدام: `لوق-السبام #الروم`")
            return

        if channel.guild.id != SERVER_ID:
            return

        self.update_settings(spam_log_channel_id=channel.id)
        await ctx.send(f"✅ تم تعيين سجل السبام إلى {channel.mention}")

    @commands.command(name="لوق-الحماية")
    async def set_security_log(
        self, ctx, channel: discord.TextChannel = None
    ):
        if not await self.require_admin(ctx):
            return

        if channel is None:
            await ctx.send("الاستخدام: `لوق-الحماية #الروم`")
            return

        if channel.guild.id != SERVER_ID:
            return

        self.update_settings(security_log_channel_id=channel.id)
        await ctx.send(f"✅ تم تعيين سجل الحماية إلى {channel.mention}")

    @commands.command(name="سبام-حد")
    async def set_spam_threshold(self, ctx, threshold: int = None):
        if not await self.require_admin(ctx):
            return

        if threshold is None or not 3 <= threshold <= 20:
            await ctx.send(
                "الاستخدام: `سبام-حد 5`\n"
                "اختر رقمًا من 3 إلى 20 رسالة."
            )
            return

        self.update_settings(spam_threshold=threshold)
        await ctx.send(
            f"✅ تم ضبط حد رصد السبام على {threshold} رسائل "
            "ضمن المدة المحددة في الإعدادات."
        )

    @commands.command(name="حماية-استثناء")
    async def protection_add_exemption(
        self, ctx, member: discord.Member = None
    ):
        if not await self.require_admin(ctx):
            return

        if member is None:
            await ctx.send("الاستخدام: `حماية-استثناء @عضو`")
            return

        if member.guild.id != SERVER_ID:
            return

        if member.id == ctx.guild.owner_id:
            await ctx.send("مالك السيرفر مستثنى أصلًا.")
            return

        settings = self.get_settings()
        users = [
            int(uid)
            for uid in settings.get("whitelist_user_ids", [])
        ]

        if member.id not in users:
            users.append(member.id)

        self.update_settings(whitelist_user_ids=users)
        await ctx.send(
            f"✅ تمت إضافة {member.mention} لقائمة الاستثناء "
            "من التهدئة التلقائية. ستظل أحداثه قابلة للتسجيل."
        )

    @commands.command(name="حماية-إلغاء-استثناء")
    async def protection_remove_exemption(
        self, ctx, member: discord.Member = None
    ):
        if not await self.require_admin(ctx):
            return

        if member is None:
            await ctx.send("الاستخدام: `حماية-إلغاء-استثناء @عضو`")
            return

        settings = self.get_settings()
        users = [
            int(uid)
            for uid in settings.get("whitelist_user_ids", [])
            if int(uid) != member.id
        ]

        self.update_settings(whitelist_user_ids=users)
        await ctx.send(
            f"✅ تمت إزالة {member.mention} من قائمة الاستثناء."
        )

    @commands.command(name="حماية-اختبار")
    async def protection_test(self, ctx):
        if not await self.require_admin(ctx):
            return

        settings = self.get_settings()
        results = []

        for kind, key, label in [
            ("spam", "spam_log_channel_id", "سجل السبام"),
            ("security", "security_log_channel_id", "سجل الحماية"),
        ]:
            channel_id = settings.get(key)

            if not channel_id:
                results.append(f"❌ {label}: لم يتم تحديد روم.")
                continue

            channel = ctx.guild.get_channel(int(channel_id))

            if channel is None:
                results.append(f"❌ {label}: الروم غير موجود أو غير متاح.")
                continue

            try:
                await channel.send(
                    f"🧪 اختبار سجل **{label}** من نظام الحماية."
                )
                results.append(f"✅ {label}: تم إرسال رسالة الاختبار.")
            except (discord.Forbidden, discord.HTTPException):
                results.append(
                    f"❌ {label}: تعذر الإرسال؛ تحقق من صلاحية "
                    "`View Channel` و`Send Messages`."
                )

        await ctx.send("\n".join(results))

    @commands.command(name="حماية-سجل")
    async def protection_recent_logs(self, ctx):
        if not await self.require_admin(ctx):
            return

        events = list(
            EVENTS_COLLECTION.find(
                {"guild_id": SERVER_ID},
                {
                    "kind": 1,
                    "title": 1,
                    "description": 1,
                    "created_at": 1,
                },
            )
            .sort("created_at", DESCENDING)
            .limit(5)
        )

        if not events:
            await ctx.send("لا توجد أحداث مسجلة حتى الآن.")
            return

        embed = discord.Embed(
            title="🧾 آخر أحداث الحماية",
            color=discord.Color.purple(),
        )

        for event in events:
            created_at = event.get("created_at")
            time_text = (
                discord.utils.format_dt(created_at, style="R")
                if created_at
                else "وقت غير معروف"
            )

            embed.add_field(
                name=f"{event.get('title', 'حدث')} — {time_text}",
                value=(
                    f"{event.get('kind', 'unknown')}\n"
                    f"{event.get('description', '')[:900]}"
                ),
                inline=False,
            )

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(ProtectionCog(bot))
