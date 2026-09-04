import discord
from discord.ext import commands
from pymongo import MongoClient

# الاتصال بقاعدة بيانات MongoDB بالرابط وكلمة المرور الجديدة
MONGO_URI = "mongodb+srv://Bydatdya237_db_user:dydatdya7268163@cluster0.aded4cm.mongodb.net/?appName=Cluster0"
client = MongoClient(MONGO_URI)
db = client["discord_bot"]
whitelist_collection = db["whitelist"]

class WhitelistView(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=60)
        self.guild_id = guild_id

    @discord.ui.select(
        cls=discord.ui.UserSelect,
        placeholder="اختر الأعضاء المسموح لهم بتحكم البوت...",
        min_values=1,
        max_values=10
    )
    async def select_users(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        # تأجيل الاستجابة فوراً لمنع خطأ "لم يستجب في الوقت المحدد"
        await interaction.response.defer(ephemeral=True)

        selected_users = select.values
        user_ids = [user.id for user in selected_users]
        
        # حفظ الأعضاء في قاعدة البيانات للسيرفر الحالي
        whitelist_collection.update_one(
            {"guild_id": self.guild_id},
            {"$set": {"allowed_users": user_ids}},
            upsert=True
        )
        
        names = ", ".join([user.name for user in selected_users])
        # رسالة النجاح حسب طلبك
        await interaction.followup.send(f"✅ تم التجديد بنجاح! الأعضاء المسموح لهم الآن: {names}", ephemeral=True)

class WhitelistCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="تحديد", help="تحديد الأعضاء المسموح لهم بالتحكم في البوت")
    async def set_whitelist(self, ctx):
        # السماح فقط لصاحب السيرفر باستخدام أمر التحديد الأمني
        if ctx.author.id != ctx.guild.owner_id:
            await ctx.send("❌ عذراً، هذا الأمر مخصص لصاحب السيرفر فقط!")
            return

        view = WhitelistView(ctx.guild.id)
        await ctx.send("🛡️ **نظام تحديد الصلاحيات:**\nالرجاء اختيار الأعضاء المسموح لهم بالتحكم في البوت من القائمة بالأسفل:", view=view)

    # أمر كشف لعرض الأشخاص المسموح لهم
    @commands.command(name="كشف", help="عرض الأشخاص المسموح لهم بالتحكم في البوت")
    async def show_whitelist(self, ctx):
        # جلب البيانات الخاصة بالسيرفر من قاعدة البيانات
        guild_data = whitelist_collection.find_one({"guild_id": ctx.guild.id})
        
        if not guild_data or "allowed_users" not in guild_data or not guild_data["allowed_users"]:
            await ctx.send("📋 **قائمة التحكم:**\nلم يتم تحديد أي عضو بعد! البوت متاح حالياً لصاحب السيرفر فقط.")
            return

        user_mentions = []
        for uid in guild_data["allowed_users"]:
            user_mentions.append(f"<@{uid}>")
        
        mentions_str = ", ".join(user_mentions)
        await ctx.send(f"📋 **قائمة الأعضاء المسموح لهم بالتحكم في البوت:**\n{mentions_str}")

async def setup(bot):
    await bot.add_cog(WhitelistCog(bot))
