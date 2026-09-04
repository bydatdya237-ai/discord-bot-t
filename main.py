import os
import discord
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
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'دخلت السيرفر باسم: {client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content == '!هلا':
        await message.channel.send('هلا بك يالغالي! منور السيرفر ⚡')

keep_alive()
TOKEN = os.environ.get('DISCORD_TOKEN')
client.run(TOKEN)
