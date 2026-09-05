import os
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Modal, Select, View
from pymongo import MongoClient
from datetime import timedelta

# === 1. لوحة تفاعلية لإدخال سبب مخصص ومدة زمنية للإسكات ===
class CustomTimeoutModal(Modal, title="تحديد سبب ومدّة مخصصة للإسكات"):
    reason_input = discord.ui.TextInput(
        label="سبب الإسكات",
        placeholder="اكتب السبب هنا (مثال: مخالفة قوانين الروم الصوتع)...",
        max_length=100
    )
    minutes_input = discord.ui.TextInput(
        label="المدة بالدقائق (أرقام فقط)",
        placeholder="مثال: 15 أو 60...",
        max_length=5
    )

    def __init__(self, target: discord.Member):
        super().__init__()
        self.target = target

    async def on_submit(self, interaction: discord.Interaction):
        try:
            minutes = int(self.minutes_input.value.strip())
            reason = self.reason_input.value.strip()
        except ValueError:
            await interaction.response.send_message("❌ يرجى إدخال رقم صحيح في خانة الدقائق!", ephemeral=True)
            return

        try:
            await self.target.timeout(timedelta(minutes=minutes), reason=reason)
            embed = discord.Embed(
                title="🔇 عقوبة إسكات مخصصة",
                description=f"تم إسكات العضو **{self.target.name}** بنجاح.",
                color=discord.Color.dark_red()
            )
            embed.add_field(name="السبب:", value=reason, inline=False)
            embed.add_field(name="المدة:", value=f"{minutes} دقيقة", inline=False)
            embed.set_footer(text=f"بواسطة المشرف: {interaction.user.name}")
            await interaction.response.send_message(embed=embed)
        except Exception:
            await interaction.response.send_message("❌ فشل إسكات العضو (تأكد أن رتبة بوتك أعلى من رتبته).", ephemeral=True)

