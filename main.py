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

# === الاتصال بقاعدة البيانات لنظام الألعاب والبيانات ===
mongo_url = os.environ.get('MONGO_URI')
client = MongoClient(mongo_url)
db = client['discord_bot_db'] # تم توحيد اسم القاعدة لتطابق الـ cogs
# ==================================================

# نظام السلاش ما يحتاج صلاحية قراءة الرسائل (Message Content)
intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'دخلت السيرفر باسم: {bot.user}')
    try:
        # مزامنة الأوامر مع ديسكورد لتظهر فوراً مع علامة /
        synced = await bot.tree.sync()
        print(f"تمت مزامنة {len(synced)} أمر بنجاح!")
    except Exception as e:
        print(f"خطأ في مزامنة الأوامر: {e}")

async def load_extensions():
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            await bot.load_extension(f'cogs.{filename[:-3]}')

@bot.event
async def setup_hook():
    await load_extensions()

keep_alive()
TOKEN = os.environ.get('TOKEN') # تعديل اسم المتغير ليطابق ما تم وضعه في Railway
bot.run(TOKEN)
