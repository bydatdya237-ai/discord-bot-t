import discord
from discord import app_commands
from discord.ui import Modal, Select, View
from pymongo import MongoClient
import os

# الاتصال بقاعدة بيانات MongoDB
MONGO_URI = os.getenv("MONGO_URI")
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["discord_bot_db"]
custom_commands_collection = db["custom_commands"]

class CreateCommandModal(Modal, title="إنشاء وتخصيص أمر جديد"):
    cmd_name = discord.ui.TextInput(
        label="اسم الأمر (بالإنجليزية بدون مسافات، مثال: welcome)",
        placeholder="اكتب الاسم هنا...",
        max_length=30
    )
    cmd_description = discord.ui.TextInput(
        label="وصف الأمر الذي يظهر للمستخدمين",
        placeholder="وصف مختصر لوظيفة الأمر...",
        style=discord.TextStyle.paragraph,
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction):
        view = CategorySelectView(self.cmd_name.value, self.cmd_description.value)
        await interaction.response.send_message(
            f"✅ تم حفظ الاسم: **/{self.cmd_name.value}**\nالخطوة التالية: اختر تصنيف ووظيفة هذا الأمر:",
            view=view,
            ephemeral=True
        )

class CategorySelect(Select):
    def __init__(self, cmd_name, cmd_desc):
        self.cmd_name = cmd_name
        self.cmd_desc = cmd_desc
        
        options = [
            discord.SelectOption(label="أوامر الإدارة والحماية", description="بان، كيك، تيم آوت، مسح، حماية", emoji="🛡️"),
            discord.SelectOption(label="أوامر التذاكر والدعم الفني", description="فتح تذكرة، بلاغات، تقديمات", emoji="🎫"),
            discord.SelectOption(label="أوامر الترحيب والمجتمع", description="ترحيب، وداع، إعطاء رتب تلقائية", emoji="✨"),
            discord.SelectOption(label="أوامر الألعاب والاقتصاد", description="نقاط، حظ، كاسحة ألغام، حجر ورقة مقص", emoji="🎮"),
            discord.SelectOption(label="أوامر الأدوات والإعلانات", description="إيمبد، تصويت، سحوبات، معلومات", emoji="🛠️")
        ]
        super().__init__(placeholder="اختر تصنيف الوظيفة...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]
        view = ActionSelectView(self.cmd_name, self.cmd_desc, category)
        await interaction.response.edit_message(
            content=f"📁 التصنيف المختار: **{category}**\nاختر الوظيفة المحددة للأمر:",
            view=view
        )

class CategorySelectView(View):
    def __init__(self, cmd_name, cmd_desc):
        super().__init__()
        self.add_item(CategorySelect(cmd_name, cmd_desc))

class ActionSelect(Select):
    def __init__(self, cmd_name, cmd_desc, category):
        self.cmd_name = cmd_name
        self.cmd_desc = cmd_desc
        
        actions_dict = {
            "أوامر الإدارة والحماية": [
                discord.SelectOption(label="حظر عضو (Ban)", description="أمر لحظر الأعضاء المخالفين"),
                discord.SelectOption(label="مسح الرسائل (Clear)", description="حذف عدد محدد من الرسائل دفعة واحدة"),
                discord.SelectOption(label="إسكات (Timeout)", description="إسكات العضو مؤقتاً"),
                discord.SelectOption(label="قفل الروم (Lock)", description="قفل القناة الحالية لمنع إرسال الرسائل")
            ],
            "أوامر التذاكر والدعم الفني": [
                discord.SelectOption(label="لوحة التذاكر (Ticket Panel)", description="إرسال رسالة زر لفتح تذكرة خاصة"),
                discord.SelectOption(label="تقديم إداري (Staff Apply)", description="نموذج التقديم على رتب السيرفر"),
                discord.SelectOption(label="دعم فني عام (Support)", description="فتح قناة مخصصة للمشاكل")
            ],
            "أوامر الترحيب والمجتمع": [
                discord.SelectOption(label="رسالة ترحيب مخصصة (Welcome)", description="إرسال كارد ترحيب بالعضو الجديد"),
                discord.SelectOption(label="رتبة تلقائية (Auto-Role)", description="منح رتبة فورية عند دخول السيرفر")
            ],
            "أوامر الألعاب والاقتصاد": [
                discord.SelectOption(label="الراتب اليومي (Daily)", description="الحصول على نقاط أو فلوس يومية"),
                discord.SelectOption(label="لعبة كاسحة الألغام (Minesweeper)", description="فتح لعبة تفاعلية في الشات"),
                discord.SelectOption(label="حجرة ورقة مقص (RPS)", description="تحدي بسيط داخل الشات")
            ],
            "أوامر الأدوات والإعلانات": [
                discord.SelectOption(label="صانع الإيمبد (Embed Builder)", description="إرسال رسالة منسقة رسمية"),
                discord.SelectOption(label="سحب عشوائي (Giveaway)", description="بدء مسابقة عشوائية على جائزة"),
                discord.SelectOption(label="معلومات العضو (Userinfo)", description="عرض تفاصيل حساب ديسكورد")
            ]
        }
        
        selected_options = actions_dict.get(category, [discord.SelectOption(label="وظيفة مخصصة عامة", description="تنفيذ أمر مخصص عام")])
        super().__init__(placeholder="اختر الوظيفة الدقيقة...", min_values=1, max_values=1, options=selected_options)

    async def callback(self, interaction: discord.Interaction):
        chosen_action = self.values[0]
        
        command_data = {
            "guild_id": interaction.guild.id,
            "name": self.cmd_name,
            "description": self.cmd_desc,
            "action": chosen_action
        }
        
        custom_commands_collection.update_one(
            {"guild_id": interaction.guild.id, "name": self.cmd_name},
            {"$set": command_data},
            upsert=True
        )

        await interaction.response.edit_message(
            content=f"🚀 **تم إنشاء وتسمية الأمر بنجاح!**\n- اسم الأمر: `/{self.cmd_name}`\n- الوصف: `{self.cmd_desc}`\n- الوظيفة المختارة: `{chosen_action}`\n\nتم حفظه بقاعدة بيانات MongoDB بنجاح!",
            view=None
        )

class ActionSelectView(View):
    def __init__(self, cmd_name, cmd_desc, category):
        super().__init__()
        self.add_item(ActionSelect(cmd_name, cmd_desc, category))

class CustomCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="انشاء_امر", description="لوحة متكاملة لإنشاء وتسمية أوامر السيرفر الجديدة")
    async def create_command(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("عذراً، هذا الأمر مخصص للمشرفين فقط!", ephemeral=True)
            return

        modal = CreateCommandModal()
        await interaction.response.send_modal(modal)

async def setup(bot):
    from discord.ext import commands
    await bot.add_cog(CustomCommands(bot))
