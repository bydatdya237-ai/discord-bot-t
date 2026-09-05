import os
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Modal, Select, View
from pymongo import MongoClient

class CreateCommandModal(Modal, title="إنشاء وتخصيص أمر جديد"):
    cmd_name = discord.ui.TextInput(
        label="اسم الأمر (بالإنجليزية بدون مسافات)",
        placeholder="مثال: welcome",
        max_length=30
    )
    cmd_description = discord.ui.TextInput(
        label="وصف الأمر الذي يظهر للمستخدمين",
        placeholder="وصف مختصر لوظيفة الأمر...",
        style=discord.TextStyle.paragraph,
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction):
        # تمرير القيم كـ نص صريح (Strings)
        view = CategorySelectView(str(self.cmd_name.value), str(self.cmd_description.value))
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
        mongo_url = os.environ.get('MONGO_URI')
        client = MongoClient(mongo_url)
        # توحيد اسم قاعدة البيانات لتكون discord_bot_db
        db = client['discord_bot_db']
        collection = db['custom_commands']

        chosen_action = self.values[0]
        
        command_data = {
            "guild_id": interaction.guild.id,
            "name": self.cmd_name,
            "description": self.cmd_desc,
            "action": chosen_action
        }
        
        collection.update_one(
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


class WhitelistCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        mongo_url = os.environ.get('MONGO_URI')
        self.client = MongoClient(mongo_url)
        # توحيد اسم قاعدة البيانات لتكون discord_bot_db متوافقة مع البقية
        self.db = self.client['discord_bot_db']
        self.whitelist_collection = self.db['whitelist_admins']

    def _has_permission(self, interaction: discord.Interaction):
        # 1. صاحب السيرفر
        if interaction.user.id == interaction.guild.owner_id:
            return True
            
        # 2. المشرفون المضافون في قاعدة البيانات
        db_admin = self.whitelist_collection.find_one({"user_id": str(interaction.user.id)})
        if db_admin:
            return True
            
        return False

    @app_commands.command(name="تحديد", description="إضافة عضو لقائمة المشرفين (خاص بصاحب السيرفر)")
    @app_commands.describe(member="العضو المراد إضافته للمشرفين")
    async def add_whitelist(self, interaction: discord.Interaction, member: discord.Member):
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message("❌ عذراً، هذا الأمر مخصص لصاحب السيرفر فقط!", ephemeral=True)
            return

        user_id = str(member.id)
        existing = self.whitelist_collection.find_one({"user_id": user_id})
        
        if existing:
            await interaction.response.send_message(f"⚠️ العضو **{member.name}** مضاف مسبقاً!", ephemeral=True)
        else:
            self.whitelist_collection.insert_one({"user_id": user_id, "name": member.name})
            await interaction.response.send_message(f"✅ تم بنجاح إضافة **{member.name}** لقائمة المشرفين!")

    @app_commands.command(name="ازالة", description="إزالة عضو من قائمة المشرفين (خاص بصاحب السيرفر)")
    @app_commands.describe(member="العضو المراد إزالته من المشرفين")
    async def remove_whitelist(self, interaction: discord.Interaction, member: discord.Member):
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message("❌ عذراً، هذا الأمر مخصص لصاحب السيرفر فقط!", ephemeral=True)
            return

        user_id = str(member.id)
        result = self.whitelist_collection.delete_one({"user_id": user_id})
        
        if result.deleted_count > 0:
            await interaction.response.send_message(f"🗑️ تم إزالة **{member.name}** بنجاح.")
        else:
            await interaction.response.send_message(f"⚠️ العضو غير موجود أساساً في القائمة.", ephemeral=True)

    @app_commands.command(name="كشف", description="عرض قائمة المشرفين المعتمدين")
    async def show_whitelist(self, interaction: discord.Interaction):
        if not self._has_permission(interaction):
            await interaction.response.send_message("❌ عذراً، ليس لديك صلاحية!", ephemeral=True)
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

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="انشاء_امر", description="لوحة متكاملة لإنشاء وتسمية أوامر السيرفر الجديدة")
    async def create_command(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("عذراً، هذا الأمر مخصص للمشرفين فقط!", ephemeral=True)
            return

        modal = CreateCommandModal()
        await interaction.response.send_modal(modal)

async def setup(bot):
    await bot.add_cog(WhitelistCog(bot))
