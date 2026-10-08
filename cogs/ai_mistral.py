import os
import asyncio
import random

import discord
from discord.ext import commands
from mistralai.client import Mistral
from pymongo import MongoClient


class MistralAutoChatCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

        # =========================================================
        # Mistral API
        # مستقل تمامًا عن Groq و Gemini
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
                    f"❌ تعذر تشغيل Mistral API: "
                    f"{type(e).__name__}: {e}"
                )

                self.mistral_client = None

        # =========================================================
        # MongoDB
        # ذاكرة Mistral مستقلة تمامًا
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
                    f"⚠️ تعذر الاتصال بـ MongoDB: "
                    f"{type(e).__name__}: {e}"
                )

                self.mongo_client = None
                self.memory_collection = None

        # =========================================================
        # الروم الذي يعمل فيه Mistral
        # =========================================================

        self.TARGET_CHANNEL_IDS = {
            1557736029040156683,
        }

        # =========================================================
        # قفل الطلبات
        # يمنع إرسال عدة طلبات Mistral بنفس الوقت
        # =========================================================

        self.lock = asyncio.Lock()

        # =========================================================
        # الذاكرة الكاملة المخزنة في MongoDB
        # =========================================================

        self.MAX_HISTORY_MESSAGES = 1000

        self.MAX_HISTORY_CHARS = 700_000

        # =========================================================
        # الذاكرة التي يتم إرسالها فعليًا إلى Mistral
        #
        # نخزن 1000 رسالة، لكن لا نرسلها كلها في كل طلب.
        # هذا يقلل استهلاك الـtokens ويحافظ على استقرار الـAPI.
        # =========================================================

        self.CONTEXT_MESSAGES = 40

        # =========================================================
        # إعادة المحاولة عند 429
        # =========================================================

        self.MAX_RETRIES = 5

        # =========================================================
        # شخصية Mistral
        # =========================================================

        self.system_prompt = """
أنت مساعد ذكاء اصطناعي داخل سيرفر ديسكورد.

تحدث باللغة العربية دائمًا وبأسلوب طبيعي وواضح.
لا تستخدم اللغة الإنجليزية إلا إذا طلب المستخدم ذلك صراحة.

اسمك أنت هو: ضياء.
مطورك هو: ضياء.

مهم جدًا:

- إذا سألك أي شخص:
  "ما اسمك؟"
  أو "وش اسمك؟"
  أو "شو اسمك؟"
  أو "ما هو اسمك؟"
  أو "اسمك مين؟"
  أو أي سؤال مشابه عن اسمك،
  يجب أن تجيب بوضوح:
  "اسمي ضياء."

- إذا سألك أي شخص:
  "من طورك؟"
  أو "مين طورك؟"
  أو "من مطورك؟"
  أو "مين مطورك؟"
  أو "من برمجك؟"
  أو "مين اللي برمجك؟"
  أو أي سؤال مشابه عن المطور،
  يجب أن تجيب بوضوح:
  "المطور ضياء."

- لا تقل إن اسمك هو اسم الشخص الذي يتحدث معك.
- لا تخلط بين اسمك واسم المستخدم.
- لا تقل إن اسمك ذكاء اصطناعي أو AI.
- اسمك هو ضياء.
- عندما تُسأل عن مطورك، لا تذكر اسم أي شخص آخر.
- حافظ على سياق المحادثة.
- تحدث بشكل طبيعي وواضح.
"""

        # =========================================================
        # ذاكرة مؤقتة داخل تشغيل البوت
        # =========================================================

        self.conversation_history = {}

    # =============================================================
    # مفتاح الذاكرة
    # =============================================================

    def get_memory_key(self, channel_id):

        return str(channel_id)

    # =============================================================
    # تحميل الذاكرة من MongoDB
    # =============================================================

    async def load_history(self, channel_id):

        memory_key = self.get_memory_key(
            channel_id
        )

        # ---------------------------------------------------------
        # إذا الذاكرة موجودة في الرام، نستخدمها مباشرة
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
    # تنظيف الذاكرة المخزنة
    # =============================================================

    def trim_history(self, history):

        if len(history) > self.MAX_HISTORY_MESSAGES:

            history = history[
                -self.MAX_HISTORY_MESSAGES:
            ]

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
            total_chars
            > self.MAX_HISTORY_CHARS
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
    # أخذ آخر جزء من الذاكرة لإرساله إلى Mistral
    # =============================================================

    def get_context_history(self, history):

        if len(history) <= self.CONTEXT_MESSAGES:

            return list(history)

        return list(
            history[
                -self.CONTEXT_MESSAGES:
            ]
        )

    # =============================================================
    # التحقق من 429
    # =============================================================

    def is_rate_limit_error(self, error):

        error_text = str(error).lower()

        error_name = type(error).__name__.lower()

        combined = (
            error_text
            + " "
            + error_name
        )

        return (
            "429" in combined
            or "rate limit" in combined
            or "rate_limit" in combined
            or "too many requests" in combined
        )

    # =============================================================
    # إرسال الطلب إلى Mistral مع إعادة المحاولة
    # =============================================================

    async def request_mistral(
        self,
        messages
    ):

        last_error = None

        for attempt in range(
            self.MAX_RETRIES
        ):

            try:

                response = await asyncio.to_thread(
                    self.mistral_client.chat.complete,
                    model="mistral-small-latest",
                    messages=messages
                )

                return response

            except Exception as e:

                last_error = e

                # -------------------------------------------------
                # إذا الخطأ ليس 429
                # لا نعيد المحاولة بشكل عشوائي
                # -------------------------------------------------

                if not self.is_rate_limit_error(e):

                    raise

                # -------------------------------------------------
                # وصلنا إلى آخر محاولة
                # -------------------------------------------------

                if attempt >= (
                    self.MAX_RETRIES - 1
                ):

                    raise

                # -------------------------------------------------
                # تأخير متزايد:
                #
                # المحاولة 1 -> 2 ثواني تقريبًا
                # المحاولة 2 -> 4 ثواني تقريبًا
                # المحاولة 3 -> 8 ثواني تقريبًا
                # المحاولة 4 -> 16 ثانية تقريبًا
                #
                # مع عشوائية بسيطة لمنع الطلبات المتزامنة.
                # -------------------------------------------------

                wait_time = (
                    2 ** (
                        attempt + 1
                    )
                )

                wait_time += random.uniform(
                    0.5,
                    1.5
                )

                print(
                    f"⚠️ Mistral أعاد 429. "
                    f"إعادة المحاولة بعد "
                    f"{wait_time:.1f} ثانية..."
                )

                await asyncio.sleep(
                    wait_time
                )

        if last_error:

            raise last_error

        return None

    # =============================================================
    # تقسيم رد Discord الطويل
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
        # تجاهل جميع الرومات الأخرى
        # =========================================================

        if (
            message.channel.id
            not in self.TARGET_CHANNEL_IDS
        ):

            return

        # =========================================================
        # إذا Mistral غير متصل
        # =========================================================

        if self.mistral_client is None:

            print(
                "❌ Mistral متوقف لأن "
                "MISTRAL_API_KEY غير موجود "
                "أو تعذر تشغيل العميل."
            )

            return

        # =========================================================
        # قفل الطلب
        # يمنع طلبات Mistral المتزامنة
        # =========================================================

        async with self.lock:

            async with message.channel.typing():

                try:

                    # =================================================
                    # تحميل الذاكرة
                    # =================================================

                    history = await self.load_history(
                        message.channel.id
                    )

                    # =================================================
                    # نسخ الذاكرة
                    # =================================================

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
                    # تنظيف الذاكرة المخزنة
                    # =================================================

                    working_history = (
                        self.trim_history(
                            working_history
                        )
                    )

                    # =================================================
                    # انتظار 3 ثواني
                    # =================================================

                    await asyncio.sleep(
                        3
                    )

                    # =================================================
                    # أخذ آخر 40 رسالة فقط للسياق
                    #
                    # الذاكرة الكاملة تبقى محفوظة في MongoDB.
                    # =================================================

                    context_history = (
                        self.get_context_history(
                            working_history
                        )
                    )

                    # =================================================
                    # بناء رسائل Mistral
                    # =================================================

                    messages = [
                        {
                            "role": "system",
                            "content": self.system_prompt
                        }
                    ]

                    for item in context_history:

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

                    # =================================================
                    # طلب Mistral
                    # =================================================

                    response = await self.request_mistral(
                        messages
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
                    # إذا لم يرجع نص
                    # =================================================

                    if (
                        not answer
                        or not str(answer).strip()
                    ):

                        print(
                            "⚠️ Mistral لم يرجع نصًا."
                        )

                        return

                    answer = str(
                        answer
                    ).strip()

                    # =================================================
                    # إضافة رد Mistral إلى الذاكرة الكاملة
                    # =================================================

                    working_history.append(
                        {
                            "role": "assistant",
                            "text": answer
                        }
                    )

                    # =================================================
                    # تنظيف الذاكرة
                    # =================================================

                    working_history = (
                        self.trim_history(
                            working_history
                        )
                    )

                    # =================================================
                    # حفظ الذاكرة الكاملة في MongoDB
                    # =================================================

                    await self.save_history(
                        message.channel.id,
                        working_history
                    )

                    # =================================================
                    # تقسيم الرد إذا كان طويلًا
                    # =================================================

                    chunks = self.split_message(
                        answer
                    )

                    if not chunks:

                        return

                    # =================================================
                    # إرسال الرد
                    # =================================================

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
