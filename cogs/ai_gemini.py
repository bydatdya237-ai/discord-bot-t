import os
import asyncio

import discord
from discord.ext import commands
from google import genai
from google.genai import types


class GeminiAutoChatCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # =========================================================
        # Gemini API
        # هذا المفتاح مستقل تمامًا عن Groq
        # =========================================================

        api_key = os.environ.get("GEMINI_API_KEY")

        if not api_key:
            print("⚠️ تحذير: مفتاح GEMINI_API_KEY غير موجود في متغيرات البيئة!")
            self.gemini_client = None
        else:
            self.gemini_client = genai.Client(api_key=api_key)

        # =========================================================
        # الرومات التي يعمل فيها Gemini فقط
        # غيّر الأرقام إلى IDs الرومات التي تريدها
        # =========================================================

        self.TARGET_CHANNEL_IDS = {
            1557727446663565412,
        }

        # =========================================================
        # منع تشغيل أكثر من طلب Gemini بنفس الوقت
        # =========================================================

        self.lock = asyncio.Lock()

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

- إذا سألك أي شخص: "ما اسمك؟" أو "وش اسمك؟" أو "شو اسمك؟" أو
  "ما هو اسمك؟" أو "اسمك مين؟" أو أي سؤال مشابه عن اسمك،
  يجب أن تجيب بوضوح: "اسمي ضياء."

- إذا سألك أي شخص: "من طورك؟" أو "مين طورك؟" أو "من مطورك؟" أو
  "مين مطورك؟" أو "من برمجك؟" أو "مين اللي برمجك؟" أو أي سؤال
  مشابه عن المطور، يجب أن تجيب بوضوح: "المطور ضياء."

- لا تقل إن اسمك هو اسم الشخص الذي يتحدث معك.
- لا تخلط بين اسمك واسم المستخدم.
- لا تقل إن اسمك ذكاء اصطناعي أو AI. اسمك هو ضياء.
- عندما تُسأل عن مطورك، لا تذكر اسم أي شخص آخر.
- حافظ على سياق المحادثة.
- تحدث بشكل طبيعي وواضح.
"""

        # =========================================================
        # ذاكرة Gemini الخاصة به فقط
        # لا علاقة لها بذاكرة Groq
        # =========================================================

        self.conversation_history = []

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):

        # =========================================================
        # Gemini يعمل فقط في الرومات المحددة هنا
        # =========================================================

        if (
            message.author.bot
            or message.channel.id not in self.TARGET_CHANNEL_IDS
        ):
            return

        # =========================================================
        # التأكد من وجود مفتاح Gemini
        # =========================================================

        if self.gemini_client is None:
            print("❌ GEMINI_API_KEY غير موجود.")
            return

        async with self.lock:
            async with message.channel.typing():
                try:

                    # =================================================
                    # إضافة رسالة المستخدم إلى ذاكرة Gemini
                    # =================================================

                    self.conversation_history.append(
                        types.Content(
                            role="user",
                            parts=[
                                types.Part.from_text(
                                    text=message.content
                                )
                            ],
                        )
                    )

                    # =================================================
                    # الاحتفاظ بآخر 10 رسائل فقط
                    # =================================================

                    if len(self.conversation_history) > 10:
                        self.conversation_history = (
                            self.conversation_history[-10:]
                        )

                    # =================================================
                    # انتظار 3 ثواني
                    # =================================================

                    await asyncio.sleep(3)

                    # =================================================
                    # إرسال الطلب إلى Gemini
                    # =================================================

                    response = await asyncio.to_thread(
                        self.gemini_client.models.generate_content,
                        model="gemini-2.5-flash-lite",
                        contents=self.conversation_history,
                        config=types.GenerateContentConfig(
                            system_instruction=self.system_prompt,
                        ),
                    )

                    answer = response.text

                    if not answer:
                        answer = "❌ لم أستطع إنشاء رد حاليًا."

                    # =================================================
                    # إضافة رد Gemini إلى ذاكرته الخاصة
                    # =================================================

                    self.conversation_history.append(
                        types.Content(
                            role="model",
                            parts=[
                                types.Part.from_text(
                                    text=answer
                                )
                            ],
                        )
                    )

                    # =================================================
                    # Discord يسمح بحوالي 2000 حرف للرسالة
                    # =================================================

                    if len(answer) > 1900:
                        answer = (
                            answer[:1900]
                            + "\n\n... (تم اختصار الرد لطوله)"
                        )

                    await message.reply(answer)

                except Exception as e:
                    print(f"❌ خطأ في Gemini: {e}")

                    await message.reply(
                        "❌ حدث خطأ أثناء معالجة رد Gemini."
                    )


async def setup(bot):
    await bot.add_cog(GeminiAutoChatCog(bot))
