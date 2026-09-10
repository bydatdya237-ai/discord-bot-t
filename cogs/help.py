import discord
from discord.ext import commands


# =========================================================
# الإعدادات
# =========================================================

# الروم الوحيد المسموح فيه استخدام -اوامر
COMMAND_ROOM_ID = 1547711993568305232

# الرتب المسموح لها باستخدام الأمر
ALLOWED_ROLE_IDS = {
    1544078469657530578,
    1544426415766896690,
    1545851911121666108
}


# =========================================================
# التحقق من الرتبة
# =========================================================

def has_allowed_role(member: discord.Member) -> bool:
    return any(
        role.id in ALLOWED_ROLE_IDS
        for role in member.roles
    )


# =========================================================
# Cog
# =========================================================

class CommandsListCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    # =====================================================
    # أمر -اوامر
    # =====================================================

    @commands.command(name="اوامر")
    async def commands_list(self, ctx):

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
        # الحصول على جميع أوامر البوت تلقائياً
        # -------------------------------------------------

        commands_list = []

        for command in self.bot.commands:

            # تجاهل الأمر نفسه
            if command.name == "اوامر":
                continue

            # تجاهل الأوامر المخفية
            if command.hidden:
                continue

            # -------------------------------------------------
            # الحصول على الـ aliases إن وجدت
            # -------------------------------------------------

            command_text = f"`-{command.name}`"

            if command.aliases:
                aliases = " ".join(
                    f"`-{alias}`"
                    for alias in command.aliases
                )

                command_text += f"\n↳ البدائل: {aliases}"

            commands_list.append(command_text)

        # -------------------------------------------------
        # إذا لم توجد أوامر
        # -------------------------------------------------

        if not commands_list:
            await ctx.send(
                "📭 لا توجد أوامر متاحة حالياً.",
                delete_after=10
            )
            return

        # -------------------------------------------------
        # ترتيب الأوامر أبجدياً
        # -------------------------------------------------

        commands_list.sort()

        # -------------------------------------------------
        # تقسيم القائمة إذا كانت طويلة
        # Discord يسمح بحد أقصى 4096 حرف للـ description
        # -------------------------------------------------

        chunks = []
        current_chunk = ""

        for command_text in commands_list:

            if len(current_chunk) + len(command_text) + 2 > 3900:

                chunks.append(current_chunk)
                current_chunk = ""

            current_chunk += command_text + "\n\n"

        if current_chunk:
            chunks.append(current_chunk)

        # -------------------------------------------------
        # إرسال القائمة
        # -------------------------------------------------

        for index, chunk in enumerate(chunks):

            embed = discord.Embed(
                title="📚 أوامر البوت",
                description=chunk,
                color=discord.Color.gold()
            )

            if index == 0:
                embed.set_footer(
                    text=f"عدد الأوامر: {len(commands_list)}"
                )

            await ctx.send(embed=embed)

        # -------------------------------------------------
        # حذف رسالة -اوامر
        # -------------------------------------------------

        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass


# =========================================================
# Setup
# =========================================================

async def setup(bot):
    await bot.add_cog(CommandsListCog(bot))
