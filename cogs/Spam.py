import asyncio
import discord
from discord.ext import commands


# =========================================================
# الإعدادات
# =========================================================

ALLOWED_ROLE_ID = 1544078469657530578

MESSAGE_COUNT = 5
MESSAGE_DELAY = 0.7


# =========================================================
# Cog
# =========================================================

class SpamCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.words = {}
        self.running = {}

    # -----------------------------------------------------
    # التحقق من الرتبة
    # -----------------------------------------------------

    def has_allowed_role(self, member: discord.Member):
        return any(role.id == ALLOWED_ROLE_ID for role in member.roles)

    # -----------------------------------------------------
    # تحديد الكلمة
    # -----------------------------------------------------

    @commands.command(name="كلمني-كلمة")
    async def set_word(self, ctx, *, word: str = None):

        if not isinstance(ctx.author, discord.Member):
            return

        if not self.has_allowed_role(ctx.author):
            return

        if not word:
            return

        self.words[ctx.author.id] = word

    # -----------------------------------------------------
    # بدء السبام
    # -----------------------------------------------------

    @commands.command(name="سبم-سبام")
    async def start_spam(self, ctx):

        if not isinstance(ctx.author, discord.Member):
            return

        if not self.has_allowed_role(ctx.author):
            return

        user_id = ctx.author.id

        # إذا كان هناك سبام شغال لهذا الشخص
        if self.running.get(user_id, False):
            return

        # إذا لم يحدد كلمة
        if user_id not in self.words:
            return

        self.running[user_id] = True

        try:
            word = self.words[user_id]

            for _ in range(MESSAGE_COUNT):

                # تم الضغط على وقفني
                if not self.running.get(user_id, False):
                    break

                await ctx.send(word)

                await asyncio.sleep(MESSAGE_DELAY)

        except (discord.Forbidden, discord.HTTPException):
            pass

        finally:
            self.running[user_id] = False

    # -----------------------------------------------------
    # إيقاف السبام
    # -----------------------------------------------------

    @commands.command(name="وقفني")
    async def stop_spam(self, ctx):

        if not isinstance(ctx.author, discord.Member):
            return

        if not self.has_allowed_role(ctx.author):
            return

        self.running[ctx.author.id] = False


async def setup(bot):
    await bot.add_cog(SpamCog(bot))
