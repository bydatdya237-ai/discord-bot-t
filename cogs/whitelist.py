import os
import discord
from discord.ext import commands
from discord import app_commands
from pymongo import MongoClient
from datetime import timedelta

class GiantCleanBotCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        mongo_url = os.environ.get('MONGO_URI')
        self.client = MongoClient(mongo_url)
        self.db = self.client['discord_bot_db']
        self.whitelist_collection = self.db['whitelist_admins']
        self.settings_collection = self.db['guild_settings']
        self.warns_collection = self.db['guild_warns']

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

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        content = message.content.strip()
        if not content:
            return

        parts = content.split(" ")
        cmd = parts[0].lower()
        args = parts[1:]
        author = message.author
        channel = message.channel
        guild = message.guild

        # ==================== 🛡️ أوامر الإدارة، الباندات، والإسكاتات المكثفة ====================

        if cmd == "حظر" or cmd == "ban":
            if author.guild_permissions.ban_members or self._has_permission(author, guild):
                if message.mentions:
                    target = message.mentions[0]
                    reason = " ".join(args[1:]) if len(args) > 1 else "بدون سبب"
                    await guild.ban(target, reason=reason)
                    await channel.send(f"🔨 تم حظر العضو **{target.name}** بنجاح. السبب: `{reason}`")
                else:
                    await channel.send("❌ يرجى منشن العضو المراد حظره.")
            else:
                await channel.send("❌ لا تمتلك صلاحية حظر الأعضاء.")

        elif cmd == "فك_الحظر" or cmd == "unban":
            if author.guild_permissions.ban_members or self._has_permission(author, guild):
                if args:
                    try:
                        user_id = int(args[0])
                        user = await self.bot.fetch_user(user_id)
                        await guild.unban(user)
                        await channel.send(f"🔓 تم ففك الحظر عن العضو **{user.name}** بنجاح.")
                    except Exception:
                        await channel.send("❌ لم أستطِع العثور على المستخدم أوفك الحظر عنه. تأكد من الآيدي.")
                else:
                    await channel.send("⚠️ يرجى كتابة آيدي العضو. مثال: `فك_الحظر 123456789`")
            else:
                await channel.send("❌ لا تمتلك صلاحية فك الحظر.")

        elif cmd == "طرد" or cmd == "kick":
            if author.guild_permissions.kick_members or self._has_permission(author, guild):
                if message.mentions:
                    target = message.mentions[0]
                    reason = " ".join(args[1:]) if len(args) > 1 else "بدون سبب"
                    await guild.kick(target, reason=reason)
                    await channel.send(f"🥾 تم طرد العضو **{target.name}** بنجاح.")
                else:
                    await channel.send("❌ يرجى منشن العضو المراد طرده.")
            else:
                await channel.send("❌ لا تمتلك صلاحية طرد الأعضاء.")

        elif cmd == "ايسكات" or cmd == "mute" or cmd == "تايم_آوت":
            if author.guild_permissions.moderate_members or self._has_permission(author, guild):
                if message.mentions:
                    target = message.mentions[0]
                    minutes = int(args[1]) if len(args) > 1 and args[1].isdigit() else 10
                    await target.timeout(timedelta(minutes=minutes), reason=f"Muted by {author}")
                    await channel.send(f"🔇 تم إسكات العضو **{target.name}** لمدة **{minutes}** دقائق.")
                else:
                    await channel.send("❌ يرجى منشن العضو وتحديد الدقائق.")
            else:
                await channel.send("❌ لا تمتلك صلاحية إسكات الأعضاء.")

        elif cmd == "فك_الإسكات" or cmd == "unmute":
            if author.guild_permissions.moderate_members or self._has_permission(author, guild):
                if message.mentions:
                    target = message.mentions[0]
                    await target.timeout(None, reason=f"Unmuted by {author}")
                    await channel.send(f"🔊 تم فك الإسكات عن العضو **{target.name}**.")
                else:
                    await channel.send("❌ يرجى منشن العضو.")
            else:
                await channel.send("❌ لا تمتلك صلاحية.")

        elif cmd == "مسح" or cmd == "clear" or cmd == "حذف":
            if author.guild_permissions.manage_messages or self._has_permission(author, guild):
                limit = int(args[0]) + 1 if args and args[0].isdigit() else 11
                deleted = await channel.purge(limit=limit)
                msg = await channel.send(f"🧹 تم مسح **{len(deleted) - 1}** رسالة بنجاح!")
                await msg.delete(delay=3)
            else:
                await channel.send("❌ لا تمتلك صلاحية إدارة الرسائل.")

        elif cmd == "قفل" or cmd == "lock":
            if author.guild_permissions.administrator or self._has_permission(author, guild):
                overwrite = channel.overwrites_for(guild.default_role)
                overwrite.send_messages = False
                await channel.set_permissions(guild.default_role, overwrite=overwrite)
                await channel.send("🔒 تم قفل هذه القناة بنجاح لمنع الكتابة.")
            else:
                await channel.send("❌ تتطلب صلاحية مدير السيرفر.")

        elif cmd == "فتح" or cmd == "unlock":
            if author.guild_permissions.administrator or self._has_permission(author, guild):
                overwrite = channel.overwrites_for(guild.default_role)
                overwrite.send_messages = True
                await channel.set_permissions(guild.default_role, overwrite=overwrite)
                await channel.send("🔓 تم فتح هذه القناة بنجاح.")
            else:
                await channel.send("❌ تتطلب صلاحية مدير السيرفر.")

        elif cmd == "الوضع_البطيء" or cmd == "slowmode":
            if author.guild_permissions.manage_channels or self._has_permission(author, guild):
                seconds = int(args[0]) if args and args[0].isdigit() else 0
                await channel.edit(slowmode_delay=seconds)
                await channel.send(f"⏱️ تم ضبط الـ Slowmode على **{seconds}** ثانية.")
            else:
                await channel.send("❌ لا تمتلك صلاحية إدارة القنوات.")

        elif cmd == "إخفاء" or cmd == "hide":
            if author.guild_permissions.manage_channels or self._has_permission(author, guild):
                overwrite = channel.overwrites_for(guild.default_role)
                overwrite.view_channel = False
                await channel.set_permissions(guild.default_role, overwrite=overwrite)
                await channel.send("👁️‍🗨️ تم إخفاء هذه القناة عن الأعضاء.")
            else:
                await channel.send("❌ لا تمتلك صلاحية.")

        elif cmd == "إظهار" or cmd == "unhide":
            if author.guild_permissions.manage_channels or self._has_permission(author, guild):
                overwrite = channel.overwrites_for(guild.default_role)
                overwrite.view_channel = True
                await channel.set_permissions(guild.default_role, overwrite=overwrite)
                await channel.send("👁️ تم إظهار هذه القناة للأعضاء.")
            else:
                await channel.send("❌ لا تمتلك صلاحية.")

        elif cmd == "حرق_القناة" or cmd == "nuke":
            if author.guild_permissions.administrator or self._has_permission(author, guild):
                new_channel = await channel.clone(reason=f"Nuked by {author}")
                await channel.delete()
                await new_channel.send(f"💥 **تم حرق وتجديد القناة بنجاح بواسطة {author.mention}!**")
            else:
                await channel.send("❌ تتطلب صلاحية مدير.")

        elif cmd == "تغيير_اللقب" or cmd == "setnick":
            if author.guild_permissions.manage_nicknames or self._has_permission(author, guild):
                if message.mentions and len(args) > 1:
                    target = message.mentions[0]
                    new_name = " ".join(args[1:])
                    await target.edit(nick=new_name)
                    await channel.send(f"✏️ تم تغيير لقب العضو إلى **{new_name}**.")
                else:
                    await channel.send("⚠️ الطريقة: `تغيير_اللقب @User الاسم_الجديد`")
            else:
                await channel.send("❌ لا تمتلك صلاحية الألقاب.")

        elif cmd == "تحذير" or cmd == "warn":
            if author.guild_permissions.moderate_members or self._has_permission(author, guild):
                if message.mentions:
                    target = message.mentions[0]
                    reason = " ".join(args[1:]) if len(args) > 1 else "بدون سبب"
                    self.warns_collection.insert_one({"user_id": target.id, "guild_id": guild.id, "reason": reason})
                    await channel.send(f"⚠️ تم تحذير العضو {target.mention} بنجاح! السبب: `{reason}`")
                else:
                    await channel.send("⚠️ منشن العضو المراد تحذيره.")
            else:
                await channel.send("❌ لا تمتلك صلاحية.")

        elif cmd == "رتبة" or cmd == "role":
            if author.guild_permissions.manage_roles or self._has_permission(author, guild):
                if message.mentions and len(args) > 1:
                    target = message.mentions[0]
                    role_name = " ".join(args[1:])
                    role = discord.utils.get(guild.roles, name=role_name)
                    if role:
                        if role in target.roles:
                            await target.remove_roles(role)
                            await channel.send(f"🗑️ تمت إزالة رتبة **{role.name}** من العضو **{target.name}**.")
                        else:
                            await target.add_roles(role)
                            await channel.send(f"✅ تم منح رتبة **{role.name}** للعضو **{target.name}**.")
                    else:
                        await channel.send("❌ الرتبة غير موجودة تماماً.")
                else:
                    await channel.send("⚠️ الاستخدام: `رتبة @User اسم_الرتبة`")
            else:
                await channel.send("❌ لا تمتلك صلاحية الرتب.")

        elif cmd == "رتبة_جماعية" or cmd == "massrole":
            if author.guild_permissions.administrator or self._has_permission(author, guild):
                if args:
                    role_name = " ".join(args)
                    role = discord.utils.get(guild.roles, name=role_name)
                    if role:
                        count = 0
                        for member in guild.members:
                            if role not in member.roles and not member.bot:
                                await member.add_roles(role)
                                count += 1
                        await channel.send(f"👥 تم منح رتبة **{role.name}** لـ `{count}` عضو بنجاح!")
                    else:
                        await channel.send("❌ الرتبة غير موجودة.")
                else:
                    await channel.send("⚠️ اكتب اسم الرتبة.")
            else:
                await channel.send("❌ تتطلب صلاحية مدير.")

        elif cmd == "سحب_رتبة_جماعية" or cmd == "massunrole":
            if author.guild_permissions.administrator or self._has_permission(author, guild):
                if args:
                    role_name = " ".join(args)
                    role = discord.utils.get(guild.roles, name=role_name)
                    if role:
                        count = 0
                        for member in guild.members:
                            if role in member.roles:
                                await member.remove_roles(role)
                                count += 1
                        await channel.send(f"🗑️ تمت إزالة رتبة **{role.name}** من `{count}` عضو.")
                    else:
                        await channel.send("❌ الرتبة غير موجودة.")
                else:
                    await channel.send("⚠️ اكتب اسم الرتبة.")
            else:
                await channel.send("❌ تتطلب صلاحية مدير.")

        elif cmd == "قفل_الكل" or cmd == "lockall":
            if author.guild_permissions.administrator or self._has_permission(author, guild):
                for c in guild.channels:
                    if isinstance(c, discord.TextChannel):
                        overwrite = c.overwrites_for(guild.default_role)
                        overwrite.send_messages = False
                        await c.set_permissions(guild.default_role, overwrite=overwrite)
                await channel.send("🔒 **تم قفل جميع قنوات السيرفر النصية بنجاح تام!**")
            else:
                await channel.send("❌ تتطلب صلاحية مدير.")

        elif cmd == "فتح_الكل" or cmd == "unlockall":
            if author.guild_permissions.administrator or self._has_permission(author, guild):
                for c in guild.channels:
                    if isinstance(c, discord.TextChannel):
                        overwrite = c.overwrites_for(guild.default_role)
                        overwrite.send_messages = True
                        await c.set_permissions(guild.default_role, overwrite=overwrite)
                await channel.send("🔓 **تم فتح جميع قنوات السيرفر النصية بنجاح!**")
            else:
                await channel.send("❌ تتطلب صلاحية مدير.")

        elif cmd == "صلاحيات" or cmd == "perms":
            target = message.mentions[0] if message.mentions else author
            perms = [p[0] for p in target.guild_permissions if p[1]]
            embed = discord.Embed(title=f"🛡️ صلاحيات العضو: {target.name}", description=", ".join(perms), color=discord.Color.dark_red())
            await channel.send(embed=embed)

        elif cmd == "تحديد_الترحيب" or cmd == "setwelcome":
            if author.guild_permissions.administrator or self._has_permission(author, guild):
                self.settings_collection.update_one(
                    {"guild_id": guild.id},
                    {"$set": {"welcome_channel": channel.id}},
                    upsert=True
                )
                await channel.send(f"✅ **تم اعتماد هذه القناة كقناة رسمية للترحيب بالأعضاء الجدد!**")
            else:
                await channel.send("❌ تتطلب صلاحية مدير السيرفر.")

        elif cmd == "تنبيه_عام" or cmd == "pingall":
            if author.id == guild.owner_id or self._has_permission(author, guild):
                await channel.send(f"📢 تنبيه إداري هام لجميع الأعضاء بواسطة {author.mention}!")
            else:
                await channel.send("❌ أمر إداري خطير.")

        elif cmd == "أوامر_الإدارة" or cmd == "modhelp" or cmd == "اوامر_الادمن":
            embed = discord.Embed(
                title="🛡️ قائمة أوامر الحماية والإدارة والسيطرة",
                description="أوامر صارمة ومخصصة لإدارة السيرفرات بحزم واحترافية عالية.",
                color=discord.Color.dark_red()
            )
            embed.add_field(
                name="⚔️ أوامر العقوبات والباندات:",
                value="`حظر` , `فك_الحظر` , `طرد` , `ايسكات` , `فك_الإسكات` , `تحذير`",
                inline=False
            )
            embed.add_field(
                name="🔒 أوامر التحكم بالقنوات والشات:",
                value="`مسح` , `قفل` , `فتح` , `الوضع_البطيء` , `إخفاء` , `إظهار` , `حرق_القناة` , `قفل_الكل` , `فتح_الكل`",
                inline=False
            )
            embed.add_field(
                name="👑 أوامر الرتب والإدارة العامة:",
                value="`رتبة` , `رتبة_جماعية` , `سحب_رتبة_جماعية` , `تغيير_اللقب` , `تحديد_الترحيب` , `صلاحيات` , `تنبيه_عام`",
                inline=False
            )
            await channel.send(embed=embed)

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
    await bot.add_cog(GiantCleanBotCog(bot))
