import os
import asyncio
import traceback
from datetime import datetime, timezone

import discord
from discord.ext import commands
from pymongo import MongoClient


# =========================================================
# إعدادات MongoDB
# =========================================================

MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    raise RuntimeError(
        "❌ MONGO_URI غير موجود في Environment Variables"
    )


mongo_client = MongoClient(MONGO_URI)

db = mongo_client["discord_bot_db"]

commands_collection = db["website_commands"]
guilds_collection = db["website_guilds"]
settings_collection = db["website_command_settings"]


# =========================================================
# أدوات مساعدة
# =========================================================

def normalize_command_name(name):
    """
    يتأكد أن اسم الأمر محفوظ بدون:
    -
    .
    /
    """
    if not name:
        return ""

    name = str(name).strip()

    while name and name[0] in ("-", ".", "/"):
        name = name[1:]

    return name.strip()


# =========================================================
# حفظ أوامر البوت
# =========================================================

def save_bot_commands(bot):

    print("🌐 [WEBSITE] بدء قراءة أوامر البوت...")

    commands_data = []

    for command in bot.commands:

        if command.hidden:
            continue

        if command.parent is not None:
            continue

        command_name = normalize_command_name(
            command.name
        )

        if not command_name:
            continue

        description = (
            command.help
            or command.description
            or "لا يوجد وصف لهذا الأمر."
        )

        commands_data.append({
            "name": command_name,
            "description": description,
            "aliases": [
                normalize_command_name(alias)
                for alias in command.aliases
            ],
        })

    commands_data.sort(
        key=lambda x: x["name"].lower()
    )

    print(
        f"📋 [WEBSITE] تم العثور على "
        f"{len(commands_data)} أمر"
    )

    commands_collection.delete_many({})

    if commands_data:
        commands_collection.insert_many(
            commands_data
        )

    db["website_settings"].update_one(
        {"_id": "commands"},
        {
            "$set": {
                "updated_at": datetime.now(timezone.utc),
                "commands_count": len(commands_data)
            }
        },
        upsert=True
    )

    print(
        "✅ [WEBSITE] تم حفظ أوامر البوت في MongoDB"
    )

    print(
        f"📦 [WEBSITE] العدد المحفوظ: "
        f"{len(commands_data)}"
    )


# =========================================================
# تجهيز بيانات السيرفر
# =========================================================

def build_guild_data(guild, installer_id=None):

    existing = guilds_collection.find_one({
        "guild_id": str(guild.id)
    })

    if installer_id is None and existing:
        installer_id = existing.get("installer_id")

    channels = []

    for channel in guild.channels:

        channel_type = channel.type.name

        channels.append({
            "id": str(channel.id),
            "name": channel.name,
            "type": channel_type,
            "position": getattr(channel, "position", 0),
        })

    channels.sort(
        key=lambda x: (
            x.get("position", 0),
            x.get("name", "").lower()
        )
    )

    roles = []

    for role in guild.roles:

        # تجاهل @everyone
        if role.is_default():
            continue

        roles.append({
            "id": str(role.id),
            "name": role.name,
            "position": role.position,
            "managed": role.managed,
        })

    roles.sort(
        key=lambda x: (
            -x.get("position", 0),
            x.get("name", "").lower()
        )
    )

    return {
        "guild_id": str(guild.id),
        "guild_name": guild.name,
        "owner_id": str(guild.owner_id),

        "installer_id": (
            str(installer_id)
            if installer_id
            else None
        ),

        "channels": channels,
        "roles": roles,

        "updated_at": datetime.now(timezone.utc)
    }


# =========================================================
# حفظ بيانات السيرفر
# =========================================================

