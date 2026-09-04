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

# === فحص مؤقت لحصر جميع الأوامر في الروم المحدد فقط ===
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.content.startswith("!"):
        if message.guild and message.author.id != message.guild.owner_id:
            if message.channel.id != TEMPORARY_CHANNEL_ID:
                try:
                    await message.delete() # حذف رسالة الأمر المخالف بصمت تام
                except:
                    pass
                return

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
