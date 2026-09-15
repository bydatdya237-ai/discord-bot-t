import asyncio
import discord
from discord.ext import commands


# =========================================================
# الإعدادات
# =========================================================

COMMAND_ROOM_ID = 1546099690968457237

ALLOWED_ROLE_IDS = {
    1544078469657530578,
}

COMMAND_NAME = "تسفير-الكل"


# =========================================================
# Cog
# =========================================================

class FakeBanAllCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.confirmations = {}

    # =====================================================
    # التحقق من الروم والرتبة
    # =====================================================

    def can_use(self, message):
        # إذا كان الأمر في روم غير مسموح:
        # لا نرد نهائيًا
        if message.channel.id != COMMAND_ROOM_ID:
            return False

        # التحقق من الرتبة
        if not any(role.id in ALLOWED_ROLE_IDS for role in message.author.roles):
            return False

        return True

    # =====================================================
    # الأمر
    # =====================================================

    @commands.command(name=COMMAND_NAME)
    async def fake_ban_all(self, ctx):

        # =================================================
        # مهم:
        # إذا كان الروم غلط أو الرتبة غلط، لا يرد البوت أبداً
        # =================================================

        if not self.can_use(ctx.message):
            return

        user_id = ctx.author.id

        # منع تشغيل أكثر من عملية لنفس الشخص
        if user_id in self.confirmations:
            return

        self.confirmations[user_id] = True

        try:

            # =================================================
            # التحذير الأول
            # =================================================

            embed1 = discord.Embed(
                title="⚠️ تحذير خطير",
                description=(
                    "**هذا الأمر سيحظر جميع المستخدمين في السيرفر!**\n\n"
                    "هل أنت متأكد أنك تريد المتابعة؟\n\n"
                    "✍️ اكتب `تم` للتأكيد."
                ),
                color=discord.Color.red()
            )

            await ctx.send(embed=embed1)

            # =================================================
            # انتظار التأكيد الأول
            # =================================================

            def check_first(message):
                return (
                    message.author.id == ctx.author.id
                    and message.channel.id == ctx.channel.id
                    and message.content.strip().lower() == "تم"
                )

            try:
                await self.bot.wait_for(
                    "message",
                    timeout=30,
                    check=check_first
                )

            except asyncio.TimeoutError:
                await ctx.send(
                    "⌛ **انتهى وقت التأكيد. تم إلغاء العملية.**"
                )
                return

            # =================================================
            # التحذير الثاني
            # =================================================

            embed2 = discord.Embed(
                title="🚨 تأكيد نهائي",
                description=(
                    "**أنت على وشك تنفيذ تسفير جميع المستخدمين!**\n\n"
                    "⚠️ هذا هو التأكيد الأخير.\n\n"
                    "إذا كنت متأكدًا، اكتب `تم` مرة ثانية."
                ),
                color=discord.Color.dark_red()
            )

            await ctx.send(embed=embed2)

            # =================================================
            # انتظار التأكيد الثاني
            # =================================================

            def check_second(message):
                return (
                    message.author.id == ctx.author.id
                    and message.channel.id == ctx.channel.id
                    and message.content.strip().lower() == "تم"
                )

            try:
                await self.bot.wait_for(
                    "message",
                    timeout=30,
                    check=check_second
                )

            except asyncio.TimeoutError:
                await ctx.send(
                    "⌛ **انتهى وقت التأكيد النهائي. تم إلغاء العملية.**"
                )
                return

            # =================================================
            # المقلب 😂
            # =================================================

            await asyncio.sleep(1)

            embed3 = discord.Embed(
                title="😂 HAHA!",
                description=(
                    "## ها صدقت ياهطف 😂😂😂\n\n"
                    "كنت مفكرني بسفّر السيرفر كله؟ 🤣\n\n"
                    "**ولا واحد انحظر يا وحش ❤️**"
                ),
                color=discord.Color.gold()
            )

            await ctx.send(embed=embed3)

        finally:
            # تنظيف حالة التأكيد
            self.confirmations.pop(user_id, None)


# =========================================================
# Setup
# =========================================================

async def setup(bot):
    await bot.add_cog(FakeBanAllCog(bot))
