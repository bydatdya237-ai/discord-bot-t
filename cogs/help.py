import discord
from discord.ext import commands

class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="اوامر", help="يعرض قائمة بجميع الأوامر المتاحة في البوت")
    async def custom_help(self, ctx):
        embed = discord.Embed(
            title="📜 قائمة أوامر البوت",
            description="جميع الأوامر المتاحة حالياً في البوت:",
            color=discord.Color.purple()
        )

        # المرور على جميع الـ Cogs والأوامر المسجلة تلقائياً
        for cog_name, cog in self.bot.cogs.items():
            commands_list = cog.get_commands()
            if commands_list:
                cmds_desc = ""
                for cmd in commands_list:
                    # جلب وصف الأمر لو وجد، أو وضع وصف افتراضي
                    description = cmd.help or "لا يوجد وصف"
                    cmds_desc += f"• `!{cmd.name}` - {description}\n"
                
                embed.add_field(name=f"📁 {cog_name}", value=cmds_desc, inline=False)

        embed.set_footer(text=f"طلب بواسطة {ctx.author.name}")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(HelpCog(bot))

