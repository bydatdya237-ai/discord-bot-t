import os
import discord
from discord.ext import commands
from pymongo import MongoClient

class WhitelistCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        mongo_url = os.environ.get('MONGO_URI')
        self.client = MongoClient(mongo_url)
        self.db = self.client['discord_db']
        self.whitelist_collection = self.db['whitelist_admins']

    def _has_permission(self, ctx):
        # 1. صاحب السيرفر
        if ctx.author.id == ctx.guild.owner_id:
            return True
            
        # 2. المشرفون المضافون في قاعدة البيانات (مثل ما سويت بأمر تحديد)
        db_admin = self.whitelist_collection.find_one({"user_id": str(ctx.author.id)})
        if db_admin:
            return True
            
        return False

    @commands.command(name="تحديد", help="إضافة عضو لقائمة المشرفين")
    async def add_whitelist(self, ctx, member: discord.Member = None):
        if ctx.author.id != ctx.guild.owner_id:
            await ctx.send("❌ عذراً، هذا الأمر مخصص لصاحب السيرفر فقط!")
            return

        if not member:
            await ctx.send("⚠️ أرجو تحديد العضو. مثال: `!تحديد @اسم_العضو`")
            return

        user_id = str(member.id)
        existing = self.whitelist_collection.find_one({"user_id": user_id})
        
        if existing:
            await ctx.send(f"⚠️ العضو **{member.name}** مضاف مسبقاً!")
        else:
            self.whitelist_collection.insert_one({"user_id": user_id, "name": member.name})
            await ctx.send(f"✅ تم بنجاح إضافة **{member.name}** لقائمة المشرفين!")

    @commands.command(name="ازالة", help="إزالة عضو من قائمة المشرفين")
    async def remove_whitelist(self, ctx, member: discord.Member = None):
        if ctx.author.id != ctx.guild.owner_id:
            await ctx.send("❌ عذراً، هذا الأمر مخصص لصاحب السيرفر فقط!")
            return

        if not member:
            await ctx.send("⚠️ أرجو تحديد العضو المراد إزالته.")
            return

        user_id = str(member.id)
        result = self.whitelist_collection.delete_one({"user_id": user_id})
        
        if result.deleted_count > 0:
            await ctx.send(f"🗑️ تم إزالة **{member.name}** بنجاح.")
        else:
            await ctx.send(f"⚠️ العضو غير موجود أساساً في القائمة.")

    @commands.command(name="كشف", help="عرض قائمة المشرفين")
    async def show_whitelist(self, ctx):
        if not self._has_permission(ctx):
            await ctx.send("❌ عذراً، ليس لديك صلاحية!")
            return

        admins = list(self.whitelist_collection.find({}))
        
        embed = discord.Embed(
            title="🛡️ قائمة المشرفين المعتمدين",
            color=discord.Color.blue()
        )
        
        if admins:
            admins_list = "\n".join([f"• <@{admin['user_id']}>" for admin in admins])
            embed.add_field(name="📂 المشرفون بالسحاب:", value=admins_list, inline=False)
        else:
            embed.add_field(name="📂 المشرفون بالسحاب:", value="لا يوجد مشرفون إضافيون.", inline=False)

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(WhitelistCog(bot))
