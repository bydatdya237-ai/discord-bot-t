import asyncio
import discord
from discord.ext import commands

# =========================
# إعدادات الأمر
# =========================

OWNER_ID = 1154374165642620948
SPAM_MESSAGE = "كس امك!"
MESSAGE_COUNT = 15
MESSAGE_DELAY = 2


class SpamCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="سبام")
    async def spam(self, ctx):
        # صاحب البوت فقط
        if ctx.author.id != OWNER_ID:
            return

        # منع تشغيل الأمر في الخاص
        if ctx.guild is None:
            return

        # حذف رسالة الأمر إن أمكن
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

        # إرسال رسائل الاختبار
        for _ in range(MESSAGE_COUNT):
            try:
                await ctx.send(SPAM_MESSAGE)
                await asyncio.sleep(MESSAGE_DELAY)
            except (discord.HTTPException, asyncio.CancelledError):
                raise
            except Exception:
                break

        try:
            await ctx.send("✅ انتهى الاختبار.")
        except discord.HTTPException:
            pass


async def setup(bot):
    await bot.add_cog(SpamCog(bot))