# === 2. قائمة اختيار الأسباب الجاهزة للإسكات ===
class TimeoutSelect(Select):
    def __init__(self, target: discord.Member):
        self.target = target
        options = [
            discord.SelectOption(label="شتم / ألفاظ نابية", description="مدة الإسكات: 15 دقيقة", emoji="⚠️"),
            discord.SelectOption(label="سبام / إزعاج متكرر", description="مدة الإسكات: 30 دقيقة", emoji="⏱️"),
            discord.SelectOption(label="تخريب أو إثارة مشاكل", description="مدة الإسكات: 60 دقيقة (ساعة)", emoji="🛑"),
            discord.SelectOption(label="إدخال سبب ومدة مخصصة", description="افتح لوحة لكتابة سبب يدوي ومدّة خاصة", emoji="✍️")
        ]
        super().__init__(placeholder="اختر سبب الإسكات المناسب...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        choice = self.values[0]

        if "مخصصة" in choice:
            await interaction.response.send_modal(CustomTimeoutModal(self.target))
            return

        # تحديد الأسباب والمدد الجاهزة بناءً على اختيارك
        if "شتم" in choice:
            minutes = 15
            reason = "شتم / ألفاظ نابية"
        elif "سبام" in choice:
            minutes = 30
            reason = "سبام / إزعاج متكرر"
        elif "تخريب" in choice:
            minutes = 60
            reason = "تخريب أو إثارة مشاكل"
        else:
            minutes = 10
            reason = "مخالفة عامة"

        try:
            await self.target.timeout(timedelta(minutes=minutes), reason=reason)
            embed = discord.Embed(
                title="🔇 تنفيذ عقوبة الإسكات",
                description=f"تم إسكات العضو **{self.target.name}** بنجاح.",
                color=discord.Color.red()
            )
            embed.add_field(name="السبب:", value=reason, inline=False)
            embed.add_field(name="المدة:", value=f"{minutes} دقيقة", inline=False)
            embed.set_footer(text=f"بواسطة المشرف: {interaction.user.name}")
            await interaction.response.edit_message(content="✅ تمت العملية بنجاح وإسكات العضو.", embed=embed, view=None)
        except Exception:
            await interaction.response.edit_message(content="❌ فشل إسكات العضو (تأكد أن رتبة بوتك أعلى منه).", view=None)

class TimeoutView(View):
    def __init__(self, target: discord.Member):
        super().__init__()
        self.add_item(TimeoutSelect(target))


# === كلاس الإدارة والأمان الشامل (منظومة الـ Slash المتكاملة) ===
class AdvancedAdminCore(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        mongo_url = os.environ.get('MONGO_URI')
        self.client = MongoClient(mongo_url)
        self.db = self.client['discord_bot_db']
        self.whitelist_collection = self.db['whitelist_admins']
        self.settings_collection = self.db['guild_settings']

    def _has_permission(self, author, guild):
        if author.id == guild.owner_id:
            return True
        db_admin = self.whitelist_collection.find_one({"user_id": str(author.id)})
        if db_admin:
            return True
        return False

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        setting = self.settings_collection.find_one({"guild_id": member.guild.id})
        if setting and "welcome_channel" in setting:
            channel = member.guild.get_channel(setting["welcome_channel"])
            if channel:
                embed = discord.Embed(
                    title="🎉 منور السيرفر يا وحش!",
                    description=f"أهلاً بك {member.mention} في سيرفر **{member.guild.name}**!\nنتمنى لك أوقاتاً ممتعة معنا.",
                    color=discord.Color.green()
                )
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.set_footer(text=f"رقم العضوية: {member.guild.member_count}")
                await channel.send(embed=embed)

    # 1. أمر الحظر (Ban)
    @app_commands.command(name="حظر", description="حظر عضو مخالف نهائياً من السيرفر")
    @app_commands.describe(member="العضو المراد حظره", reason="سبب الحظر")
    async def ban_member(self, interaction: discord.Interaction, member: discord.Member, reason: str = "لم يُذكر سبب"):
        if not interaction.user.guild_permissions.ban_members and not self._has_permission(interaction.user, interaction.guild):
            await interaction.response.send_message("❌ لا تمتلك صلاحية حظر الأعضاء!", ephemeral=True)
            return
        try:
            await member.ban(reason=reason)
            embed = discord.Embed(title="🔨 تم الحظر بنجاح", description=f"تم حظر العضو **{member.name}**.", color=discord.Color.dark_red())
            embed.add_field(name="السبب:", value=reason)
            embed.set_footer(text=f"بواسطة: {interaction.user.name}")
            await interaction.response.send_message(embed=embed)
        except Exception:
            await interaction.response.send_message("❌ فشل حظر العضو (تأكد أن رتبة بوتك أعلى من رتبته).", ephemeral=True)

    # 2. أمر الطرد (Kick)
    @app_commands.command(name="طرد", description="طرد عضو مخالف مع توثيق العملية")
    @app_commands.describe(member="العضو المراد طرده", reason="سبب الطرد")
    async def kick_member(self, interaction: discord.Interaction, member: discord.Member, reason: str = "لم يُذكر سبب"):
        if not interaction.user.guild_permissions.kick_members and not self._has_permission(interaction.user, interaction.guild):
            await interaction.response.send_message("❌ لا تمتلك صلاحية طرد الأعضاء!", ephemeral=True)
            return
        try:
            await member.kick(reason=reason)
            embed = discord.Embed(title="👢 عملية طرد ناجحة", description=f"تم طرد العضو **{member.name}**.", color=discord.Color.orange())
            embed.add_field(name="السبب:", value=reason)
            await interaction.response.send_message(embed=embed)
        except Exception:
            await interaction.response.send_message("❌ فشل طرد العضو.", ephemeral=True)

    # 3. أمر الإسكات الذكي التفاعلي (مع قائمة الأسباب)
    @app_commands.command(name="ايسكات", description="إسكات عضو مع اختيار سبب جاهز أو تحديد مدة مخصصة")
    @app_commands.describe(member="العضو المراد إסקاته")
    async def timeout_member_interactive(self, interaction: discord.Interaction, member: discord.Member):
        if not interaction.user.guild_permissions.moderate_members and not self._has_permission(interaction.user, interaction.guild):
            await interaction.response.send_message("❌ لا تمتلك صلاحية إسكات الأعضاء!", ephemeral=True)
            return
        
        view = TimeoutView(member)
        await interaction.response.send_message(
            f"⚖️ اختر سبب الإسكات المناسب للعضو **{member.name}** من القائمة أدناه، أو حدد مدة وسبب يدوي:",
            view=view,
            ephemeral=True
        )

    # 4. أمر مسح الرسائل (Purge)
    @app_commands.command(name="مسح", description="حذف عدد معين من رسائل الشات بلمح البصر")
    @app_commands.describe(amount="عدد الرسائل المراد مسحها (من 1 إلى 100)")
    async def purge_messages(self, interaction: discord.Interaction, amount: int):
        if not interaction.user.guild_permissions.manage_messages and not self._has_permission(interaction.user, interaction.guild):
            await interaction.response.send_message("❌ لا تمتلك صلاحية إدارة الرسائل!", ephemeral=True)
            return
        
        if amount > 100 or amount < 1:
            await interaction.response.send_message("⚠️ يرجى تحديد رقم بين 1 و 100.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        msg = await interaction.channel.send(f"🧹 تم تطهير وحذف **{len(deleted)}** رسالة بنجاح!")
        await msg.delete(delay=4)

    # 5. أمر قفل القناة (Lock)
    @app_commands.command(name="قفل", description="قفل الشات الحالي تماماً ومنع الجميع من التحدث طوارئ")
    async def lockdown_channel(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator and not self._has_permission(interaction.user, interaction.guild):
            await interaction.response.send_message("❌ هذا الأمر خاص بالإدارة العليا فقط!", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        overwrite = channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = False
        await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        
        embed = discord.Embed(
            title="🚨 حالة طوارئ: تم إغلاق القناة",
            description="تم تجميد هذه القناة بأمر إداري صارم.",
            color=discord.Color.red()
        )
        await channel.send(embed=embed)
        await interaction.followup.send("🔒 تم قفل الروم بنجاح.", ephemeral=True)

    # 6. أمر فتح القناة (Unlock)
    @app_commands.command(name="فتح", description="إلغاء حالة الطوارئ وفتح القناة للأعضاء")
    async def unlock_channel(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator and not self._has_permission(interaction.user, interaction.guild):
            await interaction.response.send_message("❌ هذا الأمر خاص بالإدارة العليا فقط!", ephemeral=True)
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

    # ==================== 🔒 أوامر الـ Slash الخاصة بالـ Whitelist ====================

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
            await interaction.response.send_message(f"✅ تم اعتماد **{member.name}** ضمن طاقم الإدارة العليا المعتمدين!")

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
        if not self._has_permission(interaction.user, interaction.guild):
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

async def setup(bot):
    await bot.add_cog(AdvancedAdminCore(bot))
