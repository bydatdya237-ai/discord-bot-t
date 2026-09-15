import asyncio
import discord
from discord.ext import commands


# =========================================================
# الإعدادات
# =========================================================

COMMAND_ROOM_ID = 1546099690968457237

ALLOWED_ROLE_ID = 1544078469657530578


# =========================================================
# Cog
# =========================================================

class TestCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    # =====================================================
    # مراقبة طريقة كتابة الأمر
    # =====================================================

    @commands.Cog.listener()
    async def on_message(self, message):

        # تجاهل البوتات
        if message.author.bot:
            return

        # فقط الروم المحدد
        if message.channel.id != COMMAND_ROOM_ID:
            return

        # فقط صاحب الرتبة المحددة
        if not any(role.id == ALLOWED_ROLE_ID for role in message.author.roles):
            return

        content = message.content.strip()

        # إذا بدأ بـ -تسفير لكنه ليس الأمر الصحيح
        if content.startswith("-تسفير") and content != "-تسفير-الكل":

            await message.channel.send(
                "❌ **غلط، طريقة الاستخدام:**\n"
                "`-تسفير-الكل`"
            )

            return

        # السماح لباقي أوامر البوت بالعمل
        await self.bot.process_commands(message)

    # =====================================================
    # أمر تسفير الكل
    # =====================================================

    @commands.command(name="تسفير-الكل")
    async def tasfeer_all(self, ctx):

        # يعمل فقط في الروم المحدد
        if ctx.channel.id != COMMAND_ROOM_ID:
            return

        # يعمل فقط مع الرتبة المحددة
        if not any(role.id == ALLOWED_ROLE_ID for role in ctx.author.roles):
            return

        # -------------------------------------------------
        # رسالة البداية
        # -------------------------------------------------

        message = await ctx.send(
            "🚨 **جاري الآن عملية تسفير الكل...**\n\n"
            "⏳ **30**"
        )

        # -------------------------------------------------
        # العد التنازلي 30 → 1
        # -------------------------------------------------

        for number in range(29, 0, -1):

            await asyncio.sleep(1)

            await message.edit(
                content=(
                    "🚨 **جاري الآن عملية تسفير الكل...**\n\n"
                    f"⏳ **{number}**"
                )
            )

        # -------------------------------------------------
        # المقلب 😂
        # -------------------------------------------------

        await asyncio.sleep(1)

        await message.edit(
            content=(
                "😂 **هههههههههههههههههههههههههههههه**\n\n"
                "## ياهطف صدقت 🤣🤣🤣\n\n"
                "ولا واحد انحظر يا وحش 😂❤️"
            )
        )


# =========================================================
# Setup
# =========================================================

async def setup(bot):
    await bot.add_cog(TestCog(bot))
