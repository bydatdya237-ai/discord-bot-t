import os
import asyncio
import traceback
import inspect
import re

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
# مجموعة اختصارات الموقع
# =========================================================

aliases_collection = db["website_command_aliases"]


# =========================================================
# أدوات عامة
# =========================================================

def normalize_command_name(name):
    """
    إزالة بادئة الأمر:
    -
    .
    /

    مثال:
    -رصيد  -> رصيد
    .رصيد  -> رصيد
    /رصيد  -> رصيد
    """

    if not name:
        return ""

    name = str(name).strip()

    while name and name[0] in ("-", ".", "/"):
        name = name[1:]

    return name.strip()


# =========================================================
# استخراج أمر من نص
# =========================================================

def clean_detected_command(value):

    if not value:
        return ""

    value = str(value).strip()

    value = normalize_command_name(value)

    # إزالة أي شيء بعد مسافة
    value = value.split()[0] if value else ""

    # إزالة علامات شائعة
    value = value.strip(
        "\"'`()[]{}:;,"
    )

    return normalize_command_name(value)


# =========================================================
# أدوات الاختصارات
# =========================================================

def normalize_alias(alias):
    """
    توحيد الاختصار.

    أمثلة:

    -ذ      -> ذ
    .ذ      -> ذ
    /ذ      -> ذ
    ذ       -> ذ
    """

    if not alias:
        return ""

    return normalize_command_name(alias)


def get_alias_data(guild_id, alias):
    """
    البحث عن الاختصار الخاص بالسيرفر.

    ندعم أكثر من شكل تخزين حتى لا تتعارض
    النسخ القديمة والجديدة من الموقع.
    """

    if not guild_id or not alias:
        return None

    guild_id = str(guild_id)

    clean_alias = normalize_alias(alias)

    if not clean_alias:
        return None

    # =====================================================
    # البحث بالشكل الأساسي
    # =====================================================

    data = aliases_collection.find_one({
        "guild_id": guild_id,
        "alias": clean_alias
    })

    if data:
        return data

    # =====================================================
    # في حال الموقع مخزن الاختصار مع -
    # =====================================================

    data = aliases_collection.find_one({
        "guild_id": guild_id,
        "alias": f"-{clean_alias}"
    })

    if data:
        return data

    # =====================================================
    # في حال guild_id مخزن كرقم بدل نص
    # =====================================================

    try:

        numeric_guild_id = int(guild_id)

        data = aliases_collection.find_one({
            "guild_id": numeric_guild_id,
            "alias": clean_alias
        })

        if data:
            return data

        data = aliases_collection.find_one({
            "guild_id": numeric_guild_id,
            "alias": f"-{clean_alias}"
        })

        if data:
            return data

    except Exception:

        pass

    return None


def get_original_command_from_alias(data):
    """
    استخراج الأمر الأصلي من بيانات الاختصار.

    يدعم:
    command
    command_name
    target
    """

    if not data:
        return ""

    original = (
        data.get("command")
        or data.get("command_name")
        or data.get("target")
        or ""
    )

    return normalize_command_name(
        original
    )


