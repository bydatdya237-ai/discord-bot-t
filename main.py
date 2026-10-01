import os
import discord
from discord.ext import commands
from flask import Flask
from threading import Thread
from pymongo import MongoClient


# ========================================================
# إعدادات Keep Alive
# ========================================================

app = Flask("")


@app.route("/")
def home():
    return "I am alive!"


def run():
    app.run(
        host="0.0.0.0",
        port=8080
    )


def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()


# ========================================================
# الاتصال بقاعدة البيانات
# ========================================================

mongo_url = os.environ.get("MONGO_URI")

if not mongo_url:
    raise RuntimeError(
        "❌ MONGO_URI غير موجود في Environment Variables"
    )

client = MongoClient(mongo_url)

db = client["discord_bot_db"]


# ========================================================
# إعدادات تحكم الموقع
# ========================================================

website_command_settings = db[
    "website_command_settings"
]


# ========================================================
# اختصارات الموقع
# ========================================================

website_command_aliases = db[
    "website_command_aliases"
]


# ========================================================
# Intents
# ========================================================

intents = discord.Intents.default()

intents.members = True
intents.message_content = True


# ========================================================
# Bot
# ========================================================

bot = commands.Bot(
    command_prefix="",
    intents=intents,
    help_command=None
)


# ========================================================
# اختبار تشغيل الملف
# ========================================================

print("🔥🔥🔥 MAIN FILE RUNNING 🔥🔥🔥")
print(f"📁 الملف الحالي: {__file__}")
print(f"⌨️ Command Prefix: {bot.command_prefix!r}")


# ========================================================
# أدوات اختصارات الموقع
# ========================================================

def normalize_command_name(value):

    if value is None:
        return ""

    value = str(value).strip()

    while value.startswith(
        ("-", ".", "/")
    ):
        value = value[1:].strip()

    return value


def normalize_alias(value):

    if value is None:
        return ""

    value = str(value).strip()

    while value.startswith(
        ("-", ".", "/")
    ):
        value = value[1:].strip()

    return value


def get_message_first_word(content):

    if not content:
        return ""

    parts = content.strip().split()

    if not parts:
        return ""

    return normalize_command_name(
        parts[0]
    )


# ========================================================
# استخراج كل اختصارات الأمر
# ========================================================

def find_all_website_aliases_for_command(
    guild_id,
    command_name
):

    if guild_id is None:
        return []

    command_name = normalize_command_name(
        command_name
    )

    if not command_name:
        return []

    guild_values = [
        str(guild_id),
        guild_id
    ]

    command_values = [
        command_name,
        f"-{command_name}",
        f".{command_name}",
        f"/{command_name}"
    ]

    query = {
        "$and": [
            {
                "$or": [
                    {
                        "guild_id": value
                    }
                    for value in guild_values
                ]
            },
            {
                "$or": (
                    [
                        {
                            "command": value
                        }
                        for value in command_values
                    ]
                    +
                    [
                        {
                            "command_name": value
                        }
                        for value in command_values
                    ]
                    +
                    [
                        {
                            "target": value
                        }
                        for value in command_values
                    ]
                    +
                    [
                        {
                            "original_command": value
                        }
                        for value in command_values
                    ]
                )
            }
        ]
    }

    try:

        documents = list(
            website_command_aliases.find(
                query
            )
        )

    except Exception as e:

        print(
            "=================================================="
        )

        print(
            "❌ [WEBSITE ALIAS DATABASE ERROR]"
        )

        print(
            f"❌ الخطأ: {type(e).__name__}: {e}"
        )

        print(
            "=================================================="
        )

        return []

    aliases = []
    seen = set()

    for document in documents:

        if not document:
            continue

        alias = (
            document.get("alias")
            or document.get("shortcut")
            or document.get("short")
        )

        if not alias:
            continue

        alias = normalize_alias(alias)

        if not alias:
            continue

        alias_key = alias.casefold()

        if alias_key in seen:
            continue

        seen.add(alias_key)

        aliases.append(alias)

    return aliases


# ========================================================
# البحث عن اختصار معين
# ========================================================

