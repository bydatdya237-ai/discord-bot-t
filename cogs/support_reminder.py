import asyncio
import discord
from discord.ext import commands


# =========================================================
# SETTINGS
# =========================================================

# الروم الذي يراقبه البوت
TARGET_CHANNEL_ID = 1555381169154039828

# روم التكتات
TICKET_CHANNEL_ID = 1555369541503025273

# مدة الانتظار بعد آخر رسالة
WAIT_SECONDS = 10


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

        # مؤقت منفصل لكل شخص
        self.pending_tasks = {}

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):

        # تجاهل البوتات
        if message.author.bot:
            return

        # تجاهل أي روم غير الروم المحدد
        if message.channel.id != TARGET_CHANNEL_ID:
            return

        user_id = message.author.id

        # إذا كان للشخص مؤقت سابق، نلغيه
        old_task = self.pending_tasks.get(user_id)

        if old_task and not old_task.done():
            old_task.cancel()

        # إنشاء مؤقت جديد من آخر رسالة
        task = asyncio.create_task(
            self.send_reminder_after_delay(
                message.channel,
                message.author,
                user_id
            )
        )

        self.pending_tasks[user_id] = task

    async def send_reminder_after_delay(
        self,
        channel: discord.TextChannel,
        member: discord.Member,
        user_id: int
    ):

        try:
            # انتظار 10 ثواني من آخر رسالة
            await asyncio.sleep(WAIT_SECONDS)

            # إرسال التنبيه
            await channel.send(
                f"{member.mention}\n{REMINDER_MESSAGE}"
            )

        except asyncio.CancelledError:
            # تم إرسال رسالة جديدة قبل انتهاء الـ10 ثواني
            # لذلك نلغي المؤقت القديم بدون إرسال شيء
            pass

        finally:
            # حذف المهمة من القائمة إذا كانت هي المهمة الحالية
            current_task = self.pending_tasks.get(user_id)

            if current_task is asyncio.current_task():
                self.pending_tasks.pop(user_id, None)


# =========================================================
# SETUP
# =========================================================

async def setup(bot):
    await bot.add_cog(SupportReminder(bot))
