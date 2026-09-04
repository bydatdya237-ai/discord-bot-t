import discord
from discord.ext import commands

# 📌 آيدي الرتبة المحدد للصلاحيات
ADMIN_ROLE_ID = 1545460455315873895  

class WhitelistCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _has_permission(self, ctx):
        # التحقق إذا كان المستخدم هو صاحب السيرفر
        if ctx.author.id == ctx.guild.owner_id:
            return True
        
        # التحقق إذا كان العضو يمتلك الرتبة المطابقة للآيدي
        role = ctx.guild.get_role(ADMIN_ROLE_ID)
        if role and role in ctx.author.roles:
            return True
            
        return False

    @commands.command(name="كشف", help="التحقق من حالة الصلاحيات")
    async def show_whitelist(self, ctx):
        if not self._has_permission(ctx):
            await ctx.send("❌ عذراً، هذا الأمر مخصص لصاحب السيرفر أو للأعضاء الذين يحملون الرتبة المحددة فقط!")
            return

        await ctx.send("🛡️ **نظام الصلاحيات يعمل بكفاءة!**\nلديك الصلاحية الكاملة لاستخدام هذه الأوامر.")

async def setup(bot):
    await bot.add_cog(WhitelistCog(bot))