def find_website_alias(
    guild_id,
    typed_alias
):

    if guild_id is None:
        return None

    typed_alias = normalize_alias(
        typed_alias
    )

    if not typed_alias:
        return None

    guild_values = [
        str(guild_id),
        guild_id
    ]

    alias_values = [
        typed_alias,
        f"-{typed_alias}",
        f".{typed_alias}",
        f"/{typed_alias}"
    ]

    query = {
        "$and": [
            {
                "$or": [
                    {
                        "guild_id": value
                    }
                    for value in guild_values
                ]
            },
            {
                "$or": (
                    [
                        {
                            "alias": value
                        }
                        for value in alias_values
                    ]
                    +
                    [
                        {
                            "shortcut": value
                        }
                        for value in alias_values
                    ]
                    +
                    [
                        {
                            "short": value
                        }
                        for value in alias_values
                    ]
                )
            }
        ]
    }

    try:

        return website_command_aliases.find_one(
            query
        )

    except Exception as e:

        print(
            "=================================================="
        )

        print(
            "❌ [WEBSITE ALIAS SEARCH ERROR]"
        )

        print(
            f"❌ الخطأ: {type(e).__name__}: {e}"
        )

        print(
            "=================================================="
        )

        return None


# ========================================================
# استخراج الاختصار من مستند MongoDB
# ========================================================

def get_alias_from_document(data):

    if not data:
        return None

    alias = (
        data.get("alias")
        or data.get("shortcut")
        or data.get("short")
    )

    if not alias:
        return None

    alias = normalize_alias(
        alias
    )

    if not alias:
        return None

    return alias


# ========================================================
# فحص تحكم الموقع بالأمر
# ========================================================

def website_command_allowed(ctx):

    if ctx.guild is None:
        return True

    if ctx.command is None:
        return True

    command_name = normalize_command_name(
        ctx.command.name
    )

    setting = website_command_settings.find_one(
        {
            "guild_id": str(ctx.guild.id),
            "command_name": command_name
        }
    )

    # دعم name أيضًا
    if not setting:

        setting = website_command_settings.find_one(
            {
                "guild_id": str(ctx.guild.id),
                "name": command_name
            }
        )

    if not setting:
        return True

    if not setting.get(
        "enabled",
        False
    ):
        return True

    # ====================================================
    # الرومات
    # ====================================================

    allowed_channels = setting.get(
        "channel_ids",
        []
    )

    if allowed_channels:

        allowed_channels = {
            str(channel_id)
            for channel_id in allowed_channels
        }

        if str(ctx.channel.id) not in allowed_channels:

            print(
                "=================================================="
            )

            print(
                "🚫 [WEBSITE CHANNEL BLOCK]"
            )

            print(
                f"👤 المستخدم: "
                f"{ctx.author} "
                f"(ID: {ctx.author.id})"
            )

            print(
                f"📌 الأمر: {command_name}"
            )

            print(
                f"📍 الروم الحالي: "
                f"{ctx.channel.name} "
                f"(ID: {ctx.channel.id})"
            )

            print(
                "❌ الأمر غير مسموح في هذا الروم"
            )

            print(
                "=================================================="
            )

            return False

    # ====================================================
    # الرتب
    # ====================================================

    allowed_roles = setting.get(
        "role_ids",
        []
    )

    if allowed_roles:

        allowed_roles = {
            str(role_id)
            for role_id in allowed_roles
        }

        user_roles = {
            str(role.id)
            for role in ctx.author.roles
        }

        if not user_roles.intersection(
            allowed_roles
        ):

            print(
                "=================================================="
            )

            print(
                "🚫 [WEBSITE ROLE BLOCK]"
            )

            print(
                f"👤 المستخدم: "
                f"{ctx.author} "
                f"(ID: {ctx.author.id})"
            )

            print(
                f"📌 الأمر: {command_name}"
            )

            print(
                "❌ المستخدم لا يملك رتبة مسموحة"
            )

            print(
                "=================================================="
            )

            return False

    return True


# ========================================================
# تحويل اسم المتغير إلى شكل مفهوم للمستخدم
# ========================================================

def get_usage_name(param):

    if param is None:
        return "المطلوب"

    name = str(
        getattr(
            param,
            "name",
            "المطلوب"
        )
    )

    name_lower = name.lower()

    member_names = {
        "member",
        "user",
        "person",
        "target",
        "person_member",
        "عضو",
        "شخص"
    }

    role_names = {
        "role",
        "رتبة",
        "group",
        "مجموعة"
    }

    if name_lower in member_names:
        return "@الشخص"

    if name_lower in role_names:
        return "@الرتبة"

    return f"<{name}>"


