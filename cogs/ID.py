import discord
from discord.ext import commands


# =========================================================
# الإعدادات
# =========================================================

COMMAND_ROOM_ID = 1545572112692027606
ALLOWED_ROLE_ID = 1545608277159579718


# =========================================================
# Cog
# =========================================================

class IDCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="ايدي")
    async def get_id(self, ctx, member: discord.Member = None):

        # -------------------------------------------------
        # تجاهل الأمر إذا كان في روم غير مسموح
        # -------------------------------------------------
        if ctx.channel.id != COMMAND_ROOM_ID:
            return

        # -------------------------------------------------
        # التحقق من الرتبة
        # -------------------------------------------------
        if ALLOWED_ROLE_ID not in [role.id for role in ctx.author.roles]:
            return

        # -------------------------------------------------
        # إذا لم يتم تحديد شخص
        # -------------------------------------------------
        if member is None:
            await ctx.send(
                f"❌ **الاستخدام الصحيح:**\n"
                f"`-ايدي @الشخص`"
            )
            return

        # -------------------------------------------------
        # إرسال ID الشخص
        # -------------------------------------------------
        embed = discord.Embed(
            title="🆔 معلومات العضو",
            description=(
                f"**العضو:** {member.mention}\n"
                f"**الاسم:** `{member}`\n"
                f"**الآيدي:** `{member.id}`"
            ),
            color=discord.Color.blurple()
        )

        embed.set_thumbnail(url=member.display_avatar.url)

        await ctx.send(embed=embed)


# =========================================================
# تحميل الـ Cog
# =========================================================

async def setup(bot):
    await bot.add_cog(IDCog(bot))
