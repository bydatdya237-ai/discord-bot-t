import discord
from discord.ext import commands
from discord import app_commands

# 1. قائمة منسدلة تفاعلية لاختيار التصنيف
class HelpSelect(discord.ui.Select):
    def __init__(self, bot):
        self.bot = bot
        options = [
            discord.SelectOption(label="الرئيسية", description="عرض الصفحة الرئيسية للقائمة", emoji="📜"),
            discord.SelectOption(label="أوامر الإدارة", description="الأوامر المخصصة للمشرفين وصاحب السيرفر", emoji="🛡️"),
            discord.SelectOption(label="أوامر الألعاب والنقاط", description="أوامر الحظ والرصيد والتفاعل", emoji="🎲"),
            discord.SelectOption(label="أوامر الأعضاء", description="الأوامر العامة المتاحة للجميع", emoji="👤")
        ]
        super().__init__(placeholder="اضغط هنا لاختيار تصنيف الأوامر...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]
        
        if selected == "الرئيسية":
            embed = discord.Embed(
                title=f"📜 قائمة أوامر {interaction.client.user.name}",
                description="مرحباً بك! اختر من القائمة أدناه لعرض الأوامر حسب التصنيف.",
                color=discord.Color.purple()
            )
            embed.add_field(name="📌 التصنيفات المتاحة", value="• 🛡️ أوامر الإدارة\n• 🎲 أوامر الألعاب والنقاط\n• 👤 أوامر الأعضاء", inline=False)
            await interaction.response.edit_message(embed=embed, view=self.view)
            
        elif selected == "أوامر الإدارة":
            embed = discord.Embed(title="🛡️ أوامر الإدارة", color=discord.Color.red())
            embed.add_field(name="/تحديد", value="إضافة عضو لقائمة المشرفين", inline=False)
            embed.add_field(name="/ازالة", value="إزالة عضو من قائمة المشرفين", inline=False)
            embed.add_field(name="/كشف", value="عرض قائمة المشرفين المعتمدين", inline=False)
            embed.add_field(name="/استدعاء", value="استدعاء عضو عبر رسالة خاصة مع السبب", inline=False)
            await interaction.response.edit_message(embed=embed, view=self.view)
            
        elif selected == "أوامر الألعاب والنقاط":
            embed = discord.Embed(title="🎲 أوامر الألعاب والنقاط", color=discord.Color.green())
            embed.add_field(name="/حظ", value="تجربة حظك لكسب النقاط", inline=False)
            embed.add_field(name="/رصيد", value="عرض رصيدك الحالي من النقاط", inline=False)
            await interaction.response.edit_message(embed=embed, view=self.view)
            
        elif selected == "أوامر الأعضاء":
            embed = discord.Embed(title="👤 أوامر الأعضاء", color=discord.Color.blue())
            embed.add_field(name="/اوامر", value="عرض قائمة الأوامر الرئيسية", inline=False)
            await interaction.response.edit_message(embed=embed, view=self.view)

# 2. واجهة تجمع القائمة المنسدلة
class HelpView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=120)
        self.add_item(HelpSelect(bot))

# 3. الـ Cog الأساسي لأمر /اوامر
class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="اوامر", description="يعرض قائمة بجميع الأوامر بشكل تفاعلي ومنظم")
    async def custom_help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title=f"📜 قائمة أوامر {self.bot.user.name}",
            description="مرحباً بك! استخدم القائمة المنسدلة بالأسفل لاختيار التصنيف واستعراض الأوامر:",
            color=discord.Color.purple()
        )
        embed.add_field(name="📌 التصنيفات المتاحة", value="• 🛡️ أوامر الإدارة\n• 🎲 أوامر الألعاب والنقاط\n• 👤 أوامر الأعضاء", inline=False)
        embed.set_footer(text=f"طلب بواسطة {interaction.user.name}")

        view = HelpView(self.bot)
        await interaction.response.send_message(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(HelpCog(bot))
