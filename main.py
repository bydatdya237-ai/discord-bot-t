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

@bot.event
async def on_ready():
    print(f'دخلت السيرفر باسم: {bot.user}')

# === فحص صارم يحذف الرسالة بصمت لو كانت في روم غير مخصص ===
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.content.startswith("!"):
        # استخراج اسم الأمر بدقة وتنظيفه ليتطابق مع قاعدة البيانات
        command_name = message.content[1:].strip().split(" ")[0].lower()
        
        if message.guild and message.author.id != message.guild.owner_id:
            record = command_channels_collection.find_one({"guild_id": message.guild.id, "command_name": command_name})
            
            if record:
                allowed_channel_id = int(record["channel_id"])
                if message.channel.id != allowed_channel_id:
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
