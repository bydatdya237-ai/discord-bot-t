import discord
from discord.ext import commands
from discord import app_commands

# 1. قائمة منسدلة تفاعلية تسحب الأوامر تلقائياً
class HelpSelect(discord.ui.Select):
    def __init__(self, bot):
        self.bot = bot
        options = [
            discord.SelectOption(label="الرئيسية", description="عرض الصفحة الرئيسية للقائمة", emoji="📜"),
            discord.SelectOption(label="جميع الأوامر", description="عرض كافة الأوامر المتاحة في البوت حالياً", emoji="⚡"),
            discord.SelectOption(label="أوامر الإدارة", description="الأوامر المخصصة للمشرفين وصاحب السيرفر", emoji="🛡️"),
            discord.SelectOption(label="أوامر الأعضاء والألعاب", description="الأوامر العامة وأوامر التفاعل", emoji="👤")
        ]
        super().__init__(placeholder="اضغط هنا لاختيار تصنيف الأوامر...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]
        
        if selected == "الرئيسية":
            embed = discord.Embed(
                title=f"📜 قائمة أوامر {interaction.client.user.name}",
                description="مرحباً بك! هذه قائمة المساعدة المحدثة تلقائياً. اختر من القائمة أدناه:",
                color=discord.Color.purple()
            )
            embed.add_field(name="📌 الميزات", value="• تسحب الأوامر المسجلة في البوت بشكل فوري\n• لا تحتاج لتعديلها عند إضافة أوامر جديدة", inline=False)
            await interaction.response.edit_message(embed=embed, view=self.view)
            
        elif selected == "جميع الأوامر":
            embed = discord.Embed(title="⚡ جميع الأوامر المتاحة", color=discord.Color.gold())
            commands_list = ""
            for cmd in self.bot.tree.get_commands():
                commands_list += f"• `/{cmd.name}` : {cmd.description or 'بدون وصف'}\n"
            
            embed.description = commands_list if commands_list else "لا توجد أُوامر مسجلة حالياً."
            await interaction.response.edit_message(embed=embed, view=self.view)

        elif selected == "أوامر الإدارة":
            embed = discord.Embed(title="🛡️ أوامر الإدارة والصلاحيات", color=discord.Color.red())
            admin_keywords = ["تحديد", "ازالة", "كشف", "استدعاء", "رتبة", "صلاحية_روم"]
            found = False
            for cmd in self.bot.tree.get_commands():
                if cmd.name in admin_keywords:
                    embed.add_field(name=f"/{cmd.name}", value=cmd.description or "بدون وصف", inline=False)
                    found = True
            if not found:
                embed.description = "لا توجد أوامر إدارة مسجلة حالياً."
            await interaction.response.edit_message(embed=embed, view=self.view)
            
        elif selected == "أوامر الأعضاء والألعاب":
            embed = discord.Embed(title="👤 أوامر الأعضاء والألعاب", color=discord.Color.blue())
            admin_keywords = ["تحديد", "ازالة", "كشف", "استدعاء", "رتبة", "صلاحية_روم"]
            found = False
            for cmd in self.bot.tree.get_commands():
                if cmd.name not in admin_keywords:
                    embed.add_field(name=f"/{cmd.name}", value=cmd.description or "بدون وصف", inline=False)
                    found = True
            if not found:
                embed.description = "لا توجد أوامر أخرى مسجلة حالياً."
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

    @app_commands.command(name="اوامر", description="يعرض قائمة بجميع الأوامر بشكل تفاعلي ومحدث تلقائياً")
    async def custom_help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title=f"📜 قائمة أوامر {self.bot.user.name}",
            description="مرحباً بك! استخدم القائمة المنسدلة بالأسفل لاستعراض الأوامر المحدثة في البوت:",
            color=discord.Color.purple()
        )
        embed.set_footer(text=f"طلب بواسطة {interaction.user.name}")

        view = HelpView(self.bot)
        await interaction.response.send_message(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(HelpCog(bot))
