import discord
from discord.ext import commands


class WebsiteCommands(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

        print("🌐 WebsiteCommands تم تحميله")
        print(f"📋 عدد الأوامر الحالية: {len(bot.commands)}")


async def setup(bot):
    await bot.add_cog(
        WebsiteCommands(bot)
    )

    print("✅ WebsiteCommands جاهز")
