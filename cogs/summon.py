import asyncio
import discord
from discord.ext import commands


# =========================================================
# الإعدادات
# =========================================================

# الروم الذي يسمح باستخدام أوامر الاستدعاء فيه فقط
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

    def __init__(self, bot, member=None, author=None, full=False):
        super().__init__()

        self.bot = bot
        self.member = member
        self.author = author
        self.full = full

    async def on_submit(self, interaction: discord.Interaction):

        # =====================================================
        # التأكد من ID الروم
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
        # الاستدعاء الفردي
        # =====================================================

        if not self.full:

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
                value=self.reason.value,
                inline=False
            )

            embed.set_footer(
                text=f"بواسطة المشرف: {self.author.name}"
            )

            try:
                await self.member.send(embed=embed)

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

        # =====================================================
        # الاستدعاء الكامل للسيرفر
        # =====================================================

        guild = interaction.guild

        if guild is None:
            await interaction.response.send_message(
                "❌ تعذر تحديد السيرفر.",
                ephemeral=True
            )
            return

        # تجهيز رسالة الاستدعاء
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
            value=self.reason.value,
            inline=False
        )

        embed.set_footer(
            text=f"بواسطة المشرف: {self.author.name}"
        )

        # نؤكد للمشرف أن العملية بدأت
        await interaction.response.send_message(
            "📨 جاري إرسال الاستدعاء لأعضاء السيرفر...",
            ephemeral=True
        )

        success = 0
        failed = 0

        # =====================================================
        # إرسال الرسالة للأعضاء
        # =====================================================

        for member in guild.members:

            # عدم إرسالها للبوتات
            if member.bot:
                continue

            try:
                await member.send(embed=embed)
                success += 1

            except (
                discord.Forbidden,
                discord.HTTPException,
                discord.NotFound
            ):
                failed += 1

            # تأخير بسيط لتقليل مشاكل Rate Limit
            await asyncio.sleep(1)

        # =====================================================
        # النتيجة
        # =====================================================

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
# زر الاستدعاء
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

        # الزر لصاحب الأمر فقط
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
                self.author,
                self.full
            )
        )


# =========================================================
# أمر الاستدعاء
# =========================================================

class SummonCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="استدعاء")
    async def summon(self, ctx, target=None):

        # =====================================================
        # إذا كان الأمر في روم آخر:
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
        # الاستدعاء الكامل
        # =====================================================

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

        # =====================================================
        # التأكد من وجود عضو للاستدعاء الفردي
        # =====================================================

        if target is None:
            await ctx.send(
                "⚠️ استخدم الأمر هكذا:\n"
                "`-استدعاء @الشخص`\n\n"
                "أو للاستدعاء الكامل:\n"
                "`-استدعاء كامل`"
            )
            return

        # =====================================================
        # Discord يحول المنشن إلى Member إذا كان صحيحًا
        # =====================================================

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

        # =====================================================
        # الاستدعاء الفردي
        # =====================================================

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

    # =========================================================
    # أخطاء الأمر
    # =========================================================

    @summon.error
    async def summon_error(self, ctx, error):

        # في روم آخر لا يوجد أي رد
        if ctx.channel.id != COMMAND_ROOM_ID:
            return

        if isinstance(error, commands.MemberNotFound):
            await ctx.send(
                "❌ لم أتمكن من العثور على هذا العضو."
            )

        elif isinstance(error, commands.BadArgument):
            await ctx.send(
                "❌ العضو غير صحيح.\n"
                "استخدم: `-استدعاء @الشخص`"
            )


# =========================================================
# تشغيل الـ Cog
# =========================================================

async def setup(bot):
    await bot.add_cog(SummonCog(bot))
