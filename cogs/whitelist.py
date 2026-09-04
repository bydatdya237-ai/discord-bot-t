import os
import discord
from discord.ext import commands
from pymongo import MongoClient

# 📌 آيدي الرتبة الأساسي المكتوب مسبقاً
ADMIN_ROLE_ID = 1545460455315873895  

class WhitelistCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # الاتصال بقاعدة البيانات باستخدام متغير البيئة الآمن بدون كتابة الرابط بالكود
        mongo_url = os.environ.get('MONGO_URI')
        self.client = MongoClient(mongo_url)
        self.db = self.client['discord_db']
        # مجموعة خاصة لحفظ المشرفين الإضافيين بالسحاب
        self.whitelist_collection = self.db['whitelist_admins']

    def _has_permission(self, ctx):
        # 1. صاحب السيرفر لديه صلاحية كاملة دائماً
        if ctx.author.id == ctx.guild.owner_id:
            return True
        
        # 2. التحقق من الرتبة الأساسية بالآيدي
        if any(role.id == ADMIN_ROLE_ID for role in ctx.author.roles):
            return True
            
        # 3. التحقق إذا كان العضو مضافاً يدوياً في قاعدة البيانات عبر أمر تحديد
        db_admin = self.whitelist_collection.find_one({"user_id": str(ctx.author.id)})
        if db_admin:
            return True
            
        return False

    @commands.command(name="تحديد", help="إضافة عضو لقائمة المشرفين المسموح لهم بالتحكم")
    async def add_whitelist(self, ctx, member: discord.Member = None):
        # السماح لصاحب الرتبة أو صاحب السيرفر فقط باستخدام أمر إضافة مشرفين جدد
        if not (ctx.author.id == ctx.guild.owner_id or any(role.id == ADMIN_ROLE_ID for role in ctx.author.roles)):
            await ctx.send("❌ عذراً، هذا الأمر مخصص لصاحب السيرفر أو صاحب الرتبة الرئيسية فقط!")
            return

        if not member:
            await ctx.send("⚠️ أرجو تحديد العضو بشكل صحيح. مثال: `!تحديد @اسم_العضو`")
            return

        user_id = str(member.id)
        existing = self.whitelist_collection.find_one({"user_id": user_id})
        
        if existing:
            await ctx.send(f"⚠️ العضو **{member.name}** مضاف مسبقاً في قائمة المشرفين!")
        else:
            self.whitelist_collection.insert_one({"user_id": user_id, "name": member.name})
            await ctx.send(f"✅ تم بنجاح إضافة **{member.name}** إلى قائمة المشرفين المعتمدين في قاعدة البيانات!")

    @commands.command(name="ازالة", help="إزالة عضو من قائمة المشرفين")
    async def remove_whitelist(self, ctx, member: discord.Member = None):
        if not (ctx.author.id == ctx.guild.owner_id or any(role.id == ADMIN_ROLE_ID for role in ctx.author.roles)):
            await ctx.send("❌ عذراً، هذا الأمر مخصص لصاحب السيرفر أو صاحب الرتبة الرئيسية فقط!")
            return

        if not member:
            await ctx.send("⚠️ أرجو تحديد العضو المراد إزالته. مثال: `!ازالة @اسم_العضو`")
            return

        user_id = str(member.id)
        result = self.whitelist_collection.delete_one({"user_id": user_id})
        
        if result.deleted_count > 0:
            await ctx.send(f"🗑️ تم بنجاح إزالة **{member.name}** من قائمة المشرفين.")
        else:
            await ctx.send(f"⚠️ العضو **{member.name}** غير موجود في قائمة المشرفين أساساً.")

    @commands.command(name="كشف", help="عرض قائمة المشرفين الإضافيين المخزنين بالسحاب")
    async def show_whitelist(self, ctx):
        if not self._has_permission(ctx):
            await ctx.send("❌ عذراً، ليس لديك صلاحية لاستخدام هذا الأمر!")
            return

        admins = list(self.whitelist_collection.find({}))
        
        embed = discord.Embed(
            title="🛡️ قائمة مشرفي النظام المعتمدين",
            color=discord.Color.blue()
        )
        
        embed.add_field(name="👑 الرتبة الرئيسية", value=f"<@&{ADMIN_ROLE_ID}>", inline=False)
        
        if admins:
            admins_list = "\n".join([f"• <@{admin['user_id']}> ({admin.get('name', 'Unknown')})" for admin in admins])
            embed.add_field(name="📂 المشرفون المضافون عبر قاعدة البيانات:", value=admins_list, inline=False)
        else:
            embed.add_field(name="📂 المشرفون المضافون عبر قاعدة البيانات:", value="لا يوجد مشرفون إضافيون حالياً.", inline=False)

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(WhitelistCog(bot))