def sync_guild(guild, installer_id=None):

    try:

        data = build_guild_data(
            guild,
            installer_id
        )

        guilds_collection.update_one(
            {
                "guild_id": str(guild.id)
            },
            {
                "$set": data
            },
            upsert=True
        )

        print(
            f"🌐 [WEBSITE] تم تحديث السيرفر: "
            f"{guild.name} "
            f"({guild.id})"
        )

        print(
            f"📁 الرومات: {len(data['channels'])}"
        )

        print(
            f"🎭 الرتب: {len(data['roles'])}"
        )

    except Exception as error:

        print(
            "❌ [WEBSITE] فشل تحديث بيانات السيرفر"
        )

        print(
            f"❌ السيرفر: {guild.name}"
        )

        print(
            f"❌ الخطأ: "
            f"{type(error).__name__}: {error}"
        )

        traceback.print_exc()


# =========================================================
# معرفة الشخص الذي أضاف البوت
# =========================================================

async def find_installer(guild):

    if not guild.me:
        return None

    permissions = guild.me.guild_permissions

    if not permissions.view_audit_log:

        print(
            f"⚠️ [WEBSITE] البوت لا يملك "
            f"View Audit Log في: {guild.name}"
        )

        return None

    try:

        await asyncio.sleep(3)

        async for entry in guild.audit_logs(
            limit=20,
            action=discord.AuditLogAction.bot_add
        ):

            target = getattr(
                entry,
                "target",
                None
            )

            if not target:
                continue

            if target.id != self_bot_id(guild):

                continue

            user = getattr(
                entry,
                "user",
                None
            )

            if not user:
                continue

            print(
                f"👤 [WEBSITE] الشخص الذي أضاف البوت: "
                f"{user} ({user.id})"
            )

            return str(user.id)

    except discord.Forbidden:

        print(
            f"⚠️ [WEBSITE] لا يمكن قراءة Audit Log "
            f"في: {guild.name}"
        )

    except Exception as error:

        print(
            "❌ [WEBSITE] خطأ أثناء البحث عن "
            "الشخص الذي أضاف البوت"
        )

        print(
            f"❌ {type(error).__name__}: {error}"
        )

    return None


def self_bot_id(guild):

    if guild.me:
        return guild.me.id

    return 0


# =========================================================
# Cog
# =========================================================

