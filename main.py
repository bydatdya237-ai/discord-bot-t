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
db = client['discord_bot_db']
# ==================================================

# نظام السلاش ما يحتاج صلاحية قراءة الرسائل (Message Content)
intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'دخلت السيرفر باسم: {bot.user}')
    try:
        # مزامنة الأوامر عالمياً لتعمل في أي سيرفر يتواجد فيه البوت مباشرة
        synced = await bot.tree.sync()
        
        # طباعة أسماء الأوامر المزامنة للتأكد
        command_names = [cmd.name for cmd in synced]
        print(f"الأوامر المزامنة حالياً: {command_names}")
        print(f"تمت مزامنة {len(synced)} أمر عالمياً بنجاح!")
    except Exception as e:
        print(f"خطأ في مزامنة الأوامر: {e}")

async def load_extensions():
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}')
                print(f"✅ تم تحميل الملف بنجاح: {filename}")
            except Exception as e:
                print(f"❌ فشل تحميل الملف {filename} بسبب الخطأ التالي: {e}")

@bot.event
async def setup_hook():
    await load_extensions()

keep_alive()
TOKEN = os.environ.get('TOKEN')
bot.run(TOKEN)
