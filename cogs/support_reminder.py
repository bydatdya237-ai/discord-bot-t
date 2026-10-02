import asyncio
import discord
from discord.ext import commands


# =========================================================
# SETTINGS
# =========================================================

TARGET_CHANNEL_ID = 1555381169154039828
TICKET_CHANNEL_ID = 1555369541503025273

# مدة الانتظار بعد آخر رسالة
WAIT_SECONDS = 30


# =========================================================
# COG
# =========================================================

class SupportReminder(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.pending_tasks = {}

    @commands.Cog.listener()
    async def on_message(self, message):

        # تجاهل رسائل البوتات
        if message.author.bot:
            return

        # يعمل في الروم المحدد فقط
        if message.channel.id != TARGET_CHANNEL_ID:
            return

        user_id = message.author.id

        # إلغاء المؤقت السابق إذا أرسل الشخص رسالة جديدة
        old_task = self.pending_tasks.get(user_id)

        if old_task and not old_task.done():
            old_task.cancel()

        # بدء مؤقت جديد
        task = asyncio.create_task(
            self.wait_then_send(message.channel, user_id)
        )

        self.pending_tasks[user_id] = task

    async def wait_then_send(self, channel, user_id):

        try:
            # الانتظار 30 ثانية من آخر رسالة
            await asyncio.sleep(WAIT_SECONDS)

            await channel.send(
                "يرجى كتابة مشكلتك أو استفسارك مرة واحدة فقط وإنتظار الرد من الإدارة\n"
                f"وفي حال كانت المشكلة طويلة أو تحتاج إلى شرح مفصل، توجه للتكت من <#{TICKET_CHANNEL_ID}>"
            )

        except asyncio.CancelledError:
            # تم إرسال رسالة جديدة، لذلك يتم إلغاء المؤقت القديم
            pass

        finally:
            # تنظيف المؤقت
            if self.pending_tasks.get(user_id) is asyncio.current_task():
                self.pending_tasks.pop(user_id, None)


# =========================================================
# SETUP
# =========================================================

async def setup(bot):
    await bot.add_cog(SupportReminder(bot))