# ========================================================
# بناء استخدام الأمر بواسطة الاختصار
# ========================================================

def build_alias_usage(
    ctx,
    alias_context,
    error
):

    if not alias_context:
        return None

    alias_name = normalize_alias(
        alias_context.get("alias")
    )

    if not alias_name:
        return None

    command = ctx.command

    if command is None:
        return None

    # ====================================================
    # إذا الأمر لديه usage مخصص
    # ====================================================

    usage = getattr(
        command,
        "usage",
        None
    )

    if usage:

        usage = str(usage).strip()

        if usage:

            # إزالة اسم الأمر الأصلي إذا كان
            # موجودًا في بداية usage
            usage_parts = usage.split()

            if usage_parts:

                first = normalize_command_name(
                    usage_parts[0]
                )

                command_name = normalize_command_name(
                    command.name
                )

                if first == command_name:

                    usage = " ".join(
                        usage_parts[1:]
                    )

            if usage:

                return (
                    f"{alias_name} {usage}"
                )

    # ====================================================
    # استخدام signature الخاص بالأمر
    # ====================================================

    signature = str(
        getattr(
            command,
            "signature",
            ""
        ) or ""
    ).strip()

    if signature:

        return (
            f"{alias_name} {signature}"
        )

    # ====================================================
    # آخر حل: اسم المتغير الناقص
    # ====================================================

    param = getattr(
        error,
        "param",
        None
    )

    parameter_name = get_usage_name(
        param
    )

    return (
        f"{alias_name} {parameter_name}"
    )


# ========================================================
# معالجة خطأ المتغير الناقص للاختصار
# ========================================================

async def handle_alias_missing_argument(
    ctx,
    error
):

    alias_context = getattr(
        ctx,
        "_website_alias_context",
        None
    )

    if not alias_context:

        alias_context = getattr(
            ctx.message,
            "_website_alias_context",
            None
        )

    if not alias_context:
        return False

    usage = build_alias_usage(
        ctx,
        alias_context,
        error
    )

    if not usage:
        return False

    try:

        await ctx.send(
            "❌ الاستخدام الصحيح:\n"
            f"`{usage}`"
        )

    except Exception as send_error:

        print(
            "❌ فشل إرسال استخدام الاختصار"
        )

        print(
            f"❌ {type(send_error).__name__}: "
            f"{send_error}"
        )

    print(
        "=================================================="
    )

    print(
        "⚠️ [ALIAS MISSING ARGUMENT]"
    )

    print(
        f"👤 المستخدم: "
        f"{ctx.author} "
        f"(ID: {ctx.author.id})"
    )

    print(
        f"🔤 الاختصار: "
        f"{alias_context.get('alias')}"
    )

    print(
        f"📌 الأمر الحقيقي: "
        f"{alias_context.get('target_command')}"
    )

    print(
        f"📖 الاستخدام: "
        f"{usage}"
    )

    print(
        "=================================================="
    )

    return True


# ========================================================
# معالجة الرسائل
# ========================================================

