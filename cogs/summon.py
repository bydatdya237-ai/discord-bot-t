import discord
from discord.ext import commands


# =========================================================
# الإعدادات
# =========================================================

# الروم الذي يسمح باستخدام أمر الاستدعاء فيه فقط
COMMAND_ROOM_ID = 1546860236227215400

# الرتب الثلاث المسموح لها باستخدام الأمر
ALLOWED_ROLE_IDS = {
    1544078469657530578,
    1545851911121666108,
    1544426415766896690
}


# =========================================================
# المربع الذي يحتوي ID الروم + سبب الاستدعاء
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

    def __init__(self, bot, member, author):
        super().__init__()

        self.bot = bot
        self.member = member
        self.author = author

    async def on_submit(self, interaction: discord.Interaction):

        # =====================================================
        # التأكد من أن ID الروم صحيح
        # =====================================================

        try:
            target_room_id = int(self.room_id.value.strip())

        except ValueError:
            await interaction.response.send_message(
                "❌ ID الروم غير صحيح.",
                ephemeral=True
            )
            return

        # =====================================================
        # جلب الروم
        # =====================================================

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

        # =====================================================
        # تجهيز رسالة الاستدعاء
        # =====================================================

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

        # =====================================================
        # إرسال الاستدعاء في الخاص
        # =====================================================

        try:
            await self.member.send(embed=embed)

            dm_status = "✉️ تم إرسال رسالة الاستدعاء له."

        except discord.Forbidden:
            dm_status = "⚠️ تعذر إرسال رسالة خاصة له."

        except discord.HTTPException:
            dm_status = "⚠️ حدث خطأ أثناء إرسال الرسالة الخاصة."

        # =====================================================
        # تأكيد العملية للمشرف
        # =====================================================

        await interaction.response.send_message(
            f"✅ تم استدعاء {self.member.mention} بنجاح إلى "
            f"{target_channel.mention}\n"
            f"{dm_status}",
            ephemeral=True
        )


# =========================================================
# الزر الذي يفتح المربع
# =========================================================

class SummonView(discord.ui.View):

    def __init__(self, bot, member, author):
        super().__init__(timeout=120)

        self.bot = bot
        self.member = member
        self.author = author

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

        # التأكد أن الشخص الذي ضغط الزر هو نفس الشخص الذي استخدم الأمر
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                "❌ هذا الزر ليس لك.",
                ephemeral=True
            )
            return

        # فتح المربع
        await interaction.response.send_modal(
            SummonModal(
                self.bot,
                self.member,
                self.author
            )
        )


# =========================================================
# أمر الاستدعاء
# =========================================================

class SummonCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="استدعاء")
    async def summon(
        self,
        ctx,
        member: discord.Member
    ):

        # =====================================================
        # إذا استخدم الأمر في روم آخر:
        # البوت لا يرد نهائيًا
        # =====================================================

        if ctx.channel.id != COMMAND_ROOM_ID:
            return

        # =====================================================
        # التأكد من الرتب الثلاث
        # =====================================================

        if not any(
            role.id in ALLOWED_ROLE_IDS
            for role in ctx.author.roles
        ):
            await ctx.send(
                "❌ ليس لديك صلاحية لاستخدام أمر الاستدعاء."
            )
            return

        # =====================================================
        # إرسال زر بدء الاستدعاء
        # =====================================================

        embed = discord.Embed(
            title="🚨 استدعاء عضو",
            description=(
                f"تم اختيار العضو: {member.mention}\n\n"
                "اضغط على الزر بالأسفل لإدخال **ID الروم** "
                "و**سبب الاستدعاء**."
            ),
            color=discord.Color.red()
        )

        await ctx.send(
            embed=embed,
            view=SummonView(
                self.bot,
                member,
                ctx.author
            )
        )

    # =========================================================
    # أخطاء الأمر
    # =========================================================

    @summon.error
    async def summon_error(self, ctx, error):

        # إذا كان الأمر في روم غير مسموح:
        # لا يرد البوت نهائيًا
        if ctx.channel.id != COMMAND_ROOM_ID:
            return

        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(
                "⚠️ استخدم الأمر هكذا:\n"
                "`-استدعاء @الشخص`"
            )

        elif isinstance(error, commands.MemberNotFound):
            await ctx.send(
                "❌ لم أتمكن من العثور على هذا العضو."
            )


# =========================================================
# تشغيل الـ Cog
# =========================================================

async def setup(bot):
    await bot.add_cog(SummonCog(bot))
