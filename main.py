import os
import discord
from discord.ext import commands
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
    app.run(host='0.0.0.0', port=8080)


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
# البوت
# ========================================================

bot = commands.Bot(
    command_prefix="",
    intents=intents,
    help_command=None
)


# ========================================================
# منع أي أمر يبدأ بـ - أو . أو /
# ========================================================

@bot.check
async def global_command_check(ctx):

    content = ctx.message.content.strip()

    if not content:
        return False

    # ممنوع:
    # -رصيد
    # .رصيد
    # /رصيد
    if content[0] in ("-", ".", "/"):
        return False

    return True


# ========================================================
# معالجة الرسائل
# ========================================================

@bot.event
async def on_message(message):

    # تجاهل البوتات
    if message.author.bot:
        return

    # تجاهل الخاص
    if message.guild is None:
        return

    content = message.content.strip()

    if not content:
        return

    # ====================================================
    # منع البادئات
    # ====================================================

    if content[0] in ("-", ".", "/"):
        return

    # ====================================================
    # تشغيل الأوامر بدون Prefix
    # ====================================================

    await bot.process_commands(message)


# ========================================================
# تحميل الـ Cogs
# ========================================================

async def load_extensions():

    if not os.path.exists("./cogs"):
        print("❌ مجلد cogs غير موجود!")
        return

    for filename in os.listdir("./cogs"):

        if not filename.endswith(".py"):
            continue

        if filename.startswith("_"):
            continue

        extension = f"cogs.{filename[:-3]}"

        try:

            await bot.load_extension(extension)

            print(
                f"✅ تم تحميل الملف بنجاح: {filename}"
            )

        except Exception as e:

            print(
                f"❌ فشل تحميل الملف {filename}"
            )

            print(
                f"الخطأ: {type(e).__name__}: {e}"
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

    print("========================================")
    print(f"🤖 دخلت السيرفر باسم: {bot.user}")
    print(f"🆔 ID: {bot.user.id}")
    print("========================================")

    try:

        synced = await bot.tree.sync()

        command_names = [
            command.name
            for command in synced
        ]

        print(
            f"✅ تمت مزامنة {len(synced)} أمر Slash"
        )

        if command_names:
            print(
                f"📋 أوامر Slash: {command_names}"
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


bot.run(TOKEN)
