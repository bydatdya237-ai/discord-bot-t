import asyncio
import os

import discord
from discord.ext import commands
from motor.motor_asyncio import AsyncIOMotorClient


# =========================================================
# اسم الأمر في الموقع
# =========================================================

COMMAND_NAME = "استدعاء"


# =========================================================
# Cog الاستدعاء
# =========================================================

class SummonCog(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        # =================================================
        # MongoDB
        # =================================================

        mongo_uri = os.environ.get("MONGO_URI")

        if mongo_uri:

            self.db_client = AsyncIOMotorClient(
                mongo_uri
            )

            self.db = self.db_client.discord_bot_db

            self.website_command_settings = (
                self.db.website_command_settings
            )

        else:

            self.db_client = None
            self.db = None
            self.website_command_settings = None

    # =====================================================
    # دعم guild_id كـ String أو Integer
    # =====================================================

    def guild_id_variants(self, guild_id):

        variants = [
            str(guild_id)
        ]

        try:

            variants.append(
                int(guild_id)
            )

        except Exception:
            pass

        return variants

    # =====================================================
    # جلب إعدادات الأمر من الموقع
    # =====================================================

    async def get_command_setting(
        self,
        guild_id,
        command_name
    ):

        if self.website_command_settings is None:
            return None

        guild_ids = self.guild_id_variants(
            guild_id
        )

        # -------------------------------------------------
        # الطريقة الجديدة
        # -------------------------------------------------

        setting = await self.website_command_settings.find_one(
            {
                "guild_id": {
                    "$in": guild_ids
                },
                "command_name": str(command_name)
            }
        )

        if setting:
            return setting

        # -------------------------------------------------
        # دعم البيانات القديمة
        # -------------------------------------------------

        setting = await self.website_command_settings.find_one(
            {
                "guild_id": {
                    "$in": guild_ids
                },
                "name": str(command_name)
            }
        )

        return setting

    # =====================================================
    # التحقق من صلاحية الأمر
    # =====================================================

    async def has_summon_permission(
        self,
        guild_id,
        member,
        channel_id=None
    ):

        if member is None:
            return False

        setting = await self.get_command_setting(
            guild_id,
            COMMAND_NAME
        )

        # -------------------------------------------------
        # لا يوجد إعداد
        # -------------------------------------------------

        if not setting:
            return False

        # -------------------------------------------------
        # الأمر غير مفعل
        # -------------------------------------------------

        if not setting.get(
            "enabled",
            False
        ):
            return False

        # -------------------------------------------------
        # الرتب المسموحة
        # -------------------------------------------------

        role_ids = setting.get(
            "role_ids",
            []
        )

        if not role_ids:
            return False

        allowed_role_ids = {
            str(role_id)
            for role_id in role_ids
        }

        user_role_ids = {
            str(role.id)
            for role in member.roles
        }

        # -------------------------------------------------
        # لا يملك الرتبة
        # -------------------------------------------------

        if not allowed_role_ids.intersection(
            user_role_ids
        ):
            return False

        # -------------------------------------------------
        # التحقق من الروم
        # -------------------------------------------------

        if channel_id is not None:

            channel_ids = setting.get(
                "channel_ids",
                []
            )

            if not channel_ids:
                return False

            allowed_channel_ids = {
                str(channel_id)
                for channel_id in channel_ids
            }

            if str(channel_id) not in allowed_channel_ids:
                return False

        return True

    # =====================================================
    # جلب الروم المطلوب
    # =====================================================

    async def get_target_channel(
        self,
        channel_id
    ):

        try:

            channel_id = int(
                str(channel_id).strip()
            )

        except (
            ValueError,
            TypeError
        ):

            return (
                None,
                "❌ ID الروم غير صحيح."
            )

        try:

            channel = self.bot.get_channel(
                channel_id
            )

            if channel is None:

                channel = await self.bot.fetch_channel(
                    channel_id
                )

            return (
                channel,
                None
            )

        except discord.NotFound:

            return (
                None,
                "❌ لم يتم العثور على الروم بهذا الـ ID."
            )

        except discord.Forbidden:

            return (
                None,
                "❌ البوت لا يملك صلاحية الوصول إلى هذا الروم."
            )

        except discord.HTTPException:

            return (
                None,
                "❌ حدث خطأ أثناء جلب الروم."
            )

    # =====================================================
    # إنشاء Embed الاستدعاء
    # =====================================================

    def create_summon_embed(
        self,
        target_channel,
        reason,
        author
    ):

        embed = discord.Embed(
            title="🚨 تنبيه استدعاء رسمي",
            description=(
                "لقد تم استدعاؤك للتوجه إلى الروم المحدد."
            ),
            color=discord.Color.red()
        )

        embed.add_field(
            name="📍 الروم المطلوب:",
            value=target_channel.mention,
            inline=False
        )

        embed.add_field(
            name="📝 سبب الاستدعاء:",
            value=reason,
            inline=False
        )

        embed.set_footer(
            text=f"بواسطة المشرف: {author.name}"
        )

        return embed


# =========================================================
# Modal الاستدعاء العادي والكامل
# =========================================================

class SummonModal(
    discord.ui.Modal,
    title="🚨 استدعاء عضو"
):

    room_id = discord.ui.TextInput(
        label="ID الروم المطلوب",
        placeholder="اكتب ID الروم هنا",
        required=True,
        max_length=30
    )

    reason = discord.ui.TextInput(
        label="سبب الاستدعاء",
        placeholder="اكتب سبب الاستدعاء هنا",
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=1000
    )

    def __init__(
        self,
        cog,
        member=None,
        author=None,
        full=False
    ):

        super().__init__()

        self.cog = cog
        self.member = member
        self.author = author
        self.full = full

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        # =================================================
        # التحقق من السيرفر
        # =================================================

        if interaction.guild is None:

            await interaction.response.send_message(
                "❌ تعذر تحديد السيرفر.",
                ephemeral=True
            )

            return

        # =================================================
        # التحقق من الموقع
        # =================================================

        allowed = await self.cog.has_summon_permission(
            interaction.guild.id,
            interaction.user,
            interaction.channel.id
        )

        if not allowed:

            await interaction.response.send_message(
                "❌ ليس لديك صلاحية استخدام أمر الاستدعاء.",
                ephemeral=True
            )

            return

        # =================================================
        # جلب الروم
        # =================================================

        target_channel, error = (
            await self.cog.get_target_channel(
                self.room_id.value
            )
        )

        if error:

            await interaction.response.send_message(
                error,
                ephemeral=True
            )

            return

        # =================================================
        # التأكد أن الروم من نفس السيرفر
        # =================================================

        target_guild = getattr(
            target_channel,
            "guild",
            None
        )

        if target_guild is not None:

            if target_guild.id != interaction.guild.id:

                await interaction.response.send_message(
                    "❌ لا يمكنك تحديد روم من سيرفر آخر.",
                    ephemeral=True
                )

                return

        # =================================================
        # الاستدعاء الفردي
        # =================================================

        if not self.full:

            embed = self.cog.create_summon_embed(
                target_channel,
                self.reason.value,
                self.author
            )

            try:

                await self.member.send(
                    embed=embed
                )

                await interaction.response.send_message(
                    f"✅ تم استدعاء {self.member.mention} بنجاح إلى "
                    f"{target_channel.mention}\n"
                    "✉️ تم إرسال رسالة الاستدعاء له.",
                    ephemeral=True
                )

            except discord.Forbidden:

                await interaction.response.send_message(
                    "⚠️ تعذر إرسال رسالة خاصة لهذا العضو.",
                    ephemeral=True
                )

            except discord.HTTPException:

                await interaction.response.send_message(
                    "⚠️ حدث خطأ أثناء إرسال الرسالة الخاصة.",
                    ephemeral=True
                )

            return

        # =================================================
        # الاستدعاء الكامل
        # =================================================

        guild = interaction.guild

        embed = self.cog.create_summon_embed(
            target_channel,
            self.reason.value,
            self.author
        )

        await interaction.response.send_message(
            "📨 جاري إرسال الاستدعاء لأعضاء السيرفر...",
            ephemeral=True
        )

        success = 0
        failed = 0

        for member in guild.members:

            if member.bot:
                continue

            try:

                await member.send(
                    embed=embed
                )

                success += 1

            except (
                discord.Forbidden,
                discord.HTTPException,
                discord.NotFound
            ):

                failed += 1

            await asyncio.sleep(1)

        # =================================================
        # النتيجة
        # =================================================

        try:

            await interaction.followup.send(
                "✅ **اكتمل الاستدعاء العام**\n\n"
                f"📨 تم إرسال الرسالة إلى: **{success}** عضو\n"
                f"⚠️ تعذر الإرسال إلى: **{failed}** عضو",
                ephemeral=True
            )

        except discord.HTTPException:
            pass


# =========================================================
# زر الاستدعاء العادي
# =========================================================

class SummonView(discord.ui.View):

    def __init__(
        self,
        cog,
        member,
        author,
        full=False
    ):

        super().__init__(
            timeout=120
        )

        self.cog = cog
        self.member = member
        self.author = author
        self.full = full

    @discord.ui.button(
        label="بدء الاستدعاء",
        style=discord.ButtonStyle.danger,
        emoji="🚨"
    )
    async def summon_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if interaction.user.id != self.author.id:

            await interaction.response.send_message(
                "❌ هذا الزر ليس لك.",
                ephemeral=True
            )

            return

        # =================================================
        # إعادة التحقق من صلاحيات الموقع
        # =================================================

        if interaction.guild is None:

            await interaction.response.send_message(
                "❌ تعذر تحديد السيرفر.",
                ephemeral=True
            )

            return

        allowed = await self.cog.has_summon_permission(
            interaction.guild.id,
            interaction.user,
            interaction.channel.id
        )

        if not allowed:

            await interaction.response.send_message(
                "❌ لم تعد تملك صلاحية استخدام أمر الاستدعاء.",
                ephemeral=True
            )

            return

        await interaction.response.send_modal(
            SummonModal(
                self.cog,
                self.member,
                self.author,
                self.full
            )
        )


# =========================================================
# Modal استدعاء المجموعة
# =========================================================

class GroupSummonModal(
    discord.ui.Modal,
    title="🚨 استدعاء مجموعة"
):

    room_id = discord.ui.TextInput(
        label="ID الروم المطلوب",
        placeholder="اكتب ID الروم هنا",
        required=True,
        max_length=30
    )

    reason = discord.ui.TextInput(
        label="سبب الاستدعاء",
        placeholder="اكتب سبب الاستدعاء هنا",
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=1000
    )

    def __init__(
        self,
        cog,
        member_ids,
        author
    ):

        super().__init__()

        self.cog = cog
        self.member_ids = list(
            member_ids
        )
        self.author = author

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        # =================================================
        # التحقق من السيرفر
        # =================================================

        if interaction.guild is None:

            await interaction.response.send_message(
                "❌ تعذر تحديد السيرفر.",
                ephemeral=True
            )

            return

        # =================================================
        # التحقق من صلاحية الموقع
        # =================================================

        allowed = await self.cog.has_summon_permission(
            interaction.guild.id,
            interaction.user,
            interaction.channel.id
        )

        if not allowed:

            await interaction.response.send_message(
                "❌ ليس لديك صلاحية استخدام أمر الاستدعاء.",
                ephemeral=True
            )

            return

        # =================================================
        # جلب الروم
        # =================================================

        target_channel, error = (
            await self.cog.get_target_channel(
                self.room_id.value
            )
        )

        if error:

            await interaction.response.send_message(
                error,
                ephemeral=True
            )

            return

        # =================================================
        # التأكد من نفس السيرفر
        # =================================================

        target_guild = getattr(
            target_channel,
            "guild",
            None
        )

        if target_guild is not None:

            if target_guild.id != interaction.guild.id:

                await interaction.response.send_message(
                    "❌ لا يمكنك تحديد روم من سيرفر آخر.",
                    ephemeral=True
                )

                return

        guild = interaction.guild

        # =================================================
        # إنشاء الرسالة
        # =================================================

        embed = self.cog.create_summon_embed(
            target_channel,
            self.reason.value,
            self.author
        )

        await interaction.response.send_message(
            "📨 جاري إرسال الاستدعاء للأعضاء المحددين...",
            ephemeral=True
        )

        success = 0
        failed = 0

        # =================================================
        # إرسال الرسائل
        # =================================================

        for member_id in self.member_ids:

            member = guild.get_member(
                member_id
            )

            if member is None:

                failed += 1
                continue

            if member.bot:
                continue

            try:

                await member.send(
                    embed=embed
                )

                success += 1

            except (
                discord.Forbidden,
                discord.HTTPException,
                discord.NotFound
            ):

                failed += 1

            await asyncio.sleep(1)

        # =================================================
        # النتيجة
        # =================================================

        try:

            await interaction.followup.send(
                "✅ **اكتمل الاستدعاء الجماعي**\n\n"
                f"👥 الأعضاء المحددون: **{len(self.member_ids)}**\n"
                f"📨 تم إرسال الرسالة إلى: **{success}** عضو\n"
                f"⚠️ تعذر الإرسال إلى: **{failed}** عضو",
                ephemeral=True
            )

        except discord.HTTPException:
            pass


# =========================================================
# قائمة اختيار الأعضاء
# =========================================================

class GroupMemberSelect(
    discord.ui.Select
):

    def __init__(
        self,
        group_view,
        members
    ):

        self.group_view = group_view

        options = []

        for member in members:

            description = f"@{member.name}"

            if len(description) > 100:
                description = description[:100]

            options.append(
                discord.SelectOption(
                    label=member.display_name[:100],
                    description=description,
                    value=str(member.id)
                )
            )

        # حماية إضافية
        if not options:

            options.append(
                discord.SelectOption(
                    label="لا يوجد أعضاء",
                    value="none"
                )
            )

        super().__init__(
            placeholder="👥 اختر الأعضاء الذين تريد استدعاءهم",
            min_values=1,
            max_values=min(
                len(options),
                25
            ),
            options=options,
            row=0
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        if interaction.user.id != self.group_view.author.id:

            await interaction.response.send_message(
                "❌ هذه القائمة ليست لك.",
                ephemeral=True
            )

            return

        # =================================================
        # إعادة التحقق من صلاحية الموقع
        # =================================================

        if interaction.guild is None:

            await interaction.response.send_message(
                "❌ تعذر تحديد السيرفر.",
                ephemeral=True
            )

            return

        allowed = await self.group_view.cog.has_summon_permission(
            interaction.guild.id,
            interaction.user,
            interaction.channel.id
        )

        if not allowed:

            await interaction.response.send_message(
                "❌ لم تعد تملك صلاحية استخدام أمر الاستدعاء.",
                ephemeral=True
            )

            return

        for value in self.values:

            if value == "none":
                continue

            member_id = int(value)

            if member_id not in self.group_view.selected_members:

                self.group_view.selected_members.append(
                    member_id
                )

        await interaction.response.edit_message(
            embed=self.group_view.create_embed(),
            view=self.group_view
        )


# =========================================================
# View استدعاء المجموعة
# =========================================================

class GroupSummonView(
    discord.ui.View
):

    MEMBERS_PER_PAGE = 25

    def __init__(
        self,
        cog,
        guild,
        author
    ):

        super().__init__(
            timeout=300
        )

        self.cog = cog
        self.guild = guild
        self.author = author

        self.members = [
            member
            for member in guild.members
            if not member.bot
        ]

        self.members.sort(
            key=lambda member: (
                member.display_name or ""
            ).lower()
        )

        self.page = 0
        self.selected_members = []

        self.update_components()

    # =====================================================
    # عدد الصفحات
    # =====================================================

    @property
    def total_pages(self):

        if not self.members:
            return 1

        return (
            len(self.members)
            + self.MEMBERS_PER_PAGE
            - 1
        ) // self.MEMBERS_PER_PAGE

    # =====================================================
    # أعضاء الصفحة الحالية
    # =====================================================

    def current_members(self):

        start = (
            self.page
            * self.MEMBERS_PER_PAGE
        )

        end = (
            start
            + self.MEMBERS_PER_PAGE
        )

        return self.members[
            start:end
        ]

    # =====================================================
    # Embed
    # =====================================================

    def create_embed(self):

        selected_count = len(
            self.selected_members
        )

        embed = discord.Embed(
            title="🚨 استدعاء مجموعة",
            description=(
                "اختر الأعضاء الذين تريد إرسال الاستدعاء لهم.\n\n"
                "يمكنك الانتقال بين الصفحات، "
                "والاختيارات السابقة ستبقى محفوظة.\n\n"
                f"👥 تم اختيار: **{selected_count}** عضو"
            ),
            color=discord.Color.red()
        )

        embed.set_footer(
            text=(
                f"الصفحة {self.page + 1} "
                f"من {self.total_pages}"
            )
        )

        return embed

    # =====================================================
    # تحديث الأزرار والقائمة
    # =====================================================

    def update_components(self):

        self.clear_items()

        current_members = self.current_members()

        if current_members:

            self.add_item(
                GroupMemberSelect(
                    self,
                    current_members
                )
            )

        # =================================================
        # السابق
        # =================================================

        previous_button = discord.ui.Button(
            label="السابق",
            style=discord.ButtonStyle.secondary,
            emoji="⬅️",
            disabled=self.page <= 0,
            row=1
        )

        async def previous_callback(
            interaction: discord.Interaction
        ):

            if interaction.user.id != self.author.id:

                await interaction.response.send_message(
                    "❌ هذه القائمة ليست لك.",
                    ephemeral=True
                )

                return

            if interaction.guild is None:

                await interaction.response.send_message(
                    "❌ تعذر تحديد السيرفر.",
                    ephemeral=True
                )

                return

            allowed = await self.cog.has_summon_permission(
                interaction.guild.id,
                interaction.user,
                interaction.channel.id
            )

            if not allowed:

                await interaction.response.send_message(
                    "❌ لم تعد تملك صلاحية استخدام أمر الاستدعاء.",
                    ephemeral=True
                )

                return

            if self.page > 0:
                self.page -= 1

            self.update_components()

            await interaction.response.edit_message(
                embed=self.create_embed(),
                view=self
            )

        previous_button.callback = previous_callback

        self.add_item(
            previous_button
        )

        # =================================================
        # التالي
        # =================================================

        next_button = discord.ui.Button(
            label="التالي",
            style=discord.ButtonStyle.secondary,
            emoji="➡️",
            disabled=(
                self.page
                >= self.total_pages - 1
            ),
            row=1
        )

        async def next_callback(
            interaction: discord.Interaction
        ):

            if interaction.user.id != self.author.id:

                await interaction.response.send_message(
                    "❌ هذه القائمة ليست لك.",
                    ephemeral=True
                )

                return

            if interaction.guild is None:

                await interaction.response.send_message(
                    "❌ تعذر تحديد السيرفر.",
                    ephemeral=True
                )

                return

            allowed = await self.cog.has_summon_permission(
                interaction.guild.id,
                interaction.user,
                interaction.channel.id
            )

            if not allowed:

                await interaction.response.send_message(
                    "❌ لم تعد تملك صلاحية استخدام أمر الاستدعاء.",
                    ephemeral=True
                )

                return

            if self.page < self.total_pages - 1:

                self.page += 1

            self.update_components()

            await interaction.response.edit_message(
                embed=self.create_embed(),
                view=self
            )

        next_button.callback = next_callback

        self.add_item(
            next_button
        )

        # =================================================
        # بدء الاستدعاء
        # =================================================

        summon_button = discord.ui.Button(
            label="بدء الاستدعاء",
            style=discord.ButtonStyle.danger,
            emoji="🚨",
            row=2
        )

        async def summon_callback(
            interaction: discord.Interaction
        ):

            if interaction.user.id != self.author.id:

                await interaction.response.send_message(
                    "❌ هذا الزر ليس لك.",
                    ephemeral=True
                )

                return

            if interaction.guild is None:

                await interaction.response.send_message(
                    "❌ تعذر تحديد السيرفر.",
                    ephemeral=True
                )

                return

            allowed = await self.cog.has_summon_permission(
                interaction.guild.id,
                interaction.user,
                interaction.channel.id
            )

            if not allowed:

                await interaction.response.send_message(
                    "❌ لم تعد تملك صلاحية استخدام أمر الاستدعاء.",
                    ephemeral=True
                )

                return

            if not self.selected_members:

                await interaction.response.send_message(
                    "⚠️ اختر عضوًا واحدًا على الأقل أولًا.",
                    ephemeral=True
                )

                return

            await interaction.response.send_modal(
                GroupSummonModal(
                    self.cog,
                    self.selected_members,
                    self.author
                )
            )

        summon_button.callback = summon_callback

        self.add_item(
            summon_button
        )

        # =================================================
        # إلغاء
        # =================================================

        cancel_button = discord.ui.Button(
            label="إلغاء",
            style=discord.ButtonStyle.secondary,
            emoji="❌",
            row=2
        )

        async def cancel_callback(
            interaction: discord.Interaction
        ):

            if interaction.user.id != self.author.id:

                await interaction.response.send_message(
                    "❌ هذا الزر ليس لك.",
                    ephemeral=True
                )

                return

            await interaction.response.edit_message(
                content="❌ تم إلغاء استدعاء المجموعة.",
                embed=None,
                view=None
            )

            self.stop()

        cancel_button.callback = cancel_callback

        self.add_item(
            cancel_button
        )

    # =====================================================
    # انتهاء الوقت
    # =====================================================

    async def on_timeout(self):

        self.stop()


# =========================================================
# أمر الاستدعاء
# =========================================================

class SummonCommandsCog(
    commands.Cog
):

    pass


# =========================================================
# نضيف الأمر إلى نفس الـ Cog الأساسي
# =========================================================

class SummonCog(SummonCog):

    @commands.command(
        name="استدعاء"
    )
    async def summon(
        self,
        ctx,
        target=None
    ):

        # =================================================
        # يجب أن يكون داخل سيرفر
        # =================================================

        if ctx.guild is None:
            return

        # =================================================
        # التحقق من الموقع
        # =================================================

        allowed = await self.has_summon_permission(
            ctx.guild.id,
            ctx.author,
            ctx.channel.id
        )

        # =================================================
        # إذا الأمر غير مفعل / الروم غير مسموح /
        # الرتبة غير مسموحة
        # =================================================

        if not allowed:

            # إذا كان الأمر موجودًا لكن العضو ليس لديه
            # الرتبة المسموحة، نرسل رسالة فقط إذا كان
            # الإعداد موجودًا والروم مسموحًا.

            setting = await self.get_command_setting(
                ctx.guild.id,
                COMMAND_NAME
            )

            if not setting:
                return

            if not setting.get(
                "enabled",
                False
            ):
                return

            channel_ids = setting.get(
                "channel_ids",
                []
            )

            if not channel_ids:
                return

            allowed_channels = {
                str(channel_id)
                for channel_id in channel_ids
            }

            if str(ctx.channel.id) not in allowed_channels:
                return

            await ctx.send(
                "❌ ليس لديك صلاحية لاستخدام أمر الاستدعاء."
            )

            return

        # =================================================
        # الاستدعاء الكامل
        # =================================================

        if (
            target
            and target.lower() == "كامل"
        ):

            embed = discord.Embed(
                title="🚨 استدعاء كامل",
                description=(
                    "سيتم إرسال رسالة استدعاء إلى أعضاء السيرفر.\n\n"
                    "اضغط على الزر بالأسفل لإدخال "
                    "**ID الروم** و**سبب الاستدعاء**."
                ),
                color=discord.Color.red()
            )

            await ctx.send(
                embed=embed,
                view=SummonView(
                    self,
                    None,
                    ctx.author,
                    full=True
                )
            )

            return

        # =================================================
        # استدعاء مجموعة
        # =================================================

        if (
            target
            and target.lower() == "مجموعة"
        ):

            guild = ctx.guild

            members = [
                member
                for member in guild.members
                if not member.bot
            ]

            if not members:

                await ctx.send(
                    "❌ لا يوجد أعضاء يمكن اختيارهم."
                )

                return

            view = GroupSummonView(
                self,
                guild,
                ctx.author
            )

            await ctx.send(
                embed=view.create_embed(),
                view=view
            )

            return

        # =================================================
        # بدون عضو
        # =================================================

        if target is None:

            await ctx.send(
                "⚠️ استخدم الأمر هكذا:\n"
                "`-استدعاء @الشخص`\n\n"
                "أو للاستدعاء الكامل:\n"
                "`-استدعاء كامل`\n\n"
                "أو لاستدعاء مجموعة:\n"
                "`-استدعاء مجموعة`"
            )

            return

        # =================================================
        # استدعاء عضو واحد
        # =================================================

        try:

            member = await commands.MemberConverter().convert(
                ctx,
                target
            )

        except commands.MemberNotFound:

            await ctx.send(
                "❌ لم أتمكن من العثور على هذا العضو."
            )

            return

        if member.bot:

            await ctx.send(
                "❌ لا يمكن استدعاء البوتات."
            )

            return

        embed = discord.Embed(
            title="🚨 استدعاء عضو",
            description=(
                f"تم اختيار العضو: {member.mention}\n\n"
                "اضغط على الزر بالأسفل لإدخال "
                "**ID الروم** و**سبب الاستدعاء**."
            ),
            color=discord.Color.red()
        )

        await ctx.send(
            embed=embed,
            view=SummonView(
                self,
                member,
                ctx.author,
                full=False
            )
        )

    # =====================================================
    # أخطاء الأمر
    # =====================================================

    @summon.error
    async def summon_error(
        self,
        ctx,
        error
    ):

        if ctx.guild is None:
            return

        # =================================================
        # تجاهل إذا الأمر غير موجود بالموقع
        # =================================================

        setting = await self.get_command_setting(
            ctx.guild.id,
            COMMAND_NAME
        )

        if not setting:
            return

        # =================================================
        # تجاهل إذا الأمر غير مفعل
        # =================================================

        if not setting.get(
            "enabled",
            False
        ):
            return

        # =================================================
        # تجاهل إذا الروم غير مسموح
        # =================================================

        channel_ids = setting.get(
            "channel_ids",
            []
        )

        allowed_channels = {
            str(channel_id)
            for channel_id in channel_ids
        }

        if str(ctx.channel.id) not in allowed_channels:
            return

        # =================================================
        # أخطاء العضو
        # =================================================

        if isinstance(
            error,
            commands.MemberNotFound
        ):

            await ctx.send(
                "❌ لم أتمكن من العثور على هذا العضو."
            )

            return

        if isinstance(
            error,
            commands.BadArgument
        ):

            await ctx.send(
                "❌ العضو غير صحيح.\n"
                "استخدم: `-استدعاء @الشخص`"
            )

            return

        # =================================================
        # طباعة الأخطاء غير المتوقعة في Console
        # =================================================

        print(
            f"[Summon] Error: {repr(error)}"
        )


# =========================================================
# تشغيل الـ Cog
# =========================================================

async def setup(bot):

    await bot.add_cog(
        SummonCog(bot)
    )