async def execute_website_alias(
    message
):
    """
    تشغيل الاختصار فعليًا.

    مثال:

    -ذ @أحمد

    يصبح داخليًا:

    -ذهبي @أحمد
    """

    if not message.guild:
        return False

    content = message.content.strip()

    if not content:
        return False

    # =====================================================
    # الاختصارات تعمل فقط مع -
    # =====================================================

    if not content.startswith("-"):
        return False

    parts = content.split()

    if not parts:
        return False

    typed_alias = parts[0]

    # =====================================================
    # البحث عن الاختصار
    # =====================================================

    alias_data = get_alias_data(
        message.guild.id,
        typed_alias
    )

    if not alias_data:
        return False

    # =====================================================
    # استخراج الأمر الأصلي
    # =====================================================

    original_command = get_original_command_from_alias(
        alias_data
    )

    if not original_command:
        print(
            f"⚠️ [WEBSITE ALIAS] الاختصار "
            f"{typed_alias} موجود لكن الأمر الأصلي فارغ"
        )

        return False

    # =====================================================
    # التأكد أن الأمر الأصلي موجود فعلًا
    # =====================================================

    ctx = await self_bot_get_context(
        message
    )

    # =====================================================
    # بناء محتوى الأمر الجديد
    # =====================================================

    new_content = f"-{original_command}"

    # إضافة بقية الكلام كما هو
    if len(parts) > 1:

        new_content += " "

        new_content += " ".join(
            parts[1:]
        )

    # =====================================================
    # نسخ الرسالة بشكل آمن
    # =====================================================

    old_content = message.content

    message.content = new_content

    try:

        # =================================================
        # إنشاء Context جديد
        # =================================================

        ctx = await self_bot_get_context(
            message
        )

        # =================================================
        # إذا لم يتم العثور على الأمر
        # =================================================

        if ctx.command is None:

            print(
                f"⚠️ [WEBSITE ALIAS] "
                f"الأمر الأصلي غير موجود: "
                f"-{original_command}"
            )

            return False

        # =================================================
        # تنفيذ الأمر
        # =================================================

        print(
            f"🔁 [WEBSITE ALIAS] "
            f"{old_content} -> {new_content}"
        )

        await self_bot_invoke(
            ctx
        )

        return True

    except commands.CommandError as error:

        print(
            f"❌ [WEBSITE ALIAS] خطأ أثناء تنفيذ "
            f"{old_content}"
        )

        print(
            f"❌ {type(error).__name__}: {error}"
        )

        return True

    except Exception as error:

        print(
            f"❌ [WEBSITE ALIAS] خطأ غير متوقع"
        )

        print(
            f"❌ {type(error).__name__}: {error}"
        )

        traceback.print_exc()

        return True

    finally:

        # =================================================
        # إعادة النص الأصلي
        # =================================================

        message.content = old_content


async def self_bot_get_context(
    message
):
    """
    الحصول على Context من البوت.

    هذه الدالة منفصلة حتى لا نغير أي شيء
    من نظام البوت الأساسي.
    """

    bot = message._state._get_client()

    return await bot.get_context(
        message
    )


async def self_bot_invoke(
    ctx
):
    """
    تنفيذ الأمر من الـ Context.
    """

    bot = ctx.bot

    await bot.invoke(
        ctx
    )


# =========================================================
# اكتشاف الأوامر اليدوية من on_message
# =========================================================

def detect_manual_commands(bot):

    detected = {}

    print(
        "🔎 [WEBSITE] بدء اكتشاف الأوامر اليدوية..."
    )

    for cog_name, cog in bot.cogs.items():

        try:

            method = getattr(
                cog,
                "on_message",
                None
            )

            if method is None:
                continue

            try:

                source = inspect.getsource(
                    method
                )

            except (
                OSError,
                TypeError
            ):

                continue

            # -------------------------------------------------
            # أنماط مثل:
            #
            # message.content.startswith("-رتبة")
            # message.content.startswith(".رتبة")
            # message.content.startswith("/رتبة")
            # -------------------------------------------------

            patterns = [

                r'\.content\.startswith\(\s*["\']([\-\.\/][^"\']+)["\']',

                r'\.content\s*==\s*["\']([\-\.\/][^"\']+)["\']',

                r'\.content\.startswith\(\s*f?["\']([\-\.\/][^"\']+)["\']',

            ]

            for pattern in patterns:

                matches = re.findall(
                    pattern,
                    source
                )

                for match in matches:

                    command_name = clean_detected_command(
                        match
                    )

                    if not command_name:
                        continue

                    # -------------------------------------------------
                    # استبعاد الأشياء التي ليست أوامر
                    # -------------------------------------------------

                    if command_name.lower() in {
                        "http",
                        "https",
                    }:
                        continue

                    detected[command_name] = {
                        "name": command_name,
                        "description": (
                            f"أمر يدوي من {cog_name}"
                        ),
                        "aliases": [],
                        "manual": True,
                        "auto_detected": True,
                        "source_cog": cog_name
                    }

        except Exception as error:

            print(
                f"⚠️ [WEBSITE] فشل فحص Cog: "
                f"{cog_name}"
            )

            print(
                f"⚠️ {type(error).__name__}: "
                f"{error}"
            )

    print(
        f"🔎 [WEBSITE] تم اكتشاف "
        f"{len(detected)} أمر يدوي تلقائيًا"
    )

    return list(
        detected.values()
    )


