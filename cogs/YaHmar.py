import discord
from discord.ext import commands


class YaHmar(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        # تجاهل البوتات
        if message.author.bot:
            return

        # الأمر
        if message.content.strip() != "ياحمار":
            return

        # التحقق من صاحب السيرفر
        is_server_owner = (
            message.guild is not None
            and message.author.id == message.guild.owner_id
        )

        # التحقق من صاحب البوت
        is_bot_owner = await self.bot.is_owner(message.author)

        # السماح فقط لصاحب السيرفر أو صاحب البوت
        if not (is_server_owner or is_bot_owner):
            return

        await message.channel.send(
            "هلا بتاج عمي وتاج راسي مطوري عمي وعم عيالي ضياء الغالي"
        )


async def setup(bot):
    await bot.add_cog(YaHmar(bot))
