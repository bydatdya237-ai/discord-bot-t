import os
import discord
from discord.ext import commands
from flask import Flask
from threading import Thread
from pymongo import MongoClient

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

# === الاتصال بقاعدة البيانات لنظام رومات الأوامر ===
mongo_url = os.environ.get('MONGO_URI')
client = MongoClient(mongo_url)
db = client['discord_db']
command_channels_collection = db['command_channels']
# ==================================================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# الآيدي المؤقت المخصص لجميع الأوامر
TEMPORARY_CHANNEL_ID = 1545187326093693038

@bot.event
async def on_ready():
    print(f'دخلت السيرفر باسم: {bot.user}')

# === نظام الفحص المباشر والمضمون 100% ===
@bot.event
async def on_message(message):
    # تجاهل رسائل البوتات عشان ما يدخل بنهائي لوب
    if message.author.bot:
        return

    # إذا الرسالة تبدأ بـ !
    if message.content.startswith("!"):
        # لو الكاتب مو صاحب السيرفر وروم الرسالة يختلف عن الروم المخصص
        if message.guild and message.author.id != message.guild.owner_id:
            if message.channel.id != TEMPORARY_CHANNEL_ID:
                try:
                    await message.delete() # حذف رسالة الأمر المخالف بصمت
                except Exception as e:
                    print(f"خطأ بالحذف: {e}")
                return # وقف التنفيذ تماماً ولا عاد تقرأ الأمر

    # هذي السطر هو اللي يشغل الأوامر (لازم يكون موجود وتحت الشروط)
    await bot.process_commands(message)
# =========================================================

async def load_extensions():
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            await bot.load_extension(f'cogs.{filename[:-3]}')

@bot.event
async def setup_hook():
    await load_extensions()

keep_alive()
TOKEN = os.environ.get('DISCORD_TOKEN')
bot.run(TOKEN)
