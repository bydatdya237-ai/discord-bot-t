import os
import asyncio
import discord
from discord.ext import commands
from openai import OpenAI
from pymongo import MongoClient


class OpenRouterAutoChatCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

        # ==============================
        # OpenRouter API
        # ==============================
        api_key = os.environ.get("OPENROUTER_API_KEY")

        if api_key:
            try:
                self.client = OpenAI(
                    api_key=api_key,
                    base_url="https://openrouter.ai/api/v1",
                    default_headers={
                        "X-Title": "Diaa Discord Bot"
                    }
                )
                print("✅ OpenRouter API جاهز")
            except Exception as e:
                self.client = None
                print(
                    f"❌ OpenRouter: "
                    f"{type(e).__name__}: {e}"
                )
        else:
            self.client = None
            print("⚠️ OPENROUTER_API_KEY غير موجود")

        # ==============================
        # MongoDB - ذاكرة مستقلة
        # ==============================
        mongo_uri = os.environ.get("MONGO_URI")
        self.mongo_client = None
        self.memory_collection = None

        if mongo_uri:
            try:
                self.mongo_client = MongoClient(
                    mongo_uri,
                    serverSelectionTimeoutMS=5000
                )

                db = self.mongo_client["discord_bot_db"]

                self.memory_collection = db[
                    "openrouter_conversation_history"
                ]

                print("✅ OpenRouter MongoDB جاهز")

            except Exception as e:
                print(
                    f"❌ MongoDB: "
                    f"{type(e).__name__}: {e}"
                )
        else:
            print("⚠️ MONGO_URI غير موجود")

        # ==============================
        # إعدادات الروم
        # غيّر الرقم إلى آيدي رومك الحقيقي
        # ==============================
        self.TARGET_CHANNEL_IDS = {
            1558064909126865006
        }

        # ==============================
        # إعدادات الذاكرة
        # ==============================
        self.MAX_HISTORY_MESSAGES = 1000
        self.MAX_HISTORY_CHARS = 300000
        self.CONTEXT_MESSAGES = 8

        self.lock = asyncio.Lock()
        self.history_cache = {}

        self.system_prompt = """
أنت مساعد ذكاء اصطناعي داخل سيرفر ديسكورد.

اسمك ضياء.
مطورك ضياء.

تحدث بالعربية بشكل طبيعي وواضح.
أجب عن أسئلة الأعضاء بطريقة مفيدة ومختصرة.
حافظ على سياق المحادثة القريب.
لا تطل الإجابة بدون داعٍ.
إذا سُئلت عن اسمك فقل: اسمي ضياء.
إذا سُئلت عن مطورك فقل: المطور ضياء.
"""

    # ==============================
    # تحميل الذاكرة
    # ==============================
    def load_history(self, channel_id):

        key = str(channel_id)

        if key in self.history_cache:
            return self.history_cache[key]

        history = []

        if self.memory_collection is not None:
            try:
                document = self.memory_collection.find_one(
                    {"channel_id": key}
                )

                if document:
                    history = document.get("messages", [])

            except Exception as e:
                print(
                    f"❌ تحميل الذاكرة: "
                    f"{type(e).__name__}: {e}"
                )

        self.history_cache[key] = history
        return history

    # ==============================
    # حفظ الذاكرة
    # ==============================
    def save_history(self, channel_id, history):

        key = str(channel_id)
        self.history_cache[key] = history

        if self.memory_collection is not None:
            try:
                self.memory_collection.update_one(
                    {"channel_id": key},
                    {
                        "$set": {
                            "messages": history
                        }
                    },
                    upsert=True
                )

            except Exception as e:
                print(
                    f"❌ حفظ الذاكرة: "
                    f"{type(e).__name__}: {e}"
                )

    # ==============================
    # تحديد حجم الذاكرة
    # ==============================
    def trim_history(self, history):

        history = history[
            -self.MAX_HISTORY_MESSAGES:
        ]

        total_chars = 0
        trimmed = []

        for item in reversed(history):
            content = item.get("content", "")
            size = len(content)

            if total_chars + size > self.MAX_HISTORY_CHARS:
                break

            trimmed.append(item)
            total_chars += size

        trimmed.reverse()
        return trimmed

    # ==============================
    # تقسيم ردود ديسكورد الطويلة
    # ==============================
    def split_message(self, text, limit=1900):

        return [
            text[i:i + limit]
            for i in range(0, len(text), limit)
        ]

    # ==============================
    # استقبال الرسائل
    # ==============================
    @commands.Cog.listener()
    async def on_message(self, message):

        if message.author.bot:
            return

        if message.channel.id not in self.TARGET_CHANNEL_IDS:
            return

        if self.client is None:
            print("⚠️ OpenRouter غير جاهز")
            return

        if not message.content.strip():
            return

        async with self.lock:

            channel_id = message.channel.id
            history = self.load_history(channel_id)

            history.append({
                "role": "user",
                "content": (
                    f"{message.author.display_name}: "
                    f"{message.content[:4000]}"
                )
            })

            history = self.trim_history(history)
            self.save_history(channel_id, history)

            try:
                async with message.channel.typing():

                    await asyncio.sleep(3)

                    context = history[
                        -self.CONTEXT_MESSAGES:
                    ]

                    api_messages = [
                        {
                            "role": "system",
                            "content": self.system_prompt
                        }
                    ] + context

                    response = await asyncio.to_thread(
                        self.client.chat.completions.create,
                        model="openrouter/free",
                        messages=api_messages,
                        max_tokens=300
                    )

                answer = (
                    response.choices[0].message.content
                    if response.choices
                    else None
                )

                if not answer or not answer.strip():
                    print("⚠️ OpenRouter أعاد ردًا فارغًا")
                    return

                history.append({
                    "role": "assistant",
                    "content": answer
                })

                history = self.trim_history(history)
                self.save_history(channel_id, history)

                for part in self.split_message(answer):
                    await message.reply(
                        part,
                        mention_author=False
                    )

            except Exception as e:
                # الأخطاء تظهر في Railway فقط
                print(
                    f"❌ OpenRouter API error: "
                    f"{type(e).__name__}: {e}"
                )


async def setup(bot):
    await bot.add_cog(OpenRouterAutoChatCog(bot))
