import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Modal, Select, View
import os
from pymongo import MongoClient

# === لوحة تفاعلية لإنشاء الرومات بالذكاء والسرعة المطلقة ===
class CreateChannelModal(Modal, title="مركز قيادة إنشاء الرومات الذكي"):
    channel_name = discord.ui.TextInput(
        label="اسم الروم الجديد (بدون مسافات أو بـ -)",
        placeholder="مثال: chat, general, support...",
        max_length=50
    )

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        ch_name = self.channel_name.value.strip().replace(" ", "-")
        
        # إرسال خيارات نوع الروم (صوتي أو كتابي)
        view = ChannelTypeView(ch_name)
        await interaction.response.send_message(
            f"⚡ تم رصد اسم الروم: **{ch_name}**\nاختر نوع القناة التي تريد إطلاقها فوراً:",
            view=view,
            ephemeral=True
        )

class ChannelTypeSelect(Select):
    def __init__(self, channel_name):
        self.channel_name = channel_name
        options = [
            discord.SelectOption(label="قناة كتابية (Text Channel)", description="إنشاء روم شات كتابي جديد ومنسق", emoji="💬"),
            discord.SelectOption(label="قناة صوتية (Voice Channel)", description="إنشاء روم صوتي خاص بالأعضاء", emoji="🔊"),
            discord.SelectOption(label="روم إداري مخفي (Staff Only)", description="روم كتابي سري خاص بالمشرفين فقط", emoji="🛡️")
        ]
        super().__init__(placeholder="اختر تصنيف الروم...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        choice = self.values[0]
        
        try:
            if "كتابية" in choice:
                # إنشاء روم كتابي عادي
                new_ch = await guild.create_text_channel(name=self.channel_name)
                await interaction.response.edit_message(content=f"✅ تم إطلاق الروم الكتابي بنجاح: {new_ch.mention}", view=None)
            
            elif "صوتية" in choice:
                # إنشاء روم صوتي
                new_ch = await guild.create_voice_channel(name=self.channel_name)
                await interaction.response.edit_message(content=f"✅ تم إطلاق الروم الصوتي بنجاح: **{new_ch.name}**", view=None)
            
            elif "إداري" in choice:
                # إنشاء روم إداري بصلاحيات مخفية عن الأعضاء العاديين
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    interaction.user: discord.PermissionOverwrite(read_messages=True)
                }
                new_ch = await guild.create_text_channel(name=f"secure-{self.channel_name}", overwrites=overwrites)
                await interaction.response.edit_message(content=f"🔒 تم إنشاء الروم الإداري السري بنجاح: {new_ch.mention}", view=None)
                
        except Exception as e:
            await interaction.response.edit_message(content=f"❌ حدث خطأ أثناء إنشاء الروم: تأكد أن البوت يمتلك صلاحية (Manage Channels).", view=None)

class ChannelTypeView(View):
    def __init__(self, channel_name):
        super().__init__()
        self.add_item(ChannelTypeSelect(channel_name))


# === كلاس التحكم الإداري الخارق ===
class AdvancedAdminCore(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # 1. أمر إنشاء الرومات الأسطوري (سلاش + كتابة مباشرة)
    @app_commands.command(name="انشاء", description="لوحة تحكم مرنة لإنشاء الرومات الصوتية والكتابية فوراً")
    async def create_channel_slash(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("❌ عذراً، لا تمتلك صلاحية إدارة القنوات لتنفيذ هذا الأمر!", ephemeral=True)
            return
        await interaction.response.send_modal(CreateChannelModal())

    # 2. أمر العقوبات والقفل المطلق (Lockdown)
    @app_commands.command(name="قفل", description="قفل الشات الحالي تماماً ومنع الجميع من التحدث الطوارئ القصوى")
    async def lockdown_channel(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ هذا الأمر خاص بمديري السيرفر فقط!", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        overwrite = channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = False
        await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        
        embed = discord.Embed(
            title="🚨 حالة طوارئ: تم إغلاق القناة",
            description="تم تجميد هذه القناة بأمر إداري صارم. يمنع إرسال الرسائل حتى إشعار آخر.",
            color=discord.Color.red()
        )
        await channel.send(embed=embed)
        await interaction.followup.send("🔒 تم قفل الروم بنجاح.", ephemeral=True)

    # 3. أمر فك القفل (Unlock)
    @app_commands.command(name="فتح", description="إلغاء حالة الطوارئ وفتح القناة للأعضاء")
    async def unlock_channel(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ هذا الأمر خاص بمديري السيرفر فقط!", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        overwrite = channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = True
        await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        
        embed = discord.Embed(
            title="🟢 عودة الحياة: تم فتح القناة",
            description="تمت إزالة القيود، وأصبح بإمكان الجميع التحدث الآن.",
            color=discord.Color.green()
        )
        await channel.send(embed=embed)
        await interaction.followup.send("🔓 تم فتح الروم بنجاح.", ephemeral=True)

    # 4. طرد ذكي مع تقرير أمني (Kick)
    @app_commands.command(name="طرد", description="طرد عضو مخالف مع توثيق العملية بسجل السيرفر")
    @app_commands.describe(member="العضو المراد طرده", reason="سبب الطرد")
    async def kick_member(self, interaction: discord.Interaction, member: discord.Member, reason: str = "لم يُذكر سبب"):
        if not interaction.user.guild_permissions.kick_members:
            await interaction.response.send_message("❌ لا تمتلك صلاحية طرد الأعضاء!", ephemeral=True)
            return
        
        try:
            await member.kick(reason=reason)
            embed = discord.Embed(
                title="👢 عملية طرد ناجحة",
                description=f"تم طرد العضو **{member.name}** بنجاح.",
                color=discord.Color.orange()
            )
            embed.add_field(name="السبب:", value=reason, inline=False)
            embed.set_footer(text=f"بواسطة المشرف: {interaction.user.name}")
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await interaction.response.send_message(f"❌ فشل طرد العضو (ربما رتبته أعلى من بوتك أو رتبتك).", ephemeral=True)

    # 5. تطهير الشات الجبار (Mass Purge)
    @app_commands.command(name="مسح", description="حذف عدد معين من رسائل الشات بلمح البصر")
    @app_commands.describe(amount="عدد الرسائل المراد مسحها (من 1 إلى 100)")
    async def purge_messages(self, interaction: discord.Interaction, amount: int):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ لا تمتلك صلاحية إدارة الرسائل!", ephemeral=True)
            return
        
        if amount > 100 or amount < 1:
            await interaction.response.send_message("⚠️ يرجى تحديد رقم بين 1 و 100.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        msg = await interaction.channel.send(f"🧹 تم تطهير وحذف **{len(deleted)}** رسالة بنجاح!")
        await msg.delete(delay=4)

    # نظام الاستماع السريع للكتابة المباشرة بدون رموز لأهم أوامر الإدارة
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        content = message.content.strip()
        if not content:
            return

        parts = content.split(" ")
        cmd = parts[0].lower()

        # لو كتب المستخدم كلمة "انشاء" مباشرة بالشات بدون /
        if cmd == "انشاء":
            if message.author.guild_permissions.manage_channels:
                # يمديه يستدعي اللوحة أو ينشئ بالطريقة السريعة
                await message.channel.send(f"⚡ يا هلا {message.author.mention}، لإنشاء روم فوري استخدم أمر السلاش `/انشاء` لتظهر لك لوحة الخيارات المتقدمة!")

async def setup(bot):
    await bot.add_cog(AdvancedAdminCore(bot))
