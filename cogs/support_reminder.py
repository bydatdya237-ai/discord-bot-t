import asyncio
import discord
from discord.ext import commands


# =========================================================
# SETTINGS
# =========================================================

# الروم الذي يراقبه البوت فقط
TARGET_CHANNEL_ID = 1555381169154039828

# روم التكتات
TICKET_CHANNEL_ID = 1555369541503025273

# الانتظار بعد آخر رسالة
WAIT_SECONDS = 30


# =========================================================
# MESSAGE
# =========================================================

REMINDER_MESSAGE = (
    "يرجى كتابة مشكلتك أو استفسارك مرة واحدة فقط وإنتظار الرد من الإدارة\n"
    f"وفي حال كانت المشكلة طويلة أو تحتاج إلى شرح مفصل، توجه للتكت من <#{TICKET_CHANNEL_ID}>"
)


# =========================================================
# COG
# =========================================================

class SupportReminder(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.pending_tasks = {}

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):

        # تجاهل البوتات
        if message.author.bot:
            return

        # العمل في الروم المحدد فقط
        if message.channel.id != TARGET_CHANNEL_ID:
            return

        user_id = message.author.id

        # إلغاء المؤقت السابق إذا أرسل الشخص رسالة جديدة
        old_task = self.pending_tasks.get(user_id)

        if old_task and not old_task.done():
            old_task.cancel()

        # بدء مؤقت جديد من آخر رسالة
        task = asyncio.create_task(
            self.send_reminder_after_delay(
                message.channel,
                user_id
            )
        )

        self.pending_tasks[user_id] = task

    async def send_reminder_after_delay(
        self,
        channel: discord.TextChannel,
        user_id: int
    ):

        try:
            # انتظار 30 ثواني من آخر رسالة
            await asyncio.sleep(WAIT_SECONDS)

            # إرسال الرسالة بدون منشن
            await channel.send(REMINDER_MESSAGE)

        except asyncio.CancelledError:
            # تم إرسال رسالة جديدة قبل انتهاء الـ30 ثواني
            pass

        finally:
            # تنظيف المؤقت
            current_task = self.pending_tasks.get(user_id)

            if current_task is asyncio.current_task():
                self.pending_tasks.pop(user_id, None)


# =========================================================
# SETUP
# =========================================================

async def setup(bot):
    await bot.add_cog(SupportReminder(bot))

الآن الرسالة تطلع بدون منشن نهائيًا، وبعد 10 ثوانٍ من آخر رسالة للشخص.
