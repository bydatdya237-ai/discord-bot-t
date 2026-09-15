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
        self.running = set()

    # =====================================================
    # استقبال الرسائل
    # =====================================================

    @commands.Cog.listener()
    async def on_message(self, message):

        # تجاهل البوتات
        if message.author.bot:
            return

        # يعمل فقط في الروم المحدد
        if message.channel.id != COMMAND_ROOM_ID:
            return

        # التحقق من الرتبة
        if not any(
            role.id == ALLOWED_ROLE_ID
            for role in message.author.roles
        ):
            return

        content = message.content.strip()

        # =================================================
        # طريقة الاستخدام الخاطئة
        # =================================================

        if content.startswith("-تسفير") and content != "-تسفير-الكل":

            await message.channel.send(
                "❌ **غلط، طريقة الاستخدام:**\n"
                "`-تسفير-الكل`"
            )

            return

        # =================================================
        # الأمر الصحيح
        # =================================================

        if content != "-تسفير-الكل":
            return

        # منع تشغيل أكثر من عد تنازلي لنفس الشخص
        if message.author.id in self.running:
            return

        self.running.add(message.author.id)

        try:

            # =================================================
            # بداية المقلب
            # =================================================

            countdown_message = await message.channel.send(
                "🚨 **جاري الآن عملية تسفير الكل...**\n\n"
                "⏳ **30**"
            )

            # =================================================
            # العد التنازلي
            # 30 → 29 → 28 → ... → 1
            # =================================================

            for number in range(29, 0, -1):

                await asyncio.sleep(1)

                await countdown_message.edit(
                    content=(
                        "🚨 **جاري الآن عملية تسفير الكل...**\n\n"
                        f"⏳ **{number}**"
                    )
                )

            # =================================================
            # بعد الوصول إلى 1
            # =================================================

            await asyncio.sleep(1)

            await countdown_message.edit(
                content=(
                    "😂 **هههههههههههههههههههههههههههههه**\n\n"
                    "## ياهطف صدقت 🤣🤣🤣\n\n"
                    "ولا واحد انحظر يا وحش 😂❤️"
                )
            )

        finally:

            self.running.discard(message.author.id)


# =========================================================
# Setup
# =========================================================

async def setup(bot):
    await bot.add_cog(TestCog(bot))
