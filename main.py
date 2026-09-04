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

# === نظام الفحص العام للتحقق من روم الأمر ===
@bot.check
async def global_command_channel_check(ctx):
    # صاحب السيرفر مستثنى دائماً ويقدر يكتب بأي روم
    if ctx.author.id == ctx.guild.owner_id:
        return True
        
    command_name = ctx.command.name
    
    # ابحث هل لهذا الأمر روم مخصص في قاعدة البيانات
    record = command_channels_collection.find_one({"guild_id": ctx.guild.id, "command_name": command_name})
    
    if record:
        allowed_channel_id = int(record["channel_id"])
        if ctx.channel.id != allowed_channel_id:
            # إذا كتب الأمر بروم غلط، نبهه ونمنع التنفيذ
            await ctx.send(f"❌ عذراً، هذا الأمر (`!{command_name}`) مخصص فقط للاستخدام في روم <#{allowed_channel_id}>!", delete_after=5)
            return False
            
    return True
# ============================================

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