@bot.event
async def on_message(message):

    # ====================================================
    # تجاهل البوتات
    # ====================================================

    if message.author.bot:
        return

    # ====================================================
    # تجاهل الخاص
    # ====================================================

    if message.guild is None:
        return

    content = message.content.strip()

    if not content:
        return

    # ====================================================
    # منع Prefix
    # ====================================================

    if content[0] in ("-", ".", "/"):

        print(
            "=================================================="
        )

        print(
            "🚫 [BLOCKED PREFIX]"
        )

        print(
            f"👤 المستخدم: "
            f"{message.author} "
            f"(ID: {message.author.id})"
        )

        print(
            f"💬 الرسالة: {message.content!r}"
        )

        print(
            f"🔤 Prefix الممنوع: {content[0]!r}"
        )

        print(
            "📌 لم يتم تشغيل أي أمر"
        )

        print(
            "=================================================="
        )

        return

    # ====================================================
    # تسجيل الرسالة
    # ====================================================

    print(
        "=================================================="
    )

    print(
        "📨 [MESSAGE RECEIVED]"
    )

    print(
        f"👤 المستخدم: "
        f"{message.author} "
        f"(ID: {message.author.id})"
    )

    print(
        f"💬 الرسالة: {message.content!r}"
    )

    print(
        "📌 محاولة معالجة الأمر بدون Prefix"
    )

    print(
        "=================================================="
    )

    # ====================================================
    # الاختصارات
    #
    # مهم:
    # Main هو المكان الوحيد الذي يشغل الاختصار.
    # لا يوجد on_message للاختصار داخل WebsiteCommands.
    # ====================================================

    alias_processor = getattr(
        bot,
        "website_alias_processor",
        None
    )

    if alias_processor:

        try:

            alias_handled = await alias_processor(
                message,
                bot
            )

            if alias_handled:

                print(
                    "=================================================="
                )

                print(
                    "✅ [WEBSITE ALIAS HANDLED]"
                )

                print(
                    f"👤 المستخدم: "
                    f"{message.author} "
                    f"(ID: {message.author.id})"
                )

                print(
                    "📌 تم تنفيذ الاختصار مرة واحدة"
                )

                print(
                    "=================================================="
                )

                return

        except Exception as e:

            print(
                "=================================================="
            )

            print(
                "❌ [WEBSITE ALIAS PROCESSOR ERROR]"
            )

            print(
                f"❌ الخطأ: "
                f"{type(e).__name__}: {e}"
            )

            print(
                "=================================================="
            )

    # ====================================================
    # قراءة الأمر
    # ====================================================

    ctx = await bot.get_context(
        message
    )

    # ====================================================
    # فحص الأمر الأصلي
    # ====================================================

    if ctx.command:

        command_name = normalize_command_name(
            ctx.command.name
        )

        first_word = get_message_first_word(
            message.content
        )

        # =================================================
        # منع الأمر الأصلي إذا كان له اختصار
        # =================================================

        if first_word == command_name:

            aliases = (
                find_all_website_aliases_for_command(
                    message.guild.id,
                    command_name
                )
            )

            if aliases:

                aliases_text = "، ".join(
                    aliases
                )

                print(
                    "=================================================="
                )

                print(
                    "🚫 [ORIGINAL COMMAND BLOCKED]"
                )

                print(
                    f"👤 المستخدم: "
                    f"{message.author} "
                    f"(ID: {message.author.id})"
                )

                print(
                    f"📌 الأمر الأصلي: "
                    f"{command_name}"
                )

                print(
                    f"🔤 الاختصارات المتاحة: "
                    f"{aliases_text}"
                )

                print(
                    "📌 تم منع استخدام الأمر الأصلي"
                )

                print(
                    "=================================================="
                )

                try:

                    await message.channel.send(
                        "❌ هذا الأمر غير متاح حاليًا.\n"
                        f"🔤 الاختصارات المتاحة: `{aliases_text}`"
                    )

                except Exception as e:

                    print(
                        "❌ فشل إرسال رسالة منع الأمر:"
                    )

                    print(
                        f"{type(e).__name__}: {e}"
                    )

                return

        # =================================================
        # صلاحيات الموقع
        # =================================================

        if not website_command_allowed(ctx):
            return

    # ====================================================
    # تشغيل الأوامر
    # ====================================================

    await bot.process_commands(
        message
    )


# ========================================================
# أخطاء الأوامر
# ========================================================

