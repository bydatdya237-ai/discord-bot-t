import os
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Modal, Select, View
from pymongo import MongoClient

class CreateCommandModal(Modal, title="إنشاء وتخصيص أمر خارق جديد"):
    cmd_name = discord.ui.TextInput(
        label="اسم الأمر (باللغة الإنجليزية بدون مسافات)",
        placeholder="مثال: ban, ticket, daily...",
        max_length=30
    )
    cmd_description = discord.ui.TextInput(
        label="وصف الوظيفة أو الرسالة التلقائية للأمر",
        placeholder="اكتب الوصف أو الرد التلقائي هنا...",
        style=discord.TextStyle.paragraph,
        max_length=150
    )

    async def on_submit(self, interaction: discord.Interaction):
        view = CategorySelectView(str(self.cmd_name.value), str(self.cmd_description.value))
        await interaction.response.send_message(
            f"⚡ **تم التقاط اسم الأمر:** `/{self.cmd_name.value}`\nالخطوة التالية: اختر التصنيف الاحترافي للوظيفة:",
            view=view,
            ephemeral=True
        )

class CategorySelect(Select):
    def __init__(self, cmd_name, cmd_desc):
        self.cmd_name = cmd_name
        self.cmd_desc = cmd_desc
        
        options = [
            discord.SelectOption(label="أوامر الإدارة والحماية الخارقة", description="بان، كيك، تيم آوت، مسح ذكي، قفل رومات", emoji="🛡️"),
            discord.SelectOption(label="أوامر التذاكر والدعم الفني", description="لوحات تذاكر أوتوماتيكية، تقديمات، سيرفر دعم", emoji="🎫"),
            discord.SelectOption(label="أوامر الترحيب والمجتمع", description="كارد ترحيب فخم، رتب تلقائية، موديراتور ذكي", emoji="✨"),
            discord.SelectOption(label="أوامر الألعاب والاقتصاد", description="نظام نقاط، كاسحة ألغام، روليت، حظ يومي", emoji="🎮"),
            discord.SelectOption(label="أوامر الأدوات والإعلانات", description="صانع إيمبدات خرافي، سحوبات غفوة، تفاصيل أعضاء", emoji="🛠️")
        ]
        super().__init__(placeholder="اختر التصنيف العام...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]
        view = ActionSelectView(self.cmd_name, self.cmd_desc, category)
        await interaction.response.edit_message(
            content=f"📁 **التصنيف:** {category}\nاختر الوظيفة الاحترافية المحددة:",
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
            "أوامر الإدارة والحماية الخارقة": [
                discord.SelectOption(label="حظر نهائي (Ban)", description="حظر عضو مع مسح رسائله وسجلاته"),
                discord.SelectOption(label="طرد ذكي (Kick)", description="طرد العضو المخالف بأمان"),
                discord.SelectOption(label="إسكات مؤقت (Timeout)", description="كتم صوت وعقاب مؤقت للعضو"),
                discord.SelectOption(label="حرق رسائل (Purge)", description="مسح مئات الرسائل دفعة واحدة بلمح البصر"),
                discord.SelectOption(label="قفل القناة (Lockdown)", description="قفل الشات وتأمينه ضد الهجمات")
            ],
            "أوامر التذاكر والدعم الفني": [
                discord.SelectOption(label="لوحة تذاكر أزرار (Ticket Panel)", description="إرسال لوحة تفاعلية ببرمجة خاصة لفتح التذاكر"),
                discord.SelectOption(label="تقديم الإداريين (Staff Application)", description="استقبال طلبات الانضمام للإدارة بنظام الأزرار"),
                discord.SelectOption(label="إغلاق التذكرة فوراً (Close Ticket)", description="أمر لأرشفة وحذف التذكرة")
            ],
            "أوامر الترحيب والمجتمع": [
                discord.SelectOption(label="ترحيب ملكي (Welcome Card)", description="إرسال صورة وكارد ترحيب فخم بالعضو الجديد"),
                discord.SelectOption(label="منح رتبة تلقائية (Auto-Role)", description="إعطاء رتبة الأعضاء فور دخولهم السيرفر"),
                discord.SelectOption(label="نظام الردود التلقائية (Auto-Responder)", description="رد فوري مخصص بناءً على وصف الأمر")
            ],
            "أوامر الألعاب والاقتصاد": [
                discord.SelectOption(label="الراتب اليومي (Daily Economy)", description="منح نقاط وأموال افتراضية يومية للأعضاء"),
                discord.SelectOption(label="لعبة كاسحة الألغام (Minesweeper Pro)", description="لعبة تفاعلية ممتعة ومصممة خصيصاً للشات"),
                discord.SelectOption(label="لعبة حجر ورقة مقص (RPS Challenge)", description="تحدي مباشر بين الأعضاء بالنقاط")
            ],
            "أوامر الأدوات والإعلانات": [
                discord.SelectOption(label="صانع الإيمبدات الملكية (Embed Maker)", description="تحويل الوصف إلى إيمبد فخم ومنسق رسمياً"),
                discord.SelectOption(label="سحب عشوائي فخم (Giveaway Engine)", description="بدء مسابقة عشوائية باختيار فائز أسطوري"),
                discord.SelectOption(label="فحص ملف العضو (Whois / Userinfo)", description="عرض تقرير كامل وخرافي عن حساب العضو")
            ]
        }
        
        selected_options = actions_dict.get(category, [discord.SelectOption(label="وظيفة مخصصة ذكية", description="تنفيذ أمر برمجى خاص")])
        super().__init__(placeholder="اختر الوظيفة الدقيقة للسيرفر...", min_values=1, max_values=1, options=selected_options)

    async def callback(self, interaction: discord.Interaction):
        mongo_url = os.environ.get('MONGO_URI')
        client = MongoClient(mongo_url)
        db = client['discord_bot_db']
        collection = db['custom_commands']

        chosen_action = self.values[0]
        
        command_data = {
            "guild_id": interaction.guild.id,
            "name": self.cmd_name.lower(),
            "description": self.cmd_desc,
            "action": chosen_action
        }
        
        collection.update_one(
            {"guild_id": interaction.guild.id, "name": self.cmd_name.lower()},
            {"$set": command_data},
            upsert=True
        )

        await interaction.response.edit_message(
            content=f"🔥 **تم تفعيل ونشر الأمر الأسطوري بنجاح!**\n- اسم الأمر (بدون بادئات): `{self.cmd_name.lower()}`\n- الوصف / المحتوى: `{self.cmd_desc}`\n- النظام والمهمة: `{chosen_action}`\n\n*(جاهز للاستخدام الفوري بالكتابة المباشرة في الشات!)*",
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
        self.db = self.client['discord_bot_db']
        self.whitelist_collection = self.db['whitelist_admins']
        self.custom_commands_collection = self.db['custom_commands']

    def _has_permission(self, interaction: discord.Interaction):
        if interaction.user.id == interaction.guild.owner_id:
            return True
        db_admin = self.whitelist_collection.find_one({"user_id": str(interaction.user.id)})
        if db_admin:
            return True
        return False

    @app_commands.command(name="تحديد", description="إضافة عضو لقائمة المشرفين المعتمدين")
    @app_commands.describe(member="العضو المراد إضافته")
    async def add_whitelist(self, interaction: discord.Interaction, member: discord.Member):
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message("❌ هذا الأمر مخصص لصاحب السيرفر الأساسي فقط!", ephemeral=True)
            return

        user_id = str(member.id)
        existing = self.whitelist_collection.find_one({"user_id": user_id})
        
        if existing:
            await interaction.response.send_message(f"⚠️ العضو **{member.name}** مسجل مسبقاً في قائمة الصلاحيات!", ephemeral=True)
        else:
            self.whitelist_collection.insert_one({"user_id": user_id, "name": member.name})
            await interaction.response.send_message(f"✅ تم اعتماد **{member.name}** ضمن طاقم المشرفين الأكفياء!")

    @app_commands.command(name="ازالة", description="إزالة عضو من قائمة المشرفين المعتمدين")
    @app_commands.describe(member="العضو المراد إزالته")
    async def remove_whitelist(self, interaction: discord.Interaction, member: discord.Member):
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message("❌ هذا الأمر مخصص لصاحب السيرفر الأساسي فقط!", ephemeral=True)
            return

        user_id = str(member.id)
        result = self.whitelist_collection.delete_one({"user_id": user_id})
        
        if result.deleted_count > 0:
            await interaction.response.send_message(f"🗑️ تمت إزالة **{member.name}** من قائمة الإدارة بنجاح.")
        else:
            await interaction.response.send_message(f"⚠️ هذا العضو غير موجود في قائمة المشرفين أساساً.", ephemeral=True)

    @app_commands.command(name="كشف", description="استعراض قائمة المشرفين المعتمدين في السيرفر")
    async def show_whitelist(self, interaction: discord.Interaction):
        if not self._has_permission(interaction):
            await interaction.response.send_message("❌ عذراً، لا تمتلك الصلاحية للاطلاع على السجل!", ephemeral=True)
            return

        admins = list(self.whitelist_collection.find({}))
        embed = discord.Embed(
            title="🛡️ السجل الأمني: المشرفون المعتمدون",
            color=discord.Color.dark_embed()
        )
        if admins:
            admins_list = "\n".join([f"💎 <@{admin['user_id']}>" for admin in admins])
            embed.add_field(name="قائمة الأمان:", value=admins_list, inline=False)
        else:
            embed.add_field(name="قائمة الأمان:", value="لا يوجد مشرفون إضافيون مضافون حالياً.", inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="انشاء_امر", description="فتح لوحة التحكم الخارقة لابتكار أوامر جديدة للسيرفر")
    async def create_command(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ عذراً، تتطلب هذه الميزة صلاحية مدير السيرفر (Administrator)!", ephemeral=True)
            return

        modal = CreateCommandModal()
        await interaction.response.send_modal(modal)

    # نظام الاستماع المباشر: لتنفيذ الأوامر بالكتابة العادية في الشات بدون أي رموز (بدون / أو !)
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        # استخراج أول كلمة من الرسالة كاسم للأمر
        content = message.content.strip()
        if not content:
            return
            
        parts = content.split(" ")
        command_name = parts[0].lower()

        # البحث في قاعدة البيانات عن هذا الأمر المخصص لهذا السيرفر
        cmd_doc = self.custom_commands_collection.find_one({
            "guild_id": message.guild.id,
            "name": command_name
        })

        if cmd_doc:
            action = cmd_doc.get("action", "")
            description = cmd_doc.get("description", "لا يوجد وصف إضافي.")

            # تنفيذ أسطوري ذكي بناءً على نوع المهمة المخزنة
            if "بان" in action or "Ban" in action:
                if message.author.guild_permissions.ban_members:
                    if message.mentions:
                        target = message.mentions[0]
                        await message.guild.ban(target, reason=f"Executed by {message.author}")
                        await message.channel.send(f"🚨 تم حظر العضو **{target.name}** بناءً على أمر السيرفر الخارق!")
                    else:
                        await message.channel.send(f"⚠️ يرجى منشن العضو المراد حظره بجانب الأمر.")
                else:
                    await message.channel.send(f"❌ لا تمتلك صلاحية حظر الأعضاء لتنفيذ هذا الأمر.")
            
            elif "إسكات" in action or "Timeout" in action:
                if message.author.guild_permissions.moderate_members:
                    if message.mentions:
                        target = message.mentions[0]
                        from datetime import timedelta
                        await target.timeout(timedelta(minutes=10), reason=f"Command executed by {message.author}")
                        await message.channel.send(f"🔇 تم إسكات العضو **{target.name}** لمدة 10 دقائق بنجاح.")
                    else:
                        await message.channel.send(f"⚠️ يرجى منشن العضو المراد إسكاته.")
                else:
                    await message.channel.send(f"❌ لا تمتلك صلاحية الإسكات.")

            elif "مسح" in action or "Purge" in action:
                if message.author.guild_permissions.manage_messages:
                    try:
                        await message.channel.purge(limit=10)
                        msg = await message.channel.send(f"🧹 تم تنظيف الشات بنجاح!")
                        await msg.delete(delay=3)
                    except:
                        pass
                else:
                    await message.channel.send(f"❌ لا تمتلك صلاحية إدارة الرسائل.")

            else:
                # الرد التلقائي الذكي أو محتوى الوصف المخصص
                embed = discord.Embed(
                    title=f"⚡ تنفيـذ الأمر: {command_name}",
                    description=description,
                    color=discord.Color.gold()
                )
                embed.set_footer(text=f"طلب بواسطة: {message.author.name}", icon_url=message.author.display_avatar.url)
                await message.channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(WhitelistCog(bot))