# =========================================================
# اكتشاف أسماء إعدادات الأوامر من الـCogs
# =========================================================

def detect_command_setting_names(bot):

    detected = {}

    print(
        "🔎 [WEBSITE] فحص إعدادات الأوامر داخل الـCogs..."
    )

    for cog_name, cog in bot.cogs.items():

        try:

            module = inspect.getmodule(
                cog.__class__
            )

            if module is None:
                continue

            module_dict = vars(module)

            for variable_name, value in module_dict.items():

                if not isinstance(
                    value,
                    str
                ):
                    continue

                variable_upper = str(
                    variable_name
                ).upper()

                if "COMMAND_NAME" not in variable_upper:
                    continue

                command_name = clean_detected_command(
                    value
                )

                if not command_name:
                    continue

                detected[command_name] = {
                    "name": command_name,
                    "description": (
                        f"إعداد مرتبط بالأوامر - {cog_name}"
                    ),
                    "aliases": [],
                    "manual": True,
                    "auto_detected": True,
                    "setting_only": True,
                    "source_cog": cog_name
                }

        except Exception as error:

            print(
                f"⚠️ [WEBSITE] فشل فحص إعدادات "
                f"{cog_name}: {error}"
            )

    print(
        f"🔎 [WEBSITE] تم اكتشاف "
        f"{len(detected)} إعداد أمر تلقائيًا"
    )

    return list(
        detected.values()
    )


# =========================================================
# حفظ أمر في MongoDB
# =========================================================

def save_command(command_data):

    command_name = normalize_command_name(
        command_data.get("name")
    )

    if not command_name:
        return

    description = (
        command_data.get("description")
        or "لا يوجد وصف لهذا الأمر."
    )

    aliases = []

    for alias in command_data.get(
        "aliases",
        []
    ):

        normalized = normalize_command_name(
            alias
        )

        if normalized:
            aliases.append(
                normalized
            )

    update_data = {
        "name": command_name,
        "description": description,
        "aliases": aliases,
        "manual": bool(
            command_data.get(
                "manual",
                False
            )
        ),
        "updated_at": datetime.now(
            timezone.utc
        )
    }

    if command_data.get(
        "auto_detected",
        False
    ):

        update_data["auto_detected"] = True

    if command_data.get(
        "setting_only",
        False
    ):

        update_data["setting_only"] = True

    if command_data.get(
        "source_cog"
    ):

        update_data["source_cog"] = (
            command_data["source_cog"]
        )

    commands_collection.update_one(
        {
            "name": command_name
        },
        {
            "$set": update_data
        },
        upsert=True
    )


# =========================================================
# حفظ جميع أوامر البوت
# =========================================================

