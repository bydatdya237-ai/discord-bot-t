
import os
import asyncio
import logging

import discord
from discord.ext import commands
from mistralai.client import Mistral
from pymongo import MongoClient

logger = logging.getLogger(__name__)

# الإعدادات
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")

MODEL_NAME = "ministral-3b-latest"

TARGET_CHANNELS = {
    1557736029040156683,
}

SYSTEM_PROMPT = """
أنت مساعد ذكي وودود.
افهم العربية واللهجات العربية، ورد بلغة المستخدم.
اجعل ردودك طبيعية وواضحة ومفيدة، ولا تطل بلا داعٍ.
افهم سياق المحادثة قبل الإجابة.
"""

client = Mistral(api_key=MISTRAL_API_KEY) if MISTRAL_API_KEY else None

mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000) if MONGO_URI else None
db = mongo_client["discord_bot_db"] if mongo_client is not None else None

history_collection = (
    db["mistral_conversation_history"]
    if db is not None
    else None
)


class MistralAutoChatCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_reply(self, messages):
        if client is None:
            logger.error("MISTRAL_API_KEY غير موجود.")
            return None

        try:
            response = await asyncio.to_thread(
                client.chat.complete,
                model=MODEL_NAME,
                messages=messages,
                temperature=0.5,
                max_tokens=600,
            )

            if not response or not response.choices:
                logger.warning("Mistral لم يُرجع أي رد.")
                return None

            content = response.choices[0].message.content

            if isinstance(content, str):
                reply = content.strip()
            elif isinstance(content, list):
                reply = "".join(
                    item.text
                    for item in content
                    if getattr(item, "text", None)
                ).strip()
            else:
                return None

            return reply or None

        except Exception:
            logger.exception("خطأ أثناء طلب الرد من Mistral.")
            return None

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        if message.channel.id not in TARGET_CHANNELS:
            return

        if history_collection is None:
            logger.error("MONGO_URI غير موجود أو MongoDB غير مهيأ.")
            return

        try:
            channel_id = str(message.channel.id)

            # إظهار حالة الكتابة خلال الانتظار وتوليد الرد
            async with message.channel.typing():
                await asyncio.sleep(3)

                history_doc = await asyncio.to_thread(
                    history_collection.find_one,
                    {"channel_id": channel_id},
                )

                history = (
                    history_doc.get("messages", [])
                    if history_doc
                    else []
                )

                history.append({
                    "role": "user",
                    "content": (
                        f"{message.author.display_name}: "
                        f"{message.content[:3000]}"
                    ),
                })

                history = history[-16:]

                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    *history,
                ]

                reply = await self.get_reply(messages)

            # عند فشل الرد، لا يرسل شيئًا في ديسكورد
            if not reply:
                return

            reply = reply[:1900]

            await message.reply(
                reply,
                mention_author=False,
                allowed_mentions=discord.AllowedMentions.none(),
            )

            # حفظ الذاكرة بعد نجاح إرسال الرد
            history.append({
                "role": "assistant",
                "content": reply,
            })
            history = history[-16:]

            await asyncio.to_thread(
                history_collection.update_one,
                {"channel_id": channel_id},
                {
                    "$set": {
                        "channel_id": channel_id,
                        "messages": history,
                    }
                },
                upsert=True,
            )

        except Exception:
            # تسجيل الخطأ في Railway فقط
            logger.exception("خطأ داخل MistralAutoChatCog.")


async def setup(bot):
    await bot.add_cog(MistralAutoChatCog(bot))
