import discord
from discord.ext import commands
from discord import app_commands

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

class SummonCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # تم تصحيح help إلى description هنا
    @app_commands.command(name="استدعاء", description="استدعاء عضو عبر رسالة خاصة مع السبب وروم التوجه")
    @app_commands.describe(member="العضو المراد استدعاؤه")
    async def summon(self, interaction: discord.Interaction, member: discord.Member):
        if member.bot:
            await interaction.response.send_message("❌ لا يمكنك استدعاء بوت!", ephemeral=True)
            return
        
        await interaction.response.send_modal(SummonModal(target_user=member))

async def setup(bot):
    await bot.add_cog(SummonCog(bot))
    try:
        await bot.tree.sync()
    except Exception as e:
        print(f"Failed to sync tree: {e}")
