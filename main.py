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
# فحص تحكم الموقع بالأمر
# ========================================================

def website_command_allowed(ctx):

    # ====================================================
    # إذا ما فيه سيرفر
    # ====================================================

    if ctx.guild is None:
        return True

    # ====================================================
    # إذا ما فيه أمر
    # ====================================================

    if ctx.command is None:
        return True

    # ====================================================
    # اسم الأمر الحقيقي
    # ====================================================

    command_name = str(
        ctx.command.name
    )

    # ====================================================
    # إزالة Prefix احتياطيًا
    # ====================================================

    for prefix in ("-", ".", "/"):

        if command_name.startswith(prefix):

            command_name = command_name[1:]


    # ====================================================
    # البحث عن إعدادات الأمر
    # ====================================================

    setting = website_command_settings.find_one(
        {
            "guild_id": str(ctx.guild.id),
            "command_name": command_name
        }
    )


    # ====================================================
    # لا توجد إعدادات
    #
    # نخلي الأمر يعمل مثل السابق
    # ====================================================

    if not setting:

        return True


    # ====================================================
    # التحكم غير مفعل
    # ====================================================

    if not setting.get(
        "enabled",
        False
    ):

        return True


    # ====================================================
    # الرومات المسموح فيها
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
    # الرتب المسموح لها
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


    # ====================================================
    # مسموح
    # ====================================================

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

    # ====================================================
    # رسالة فارغة
    # ====================================================

    if not content:
        return

    # ====================================================
    # منع Prefix
    #
    # -رصيد
    # .رصيد
    # /رصيد
    #
    # كلها يتم تجاهلها نهائياً.
    # ====================================================

    if content[0] in ("-", ".", "/"):

        print(
            "=================================================="
        )
        print("🚫 [BLOCKED PREFIX]")
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
        print("📌 لم يتم تشغيل أي أمر")
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
    print("📨 [MESSAGE RECEIVED]")
    print(
        f"👤 المستخدم: "
        f"{message.author} "
        f"(ID: {message.author.id})"
    )
    print(
        f"💬 الرسالة: {message.content!r}"
    )
    print("📌 محاولة معالجة الأمر بدون Prefix")
    print(
        "=================================================="
    )

    # ====================================================
    # قراءة الأمر قبل تشغيله
    # ====================================================

    ctx = await bot.get_context(
        message
    )

    # ====================================================
    # إذا كان أمرًا معروفًا
    # نتحقق من إعدادات الموقع
    # ====================================================

    if ctx.command:

        if not website_command_allowed(ctx):

            # ------------------------------------------------
            # مهم:
            # لا نرسل رسالة للمستخدم.
            # الأمر يتجاهل بصمت.
            # ------------------------------------------------

            return

    # ====================================================
    # تشغيل الأوامر
    # ====================================================

    await bot.process_commands(message)


# ========================================================
# أخطاء الأوامر
# ========================================================

@bot.event
async def on_command_error(ctx, error):

    # ====================================================
    # أمر غير موجود
    # ====================================================

    if isinstance(error, commands.CommandNotFound):

        print(
            "=================================================="
        )
        print("⚠️ [COMMAND NOT FOUND]")
        print(
            f"👤 المستخدم: "
            f"{ctx.author} "
            f"(ID: {ctx.author.id})"
        )
        print(
            f"💬 الرسالة: {ctx.message.content!r}"
        )
        print("📌 لا يوجد أمر بهذا الاسم")
        print(
            "=================================================="
        )

        return

    # ====================================================
    # فشل صلاحيات / Check
    # ====================================================

    if isinstance(error, commands.CheckFailure):

        print(
            "=================================================="
        )
        print("🚫 [COMMAND CHECK FAILED]")
        print(
            f"👤 المستخدم: "
            f"{ctx.author} "
            f"(ID: {ctx.author.id})"
        )
        print(
            f"💬 الرسالة: {ctx.message.content!r}"
        )

        if ctx.command:
            print(
                f"📌 الأمر: {ctx.command.name}"
            )

        print("📌 أحد شروط الأمر رفض التنفيذ")
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

        print(
            "=================================================="
        )
        print("⚠️ [MISSING ARGUMENT]")
        print(
            f"👤 المستخدم: "
            f"{ctx.author} "
            f"(ID: {ctx.author.id})"
        )
        print(
            f"💬 الرسالة: {ctx.message.content!r}"
        )

        if ctx.command:
            print(
                f"📌 الأمر: {ctx.command.name}"
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
    print("❌ [COMMAND ERROR]")
    print(
        f"👤 المستخدم: "
        f"{ctx.author} "
        f"(ID: {ctx.author.id})"
    )
    print(
        f"💬 الرسالة: {ctx.message.content!r}"
    )

    if ctx.command:
        print(
            f"📌 الأمر: {ctx.command.name}"
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

    if not os.path.exists("./cogs"):

        print(
            "❌ مجلد cogs غير موجود!"
        )

        return

    for filename in os.listdir("./cogs"):

        if not filename.endswith(".py"):
            continue

        if filename.startswith("_"):
            continue

        extension = f"cogs.{filename[:-3]}"

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
        f"🤖 دخلت السيرفر باسم: {bot.user}"
    )

    print(
        f"🆔 ID: {bot.user.id}"
    )

    print(
        f"⌨️ Command Prefix: {bot.command_prefix!r}"
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

TOKEN = os.environ.get("TOKEN")

if not TOKEN:

    raise RuntimeError(
        "❌ TOKEN غير موجود في Environment Variables"
    )


print(
    "🚀 جاري تشغيل البوت..."
)

bot.run(TOKEN)