class WebsiteCommands(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        self.updated = False

        self.bot.add_check(
            self.website_permission_check
        )

        print(
            "🌐 [WEBSITE] WebsiteCommands تم تحميله"
        )

    # =====================================================
    # التحقق من صلاحيات الموقع للأوامر
    # =====================================================

    async def website_permission_check(self, ctx):

        # الرسائل الخاصة
        if ctx.guild is None:
            return True

        if ctx.command is None:
            return True

        command_name = normalize_command_name(
            ctx.command.qualified_name
        )

        setting = settings_collection.find_one({
            "guild_id": str(ctx.guild.id),
            "command_name": command_name
        })

        # لا يوجد إعداد من الموقع
        if not setting:
            return True

        # إعداد الموقع غير مفعل
        if not setting.get("enabled", False):
            return True

        allowed_channels = {
            str(channel_id)
            for channel_id in setting.get(
                "channel_ids",
                []
            )
        }

        allowed_roles = {
            str(role_id)
            for role_id in setting.get(
                "role_ids",
                []
            )
        }

        # =================================================
        # فحص الروم
        # =================================================

        if allowed_channels:

            if str(ctx.channel.id) not in allowed_channels:

                print(
                    "🚫 [WEBSITE] الأمر مرفوض بسبب الروم"
                )

                print(
                    f"👤 {ctx.author} "
                    f"({ctx.author.id})"
                )

                print(
                    f"📌 الأمر: {command_name}"
                )

                print(
                    f"📁 الروم: "
                    f"{ctx.channel.name}"
                )

                return False

        # =================================================
        # فحص الرتبة
        # =================================================

        if allowed_roles:

            user_role_ids = {
                str(role.id)
                for role in ctx.author.roles
            }

            if not (
                user_role_ids
                & allowed_roles
            ):

                print(
                    "🚫 [WEBSITE] الأمر مرفوض "
                    "بسبب الرتبة"
                )

                print(
                    f"👤 {ctx.author} "
                    f"({ctx.author.id})"
                )

                print(
                    f"📌 الأمر: {command_name}"
                )

                return False

        return True

    # =====================================================
    # عند تشغيل البوت
    # =====================================================

    @commands.Cog.listener()
    async def on_ready(self):

        if self.updated:
            return

        self.updated = True

        print(
            "🌐 [WEBSITE] البوت أصبح جاهزًا"
        )

        await asyncio.sleep(5)

        # -------------------------------------------------
        # حفظ الأوامر
        # -------------------------------------------------

        try:

            save_bot_commands(self.bot)

        except Exception as error:

            print(
                "❌ [WEBSITE] حدث خطأ أثناء حفظ الأوامر"
            )

            print(
                f"❌ نوع الخطأ: "
                f"{type(error).__name__}"
            )

            print(
                f"❌ الخطأ: {error}"
            )

            traceback.print_exc()

        # -------------------------------------------------
        # تحديث جميع السيرفرات
        # -------------------------------------------------

        print(
            "🌐 [WEBSITE] بدء مزامنة السيرفرات..."
        )

        for guild in self.bot.guilds:

            try:

                existing = guilds_collection.find_one({
                    "guild_id": str(guild.id)
                })

                installer_id = None

                if existing:

                    installer_id = existing.get(
                        "installer_id"
                    )

                sync_guild(
                    guild,
                    installer_id
                )

            except Exception as error:

                print(
                    f"❌ فشل مزامنة: {guild.name}"
                )

                print(
                    f"❌ {type(error).__name__}: "
                    f"{error}"
                )

        print(
            "✅ [WEBSITE] انتهت مزامنة السيرفرات"
        )

    # =====================================================
    # دخول البوت إلى سيرفر
    # =====================================================

    @commands.Cog.listener()
    async def on_guild_join(self, guild):

        print(
            "🎉 [WEBSITE] دخل البوت سيرفرًا جديدًا"
        )

        print(
            f"🏠 السيرفر: {guild.name}"
        )

        print(
            f"🆔 ID: {guild.id}"
        )

        installer_id = None

        try:

            installer_id = await find_installer(
                guild
            )

        except Exception as error:

            print(
                f"⚠️ فشل معرفة المثبت: {error}"
            )

        sync_guild(
            guild,
            installer_id
        )

    # =====================================================
    # تحديث الرومات
    # =====================================================

    @commands.Cog.listener()
    async def on_guild_channel_create(
        self,
        channel
    ):

        if channel.guild:

            sync_guild(
                channel.guild
            )

    @commands.Cog.listener()
    async def on_guild_channel_delete(
        self,
        channel
    ):

        if channel.guild:

            sync_guild(
                channel.guild
            )

    # =====================================================
    # تحديث الرتب
    # =====================================================

    @commands.Cog.listener()
    async def on_guild_role_create(
        self,
        role
    ):

        if role.guild:

            sync_guild(
                role.guild
            )

    @commands.Cog.listener()
    async def on_guild_role_delete(
        self,
        role
    ):

        if role.guild:

            sync_guild(
                role.guild
            )

    @commands.Cog.listener()
    async def on_guild_role_update(
        self,
        before,
        after
    ):

        if after.guild:

            sync_guild(
                after.guild
            )

    # =====================================================
    # تنظيف عند إزالة الـ Cog
    # =====================================================

    def cog_unload(self):

        try:

            self.bot.remove_check(
                self.website_permission_check
            )

        except Exception:

            pass


# =========================================================
# تحميل الـ Cog
# =========================================================

async def setup(bot):

    await bot.add_cog(
        WebsiteCommands(bot)
    )

    print(
        "✅ [WEBSITE] WebsiteCommands جاهز"
    )
