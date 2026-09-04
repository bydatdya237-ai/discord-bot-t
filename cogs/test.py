import discord
from discord.ext import commands

class TestCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def هلا(self, ctx):
        if ctx.channel.id != 1545187326093693038:
            return
        await ctx.send('هلا بك يالغالي! منور السيرفر ⚡ (من نظام الملفات)')

async def setup(bot):
    await bot.add_cog(TestCog(bot))

