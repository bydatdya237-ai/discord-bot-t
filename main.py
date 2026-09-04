import os
import discord
from discord.ext import commands
from flask import Flask
from threading import Thread
from pymompgo import MongoClient # (أو pymongo)

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

# تفعيل الصلاحيات (Intents) بالكامل لتجنب تجاهل رسائل الأعضاء
intents = discord.Intents.default()
intents.message_content = True  # ضروري جداً لقراءة الأوامر مثل !حظ و !رصيد
intents.members = True          # ضروري جداً لقراءة الأعضاء ورتبهم

bot = commands.Bot(command_prefix="!", intents=intents)

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

# تشغيل سيرفر الـ Web وتشغيل البوت باستخدام متغير البيئة المدمج الآمن
keep_alive()
TOKEN = os.environ.get('DISCORD_TOKEN')
bot.run(TOKEN)
