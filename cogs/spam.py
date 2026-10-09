import os
import asyncio
import discord
from discord.ext import commands

# إعدادات البوت
OWNER_ID = 1154374165642620948  # ضع آيدي حسابك هنا
SPAM_MESSAGE = "كس  امك!"

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None
)

@bot.command(name="سبام")
async def spam(ctx):
    # التحقق من هوية صاحب البوت
    if ctx.author.id != OWNER_ID:
        return

    # عدد محدود للاختبار
    message_count = 15

    try:
        await ctx.message.delete()
    except discord.HTTPException:
        pass

    for _ in range(message_count):
        try:
            await ctx.send(SPAM_MESSAGE)
            await asyncio.sleep(2)
        except discord.HTTPException:
            break

    try:
        await ctx.send("✅ انتهى الاختبار.")
    except discord.HTTPException:
        pass

bot.run(os.environ["DISCORD_BOT_TOKEN"])
