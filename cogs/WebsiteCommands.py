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
    رصيد   -> رصيد
    """

    if not name:
        return ""

    name = str(name).strip()

    while name and name[0] in ("-", ".", "/"):
        name = name[1:]

    return name.strip()


# =========================================================
# أدوات الاختصارات
# =========================================================

def normalize_alias(value):
    """
    توحيد الاختصار.

    أمثلة:

    ذ
    -ذ
    .ذ
    /ذ

    كلها تصبح:

    ذ
    """

    if not value:
        return ""

    value = str(value).strip()

    return normalize_command_name(value)


def find_website_alias(guild_id, typed_alias):
    """
    البحث عن الاختصار الخاص بالسيرفر.

    يدعم تخزين guild_id كنص أو رقم.
    ويدعم الاختصار مع أو بدون بادئة.
    """

    if not guild_id or not typed_alias:
        return None

    guild_id = str(guild_id)

    alias = normalize_alias(
        typed_alias
    )

    if not alias:
        return None

    # =====================================================
    # البحث الأساسي
    # =====================================================

    data = aliases_collection.find_one({
        "guild_id": guild_id,
        "alias": alias
    })

    if data:
        return data

    # =====================================================
    # لو الموقع حفظ الاختصار مع -
    # =====================================================

    data = aliases_collection.find_one({
        "guild_id": guild_id,
        "alias": f"-{alias}"
    })

    if data:
        return data

    # =====================================================
    # لو الموقع حفظ guild_id كرقم
    # =====================================================

    try:

        numeric_guild_id = int(
            guild_id
        )

        data = aliases_collection.find_one({
            "guild_id": numeric_guild_id,
            "alias": alias
        })

        if data:
            return data

        data = aliases_collection.find_one({
            "guild_id": numeric_guild_id,
            "alias": f"-{alias}"
        })

        if data:
            return data

    except Exception:
        pass

    return None


def get_alias_target(data):
    """
    استخراج الأمر الحقيقي من بيانات الاختصار.

    يدعم أكثر من اسم للحقل حتى يكون
    متوافقًا مع نسخ الموقع المختلفة.
    """

    if not data:
        return ""

    target = (
        data.get("command")
        or data.get("command_name")
        or data.get("target")
        or data.get("original_command")
        or ""
    )

    return normalize_command_name(
        target
    )


# =========================================================
# منع تكرار معالجة الاختصار
# =========================================================

_ALIAS_GUARD_ATTRIBUTE = (
    "_website_alias_processing"
)


# =========================================================
# تشغيل الاختصار فعليًا
# =========================================================

async def process_website_alias(
    message,
    bot
):
    """
    تشغيل الاختصار فعليًا.

    مثال:

    المستخدم يكتب:

    ث @شخص

    MongoDB:

    alias = ث
    command = الاستدعاء

    يصبح:

    الاستدعاء @شخص

    ثم يتم تشغيل الأمر الأصلي.
    """

    # =====================================================
    # تجاهل البوتات
    # =====================================================

    if message.author.bot:
        return False

    # =====================================================
    # الرسائل الخاصة لا نلمسها
    # =====================================================

    if message.guild is None:
        return False

    # =====================================================
    # منع إعادة معالجة نفس الرسالة
    # =====================================================

    if getattr(
        message,
        _ALIAS_GUARD_ATTRIBUTE,
        False
    ):
        return False

    content = message.content.strip()

    if not content:
        return False

    # =====================================================
    # استخراج أول كلمة
    #
    # ث
    # ث @شخص
    # ث السبب
    # =====================================================

    parts = content.split()

    if not parts:
        return False

    typed_alias = parts[0]

    # =====================================================
    # البحث عن الاختصار
    # =====================================================

    alias_data = find_website_alias(
        message.guild.id,
        typed_alias
    )

    # =====================================================
    # ليست اختصارًا
    # =====================================================

    if not alias_data:
        return False

    # =====================================================
    # استخراج الأمر الأصلي
    # =====================================================

    target_command = get_alias_target(
        alias_data
    )

    if not target_command:

        print(
            f"⚠️ [ALIAS] الاختصار "
            f"{typed_alias} موجود لكن الأمر الهدف فارغ"
        )

        return False

    # =====================================================
    # بناء الأمر الجديد
    #
    # ث
    # ↓
    # الاستدعاء
    #
    # ث @أحمد
    # ↓
    # الاستدعاء @أحمد
    # =====================================================

    new_content = target_command

    if len(parts) > 1:

        new_content += " "

        new_content += " ".join(
            parts[1:]
        )

    old_content = message.content

    print(
        "=================================================="
    )

    print(
        "🔁 [ALIAS] تم العثور على اختصار"
    )

    print(
        f"👤 المستخدم: "
        f"{message.author} ({message.author.id})"
    )

    print(
        f"📌 الاختصار: {old_content}"
    )

    print(
        f"🎯 الأمر الحقيقي: {new_content}"
    )

    print(
        "=================================================="
    )

    # =====================================================
    # وضع علامة حماية
    # =====================================================

    try:

        setattr(
            message,
            _ALIAS_GUARD_ATTRIBUTE,
            True
        )

    except Exception:
        pass

    # =====================================================
    # تغيير محتوى الرسالة مؤقتًا
    # =====================================================

    message.content = new_content

    try:

        # =================================================
        # أولًا:
        # محاولة العثور على أمر discord.py
        # =================================================

        ctx = await bot.get_context(
            message
        )

        # =================================================
        # إذا كان الأمر مسجلًا في bot.commands
        # =================================================

        if ctx.command is not None:

            print(
                f"✅ [ALIAS] الأمر مسجل في Discord.py: "
                f"{ctx.command.qualified_name}"
            )

            await bot.invoke(
                ctx
            )

            return True

        # =================================================
        # ثانيًا:
        #
        # إذا كان الأمر يدويًا داخل on_message
        #
        # مثال:
        #
        # if message.content.startswith("الاستدعاء"):
        #
        # =================================================

        print(
            "🔄 [ALIAS] الأمر ليس Discord.py command، "
            "سيتم تمريره إلى on_message"
        )

        await bot.dispatch(
            "message",
            message
        )

        return True

    except commands.CommandError as error:

        print(
            "❌ [ALIAS] حدث خطأ أثناء تنفيذ الأمر"
        )

        print(
            f"❌ {type(error).__name__}: {error}"
        )

        return True

    except Exception as error:

        print(
            "❌ [ALIAS] خطأ غير متوقع"
        )

        print(
            f"❌ {type(error).__name__}: {error}"
        )

        traceback.print_exc()

        return True

    finally:

        # =================================================
        # إعادة محتوى الرسالة الأصلي
        # =================================================

        message.content = old_content

        try:

            delattr(
                message,
                _ALIAS_GUARD_ATTRIBUTE
            )

        except Exception:
            pass


# =========================================================
# استخراج أمر من نص
# =========================================================

def clean_detected_command(value):

    if not value:
        return ""

    value = str(value).strip()

    value = normalize_command_name(
        value
    )

    # إزالة أي شيء بعد مسافة
    value = (
        value.split()[0]
        if value
        else ""
    )

    # إزالة علامات شائعة
    value = value.strip(
        "\"'`()[]{}:;,"
    )

    return normalize_command_name(
        value
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
            # message.content.startswith("رتبة")
            # -------------------------------------------------

            patterns = [

                r'\.content\.startswith\(\s*["\']([\-\.\/][^"\']+)["\']',

                r'\.content\s*==\s*["\']([\-\.\/][^"\']+)["\']',

                r'\.content\.startswith\(\s*f?["\']([\-\.\/][^"\']+)["\']',

                r'\.content\.startswith\(\s*["\']([^"\']+)["\']',

                r'\.content\s*==\s*["\']([^"\']+)["\']',

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

    # -----------------------------------------------------
    # بيانات إضافية للأوامر المكتشفة تلقائيًا
    # -----------------------------------------------------

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

        # الأمر اليدوي لا يستبدل أمر Discord الحقيقي
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

        if message.author.bot:
            return

        if message.guild is None:
            return

        try:

            await process_website_alias(
                message,
                self.bot
            )

        except Exception as error:

            print(
                "❌ [ALIAS] خطأ في نظام الاختصارات"
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
        # نخلي الأمر يعمل طبيعي
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