def save_bot_commands(bot):

    print(
        "=================================================="
    )

    print(
        "🌐 [WEBSITE] بدء مزامنة أوامر البوت..."
    )

    all_commands = {}

    # =====================================================
    # 1 - أوامر commands.py / @commands.command
    # =====================================================

    for command in bot.commands:

        try:

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

            aliases = [
                normalize_command_name(alias)
                for alias in command.aliases
            ]

            aliases = [
                alias
                for alias in aliases
                if alias
            ]

            all_commands[command_name] = {
                "name": command_name,
                "description": description,
                "aliases": aliases,
                "manual": False,
                "auto_detected": True,
                "source_cog": (
                    command.cog_name
                    if getattr(
                        command,
                        "cog_name",
                        None
                    )
                    else None
                )
            }

        except Exception as error:

            print(
                f"⚠️ [WEBSITE] خطأ في قراءة أمر: "
                f"{error}"
            )

    print(
        f"📋 [WEBSITE] أوامر Discord المسجلة: "
        f"{len(all_commands)}"
    )

    # =====================================================
    # 2 - الأوامر اليدوية داخل on_message
    # =====================================================

    manual_commands = detect_manual_commands(
        bot
    )

    for command_data in manual_commands:

        command_name = normalize_command_name(
            command_data.get("name")
        )

        if not command_name:
            continue

        if command_name not in all_commands:

            all_commands[
                command_name
            ] = command_data

    # =====================================================
    # 3 - إعدادات الأوامر الخاصة بالـCogs
    # =====================================================

    setting_commands = detect_command_setting_names(
        bot
    )

    for command_data in setting_commands:

        command_name = normalize_command_name(
            command_data.get("name")
        )

        if not command_name:
            continue

        if command_name not in all_commands:

            all_commands[
                command_name
            ] = command_data

    # =====================================================
    # حفظ كل شيء
    # =====================================================

    for command_data in all_commands.values():

        try:

            save_command(
                command_data
            )

        except Exception as error:

            print(
                f"❌ [WEBSITE] فشل حفظ الأمر "
                f"{command_data.get('name')}"
            )

            print(
                f"❌ {type(error).__name__}: "
                f"{error}"
            )

    # =====================================================
    # إحصائيات
    # =====================================================

    total_commands = (
        commands_collection.count_documents({})
    )

    db["website_settings"].update_one(
        {
            "_id": "commands"
        },
        {
            "$set": {
                "updated_at": datetime.now(
                    timezone.utc
                ),
                "commands_count": total_commands
            }
        },
        upsert=True
    )

    print(
        "=================================================="
    )

    print(
        "✅ [WEBSITE] تم حفظ جميع أوامر البوت"
    )

    print(
        f"📦 إجمالي الأوامر في MongoDB: "
        f"{total_commands}"
    )

    print(
        "=================================================="
    )


# =========================================================
# تجهيز بيانات السيرفر
# =========================================================

def build_guild_data(
    guild,
    installer_id=None
):

    existing = guilds_collection.find_one(
        {
            "guild_id": str(guild.id)
        }
    )

    if installer_id is None and existing:

        installer_id = existing.get(
            "installer_id"
        )

    channels = []

    for channel in guild.channels:

        channel_type = channel.type.name

        channels.append({
            "id": str(channel.id),
            "name": channel.name,
            "type": channel_type,
            "position": getattr(
                channel,
                "position",
                0
            ),
        })

    channels.sort(
        key=lambda x: (
            x.get(
                "position",
                0
            ),
            x.get(
                "name",
                ""
            ).lower()
        )
    )

    roles = []

    for role in guild.roles:

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
            -x.get(
                "position",
                0
            ),
            x.get(
                "name",
                ""
            ).lower()
        )
    )

    return {
        "guild_id": str(guild.id),

        "guild_name": guild.name,

        "owner_id": str(
            guild.owner_id
        ),

        "installer_id": (
            str(installer_id)
            if installer_id
            else None
        ),

        "channels": channels,

        "roles": roles,

        "updated_at": datetime.now(
            timezone.utc
        )
    }


# =========================================================
# حفظ بيانات السيرفر
# =========================================================

