import os
import asyncio

import discord
from discord.ext import commands
from mistralai.client import Mistral
from pymongo import MongoClient


class MistralAutoChatCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

        # =========================================================
        # MISTRAL API
        # =========================================================

        api_key = os.environ.get("MISTRAL_API_KEY")

        if not api_key:
            print(
                "⚠️ MISTRAL_API_KEY غير موجود في Environment Variables"
            )
            self.mistral_client = None

        else:
            try:
                self.mistral_client = Mistral(
                    api_key=api_key
                )

                print(
                    "✅ تم تشغيل Mistral API"
                )

            except Exception as e:
                print(
                    f"❌ خطأ في تشغيل Mistral: "
                    f"{type(e).__name__}: {e}"
                )

                self.mistral_client = None

        # =========================================================
        # MONGODB
        # ذاكرة Mistral مستقلة عن Groq و Gemini
        # =========================================================

        mongo_uri = os.environ.get("MONGO_URI")

        if not mongo_uri:

            print(
                "⚠️ MONGO_URI غير موجود"
            )

            self.mongo_client = None
            self.memory_collection = None

        else:

            try:

                self.mongo_client = MongoClient(
                    mongo_uri
                )

                self.db = self.mongo_client[
                    "discord_bot_db"
                ]

                self.memory_collection = self.db[
                    "mistral_conversation_history"
                ]

                print(
                    "✅ تم تشغيل ذاكرة Mistral عبر MongoDB"
                )

            except Exception as e:

                print(
                    f"⚠️ خطأ في MongoDB: "
                    f"{type(e).__name__}: {e}"
                )

                self.mongo_client = None
                self.memory_collection = None

        # =========================================================
        # روم MISTRAL
        # =========================================================

        self.TARGET_CHANNEL_IDS = {
            1557736029040156683,
        }

        # =========================================================
        # منع أكثر من طلب بنفس الوقت
        # =========================================================

        self.lock = asyncio.Lock()

        # =========================================================
        # الذاكرة المحفوظة في MongoDB
        # =========================================================

        self.MAX_HISTORY_MESSAGES = 1000

        self.MAX_HISTORY_CHARS = 300_000

        # =========================================================
        # الذاكرة التي نرسلها فعليًا إلى Mistral
        #
        # آخر 8 رسائل فقط
        # =========================================================

        self.CONTEXT_MESSAGES = 8

        # =========================================================
        # شخصية بسيطة
        # =========================================================

        self.system_prompt = """
أنت مساعد ذكاء اصطناعي داخل سيرفر ديسكورد.

اسمك ضياء.
مطورك ضياء.

تحدث بالعربية بشكل طبيعي وواضح ومختصر.

إذا سُئلت عن اسمك:
قل: اسمي ضياء.

إذا سُئلت عن مطورك:
قل: المطور ضياء.

حافظ على سياق المحادثة القريب.
لا تطيل الرد بدون سبب.
"""

        # =========================================================
        # ذاكرة مؤقتة
        # =========================================================

        self.conversation_history = {}

    # =============================================================
    # مفتاح الذاكرة
    # =============================================================

    def get_memory_key(self, channel_id):

        return str(channel_id)

    # =============================================================
    # تحميل الذاكرة
    # =============================================================

    async def load_history(self, channel_id):

        memory_key = self.get_memory_key(
            channel_id
        )

        # ---------------------------------------------------------
        # إذا موجودة في الذاكرة المؤقتة
        # ---------------------------------------------------------

        if memory_key in self.conversation_history:

            return self.conversation_history[
                memory_key
            ]

        # ---------------------------------------------------------
        # إذا MongoDB غير متوفر
        # ---------------------------------------------------------

        if self.memory_collection is None:

            self.conversation_history[
                memory_key
            ] = []

            return []

        try:

            document = await asyncio.to_thread(
                self.memory_collection.find_one,
                {
                    "_id": memory_key
                }
            )

            if not document:

                self.conversation_history[
                    memory_key
                ] = []

                return []

            history = document.get(
                "messages",
                []
            )

            cleaned_history = []

            for item in history:

                if (
                    isinstance(item, dict)
                    and item.get("role")
                    in ("user", "assistant")
                    and isinstance(
                        item.get("text"),
                        str
                    )
                ):

                    cleaned_history.append(
                        {
                            "role": item["role"],
                            "text": item["text"]
                        }
                    )

            cleaned_history = self.trim_history(
                cleaned_history
            )

            self.conversation_history[
                memory_key
            ] = cleaned_history

            return cleaned_history

        except Exception as e:

            print(
                f"⚠️ خطأ أثناء تحميل ذاكرة Mistral: "
                f"{type(e).__name__}: {e}"
            )

            self.conversation_history[
                memory_key
            ] = []

            return []

    # =============================================================
    # حفظ الذاكرة
    # =============================================================

    async def save_history(
        self,
        channel_id,
        history
    ):

        memory_key = self.get_memory_key(
            channel_id
        )

        history = self.trim_history(
            history
        )

        self.conversation_history[
            memory_key
        ] = history

        if self.memory_collection is None:

            return

        try:

            await asyncio.to_thread(
                self.memory_collection.update_one,
                {
                    "_id": memory_key
                },
                {
                    "$set": {
                        "channel_id": channel_id,
                        "messages": history
                    }
                },
                True
            )

        except Exception as e:

            print(
                f"⚠️ خطأ أثناء حفظ ذاكرة Mistral: "
                f"{type(e).__name__}: {e}"
            )

    # =============================================================
    # تنظيف الذاكرة
    # =============================================================

    def trim_history(self, history):

        # ---------------------------------------------------------
        # لا نسمح بأكثر من 1000 رسالة محفوظة
        # ---------------------------------------------------------

        if len(history) > self.MAX_HISTORY_MESSAGES:

            history = history[
                -self.MAX_HISTORY_MESSAGES:
            ]

        # ---------------------------------------------------------
        # حماية من حجم ضخم جدًا
        # ---------------------------------------------------------

        total_chars = sum(
            len(
                item.get(
                    "text",
                    ""
                )
            )
            for item in history
            if isinstance(item, dict)
        )

        while (
            total_chars > self.MAX_HISTORY_CHARS
            and len(history) > 2
        ):

            removed = history.pop(0)

            total_chars -= len(
                removed.get(
                    "text",
                    ""
                )
            )

        return history

    # =============================================================
    # أخذ آخر 8 رسائل فقط للسياق
    # =============================================================

    def get_context(self, history):

        if len(history) <= self.CONTEXT_MESSAGES:

            return list(history)

        return list(
            history[
                -self.CONTEXT_MESSAGES:
            ]
        )

    # =============================================================
    # تقسيم الرد الطويل
    # =============================================================

    def split_message(
        self,
        text,
        max_length=1900
    ):

        chunks = []

        current = ""

        for word in text.split():

            if (
                len(current)
                + len(word)
                + 1
                > max_length
            ):

                if current:

                    chunks.append(
                        current
                    )

                current = word

            else:

                if current:

                    current += " "

                current += word

        if current:

            chunks.append(
                current
            )

        return chunks

    # =============================================================
    # استقبال الرسائل
    # =============================================================

    @commands.Cog.listener()
    async def on_message(
        self,
        message: discord.Message
    ):

        # =========================================================
        # تجاهل البوتات
        # =========================================================

        if message.author.bot:

            return

        # =========================================================
        # تجاهل أي روم غير روم Mistral
        # =========================================================

        if (
            message.channel.id
            not in self.TARGET_CHANNEL_IDS
        ):

            return

        # =========================================================
        # إذا API غير متوفر
        # =========================================================

        if self.mistral_client is None:

            print(
                "❌ Mistral غير متصل."
            )

            return

        # =========================================================
        # منع الطلبات المتزامنة
        # =========================================================

        async with self.lock:

            try:

                # =================================================
                # تحميل الذاكرة
                # =================================================

                history = await self.load_history(
                    message.channel.id
                )

                working_history = list(
                    history
                )

                # =================================================
                # إضافة رسالة المستخدم
                # =================================================

                working_history.append(
                    {
                        "role": "user",
                        "text": message.content
                    }
                )

                # =================================================
                # تنظيف الذاكرة المحفوظة
                # =================================================

                working_history = (
                    self.trim_history(
                        working_history
                    )
                )

                # =================================================
                # انتظار 3 ثواني
                # =================================================

                async with message.channel.typing():

                    await asyncio.sleep(3)

                    # =============================================
                    # نرسل آخر 8 رسائل فقط
                    # =============================================

                    context = self.get_context(
                        working_history
                    )

                    # =============================================
                    # تجهيز الرسائل
                    # =============================================

                    messages = [
                        {
                            "role": "system",
                            "content": self.system_prompt
                        }
                    ]

                    for item in context:

                        role = item.get(
                            "role"
                        )

                        text = item.get(
                            "text",
                            ""
                        )

                        if (
                            role in (
                                "user",
                                "assistant"
                            )
                            and text
                        ):

                            messages.append(
                                {
                                    "role": role,
                                    "content": text
                                }
                            )

                    # =============================================
                    # إرسال الطلب
                    # =============================================

                    response = await asyncio.to_thread(
                        self.mistral_client.chat.complete,
                        model="ministral-3b-latest",
                        messages=messages,
                        max_tokens=300
                    )

                # =================================================
                # استخراج الرد
                # =================================================

                answer = None

                if (
                    response
                    and getattr(
                        response,
                        "choices",
                        None
                    )
                ):

                    answer = (
                        response
                        .choices[0]
                        .message
                        .content
                    )

                # =================================================
                # التأكد من وجود رد
                # =================================================

                if (
                    not answer
                    or not str(answer).strip()
                ):

                    print(
                        "⚠️ Mistral لم يرجع ردًا."
                    )

                    return

                answer = str(
                    answer
                ).strip()

                # =================================================
                # حفظ رد Mistral في الذاكرة
                # =================================================

                working_history.append(
                    {
                        "role": "assistant",
                        "text": answer
                    }
                )

                working_history = (
                    self.trim_history(
                        working_history
                    )
                )

                # =================================================
                # حفظ الذاكرة في MongoDB
                # =================================================

                await self.save_history(
                    message.channel.id,
                    working_history
                )

                # =================================================
                # إرسال الرد
                # =================================================

                chunks = self.split_message(
                    answer
                )

                for index, chunk in enumerate(
                    chunks
                ):

                    if index == 0:

                        await message.reply(
                            chunk
                        )

                    else:

                        await message.channel.send(
                            chunk
                        )

            except Exception as e:

                # =================================================
                # لا نرسل الخطأ للمستخدم
                # Railway Logs فقط
                # =================================================

                print(
                    f"❌ خطأ في Mistral: "
                    f"{type(e).__name__}: {e}"
                )

                return


# =============================================================
# تحميل الـ Cog
# =============================================================

async def setup(bot):

    await bot.add_cog(
        MistralAutoChatCog(bot)
    )
