import discord
from discord.ext import commands
from pymongo import MongoClient

# الاتصال بقاعدة بيانات MongoDB بالرابط وكلمة المرور الجديدة
MONGO_URI = "mongodb+srv://Bydatdya237_db_user:dydatdya7268163@cluster0.aded4cm.mongodb.net/?appName=Cluster0"
client = MongoClient(MONGO_URI)
db = client["discord_bot"]
whitelist_collection = db["whitelist"]

class WhitelistCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="تحديد", help="إضافة عضو لقائمة المسموح لهم بالتحكم. مثال: !تحديد @اسم_العضو")
    async def set_whitelist(self, ctx, member: discord.Member = None):
        # السماح فقط لصاحب السيرفر
        if ctx.author.id != ctx.guild.owner_id:
            await ctx.send("❌ عذراً، هذا الأمر مخصص لصاحب السيرفر فقط!")
            return

        if not member:
            await ctx.send("❌ عذراً، يجب عليك منشن العضو المراد إضافته! مثال: `!تحديد @ضياء`")
            return

        # جلب البيانات الحالية أو إنشاء قائمة جديدة للسيرفر
        guild_data = whitelist_collection.find_one({"guild_id": ctx.guild.id})
        allowed_users = guild_data.get("allowed_users", []) if guild_data else []

        if member.id in allowed_users:
            await ctx.send(f"⚠️ العضو {member.mention} موجود مسبقاً في قائمة المسموح لهم!")
            return

        allowed_users.append(member.id)

        # حفظ التحديث في قاعدة البيانات
        whitelist_collection.update_one(
            {"guild_id": ctx.guild.id},
            {"$set": {"allowed_users": allowed_users}},
            upsert=True
        )
        
        await ctx.send(f"✅ تم إضافة العضو {member.mention} بنجاح إلى قائمة التحكم المسموح لها!")

    @commands.command(name="إزالة", help="إزالة عضو من قائمة المسموح لهم. مثال: !إزالة @اسم_العضو")
    async def remove_whitelist(self, ctx, member: discord.Member = None):
        if ctx.author.id != ctx.guild.owner_id:
            await ctx.send("❌ عذراً، هذا الأمر مخصص لصاحب السيرفر فقط!")
            return

        if not member:
            await ctx.send("❌ عذراً، يجب عليك منشن العضو المراد إزالته! مثال: `!إزالة @ضياء`")
            return

        guild_data = whitelist_collection.find_one({"guild_id": ctx.guild.id})
        if not guild_data or "allowed_users" not in guild_data:
            await ctx.send("📋 القائمة فارغة أصلاً ولا توجد أي أعضاء مضافين.")
            return

        allowed_users = guild_data["allowed_users"]
        if member.id not in allowed_users:
            await ctx.send(f"⚠️ العضو {member.mention} ليس موجوداً في القائمة من الأساس.")
            return

        allowed_users.remove(member.id)
        whitelist_collection.update_one(
            {"guild_id": ctx.guild.id},
            {"$set": {"allowed_users": allowed_users}},
            upsert=True
        )

        await ctx.send(f"🗑️ تم إزالة العضو {member.mention} من قائمة التحكم بنجاح.")

    @commands.command(name="كشف", help="عرض الأشخاص المسموح لهم بالتحكم في البوت")
    async def show_whitelist(self, ctx):
        guild_data = whitelist_collection.find_one({"guild_id": ctx.guild.id})
        
        if not guild_data or "allowed_users" not in guild_data or not guild_data["allowed_users"]:
            await ctx.send("📋 **قائمة التحكم:**\nلم يتم تحديد أي عضو بعد! البوت متاح حالياً لصاحب السيرفر فقط.")
            return

        user_mentions = [f"<@{uid}>" for uid in guild_data["allowed_users"]]
        mentions_str = ", ".join(user_mentions)
        await ctx.send(f"📋 **قائمة الأعضاء المسموح لهم بالتحكم في البوت:**\n{mentions_str}")

async def setup(bot):
    await bot.add_cog(WhitelistCog(bot))
