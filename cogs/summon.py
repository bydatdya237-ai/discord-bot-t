import os
import discord
from discord.ext import commands
from discord import app_commands
from pymongo import MongoClient

# 1. نافذة الإدخال (Modal) تبقى كما هي بدون تغيير
class SummonModal(discord.ui.Modal, title="تفاصيل الاستدعاء"):
    reason = discord.ui.TextInput(
        label="سبب الاستدعاء",
        style=discord.TextStyle.paragraph,
        placeholder="اكتب سبب الاستدعاء هنا...",
        required=True,
        max_length=300
    )
    
    room_id = discord.ui.TextInput(
        label="ايدي الروم المطلوبة",
        style=discord.TextStyle.short,
        placeholder="مثال: 123456789012345678",
        required=True,
        max_length=30
    )

    def __init__(self, target_user: discord.Member):
        super().__init__()
        self.target_user = target_user

    async def on_submit(self, interaction: discord.Interaction):
        try:
            channel_id = int(self.room_id.value)
            channel = interaction.guild.get_channel(channel_id)
            channel_mention = f"<#{channel_id}>" if channel else f"روم رقم: {channel_id}"
        except ValueError:
            channel_mention = f"روم رقم: {self.room_id.value}"

        embed = discord.Embed(
            title="🚨 تنبيه استدعاء جديد",
            description=f"لقد تم استدعاؤك بواسطة **{interaction.user.name}** في سيرفر **{interaction.guild.name}**.",
            color=discord.Color.red()
        )
        embed.add_field(name="📌 السبب", value=self.reason.value, inline=False)
        embed.add_field(name="🔗 الروم المطلوب", value=channel_mention, inline=False)
        embed.set_footer(text=f"تم الاستدعاء عبر نظام البوت")

        try:
            await self.target_user.send(embed=embed)
            await interaction.response.send_message(f"✅ تم إرسال الاستدعاء إلى العضو {self.target_user.mention} بنجاح عبر الخاص!", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(f"❌ عذراً، لا يمكنني إرسال رسالة خاصة لـ {self.target_user.mention} لأن خاصه مغلق.", ephemeral=True)

# 2. زر تفاعلي يربط الأمر بالـ Modal
class SummonView(discord.ui.View):
    def __init__(self, target_user: discord.Member):
        super().__init__(timeout=60)
        self.target_user = target_user

    @discord.ui.button(label="اضغط هنا لكتابة تفاصيل الاستدعاء", style=discord.ButtonStyle.primary, emoji="📋")
    async def open_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SummonModal(target_user=self.target_user))

class SummonCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        mongo_url = os.environ.get('MONGO_URI')
        self.client = MongoClient(mongo_url)
        self.db = self.client['discord_db']
        self.whitelist_collection = self.db['whitelist_admins']

    def _has_permission(self, interaction: discord.Interaction):
        # 1. صاحب السيرفر مسموح له دائماً
        if interaction.user.id == interaction.guild.owner_id:
            return True
            
        # 2. المشرفون المضافون في قاعدة البيانات
        db_admin = self.whitelist_collection.find_one({"user_id": str(interaction.user.id)})
        if db_admin:
            return True
            
        return False

    # 3. تحويل الأمر ليصبح أمر سلاش (`/استدعاء`) ومحمي للمشرفين
    @app_commands.command(name="استدعاء", description="استدعاء عضو عبر رسالة خاصة مع السبب وروم التوجه")
    @app_commands.describe(member="العضو المراد استدعاؤه")
    async def summon(self, interaction: discord.Interaction, member: discord.Member):
        # التحقق من الصلاحية قبل تنفيذ أي شيء
        if not self._has_permission(interaction):
            await interaction.response.send_message("❌ عذراً، هذا الأمر مخصص للمشرفين وصاحب السيرفر فقط!", ephemeral=True)
            return

        if member.bot:
            await interaction.response.send_message("❌ لا يمكنك استدعاء بوت!", ephemeral=True)
            return
        
        view = SummonView(target_user=member)
        await interaction.response.send_message(f"📌 لإتمام استدعاء العضو {member.mention}, اضغط على الزر بالأسفل:", view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(SummonCog(bot))
