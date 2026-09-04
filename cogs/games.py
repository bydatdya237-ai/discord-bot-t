import discord
from discord.ext import commands

class GamesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="العاب", help="يعرض لك قائمة بأسماء الألعاب المتاحة")
    async def games_list(self, ctx):
        # قائمة أسماء الألعاب المقترحة
        games = [
            "🎮 Call of Duty: Warzone",
            "🎮 Valorant",
            "🎮 Grand Theft Auto V",
            "🎮 Minecraft",
            "🎮 Counter-Strike 2",
            "🎮 Apex Legends",
            "🎮 Rocket League",
            "🎮 EA Sports FC 24"
        ]
        
        # تنسيق القائمة بشكل جميل داخل رسالة
        games_text = "\n".join(games)
        
        embed = discord.Embed(
            title="🎯 قائمة الألعاب المقترحة",
            description=f"هذه قائمة بأبرز الألعاب الحالية:\n\n{games_text}",
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"طلب بواسطة {ctx.author.name}")
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(GamesCog(bot))

