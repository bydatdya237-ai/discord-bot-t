import asyncio
import discord
from discord.ext import commands

OWNER_ID = 1154374165642620948
MESSAGE_COUNT = 100
MESSAGE_DELAY = 0


class SpamCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_users = set()

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        if message.author.id != OWNER_ID:
            return

        if message.guild is None:
            return

        if not message.content.startswith("سبام "):
            return

        if not message.mentions:
            await message.channel.send(
                "❌ استخدم الأمر مع منشن العضو."
            )
            return

        member = message.mentions[0]

        if message.author.id in self.active_users:
            return

        self.active_users.add(message.author.id)

        try:
            for _ in range(MESSAGE_COUNT):
                await member.send(
                    f"مرحبًا {member.mention}، يسطااا رجع  الذهب يابرو ."
                )
                await asyncio.sleep(MESSAGE_DELAY)

            await message.channel.send(
                "✅ تم إرسال رسائل الاختبار الثلاث بالخاص."
            )

        except discord.Forbidden:
            await message.channel.send(
                "❌ تعذّر الإرسال؛ قد تكون الرسائل الخاصة مغلقة."
            )

        except discord.HTTPException:
            await message.channel.send(
                "❌ تعذّر إرسال إحدى رسائل الاختبار."
            )

        finally:
            self.active_users.discard(message.author.id)


async def setup(bot):
    await bot.add_cog(SpamCog(bot))
