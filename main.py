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