def sync_guild(
    guild,
    installer_id=None
):

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
            f"{guild.name} ({guild.id})"
        )

        print(
            f"📁 الرومات: "
            f"{len(data['channels'])}"
        )

        print(
            f"🎭 الرتب: "
            f"{len(data['roles'])}"
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

            if target.id != self_bot_id(
                guild
            ):
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

            return str(
                user.id
            )

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

class WebsiteCommands(
    commands.Cog
):

    def __init__(
        self,
        bot
    ):

        self.bot = bot

        self.updated = False

        self.bot.add_check(
            self.website_permission_check
        )

        print(
            "🌐 [WEBSITE] WebsiteCommands تم تحميله"
        )

    # =====================================================
    # الاختصارات الفعلية
    # =====================================================

    @commands.Cog.listener()
    async def on_message(
        self,
        message
    ):

        # -------------------------------------------------
        # تجاهل البوتات
        # -------------------------------------------------

        if message.author.bot:
            return

        # -------------------------------------------------
        # إذا لم تكن رسالة سيرفر
        # -------------------------------------------------

        if message.guild is None:
            return

        try:

            await execute_website_alias(
                message
            )

        except Exception as error:

            print(
                "❌ [WEBSITE ALIAS] "
                "حدث خطأ في نظام الاختصارات"
            )

            print(
                f"❌ {type(error).__name__}: "
                f"{error}"
            )

            traceback.print_exc()

    # =====================================================
    # التحقق من صلاحيات الموقع
    # =====================================================

    async def website_permission_check(
        self,
        ctx
    ):

        if ctx.guild is None:
            return True

        if ctx.command is None:
            return True

        command_name = normalize_command_name(
            ctx.command.qualified_name
        )

        # =================================================
        # دعم command_name و name
        # =================================================

        setting = settings_collection.find_one(
            {
                "guild_id": str(
                    ctx.guild.id
                ),
                "command_name": command_name
            }
        )

        if not setting:

            setting = settings_collection.find_one(
                {
                    "guild_id": str(
                        ctx.guild.id
                    ),
                    "name": command_name
                }
            )

        # =================================================
        # إذا لا يوجد إعداد للموقع
        # =================================================

        if not setting:
            return True

        # =================================================
        # إذا الأمر معطل
        # =================================================

        if not setting.get(
            "enabled",
            False
        ):

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

            if str(
                ctx.channel.id
            ) not in allowed_channels:

                print(
                    "🚫 [WEBSITE] الأمر مرفوض بسبب الروم"
                )

                print(
                    f"👤 {ctx.author} "
                    f"({ctx.author.id})"
                )

                print(
                    f"📌 الأمر: "
                    f"{command_name}"
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
                    f"📌 الأمر: "
                    f"{command_name}"
                )

                return False

        return True

    # =====================================================
    # عند تشغيل البوت
    # =====================================================

    @commands.Cog.listener()
    async def on_ready(
        self
    ):

        if self.updated:
            return

        self.updated = True

        print(
            "🌐 [WEBSITE] البوت أصبح جاهزًا"
        )

        await asyncio.sleep(5)

        # =================================================
        # مزامنة جميع الأوامر
        # =================================================

        try:

            save_bot_commands(
                self.bot
            )

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

        # =================================================
        # تحديث جميع السيرفرات
        # =================================================

        print(
            "🌐 [WEBSITE] بدء مزامنة السيرفرات..."
        )

        for guild in self.bot.guilds:

            try:

                existing = guilds_collection.find_one(
                    {
                        "guild_id": str(
                            guild.id
                        )
                    }
                )

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
                    f"❌ فشل مزامنة: "
                    f"{guild.name}"
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
    async def on_guild_join(
        self,
        guild
    ):

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
                f"⚠️ فشل معرفة المثبت: "
                f"{error}"
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
    # تنظيف عند إزالة Cog
    # =====================================================

    def cog_unload(
        self
    ):

        try:

            self.bot.remove_check(
                self.website_permission_check
            )

        except Exception:

            pass


# =========================================================
# Setup
# =========================================================

async def setup(
    bot
):

    await bot.add_cog(
        WebsiteCommands(bot)
    )

    print(
        "✅ [WEBSITE] WebsiteCommands جاهز"
    )
