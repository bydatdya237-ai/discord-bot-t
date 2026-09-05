import os
import discord
from discord.ext import commands
from discord import app_commands
from pymongo import MongoClient
import random
from datetime import timedelta

class GiantCleanBotCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        mongo_url = os.environ.get('MONGO_URI')
        self.client = MongoClient(mongo_url)
        self.db = self.client['discord_bot_db']
        self.whitelist_collection = self.db['whitelist_admins']
        self.economy_collection = self.db['economy']
        self.afk_collection = self.db['afk']
        self.settings_collection = self.db['guild_settings']

    def _has_permission(self, author, guild):
        if author.id == guild.owner_id:
            return True
        db_admin = self.whitelist_collection.find_one({"user_id": str(author.id)})
        if db_admin:
            return True
        return False

    def get_user_eco(self, user_id):
        data = self.economy_collection.find_one({"user_id": user_id})
        if not data:
            data = {"user_id": user_id, "wallet": 1000, "bank": 5000, "rep": 0}
            self.economy_collection.insert_one(data)
        return data

    def update_user_eco(self, user_id, update_data):
        self.economy_collection.update_one({"user_id": user_id}, update_data, upsert=True)

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

        afk_data = self.afk_collection.find_one({"user_id": message.author.id})
        if afk_data:
            self.afk_collection.delete_one({"user_id": message.author.id})
            try:
                await message.reply(f"welcome back **{message.author.name}**! I have removed your AFK status.", delete_after=5)
            except Exception:
                pass

        if message.mentions:
            for mention in message.mentions:
                mentioned_afk = self.afk_collection.find_one({"user_id": mention.id})
                if mentioned_afk:
                    await message.channel.send(f"⚠️ العضو **{mention.name}** أفتك (AFK) حالياً: `{mentioned_afk['reason']}`")

        content = message.content.strip()
        if not content:
            return

        parts = content.split(" ")
        cmd = parts[0].lower()
        args = parts[1:]
        author = message.author
        channel = message.channel
        guild = message.guild

        # ==================== 🛡️ 1. أوامر الحماية والإدارة ====================

        if cmd == "حظر" or cmd == "ban":
            if author.guild_permissions.ban_members or self._has_permission(author, guild):
                if message.mentions:
                    target = message.mentions[0]
                    reason = " ".join(args[1:]) if len(args) > 1 else "No reason provided"
                    await guild.ban(target, reason=reason)
                    await channel.send(f"🔨 تم حظر العضو **{target.name}** بنجاح. السبب: `{reason}`")
                else:
                    await channel.send("❌ يرجى منشن العضو المراد حظره.")
            else:
                await channel.send("❌ لا تمتلك صلاحية حظر الأعضاء.")

        elif cmd == "طرد" or cmd == "kick":
            if author.guild_permissions.kick_members or self._has_permission(author, guild):
                if message.mentions:
                    target = message.mentions[0]
                    reason = " ".join(args[1:]) if len(args) > 1 else "No reason provided"
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
                await channel.send("🔒 تم قفل هذه القناة بنجاح.")
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

        elif cmd == "تحديد_الترحيب" or cmd == "setwelcome":
            if author.guild_permissions.administrator or self._has_permission(author, guild):
                self.settings_collection.update_one(
                    {"guild_id": guild.id},
                    {"$set": {"welcome_channel": channel.id}},
                    upsert=True
                )
                await channel.send(f"✅ **تم اعتماد هذه القناة كقناة رسمية للترحيب بالأعضاء الجدد تلقائياً!**")
            else:
                await channel.send("❌ تتطلب صلاحية مدير السيرفر.")


        # ==================== 💰 2. أوامر الاقتصاد والبنوك ====================

        elif cmd == "فلوس" or cmd == "balance" or cmd == "راتبي" or cmd == "كاش":
            target = message.mentions[0] if message.mentions else author
            eco = self.get_user_eco(target.id)
            embed = discord.Embed(title=f"💳 محفظة الحساب: {target.name}", color=discord.Color.green())
            embed.add_field(name="الكاش الجاهز:", value=f"💸 `{eco['wallet']}$`", inline=True)
            embed.add_field(name="الرصيد بالبنك:", value=f"🏦 `{eco['bank']}$`", inline=True)
            embed.set_thumbnail(url=target.display_avatar.url)
            await channel.send(embed=embed)

        elif cmd == "راتب" or cmd == "daily":
            eco = self.get_user_eco(author.id)
            added = 2500
            self.update_user_eco(author.id, {"$inc": {"wallet": added}})
            await channel.send(f"🎁 استلمت راتبك اليومي يا **{author.name}** بقيمة `+2500$` كاش في جيبك!")

        elif cmd == "اشتغل" or cmd == "work":
            earned = random.randint(200, 800)
            jobs = ["مطور برمجيات خبيثة", "قائد عصابة", "طيار حربي", "مهندس ذكاء اصطناعي", "تاجر عملات رقمية", "مراسل ميداني"]
            job_name = random.choice(jobs)
            self.update_user_eco(author.id, {"$inc": {"wallet": earned}})
            await channel.send(f"💼 اشتغلت بمهنة **{job_name}** وحصلت على أجر قدره `+{earned}$`!")

        elif cmd == "إيداع" or cmd == "dep":
            if args and args[0].isdigit():
                amount = int(args[0])
                eco = self.get_user_eco(author.id)
                if eco['wallet'] >= amount:
                    self.update_user_eco(author.id, {"$inc": {"wallet": -amount, "bank": amount}})
                    await channel.send(f"📥 تم إيداع `{amount}$` في البنك الآمن بنجاح.")
                else:
                    await channel.send("❌ ما معاك كاش يكفي في محفظتك لإيداع هذا المبلغ!")
            else:
                await channel.send("⚠️ حدد المبلغ. مثال: `إيداع 1000`")

        elif cmd == "سحب" or cmd == "with":
            if args and args[0].isdigit():
                amount = int(args[0])
                eco = self.get_user_eco(author.id)
                if eco['bank'] >= amount:
                    self.update_user_eco(author.id, {"$inc": {"wallet": amount, "bank": -amount}})
                    await channel.send(f"📤 تم سحب `{amount}$` من البنك إلى محفظتك بنجاح.")
                else:
                    await channel.send("❌ رصيدك البنكي لا يحتوي على هذا المبلغ!")
            else:
                await channel.send("⚠️ حدد المبلغ المراد سحبه. مثال: `سحب 500`")

        elif cmd == "تحويل" or cmd == "pay":
            if message.mentions and len(args) > 1 and args[1].isdigit():
                target = message.mentions[0]
                amount = int(args[1])
                if target.id == author.id:
                    await channel.send("❌ ما تقدر تحول لنفسك!")
                    return
                eco = self.get_user_eco(author.id)
                if eco['wallet'] >= amount:
                    self.update_user_eco(author.id, {"$inc": {"wallet": -amount}})
                    self.update_user_eco(target.id, {"$inc": {"wallet": amount}})
                    await channel.send(f"💸 تم تحويل مبلغ `{amount}$` بنجاح إلى العضو **{target.name}**.")
                else:
                    await channel.send("❌ محفظتك لا تحتوي على هذا المبلغ!")
            else:
                await channel.send("⚠️ طريقة الاستخدام: `تحويل @User 500`")

        elif cmd == "سرقة" or cmd == "crime":
            eco = self.get_user_eco(author.id)
            if eco['wallet'] < 300:
                await channel.send("❌ تحتاج إلى 300$ كاش على الأقل لتنفيذ عملية سرقة!")
                return
            success = random.choice([True, False, False, True])
            if success:
                loot = random.randint(1000, 4000)
                self.update_user_eco(author.id, {"$inc": {"wallet": loot}})
                await channel.send(f"🦹 نجحت خطة السطو وحصلت على غنيمة ضخمة بقيمة `+{loot}$`!")
            else:
                fine = random.randint(300, 900)
                self.update_user_eco(author.id, {"$inc": {"wallet": -fine}})
                await channel.send(f"🚨 كشفتك الشرطة وتم القبض عليك، غرامة قدرها `-{fine}$`!")

        elif cmd == "سرقة_عضو" or cmd == "rob":
            if message.mentions:
                target = message.mentions[0]
                if target.id == author.id:
                    await channel.send("❌ تسرق نفسك؟ صاحي أنت؟")
                    return
                target_eco = self.get_user_eco(target.id)
                if target_eco['wallet'] < 500:
                    await channel.send(f"❌ العضو **{target.name}** مفلس ولا يملك كاش يستحق السرقة!")
                    return
                success = random.choice([True, False, False])
                if success:
                    stolen = random.randint(100, int(target_eco['wallet'] / 2))
                    self.update_user_eco(target.id, {"$inc": {"wallet": -stolen}})
                    self.update_user_eco(author.id, {"$inc": {"wallet": stolen}})
                    await channel.send(f"🥷 هجمت على **{target.name}** وسرقت منه مبلغ `{stolen}$` في الخفاء!")
                else:
                    fine = 300
                    self.update_user_eco(author.id, {"$inc": {"wallet": -fine}})
                    await channel.send(f"💥 انقفطت أثناء السرقة وتم تغريمك `{fine}$`!")
            else:
                await channel.send("⚠️ منشن الشخص المراد سرقته: `سرقة_عضو @User`")

        elif cmd == "تنقيب" or cmd == "slut":
            earned = random.randint(500, 1500)
            self.update_user_eco(author.id, {"$inc": {"wallet": earned}})
            await channel.send(f"⛏️ نقبت في مناجم الذهب السرية وبعت الحطام بقيمة `+{earned}$`!")

        elif cmd == "متجر" or cmd == "store":
            embed = discord.Embed(title="🛒 متجر السيرفر الافتراضي", color=discord.Color.blue())
            embed.add_field(name="1. رتبة VIP الأسطورية", value="السعر: `15,000$` | الأمر: `شراء vip`", inline=False)
            embed.add_field(name="2. رتبة الملوك الملكية", value="السعر: `50,000$` | الأمر: `شراء king`", inline=False)
            await channel.send(embed=embed)

        elif cmd == "شراء" or cmd == "buy":
            if args:
                item = args[0].lower()
                eco = self.get_user_eco(author.id)
                if item == "vip":
                    if eco['bank'] >= 15000:
                        self.update_user_eco(author.id, {"$inc": {"bank": -15000}})
                        role = discord.utils.get(guild.roles, name="VIP")
                        if role:
                            await author.add_roles(role)
                        await channel.send(f"🎉 مبروك يا **{author.name}** اشتريت رتبة VIP بنجاح!")
                    else:
                        await channel.send("❌ رصيدك البنكي لا يكفي (تحتاج 15,000$)!")
                elif item == "king":
                    if eco['bank'] >= 50000:
                        self.update_user_eco(author.id, {"$inc": {"bank": -50000}})
                        role = discord.utils.get(guild.roles, name="King")
                        if role:
                            await author.add_roles(role)
                        await channel.send(f"👑 مبروك يا فخم اشتريت رتبة King الأسطورية!")
                    else:
                        await channel.send("❌ رصيدك البنكي لا يكفي (تحتاج 50,000$)!")
                else:
                    await channel.send("❌ السلعة غير موجودة في المتجر.")
            else:
                await channel.send("⚠️ اكتب اسم السلعة. مثال: `شراء vip`")

        elif cmd == "أغنياء" or cmd == "leaderboard" or cmd == "توب":
            top_users = self.economy_collection.find().sort("bank", -1).limit(5)
            embed = discord.Embed(title="🏆 قائمة أغنياء السيرفر", color=discord.Color.gold())
            desc = ""
            for idx, user_doc in enumerate(top_users, 1):
                member_obj = guild.get_member(user_doc['user_id'])
                name = member_obj.name if member_obj else f"User ID: {user_doc['user_id']}"
                total_money = user_doc['wallet'] + user_doc['bank']
                desc += f"**{idx}.** {name} ⟷ الإجمالي: `{total_money}$`\n"
            embed.description = desc if desc else "لا توجد بيانات كافية بعد."
            await channel.send(embed=embed)

        elif cmd == "تصفير_اقتصاد" or cmd == "reseteco":
            if author.id == guild.owner_id or self._has_permission(author, guild):
                if message.mentions:
                    target = message.mentions[0]
                    self.economy_collection.delete_one({"user_id": target.id})
                    await channel.send(f"🔄 تم تصفير اقتصاد العضو **{target.name}** بنجاح.")
                else:
                    await channel.send("⚠️ منشن العضو.")
            else:
                await channel.send("❌ خاص بالإدارة العليا.")

        elif cmd == "عطاء" or cmd == "givemoney":
            if author.id == guild.owner_id or self._has_permission(author, guild):
                if message.mentions and len(args) > 1 and args[1].isdigit():
                    target = message.mentions[0]
                    amount = int(args[1])
                    self.update_user_eco(target.id, {"$inc": {"wallet": amount}})
                    await channel.send(f"🎁 تم ضخ مبلغ `{amount}$` في محفظة العضو **{target.name}** الإدارية.")
                else:
                    await channel.send("⚠️ الاستخدام: `عطاء @User 5000`")
            else:
                await channel.send("❌ ليس لديك صلاحية.")

        elif cmd == "خصم_مالي" or cmd == "takemoney":
            if author.id == guild.owner_id or self._has_permission(author, guild):
                if message.mentions and len(args) > 1 and args[1].isdigit():
                    target = message.mentions[0]
                    amount = int(args[1])
                    self.update_user_eco(target.id, {"$inc": {"wallet": -amount}})
                    await channel.send(f"💸 تم خصم مبلغ `{amount}$` من محفظة العضو **{target.name}**.")
                else:
                    await channel.send("⚠️ الاستخدام: `خصم_مالي @User 1000`")
            else:
                await channel.send("❌ ليس لديك صلاحية.")


        # ==================== 🛠️ 3. أوامر الأدوات والمعلومات ====================

        elif cmd == "بينغ" or cmd == "ping":
            latency = round(self.bot.latency * 1000)
            await channel.send(f"🏓 سرعة استجابة البوت الحالية: `{latency}ms`")

        elif cmd == "سيرفر" or cmd == "serverinfo":
            embed = discord.Embed(title=f"📊 معلومات السيرفر: {guild.name}", color=discord.Color.blue())
            embed.add_field(name="👑 الأونر الأساسي:", value=guild.owner.mention, inline=True)
            embed.add_field(name="👥 إجمالي الأعضاء:", value=f"`{guild.member_count}` عضو", inline=True)
            embed.add_field(name="🛡️ عدد الرتب:", value=f"`{len(guild.roles)}` رتبة", inline=True)
            embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
            await channel.send(embed=embed)

        elif cmd == "بروفايل" or cmd == "userinfo":
            target = message.mentions[0] if message.mentions else author
            embed = discord.Embed(title=f"👤 ملف العضو: {target.name}", color=discord.Color.gold())
            embed.add_field(name="🆔 الآيدي:", value=f"`{target.id}`", inline=True)
            embed.add_field(name="📅 تاريخ الانضمام للديسكورد:", value=f"<t:{int(target.created_at.timestamp())}:R>", inline=False)
            embed.set_thumbnail(url=target.display_avatar.url)
            await channel.send(embed=embed)

        elif cmd == "صورة" or cmd == "avatar":
            target = message.mentions[0] if message.mentions else author
            embed = discord.Embed(title=f"🖼️ الصورة الشخصية لـ {target.name}", color=discord.Color.blurple())
            embed.set_image(url=target.display_avatar.url)
            await channel.send(embed=embed)

        elif cmd == "بانر" or cmd == "banner":
            target = message.mentions[0] if message.mentions else author
            user_obj = await self.bot.fetch_user(target.id)
            if user_obj.banner:
                embed = discord.Embed(title=f"Banner: {target.name}", color=discord.Color.dark_purple())
                embed.set_image(url=user_obj.banner.url)
                await channel.send(embed=embed)
            else:
                await channel.send("❌ هذا المستخدم ليس لديه بانر شخصي.")

        elif cmd == "افك" or cmd == "afk":
            reason = " ".join(args) if args else "مشغول / غائب مؤقتاً"
            self.afk_collection.update_one(
                {"user_id": author.id},
                {"$set": {"reason": reason}},
                upsert=True
            )
            await channel.send(f"💤 تم تفعيل وضع **AFK** لك بنجاح: `{reason}`")

        elif cmd == "قول" or cmd == "say":
            if author.guild_permissions.manage_messages or self._has_permission(author, guild):
                text = " ".join(args)
                if text:
                    await message.delete()
                    await channel.send(text)
                else:
                    await channel.send("⚠️ اكتب النص المراد إرساله.")
            else:
                await channel.send("❌ لا تمتلك صلاحية.")

        elif cmd == "إيمبد" or cmd == "embed":
            if author.guild_permissions.manage_messages or self._has_permission(author, guild):
                text = " ".join(args)
                if text:
                    await message.delete()
                    embed = discord.Embed(description=text, color=discord.Color.random())
                    await channel.send(embed=embed)
                else:
                    await channel.send("⚠️ اكتب محتوى الإيمبد.")
            else:
                await channel.send("❌ لا تمتلك صلاحية.")

        elif cmd == "استطلاع" or cmd == "poll":
            if author.guild_permissions.manage_messages or self._has_permission(author, guild):
                question = " ".join(args)
                if question:
                    await message.delete()
                    embed = discord.Embed(title="📊 استطلاع رأي جديد", description=question, color=discord.Color.magenta())
                    embed.set_footer(text=f"بواسطة: {author.name}")
                    msg = await channel.send(embed=embed)
                    await msg.add_reaction("👍")
                    await msg.add_reaction("👎")
                else:
                    await channel.send("⚠️ اكتب سؤال الاستطلاع.")
            else:
                    await channel.send("❌ لا تمتلك صلاحية.")

        elif cmd == "أعضاء" or cmd == "membercount":
            await channel.send(f"👥 إجمالي الأعضاء المتواجدين في السيرفر حالياً: **{guild.member_count}** عضو أسطوري!")

        elif cmd == "معلومات_البوت" or cmd == "botinfo":
            embed = discord.Embed(title="🤖 معلومات البوت الخارق", description="بوت تدميري واحترافي مخصص لإدارة السيرفرات بأعلى كفاءة.", color=discord.Color.dark_grey())
            embed.add_field(name="البرمجة:", value="Python & Discord.py", inline=True)
            embed.add_field(name="قاعدة البيانات:", value="MongoDB Atlas", inline=True)
            await channel.send(embed=embed)

        elif cmd == "حالة_التشغيل" or cmd == "uptime":
            await channel.send("⚡ البوت يعمل بكامل طاقته ودون انقطاع 24/7.")

        elif cmd == "رتب" or cmd == "roles":
            roles_list = ", ".join([role.mention for role in guild.roles[1:]])
            embed = discord.Embed(title="📜 قائمة رتب السيرفر", description=roles_list if roles_list else "لا توجد رتب.", color=discord.Color.teal())
            await channel.send(embed=embed)

        elif cmd == "قنوات" or cmd == "channels":
            channels_list = ", ".join([c.name for c in guild.channels])
            embed = discord.Embed(title="📁 قائمة قنوات السيرفر", description=channels_list, color=discord.Color.orange())
            await channel.send(embed=embed)

        elif cmd == "رابط" or cmd == "invite":
            await channel.send(f"🔗 رابط دعوة السيرفر الرسمي: https://discord.gg/yourserver")

        elif cmd == "المطور" or cmd == "developer":
            embed = discord.Embed(title="💻 فريق التطوير", description="تم تطوير هذا البوت وبرمجته خصيصاً لتلبية كافة الاحتياجات بأعلى احترافية.", color=discord.Color.red())
            await channel.send(embed=embed)

        elif cmd == "إيمبد_عنوان" or cmd == "sayembed":
            if author.guild_permissions.administrator or self._has_permission(author, guild):
                if len(args) > 1:
                    title = args[0]
                    desc = " ".join(args[1:])
                    await message.delete()
                    embed = discord.Embed(title=title, description=desc, color=discord.Color.gold())
                    await channel.send(embed=embed)
                else:
                    await channel.send("⚠️ الاستخدام: `إيمبد_عنوان العنوان الوصف`")
            else:
                await channel.send("❌ ليس لديك صلاحية.")

        elif cmd == "تنبيه_عام" or cmd == "pingall":
            if author.id == guild.owner_id or self._has_permission(author, guild):
                await channel.send(f"📢 تنبيه عام لجميع الأعضاء بواسطة {author.mention}!")
            else:
                await channel.send("❌ أمر إداري خطير.")

        elif cmd == "أوامر" or cmd == "help" or cmd == "اوامر":
            embed = discord.Embed(
                title="📚 قائمة الأوامر الشاملة (تعمل مباشرة بدون رموز)",
                description="اكتب الأمر مباشرة في الشات (مثال: `فلوس` أو `ban` أو `سيرفر`)",
                color=discord.Color.dark_magenta()
            )
            embed.add_field(
                name="🛡️ 1. الحماية والإدارة:", 
                value="`حظر` , `طرد` , `ايسكات` , `مسح` , `قفل` , `فتح` , `الوضع_البطيء` , `إخفاء` , `إظهار` , `حرق_القناة` , `تغيير_اللقب` , `تحذير` , `رتبة` , `تحديد_الترحيب`", 
                inline=False
            )
            embed.add_field(
                name="💰 2. الاقتصاد:", 
                value="`فلوس` , `راتب` , `اشتغل` , `إيداع` , `سحب` , `تحويل` , `سرقة` , `سرقة_عضو` , `تنقيب` , `متجر` , `شراء` , `أغنياء` , `تصفير_اقتصاد` , `عطاء` , `خصم_مالي`", 
                inline=False
            )
            embed.add_field(
                name="🛠️ 3. الأدوات والمعلومات:", 
                value="`بينغ` , `سيرفر` , `بروفايل` , `صورة` , `بانر` , `افك` , `قول` , `إيمبد` , `استطلاع` , `أعضاء` , `معلومات_البوت` , `حالة_التشغيل` , `رتب` , `قنوات` , `رابط` ,`المطور` , `إيمبد_عنوان` , `تنبيه_عام`", 
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
