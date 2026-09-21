import os
import discord
from discord.ext import commands
from discord.ext.commands.view import StringView
from flask import Flask
from threading import Thread
from pymongo import MongoClient


# ========================================================
# إعدادات Keep Alive
# ========================================================

app = Flask('')


@app.route('/')
def home():
    return "I am alive!"


def run():
    app.run(
        host='0.0.0.0',
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
# Bot مخصص
#
# لا نستخدم command_prefix="" بالطريقة التقليدية.
#
# البوت يبحث عن اسم الأمر مباشرة من الرسالة.
# ========================================================

class NoPrefixBot(commands.Bot):

    async def get_context(
        self,
        message,
        *,
        cls=commands.Context
    ):

        content = message.content.strip()

        # ==================================================
        # إنشاء Context
        # ==================================================

        ctx = cls(
            message=message,
            bot=self
        )

        ctx.prefix = ""
        ctx.command = None

        # ==================================================
        # رسالة فارغة
        # ==================================================

        if not content:
            return ctx

        # ==================================================
        # منع Prefix
        # ==================================================

        if content[0] in ("-", ".", "/"):

            print(
                "=================================================="
            )

            print(
                "🚫 [COMMAND BLOCKED]"
            )

            print(
                f"👤 المستخدم: "
                f"{message.author} "
                f"(ID: {message.author.id})"
            )

            print(
                f"💬 المحتوى: {message.content!r}"
            )

            print(
                f"🔤 Prefix المكتشف: {content[0]!r}"
            )

            print(
                "📌 السبب: Prefix غير مسموح"
            )

            print(
                "=================================================="
            )

            return ctx

        # ==================================================
        # إنشاء View للرسالة
        # ==================================================

        view = StringView(message.content)

        ctx.view = view

        # ==================================================
        # قراءة أول كلمة فقط
        #
        # مثال:
        #
        # رصيد
        # توب 1
        # اعطي @شخص 5000
        #
        # أول كلمة هي اسم الأمر.
        # ==================================================

        command_name = view.get_word()

        if not command_name:

            return ctx

        # ==================================================
        # البحث عن الأمر
        # ==================================================

        command = self.get_command(command_name)

        # ==================================================
        # الأمر غير موجود
        # ==================================================

        if command is None:

            print(
                "=================================================="
            )

            print(
                "⚠️ [COMMAND NOT FOUND]"
            )

            print(
                f"👤 المستخدم: "
                f"{message.author} "
                f"(ID: {message.author.id})"
            )

            print(
                f"💬 المحتوى: {message.content!r}"
            )

            print(
                f"🔎 الأمر المطلوب: {command_name!r}"
            )

            print(
                "📌 السبب: لا يوجد أمر مسجل بهذا الاسم"
            )

            print(
                "=================================================="
            )

            return ctx

        # ==================================================
        # الأمر موجود
        # ==================================================

        ctx.command = command

        ctx.prefix = ""

        print(
            "=================================================="
        )

        print(
            "✅ [COMMAND DETECTED]"
        )

        print(
            f"👤 المستخدم: "
            f"{message.author} "
            f"(ID: {message.author.id})"
        )

        print(
            f"💬 المحتوى: {message.content!r}"
        )

        print(
            f"⚡ الأمر: {command.name!r}"
        )

        print(
            "📌 Prefix: بدون Prefix"
        )

        print(
            "=================================================="
        )

        return ctx


# ========================================================
# البوت
#
# مهم:
# command_prefix هنا مجرد قيمة شكلية لأننا عملنا
# get_context مخصص فوق.
# ========================================================

bot = NoPrefixBot(
    command_prefix="",
    intents=intents,
    help_command=None
)


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
    # تجاهل الرسائل الفارغة
    # ====================================================

    if not content:
        return

    # ====================================================
    # منع Prefix
    #
    # هذا الفحص يتم قبل process_commands.
    # ====================================================

    if content[0] in ("-", ".", "/"):

        print(
            "=================================================="
        )

        print(
            "🚫 [MESSAGE BLOCKED]"
        )

        print(
            f"👤 المستخدم: "
            f"{message.author} "
            f"(ID: {message.author.id})"
        )

        print(
            f"💬 المحتوى: {message.content!r}"
        )

        print(
            f"🔤 Prefix: {content[0]!r}"
        )

        print(
            "📌 السبب: الرسالة تبدأ بـ Prefix ممنوع"
        )

        print(
            "=================================================="
        )

        return

    # ====================================================
    # تشغيل نظام الأوامر
    # ====================================================

    await bot.process_commands(message)


# ========================================================
# مراقبة أخطاء الأوامر
# ========================================================

@bot.event
async def on_command_error(ctx, error):

    # ====================================================
    # الأمر غير موجود
    # ====================================================

    if isinstance(
        error,
        commands.CommandNotFound
    ):

        print(
            "=================================================="
        )

        print(
            "⚠️ [COMMAND NOT FOUND ERROR]"
        )

        print(
            f"👤 المستخدم: "
            f"{ctx.author} "
            f"(ID: {ctx.author.id})"
        )

        print(
            f"💬 المحتوى: {ctx.message.content!r}"
        )

        print(
            "📌 السبب: الأمر غير موجود"
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
            f"💬 المحتوى: {ctx.message.content!r}"
        )

        print(
            f"📌 الأمر: "
            f"{ctx.command.name if ctx.command else 'غير معروف'}"
        )

        print(
            "📌 السبب: أحد شروط الأمر رفض التنفيذ"
        )

        print(
            "=================================================="
        )

        return

    # ====================================================
    # متغير مطلوب
    # ====================================================

    if isinstance(
        error,
        commands.MissingRequiredArgument
    ):

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
            f"💬 المحتوى: {ctx.message.content!r}"
        )

        print(
            f"📌 الأمر: "
            f"{ctx.command.name if ctx.command else 'غير معروف'}"
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
        f"💬 المحتوى: {ctx.message.content!r}"
    )

    print(
        f"📌 الأمر: "
        f"{ctx.command.name if ctx.command else 'غير معروف'}"
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
        "========================================"
    )

    print(
        f"🤖 دخلت السيرفر باسم: {bot.user}"
    )

    print(
        f"🆔 ID: {bot.user.id}"
    )

    print(
        "🚫 Prefixes الممنوعة: - . /"
    )

    print(
        "✅ نظام الأوامر: بدون Prefix"
    )

    print(
        "========================================"
    )

    try:

        synced = await bot.tree.sync()

        command_names = [
            command.name
            for command in synced
        ]

        print(
            f"✅ تمت مزامنة "
            f"{len(synced)} أمر Slash"
        )

        if command_names:

            print(
                f"📋 أوامر Slash: "
                f"{command_names}"
            )

    except Exception as e:

        print(
            f"❌ خطأ في مزامنة أوامر Slash: "
            f"{type(e).__name__}: {e}"
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
    "🔥🔥🔥 MAIN FILE RUNNING - NO PREFIX VERSION 🔥🔥🔥"
)

bot.run(TOKEN)
