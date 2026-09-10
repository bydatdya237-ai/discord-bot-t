import discord
from discord.ext import commands
from discord import ui


# =========================================================
# الإعدادات
# =========================================================

# الروم الوحيد الذي يعمل فيه أمر -طلب
COMMAND_ROOM_ID = 1546948315478888448

# الروم الذي تصل إليه الطلبات
LOG_CHANNEL_ID = 1545187326093693038

# الرتب المسموح لها باستخدام الأمر والتحكم بالطلبات
ALLOWED_ROLE_IDS = {
    1544078469657530578,
    1545851911121666108
}


# =========================================================
# التحقق من الرتبة
# =========================================================

def has_allowed_role(member: discord.Member) -> bool:
    return any(role.id in ALLOWED_ROLE_IDS for role in member.roles)


# =========================================================
# قائمة اختيار نوع الطلب
# =========================================================

class OrderSelect(ui.Select):

    def __init__(self, target_user: discord.Member):
        self.target_user = target_user

        options = [
            discord.SelectOption(
                label="رفع طلب عملة",
                description="رفع طلب خاص بالعملة",
                emoji="💰"
            ),
            discord.SelectOption(
                label="رفع طلب رتبة",
                description="رفع طلب خاص بالرتبة",
                emoji="👑"
            ),
            discord.SelectOption(
                label="رفع طلب بنك",
                description="رفع طلب خاص بالبنك",
                emoji="🏦"
            ),
        ]

        super().__init__(
            placeholder="اختر نوع الطلب...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):

        modal = OrderModal(
            order_type=self.values[0],
            target_user=self.target_user
        )

        await interaction.response.send_modal(modal)


class OrderSelectView(ui.View):

    def __init__(self, target_user: discord.Member):
        super().__init__(timeout=300)

        self.add_item(OrderSelect(target_user))


# =========================================================
# نافذة كتابة السبب
# =========================================================

class OrderModal(ui.Modal, title="تقديم طلب جديد"):

    def __init__(
        self,
        order_type: str,
        target_user: discord.Member
    ):
        super().__init__()

        self.order_type = order_type
        self.target_user = target_user

        self.reason_input = ui.TextInput(
            label="السبب / التفاصيل",
            style=discord.TextStyle.paragraph,
            placeholder="اكتب تفاصيل أو سبب طلبك هنا...",
            required=True,
            max_length=1000
        )

        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):

        log_channel = interaction.guild.get_channel(LOG_CHANNEL_ID)

        if not log_channel:
            await interaction.response.send_message(
                "❌ عذراً، روم سجل الطلبات غير موجود.",
                ephemeral=True
            )
            return

        # =================================================
        # إنشاء الطلب
        # =================================================

        embed = discord.Embed(
            title="📋 طلب جديد",
            color=discord.Color.gold()
        )

        embed.add_field(
            name="نوع الطلب",
            value=self.order_type,
            inline=False
        )

        embed.add_field(
            name="العضو المطلوب له الطلب",
            value=self.target_user.mention,
            inline=True
        )

        embed.add_field(
            name="ايدي العضو",
            value=str(self.target_user.id),
            inline=True
        )

        embed.add_field(
            name="السبب",
            value=self.reason_input.value,
            inline=False
        )

        embed.add_field(
            name="مقدم الطلب",
            value=interaction.user.mention,
            inline=False
        )

        embed.add_field(
            name="حالة الطلب",
            value="⏳ قيد المراجعة",
            inline=False
        )

        await log_channel.send(
            embed=embed,
            view=OrderActionView()
        )

        await interaction.response.send_message(
            f"✅ تم إرسال الطلب بنجاح للعضو {self.target_user.mention}",
            ephemeral=True
        )


# =========================================================
# أزرار التحكم بالطلب
# =========================================================

class OrderActionView(ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    # =====================================================
    # تم التسليم
    # =====================================================

    @ui.button(
        label="تم التسليم",
        style=discord.ButtonStyle.green,
        emoji="✅"
    )
    async def accept_order(
        self,
        interaction: discord.Interaction,
        button: ui.Button
    ):

        if not isinstance(interaction.user, discord.Member):
            return

        if not has_allowed_role(interaction.user):
            await interaction.response.send_message(
                "❌ ليس لديك صلاحية للتحكم بالطلبات!",
                ephemeral=True
            )
            return

        embed = interaction.message.embeds[0]

        embed.color = discord.Color.green()

        for i, field in enumerate(embed.fields):

            if field.name == "حالة الطلب":

                embed.set_field_at(
                    i,
                    name="حالة الطلب",
                    value="✅ تم التسليم",
                    inline=False
                )

        await interaction.message.edit(
            embed=embed,
            view=None
        )

        await interaction.response.send_message(
            f"✅ تم قبول الطلب بواسطة {interaction.user.mention}",
            ephemeral=True
        )

    # =====================================================
    # لم يتم التسليم
    # =====================================================

    @ui.button(
        label="لم يتم التسليم",
        style=discord.ButtonStyle.red,
        emoji="❌"
    )
    async def reject_order(
        self,
        interaction: discord.Interaction,
        button: ui.Button
    ):

        if not isinstance(interaction.user, discord.Member):
            return

        if not has_allowed_role(interaction.user):
            await interaction.response.send_message(
                "❌ ليس لديك صلاحية للتحكم بالطلبات!",
                ephemeral=True
            )
            return

        embed = interaction.message.embeds[0]

        embed.color = discord.Color.red()

        for i, field in enumerate(embed.fields):

            if field.name == "حالة الطلب":

                embed.set_field_at(
                    i,
                    name="حالة الطلب",
                    value="❌ لم يتم التسليم",
                    inline=False
                )

        await interaction.message.edit(
            embed=embed,
            view=None
        )

        await interaction.response.send_message(
            f"❌ تم رفض الطلب بواسطة {interaction.user.mention}",
            ephemeral=True
        )


# =========================================================
# Cog
# =========================================================

class OrdersCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    # =====================================================
    # أمر -طلب
    # =====================================================

    @commands.command(name="طلب")
    async def order_cmd(
        self,
        ctx,
        member: discord.Member = None
    ):

        # -------------------------------------------------
        # الروم المسموح فقط
        # -------------------------------------------------

        if ctx.channel.id != COMMAND_ROOM_ID:
            return

        # -------------------------------------------------
        # التحقق من الرتبة
        # -------------------------------------------------

        if not isinstance(ctx.author, discord.Member):
            return

        if not has_allowed_role(ctx.author):
            return

        # -------------------------------------------------
        # إذا لم يتم تحديد شخص
        # -------------------------------------------------

        if member is None:

            await ctx.send(
                "❌ **خطأ في الاستخدام**\n"
                "يجب تحديد العضو المطلوب بالمنشن.\n\n"
                "📝 **مثال:**\n"
                "`-طلب @الشخص`",
                delete_after=10
            )

            # حذف رسالة الأمر
            try:
                await ctx.message.delete()
            except discord.HTTPException:
                pass

            return

        # -------------------------------------------------
        # رسالة اختيار نوع الطلب
        # -------------------------------------------------

        embed = discord.Embed(
            title="📄 رفع طلب",
            description=(
                f"**العضو:** {member.mention}\n\n"
                "اختر نوع الطلب من القائمة بالأسفل."
            ),
            color=discord.Color.gold()
        )

        await ctx.send(
            embed=embed,
            view=OrderSelectView(member)
        )

        # -------------------------------------------------
        # حذف أمر -طلب @الشخص
        # -------------------------------------------------

        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass


# =========================================================
# Setup
# =========================================================

async def setup(bot):
    await bot.add_cog(OrdersCog(bot))
