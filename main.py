import os
import discord
from discord.ext import commands
from flask import Flask
from threading import Thread

# === الاتصال بقاعدة بيانات MongoDB ===
from pymongo import MongoClient

MONGO_URI = "mongodb+srv://Bydatdya237_db_user:NovcUW863kD2T8Z0@cluster0.aded4cm.mongodb.net/?appName=Cluster0"
client = MongoClient(MONGO_URI)
db = client["discord_bot"]
whitelist_collection = db["whitelist"]
# ====================================

app = Flask('')

@app.route('/')
def home():
    return "I am alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# === دالة الفحص العامة للتحكم بالأعضاء المسموح لهم ===
@bot.check
def check_whitelist(ctx):
    if ctx.author.bot:
        return False
        
    # صاحب السيرفر مستثنى دائماً وله الصلاحية المطلقة
    if ctx.author.id == ctx.guild.owner_id:
        return True
        
    # جلب قائمة الأعضاء المسموح لهم من قاعدة البيانات
    guild_data = whitelist_collection.find_one({"guild_id": ctx.guild.id})
    if not guild_data or "allowed_users" not in guild_data:
        return False # لو ما تم تحديد أحد نهائياً، البوت مقفل على الكل عدا صاحب السيرفر
        
    return ctx.author.id in guild_data["allowed_users"]
# ====================================================

@bot.event
async def on_ready():
    print(f'دخلت السيرفر باسم: {bot.user}')

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
