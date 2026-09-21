import os
import discord
from discord.ext import commands
from flask import Flask
from threading import Thread
from pymongo import MongoClient
from discord.ext.commands.view import StringView

# === إعدادات سيرفر الحفاظ على البوت شغال (Keep Alive) ===
app = Flask('')

@app.route('/')
def home():
    return "I am alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# ========================================================

# === الاتصال بقاعدة البيانات لنظام الألعاب والبيانات ===
mongo_url = os.environ.get('MONGO_URI')
client = MongoClient(mongo_url)
db = client['discord_bot_db']

# ==================================================

# تفعيل الصلاحيات الأساسية وقراءة محتوى الرسائل للذكاء الاصطناعي
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

# ========================================================
# البوت
# ========================================================

bot = commands.Bot(
    command_prefix="-",
    intents=intents
)


# ========================================================
# تشغيل الأوامر بدون Prefix
# ========================================================

@bot.event
async def on_message(message):

    if message.author.bot:
        return

    if not message.guild:
        return

    content = message.content.strip()

    if not content:
        return

    parts = content.split(maxsplit=1)

    command_name = parts[0]

    # إذا بدأ المستخدم بـ - نتجاهله نهائياً
    if command_name.startswith("-"):
        return

    command = bot.get_command(command_name)

    if command is None:
        return

    ctx = await bot.get_context(message)

    ctx.prefix = ""
    ctx.command = command

    ctx.view = StringView(content)
    ctx.view.index = len(command_name)

    try:
        await command.invoke(ctx)

    except commands.CommandError:
        pass


# ========================================================
# جاهزية البوت
# ========================================================

@bot.event
async def on_ready():

    print(f'دخلت السيرفر باسم: {bot.user}')

    try:

        # مزامنة أوامر Slash
        synced = await bot.tree.sync()

        command_names = [
            cmd.name
            for cmd in synced
        ]

        print(
            f"الأوامر المزامنة حالياً: "
            f"{command_names}"
        )

        print(
            f"تمت مزامنة {len(synced)} "
            f"أمر عالمياً بنجاح!"
        )

    except Exception as e:

        print(
            f"خطأ في مزامنة الأوامر: {e}"
        )


# ========================================================
# تحميل الـ Cogs
# ========================================================

async def load_extensions():

    for filename in os.listdir('./cogs'):

        if filename.endswith('.py'):

            try:

                await bot.load_extension(
                    f'cogs.{filename[:-3]}'
                )

                print(
                    f'✅ تم تحميل الملف بنجاح: '
                    f'{filename}'
                )

            except Exception as e:

                print(
                    f'❌ فشل تحميل الملف '
                    f'{filename} بسبب الخطأ التالي: '
                    f'{e}'
                )


# ========================================================
# Setup Hook
# ========================================================

@bot.event
async def setup_hook():

    await load_extensions()


# ========================================================
# تشغيل البوت
# ========================================================

keep_alive()

TOKEN = os.environ.get('TOKEN')

bot.run(TOKEN)
