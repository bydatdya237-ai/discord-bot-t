import os
import asyncio

import discord
from discord.ext import commands
from google import genai
from google.genai import types
from pymongo import MongoClient


class GeminiAutoChatCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

        # =========================================================
        # Gemini API
        # مستقل تمامًا عن Groq
        # =========================================================

        api_key = os.environ.get("GEMINI_API_KEY")

        if not api_key:
            print("⚠️ GEMINI_API_KEY غير موجود في Environment Variables")
            self.gemini_client = None
        else:
            self.gemini_client = genai.Client(api_key=api_key)

        # =========================================================
        # MongoDB
        # ذاكرة Gemini مستقلة
        # =========================================================

        mongo_uri = os.environ.get("MONGO_URI")

        if not mongo_uri:
            print("⚠️ MONGO_URI غير موجود - ذاكرة Gemini لن تكون دائمة")
            self.mongo_client = None
            self.memory_collection = None
        else:
            try:
                self.mongo_client = MongoClient(mongo_uri)

                self.db = self.mongo_client["discord_bot_db"]

                self.memory_collection = self.db[
                    "gemini_conversation_history"
                ]

                print("✅ تم تشغيل ذاكرة Gemini عبر MongoDB")

            except Exception as e:
                print(f"⚠️ تعذر الاتصال بـ MongoDB: {e}")

                self.mongo_client = None
                self.memory_collection = None

        # =========================================================
        # الرومات التي يعمل فيها Gemini فقط
        # =========================================================

        self.TARGET_CHANNEL_IDS = {
            1557727446663565412,
        }

        # =========================================================
        # قفل الطلبات
        # =========================================================

        self.lock = asyncio.Lock()

        # =========================================================
        # أقصى عدد رسائل محفوظة لكل روم
        #
        # 1000 رسالة تعتبر ذاكرة كبيرة جدًا.
        # =========================================================

        self.MAX_HISTORY_MESSAGES = 1000

        # =========================================================
        # حد حماية إضافي لحجم النص المرسل إلى Gemini
        #
        # يمنع وصول الذاكرة إلى حجم ضخم جدًا حتى لو كانت
        # الرسائل طويلة.
        # =========================================================

        self.MAX_HISTORY_CHARS = 700_000

        # =========================================================
        # شخصية Gemini
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
        # ذاكرة مؤقتة في RAM
        #
        # MongoDB هي الذاكرة الدائمة.
        # =========================================================

        self.conversation_history = {}

    # =============================================================
    # الحصول على مفتاح الذاكرة الخاص بالروم
    # =============================================================

    def get_memory_key(self, channel_id):
        return str(channel_id)

    # =============================================================
    # تحميل الذاكرة من MongoDB
    # =============================================================

    async def load_history(self, channel_id):

        memory_key = self.get_memory_key(channel_id)

        # إذا كانت موجودة في الذاكرة المؤقتة
        if memory_key in self.conversation_history:
            return self.conversation_history[memory_key]

        # إذا MongoDB غير متوفرة
        if self.memory_collection is None:
            self.conversation_history[memory_key] = []
            return []

        try:

            document = await asyncio.to_thread(
                self.memory_collection.find_one,
                {
                    "_id": memory_key
                }
            )

            if not document:
                self.conversation_history[memory_key] = []
                return []

            history = document.get("messages", [])

            # تنظيف البيانات القديمة
            cleaned_history = []

            for item in history:

                if (
                    isinstance(item, dict)
                    and item.get("role") in ("user", "model")
                    and isinstance(item.get("text"), str)
                ):
                    cleaned_history.append(item)

            self.conversation_history[memory_key] = cleaned_history

            return cleaned_history

        except Exception as e:

            print(f"⚠️ خطأ أثناء تحميل ذاكرة Gemini: {e}")

            self.conversation_history[memory_key] = []

            return []

    # =============================================================
    # حفظ الذاكرة في MongoDB
    # =============================================================

    async def save_history(self, channel_id, history):

        memory_key = self.get_memory_key(channel_id)

        # تحديث الذاكرة المحلية
        self.conversation_history[memory_key] = history

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

            print(f"⚠️ خطأ أثناء حفظ ذاكرة Gemini: {e}")

    # =============================================================
    # ترتيب وتنظيف الذاكرة
    # =============================================================

    def trim_history(self, history):

        # ---------------------------------------------------------
        # أولاً: عدد الرسائل
        # ---------------------------------------------------------

        if len(history) > self.MAX_HISTORY_MESSAGES:

            history = history[
                -self.MAX_HISTORY_MESSAGES:
            ]

        # ---------------------------------------------------------
        # ثانيًا: حجم النص
        # ---------------------------------------------------------

        total_chars = sum(
            len(item.get("text", ""))
            for item in history
        )

        while (
            total_chars > self.MAX_HISTORY_CHARS
            and len(history) > 2
        ):

            removed = history.pop(0)

            total_chars -= len(
                removed.get("text", "")
            )

        return history

    # =============================================================
    # تحويل الذاكرة إلى صيغة Gemini
    # =============================================================

    def build_gemini_history(self, history):

        result = []

        for item in history:

            role = item.get("role")
            text = item.get("text", "")

            if role not in ("user", "model"):
                continue

            if not text:
                continue

            result.append(
                types.Content(
                    role=role,
                    parts=[
                        types.Part.from_text(
                            text=text
                        )
                    ],
                )
            )

        return result

    # =============================================================
    # استقبال رسائل Discord
    # =============================================================

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):

        # =========================================================
        # تجاهل البوتات والرومات الأخرى
        # =========================================================

        if (
            message.author.bot
            or message.channel.id not in self.TARGET_CHANNEL_IDS
        ):
            return

        # =========================================================
        # إذا Gemini غير متصل
        # لا نرسل أي شيء للمستخدم
        # =========================================================

        if self.gemini_client is None:
            print("❌ Gemini متوقف لأن GEMINI_API_KEY غير موجود.")
            return

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
                    # إنشاء نسخة مؤقتة
                    #
                    # مهم جدًا:
                    # لا نحفظ رسالة المستخدم في MongoDB إلا بعد
                    # نجاح Gemini.
                    # =================================================

                    working_history = list(history)

                    working_history.append(
                        {
                            "role": "user",
                            "text": message.content
                        }
                    )

                    # =================================================
                    # تنظيف الذاكرة
                    # =================================================

                    working_history = self.trim_history(
                        working_history
                    )

                    # =================================================
                    # انتظار 3 ثواني
                    # =================================================

                    await asyncio.sleep(3)

                    # =================================================
                    # تحويل التاريخ إلى صيغة Gemini
                    # =================================================

                    gemini_contents = self.build_gemini_history(
                        working_history
                    )

                    # =================================================
                    # طلب Gemini
                    # =================================================

                    response = await asyncio.to_thread(
                        self.gemini_client.models.generate_content,
                        model="gemini-3.5-flash-lite",
                        contents=gemini_contents,
                        config=types.GenerateContentConfig(
                            system_instruction=self.system_prompt,
                        ),
                    )

                    # =================================================
                    # استخراج الرد
                    # =================================================

                    answer = getattr(
                        response,
                        "text",
                        None
                    )

                    # =================================================
                    # إذا Gemini لم يعطِ ردًا
                    # لا نحفظ الرسالة ولا نرسل شيئًا
                    # =================================================

                    if not answer or not answer.strip():

                        print(
                            "⚠️ Gemini لم يرجع نصًا."
                        )

                        return

                    answer = answer.strip()

                    # =================================================
                    # إضافة رد Gemini إلى نسخة الذاكرة
                    # =================================================

                    working_history.append(
                        {
                            "role": "model",
                            "text": answer
                        }
                    )

                    # =================================================
                    # تنظيف الذاكرة مرة أخرى
                    # =================================================

                    working_history = self.trim_history(
                        working_history
                    )

                    # =================================================
                    # حفظ الذاكرة بعد نجاح الطلب فقط
                    # =================================================

                    await self.save_history(
                        message.channel.id,
                        working_history
                    )

                    # =================================================
                    # تقسيم الرد إذا تجاوز حد Discord
                    # =================================================

                    if len(answer) <= 1900:

                        await message.reply(
                            answer
                        )

                    else:

                        chunks = []

                        current = ""

                        for word in answer.split():

                            if len(current) + len(word) + 1 > 1900:

                                chunks.append(current)

                                current = word

                            else:

                                if current:
                                    current += " "

                                current += word

                        if current:
                            chunks.append(current)

                        for index, chunk in enumerate(chunks):

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
                    # مهم:
                    # لا نرسل خطأ للمستخدم.
                    # فقط يظهر في Railway Logs.
                    # =================================================

                    print(
                        f"❌ خطأ في Gemini: {type(e).__name__}: {e}"
                    )

                    return


# =============================================================
# تحميل الـCog
# =============================================================

async def setup(bot):
    await bot.add_cog(
        GeminiAutoChatCog(bot)
    )