@bot.event
async def on_command_error(
    ctx,
    error
):

    # ====================================================
    # منع تكرار معالجة الخطأ
    # ====================================================

    if getattr(
        ctx,
        "_website_error_handled",
        False
    ):
        return

    try:

        setattr(
            ctx,
            "_website_error_handled",
            True
        )

    except Exception:
        pass

    # ====================================================
    # أمر غير موجود
    # ====================================================

    if isinstance(
        error,
        commands.CommandNotFound
    ):

        print(
            "=================================================="
        )

        print(
            "⚠️ [COMMAND NOT FOUND]"
        )

        print(
            f"👤 المستخدم: "
            f"{ctx.author} "
            f"(ID: {ctx.author.id})"
        )

        print(
            f"💬 الرسالة: "
            f"{ctx.message.content!r}"
        )

        print(
            "📌 لا يوجد أمر بهذا الاسم"
        )

        print(
            "=================================================="
        )

        return

    # ====================================================
    # فشل Check
    # ====================================================

    if isinstance(
        error,
        commands.CheckFailure
    ):

        print(
            "=================================================="
        )

        print(
            "🚫 [COMMAND CHECK FAILED]"
        )

        print(
            f"👤 المستخدم: "
            f"{ctx.author} "
            f"(ID: {ctx.author.id})"
        )

        print(
            f"💬 الرسالة: "
            f"{ctx.message.content!r}"
        )

        if ctx.command:

            print(
                f"📌 الأمر: "
                f"{ctx.command.name}"
            )

        print(
            "📌 أحد شروط الأمر رفض التنفيذ"
        )

        print(
            "=================================================="
        )

        return

    # ====================================================
    # متغير ناقص
    # ====================================================

    if isinstance(
        error,
        commands.MissingRequiredArgument
    ):

        # =================================================
        # إذا الأمر جاء من اختصار
        # =================================================

        handled = await handle_alias_missing_argument(
            ctx,
            error
        )

        if handled:
            return

        # =================================================
        # أمر عادي
        # =================================================

        print(
            "=================================================="
        )

        print(
            "⚠️ [MISSING ARGUMENT]"
        )

        print(
            f"👤 المستخدم: "
            f"{ctx.author} "
            f"(ID: {ctx.author.id})"
        )

        print(
            f"💬 الرسالة: "
            f"{ctx.message.content!r}"
        )

        if ctx.command:

            print(
                f"📌 الأمر: "
                f"{ctx.command.name}"
            )

        print(
            f"📌 المتغير المطلوب: "
            f"{error.param.name}"
        )

        print(
            "=================================================="
        )

        return

    # ====================================================
    # خطأ آخر
    # ====================================================

    print(
        "=================================================="
    )

    print(
        "❌ [COMMAND ERROR]"
    )

    print(
        f"👤 المستخدم: "
        f"{ctx.author} "
        f"(ID: {ctx.author.id})"
    )

    print(
        f"💬 الرسالة: "
        f"{ctx.message.content!r}"
    )

    if ctx.command:

        print(
            f"📌 الأمر: "
            f"{ctx.command.name}"
        )

    print(
        f"❌ الخطأ: "
        f"{type(error).__name__}: {error}"
    )

    print(
        "=================================================="
    )


# ========================================================
# تحميل الـ Cogs
# ========================================================

async def load_extensions():

    if not os.path.exists(
        "./cogs"
    ):

        print(
            "❌ مجلد cogs غير موجود!"
        )

        return

    for filename in os.listdir(
        "./cogs"
    ):

        if not filename.endswith(
            ".py"
        ):
            continue

        if filename.startswith(
            "_"
        ):
            continue

        extension = (
            f"cogs.{filename[:-3]}"
        )

        try:

            await bot.load_extension(
                extension
            )

            print(
                f"✅ تم تحميل الملف بنجاح: "
                f"{filename}"
            )

        except Exception as e:

            print(
                f"❌ فشل تحميل الملف: "
                f"{filename}"
            )

            print(
                f"الخطأ: "
                f"{type(e).__name__}: {e}"
            )


# ========================================================
# Setup Hook
# ========================================================

@bot.event
async def setup_hook():

    await load_extensions()


# ========================================================
# جاهزية البوت
# ========================================================

@bot.event
async def on_ready():

    print(
        "=================================================="
    )

    print(
        f"🤖 دخلت السيرفر باسم: "
        f"{bot.user}"
    )

    print(
        f"🆔 ID: "
        f"{bot.user.id}"
    )

    print(
        f"⌨️ Command Prefix: "
        f"{bot.command_prefix!r}"
    )

    print(
        "🚫 Prefixes الممنوعة: - . /"
    )

    print(
        "✅ الأوامر تعمل بدون Prefix"
    )

    print(
        "🌐 تحكم الموقع بالرومات والرتب مفعل"
    )

    print(
        "🔤 نظام اختصارات الموقع مفعل"
    )

    print(
        "🔤 دعم عدة اختصارات لنفس الأمر مفعل"
    )

    print(
        "🚫 الأمر الأصلي يتم منعه إذا كان له اختصار"
    )

    print(
        f"📦 عدد الأوامر المسجلة: "
        f"{len(bot.commands)}"
    )

    print(
        "=================================================="
    )


# ========================================================
# تشغيل Keep Alive
# ========================================================

keep_alive()


# ========================================================
# تشغيل البوت
# ========================================================

TOKEN = os.environ.get(
    "TOKEN"
)

if not TOKEN:

    raise RuntimeError(
        "❌ TOKEN غير موجود في Environment Variables"
    )


print(
    "🚀 جاري تشغيل البوت..."
)


bot.run(
    TOKEN
)
