import asyncio
import discord
from discord.ext import commands

=========================================================

SETTINGS

=========================================================

TARGET_CHANNEL_ID = 1555381169154039828
TICKET_CHANNEL_ID = 1555369541503025273

مدة الانتظار بعد آخر رسالة

WAIT_SECONDS = 1

نص رسالة التنبيه الثابتة

REMINDER_TEXT = (
"يرجى كتابة مشكلتك أو استفسارك مرة واحدة فقط وانتظار الرد من الإدارة.\n"
f"وفي حال كانت المشكلة طويلة أو تحتاج إلى شرح مفصل، توجه للتكت من <#{TICKET_CHANNEL_ID}>"
)

=========================================================

COG

=========================================================

class SupportReminder(commands.Cog):

def __init__(self, bot):
    self.bot = bot
    self.pending_task = None
    self.reminder_message_id = None
    self.reminder_lock = asyncio.Lock()
    self.ready_once = False

@commands.Cog.listener()
async def on_ready(self):
    if self.ready_once:
        return

    self.ready_once = True
    await self.restore_reminder()

async def restore_reminder(self):
    channel = self.bot.get_channel(TARGET_CHANNEL_ID)

    if channel is None:
        try:
            channel = await self.bot.fetch_channel(
                TARGET_CHANNEL_ID
            )
        except (
            discord.NotFound,
            discord.Forbidden,
            discord.HTTPException
        ):
            return

    if not isinstance(channel, discord.TextChannel):
        return

    try:
        async for message in channel.history(limit=100):
            if (
                message.author.id == self.bot.user.id
                and message.content == REMINDER_TEXT
            ):
                self.reminder_message_id = message.id
                return

    except (
        discord.Forbidden,
        discord.HTTPException
    ):
        return

@commands.Cog.listener()
async def on_message(self, message):

    # تجاهل رسائل البوتات
    if message.author.bot:
        return

    # العمل في الروم المحدد فقط
    if message.channel.id != TARGET_CHANNEL_ID:
        return

    # إلغاء المؤقت السابق عند وصول رسالة جديدة
    if self.pending_task and not self.pending_task.done():
        self.pending_task.cancel()

    # بدء مؤقت جديد
    self.pending_task = asyncio.create_task(
        self.wait_then_update(message.channel)
    )

async def wait_then_update(self, channel):

    current_task = asyncio.current_task()

    try:
        # الانتظار بعد آخر رسالة
        await asyncio.sleep(WAIT_SECONDS)

        async with self.reminder_lock:

            # جلب رسالة التنبيه الحالية
            old_message = None

            if self.reminder_message_id is not None:
                try:
                    old_message = await channel.fetch_message(
                        self.reminder_message_id
                    )
                except (
                    discord.NotFound,
                    discord.Forbidden,
                    discord.HTTPException
                ):
                    old_message = None

            # حذف رسالة التنبيه القديمة
            if old_message is not None:
                try:
                    await old_message.delete()
                except discord.NotFound:
                    pass
                except (
                    discord.Forbidden,
                    discord.HTTPException
                ):
                    pass

            # إرسال رسالة التنبيه في أسفل الروم
            new_message = await channel.send(REMINDER_TEXT)

            self.reminder_message_id = new_message.id

    except asyncio.CancelledError:
        pass

    except discord.HTTPException as error:
        print(f"[SupportReminder] Discord error: {error}")

    finally:
        if self.pending_task is current_task:
            self.pending_task = None

=========================================================

SETUP

=========================================================

async def setup(bot):
await bot.add_cog(SupportReminder(bot))
