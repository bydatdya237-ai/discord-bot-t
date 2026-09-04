import os
import discord
from discord.ext import commands
from flask import Flask
from threading import Thread

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

# === التعديل المضاف هنا ===
@bot.check
def globally_block_non_authorized(ctx):
    # السماح للبوتات (إن وجدت) لكي لا يحدث تداخل أو حظر داخلي
    if ctx.author.bot:
        return False
        
    allowed_role_id = 1545427714855669871
    
    # التحقق مما إذا كان المستخدم يملك الرتبة المحددة أو هو صاحب السيرفر
    has_role = any(role.id == allowed_role_id for role in ctx.author.roles)
    is_owner = ctx.author.id == ctx.guild.owner_id
    
    return has_role or is_owner
# =========================

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
