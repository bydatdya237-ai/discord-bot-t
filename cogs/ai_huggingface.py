
import os
import asyncio
import logging

import discord
from discord.ext import commands
from openai import OpenAI
from pymongo import MongoClient

logger = logging.getLogger(__name__)

# إعدادات Hugging Face
HF_TOKEN = os.getenv("HF_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

MODEL_NAME = "CohereLabs/tiny-aya-earth:cohere"

# ضع آيدي الروم الجديد هنا
TARGET_CHANNEL_ID = 1558187899160109127

SYSTEM_PROMPT = """
أنت مساعد ذكي وودود.
افهم العربية واللهجات العربية، ورد بلغة المستخدم.
اجعل ردودك طبيعية وواضحة ومفيدة ومختصرة.
افهم سياق المحادثة قبل الإجابة.
"""

client = (
    OpenAI(
        base_url="https://router.huggingface.co/v1",
        api_key=HF_TOKEN,
        timeout=60.0,
        max_retries=1,
    )
    if HF_TOKEN else None
)

mongo_client = (
    MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    if MONGO_URI else None
)

db = mongo_client["discord_bot_db"] if mongo_client is not None else None

history_collection = (
    db["huggingface_conversation_history"]
    if db is not None else None
)


class HuggingFaceAutoChatCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_reply(self, messages):
        if client is None:
            logger.error("متغير HF_TOKEN غير موجود.")
            return None

        try:
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model=MODEL_NAME,
                messages=messages,
                temperature=0.5,
                max_tokens=500,
            )

            if not response.choices:
                logger.warning("Hugging Face لم يُرجع ردًا.")
                return None

            reply = response.choices[0].message.content

            if isinstance(reply, str) and reply.strip():
                return reply.strip()

            return None

        except Exception:
            logger.exception("خطأ في طلب Hugging Face.")
            return None

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        if message.channel.id != TARGET_CHANNEL_ID:
            return

        if history_collection is None:
            logger.error("متغير MONGO_URI غير موجود.")
            return

        try:
            channel_id = str(message.channel.id)

            async with message.channel.typing():
                await asyncio.sleep(3)

                history_doc = await asyncio.to_thread(
                    history_collection.find_one,
                    {"channel_id": channel_id},
                )

                history = (
                    history_doc.get("messages", [])
                    if history_doc else []
                )

                history.append({
                    "role": "user",
                    "content": (
                        f"{message.author.display_name}: "
                        f"{message.content[:2500]}"
                    ),
                })

                history = history[-16:]

                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    *history,
                ]

                reply = await self.get_reply(messages)

            # لا يرسل أخطاء إلى ديسكورد
            if not reply:
                return

            reply = reply[:1900]

            await message.reply(
                reply,
                mention_author=False,
                allowed_mentions=discord.AllowedMentions.none(),
            )

            history.append({
                "role": "assistant",
                "content": reply,
            })

            history = history[-16:]

            await asyncio.to_thread(
                history_collection.update_one,
                {"channel_id": channel_id},
                {"$set": {
                    "channel_id": channel_id,
                    "messages": history,
                }},
                upsert=True,
            )

        except Exception:
            logger.exception("خطأ داخل HuggingFaceAutoChatCog.")


async def setup(bot):
    await bot.add_cog(HuggingFaceAutoChatCog(bot))
