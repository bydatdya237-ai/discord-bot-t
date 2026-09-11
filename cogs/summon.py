import asyncio
import discord
from discord.ext import commands


# =========================================================
# الإعدادات
# =========================================================

COMMAND_ROOM_ID = 1546860236227215400

ALLOWED_ROLE_IDS = {
    1544078469657530578,
    1545851911121666108,
    1544426415766896690
}


# =========================================================
# مربع الاستدعاء العادي / الكامل
# =========================================================

class SummonModal(discord.ui.Modal, title="🚨 استدعاء عضو"):

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

    def __init__(self, bot, member=None, author=None, full=False):
        super().__init__()
        self.bot = bot
        self.member = member
        self.author = author
        self.full = full

    async def on_submit(self, interaction: discord.Interaction):

        try:
            target_room_id = int(self.room_id.value.strip())

        except ValueError:
            await interaction.response.send_message(
                "❌ ID الروم غير صحيح.",
                ephemeral=True
            )
            return

        # -------------------------------------------------
        # جلب الروم
        # -------------------------------------------------

        try:
            target_channel = self.bot.get_channel(target_room_id)

            if target_channel is None:
                target_channel = await self.bot.fetch_channel(
                    target_room_id
                )

        except discord.NotFound:
            await interaction.response.send_message(
                "❌ لم يتم العثور على الروم بهذا الـ ID.",
                ephemeral=True
            )
            return

        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ البوت لا يملك صلاحية الوصول إلى هذا الروم.",
                ephemeral=True
            )
            return

        except discord.HTTPException:
            await interaction.response.send_message(
                "❌ حدث خطأ أثناء جلب الروم.",
                ephemeral=True
            )
            return

        # -------------------------------------------------
        # الاستدعاء الفردي
        # -------------------------------------------------

        if not self.full:

            embed = discord.Embed(
                title="🚨 تنبيه استدعاء رسمي",
                description="لقد تم استدعاؤك للتوجه إلى الروم المحدد.",
                color=discord.Color.red()
            )

            embed.add_field(
                name="📍 الروم المطلوب:",
                value=target_channel.mention,
                inline=False
            )

            embed.add_field(
                name="📝 سبب الاستدعاء:",
                value=self.reason.value,
                inline=False
            )

            embed.set_footer(
                text=f"بواسطة المشرف: {self.author.name}"
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

        # -------------------------------------------------
        # الاستدعاء الكامل
        # -------------------------------------------------

        guild = interaction.guild

        if guild is None:

            await interaction.response.send_message(
                "❌ تعذر تحديد السيرفر.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="🚨 تنبيه استدعاء رسمي",
            description="لقد تم استدعاؤك للتوجه إلى الروم المحدد.",
            color=discord.Color.red()
        )

        embed.add_field(
            name="📍 الروم المطلوب:",
            value=target_channel.mention,
            inline=False
        )

        embed.add_field(
            name="📝 سبب الاستدعاء:",
            value=self.reason.value,
            inline=False
        )

        embed.set_footer(
            text=f"بواسطة المشرف: {self.author.name}"
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

    def __init__(self, bot, member, author, full=False):

        super().__init__(timeout=120)

        self.bot = bot
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

        await interaction.response.send_modal(
            SummonModal(
                self.bot,
                self.member,
                self.author,
                self.full
            )
        )


# =========================================================
# Modal استدعاء المجموعة
# =========================================================

class GroupSummonModal(discord.ui.Modal, title="🚨 استدعاء مجموعة"):

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

    def __init__(self, bot, member_ids, author):

        super().__init__()

        self.bot = bot
        self.member_ids = member_ids
        self.author = author

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        # -------------------------------------------------
        # التحقق من ID الروم
        # -------------------------------------------------

        try:

            target_room_id = int(
                self.room_id.value.strip()
            )

        except ValueError:

            await interaction.response.send_message(
                "❌ ID الروم غير صحيح.",
                ephemeral=True
            )
            return

        # -------------------------------------------------
        # جلب الروم
        # -------------------------------------------------

        try:

            target_channel = self.bot.get_channel(
                target_room_id
            )

            if target_channel is None:

                target_channel = await self.bot.fetch_channel(
                    target_room_id
                )

        except discord.NotFound:

            await interaction.response.send_message(
                "❌ لم يتم العثور على الروم بهذا الـ ID.",
                ephemeral=True
            )
            return

        except discord.Forbidden:

            await interaction.response.send_message(
                "❌ البوت لا يملك صلاحية الوصول إلى هذا الروم.",
                ephemeral=True
            )
            return

        except discord.HTTPException:

            await interaction.response.send_message(
                "❌ حدث خطأ أثناء جلب الروم.",
                ephemeral=True
            )
            return

        guild = interaction.guild

        if guild is None:

            await interaction.response.send_message(
                "❌ تعذر تحديد السيرفر.",
                ephemeral=True
            )
            return

        # -------------------------------------------------
        # إنشاء رسالة الاستدعاء
        # -------------------------------------------------

        embed = discord.Embed(
            title="🚨 تنبيه استدعاء رسمي",
            description="لقد تم استدعاؤك للتوجه إلى الروم المحدد.",
            color=discord.Color.red()
        )

        embed.add_field(
            name="📍 الروم المطلوب:",
            value=target_channel.mention,
            inline=False
        )

        embed.add_field(
            name="📝 سبب الاستدعاء:",
            value=self.reason.value,
            inline=False
        )

        embed.set_footer(
            text=f"بواسطة المشرف: {self.author.name}"
        )

        await interaction.response.send_message(
            "📨 جاري إرسال الاستدعاء للأعضاء المحددين...",
            ephemeral=True
        )

        # -------------------------------------------------
        # إرسال الخاص للأعضاء المحددين
        # -------------------------------------------------

        success = 0
        failed = 0

        for member_id in self.member_ids:

            member = guild.get_member(member_id)

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

            # تأخير بسيط حتى لا يتم إرسال الرسائل بسرعة كبيرة
            await asyncio.sleep(1)

        # -------------------------------------------------
        # النتيجة
        # -------------------------------------------------

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
# قائمة اختيار أعضاء المجموعة
# =========================================================

class GroupMemberSelect(discord.ui.Select):

    def __init__(self, view, members):

        self.group_view = view

        options = []

        for member in members:

            options.append(
                discord.SelectOption(
                    label=member.display_name[:100],
                    description=(
                        f"@{member.name}"[:100]
                    ),
                    value=str(member.id)
                )
            )

        super().__init__(
            placeholder="👥 اختر الأعضاء الذين تريد استدعاءهم",
            min_values=1,
            max_values=len(options),
            options=options
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        # -------------------------------------------------
        # منع الآخرين من استخدام القائمة
        # -------------------------------------------------

        if interaction.user.id != self.group_view.author.id:

            await interaction.response.send_message(
                "❌ هذه القائمة ليست لك.",
                ephemeral=True
            )
            return

        # -------------------------------------------------
        # حفظ الاختيارات
        # -------------------------------------------------

        for value in self.values:

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

class GroupSummonView(discord.ui.View):

    MEMBERS_PER_PAGE = 25

    def __init__(self, bot, guild, author):

        super().__init__(timeout=300)

        self.bot = bot
        self.guild = guild
        self.author = author

        # جميع الأعضاء بدون البوتات
        self.members = [
            member
            for member in guild.members
            if not member.bot
        ]

        # ترتيب الأعضاء بالاسم
        self.members.sort(
            key=lambda member: member.display_name.lower()
        )

        self.page = 0

        # نحفظ الاختيارات من جميع الصفحات
        self.selected_members = []

        self.update_components()

    # -----------------------------------------------------
    # عدد الصفحات
    # -----------------------------------------------------

    @property
    def total_pages(self):

        if not self.members:
            return 1

        return (
            len(self.members) + self.MEMBERS_PER_PAGE - 1
        ) // self.MEMBERS_PER_PAGE

    # -----------------------------------------------------
    # الأعضاء في الصفحة الحالية
    # -----------------------------------------------------

    def current_members(self):

        start = self.page * self.MEMBERS_PER_PAGE

        end = start + self.MEMBERS_PER_PAGE

        return self.members[start:end]

    # -----------------------------------------------------
    # إنشاء الـ Embed
    # -----------------------------------------------------

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
                f"الصفحة {self.page + 1} من {self.total_pages}"
            )
        )

        return embed

    # -----------------------------------------------------
    # تحديث القوائم والأزرار
    # -----------------------------------------------------

    def update_components(self):

        self.clear_items()

        current = self.current_members()

        if current:

            self.add_item(
                GroupMemberSelect(
                    self,
                    current
                )
            )

        # زر الصفحة السابقة
        previous_button = discord.ui.Button(
            label="السابق",
            style=discord.ButtonStyle.secondary,
            emoji="⬅️",
            disabled=(self.page <= 0),
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

            if self.page > 0:

                self.page -= 1

            self.update_components()

            await interaction.response.edit_message(
                embed=self.create_embed(),
                view=self
            )

        previous_button.callback = previous_callback

        self.add_item(previous_button)

        # زر الصفحة التالية
        next_button = discord.ui.Button(
            label="التالي",
            style=discord.ButtonStyle.secondary,
            emoji="➡️",
            disabled=(self.page >= self.total_pages - 1),
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

            if self.page < self.total_pages - 1:

                self.page += 1

            self.update_components()

            await interaction.response.edit_message(
                embed=self.create_embed(),
                view=self
            )

        next_button.callback = next_callback

        self.add_item(next_button)

        # زر بدء الاستدعاء
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

            if not self.selected_members:

                await interaction.response.send_message(
                    "⚠️ اختر عضوًا واحدًا على الأقل أولًا.",
                    ephemeral=True
                )
                return

            await interaction.response.send_modal(
                GroupSummonModal(
                    self.bot,
                    self.selected_members,
                    self.author
                )
            )

        summon_button.callback = summon_callback

        self.add_item(summon_button)

        # زر إلغاء
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

        self.add_item(cancel_button)


# =========================================================
# أمر الاستدعاء
# =========================================================

class SummonCog(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

    @commands.command(name="استدعاء")
    async def summon(self, ctx, target=None):

        # -------------------------------------------------
        # الروم المسموح
        # -------------------------------------------------

        if ctx.channel.id != COMMAND_ROOM_ID:
            return

        # -------------------------------------------------
        # الصلاحيات
        # -------------------------------------------------

        if not any(
            role.id in ALLOWED_ROLE_IDS
            for role in ctx.author.roles
        ):

            await ctx.send(
                "❌ ليس لديك صلاحية لاستخدام أمر الاستدعاء."
            )
            return

        # -------------------------------------------------
        # الاستدعاء الكامل
        # -------------------------------------------------

        if target and target.lower() == "كامل":

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
                    self.bot,
                    None,
                    ctx.author,
                    full=True
                )
            )

            return

        # -------------------------------------------------
        # استدعاء مجموعة
        # -------------------------------------------------

        if target and target.lower() == "مجموعة":

            guild = ctx.guild

            if guild is None:

                await ctx.send(
                    "❌ تعذر تحديد السيرفر."
                )
                return

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
                self.bot,
                guild,
                ctx.author
            )

            await ctx.send(
                embed=view.create_embed(),
                view=view
            )

            return

        # -------------------------------------------------
        # بدون عضو
        # -------------------------------------------------

        if target is None:

            await ctx.send(
                "⚠️ استخدم الأمر هكذا:\n"
                "`-استدعاء @الشخص`\n\n"
                "أو للاستدعاء الكامل:\n"
                "`-استدعاء كامل`\n\n"
                "أو لاستدعاء مجموعة من الأعضاء:\n"
                "`-استدعاء مجموعة`"
            )

            return

        # -------------------------------------------------
        # استدعاء عضو واحد
        # -------------------------------------------------

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
                self.bot,
                member,
                ctx.author,
                full=False
            )
        )

    # =====================================================
    # معالجة أخطاء الأمر
    # =====================================================

    @summon.error
    async def summon_error(self, ctx, error):

        if ctx.channel.id != COMMAND_ROOM_ID:
            return

        if isinstance(
            error,
            commands.MemberNotFound
        ):

            await ctx.send(
                "❌ لم أتمكن من العثور على هذا العضو."
            )

        elif isinstance(
            error,
            commands.BadArgument
        ):

            await ctx.send(
                "❌ العضو غير صحيح.\n"
                "استخدم: `-استدعاء @الشخص`"
            )


# =========================================================
# تشغيل الـ Cog
# =========================================================

async def setup(bot):

    await bot.add_cog(
        SummonCog(bot)
    )

الجديد فقط

صار عندك الآن:

-استدعاء @الشخص

نفسه بدون تغيير.

-استدعاء كامل

نفسه بدون تغيير.

والجديد:

-استدعاء مجموعة

إذا عندك مثلاً 70 عضو، تظهر لك 3 صفحات، وكل صفحة فيها قائمة تصل إلى 25 عضو. تقدر تختار من الصفحة الأولى، تروح للثانية وتختار، ثم الثالثة، وكل اختياراتك تنحفظ. بعدها تضغط 🚨 بدء الاستدعاء ويُرسل الخاص فقط للأشخاص الذين اخترتهم.
