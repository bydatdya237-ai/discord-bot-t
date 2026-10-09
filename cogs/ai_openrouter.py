import os
import asyncio
import discord

from discord.ext import commands
from openai import OpenAI
from pymongo import MongoClient


# =====================================================
# إعدادات OpenRouter
# =====================================================

class OpenRouterAutoChatCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.client = None
        self.mongo_client = None
        self.memory_collection = None

        # =================================================
        # API KEY
        # =================================================

        api_key = os.environ.get("OPENROUTER_API_KEY")

        if api_key:
            try:
                self.client = OpenAI(
                    api_key=api_key,
                    base_url="https://openrouter.ai/api/v1",
                    default_headers={
                        "X-Title": "Diaa Discord Bot"
                    },
                    timeout=45.0,
                    max_retries=1
                )

                print("✅ OpenRouter API جاهز")

            except Exception as e:
                print(
                    f"❌ OpenRouter initialization: "
                    f"{type(e).__name__}: {e}"
                )
        else:
            print("⚠️ OPENROUTER_API_KEY غير موجود")

        # =================================================
        # MongoDB - ذاكرة مستقلة تماماً
        # =================================================

        mongo_uri = os.environ.get("MONGO_URI")

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

                print("✅ OpenRouter memory جاهزة")

            except Exception as e:
                print(
                    f"❌ MongoDB initialization: "
                    f"{type(e).__name__}: {e}"
                )
        else:
            print("⚠️ MONGO_URI غير موجود")

        # =================================================
        # آيدي الروم - غيّره إلى آيدي رومك الحقيقي
        # =================================================

        self.TARGET_CHANNEL_IDS = {
            1550000000000000000
        }

        # =================================================
        # إعدادات الذاكرة والسياق
        # =================================================

        self.MAX_HISTORY_MESSAGES = 1000
        self.MAX_HISTORY_CHARS = 300000
        self.CONTEXT_MESSAGES = 12

        self.lock = asyncio.Lock()
        self.history_cache = {}

        # =================================================
        # تعليمات الذكاء الاصطناعي
        # =================================================

        self.system_prompt = """
أنت ضياء، مساعد ذكاء اصطناعي داخل سيرفر ديسكورد.
مطورك هو ضياء.

اللغة والأسلوب:
- أجب بالعربية دائمًا، حتى لو كان السؤال بالإنجليزية.
- استخدم لهجة عربية طبيعية وبسيطة ومفهومة.
- لا تستخدم الإنجليزية إلا إذا طلب المستخدم ذلك أو احتجت إلى مصطلح تقني.
- لا تبدأ كل إجابة بعبارات متكررة مثل: بالتأكيد، بالطبع، يسعدني مساعدتك.
- كن ودودًا وطبيعيًا، ولا تتحدث بأسلوب رسمي جامد.

فهم الأسئلة:
- اقرأ السؤال جيدًا وحدد المطلوب قبل الإجابة.
- أجب عن السؤال نفسه مباشرة، ولا تغيّر الموضوع.
- راعِ الرسائل السابقة لفهم سياق المحادثة.
- إذا كان السؤال غير واضح فعلًا، اطلب توضيحًا قصيرًا.
- لا تكرر كلام المستخدم دون فائدة.

جودة الإجابات:
- أعطِ إجابات دقيقة ومفيدة ومباشرة.
- لا تخترع معلومات أو حقائق أو مصادر.
- إذا لم تكن متأكدًا من معلومة، وضّح ذلك بصدق.
- اشرح التفاصيل عندما يحتاج السؤال إلى شرح.
- اجعل الإجابات البسيطة قصيرة، والأسئلة المعقدة مفصلة بقدر الحاجة.
- في الأسئلة التقنية، اشرح بطريقة سهلة ومفهومة.

هويتك:
- إذا سُئلت عن اسمك، قل: اسمي ضياء.
- إذا سُئلت عن مطورك، قل: المطور ضياء.
- لا تدّعِ أنك إنسان حقيقي.

أنت مساعد عام، ويمكنك المساعدة في البرمجة والتقنية
والألعاب والمعلومات العامة والمحادثات اليومية.
"""

    # =====================================================
    # تحميل الذاكرة من MongoDB
    # =====================================================

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
                    f"❌ Memory load error: "
                    f"{type(e).__name__}: {e}"
                )

        self.history_cache[key] = history
        return history

    # =====================================================
    # حفظ الذاكرة
    # =====================================================

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
                    f"❌ Memory save error: "
                    f"{type(e).__name__}: {e}"
                )

    # =====================================================
    # تقليل حجم الذاكرة
    # =====================================================

    def trim_history(self, history):

        history = history[-self.MAX_HISTORY_MESSAGES:]

        result = []
        total_chars = 0

        for item in reversed(history):

            content = item.get("content", "")
            size = len(content)

            if total_chars + size > self.MAX_HISTORY_CHARS:
                break

            result.append(item)
            total_chars += size

        result.reverse()
        return result

    # =====================================================
    # تقسيم الرسائل الطويلة
    # =====================================================

    def split_message(self, content, limit=1900):

        return [
            content[i:i + limit]
            for i in range(0, len(content), limit)
        ]

    # =====================================================
    # استقبال رسائل ديسكورد
    # =====================================================

    @commands.Cog.listener()
    async def on_message(self, message):

        # تجاهل البوتات
        if message.author.bot:
            return

        # تجاهل جميع الرومات الأخرى
        if message.channel.id not in self.TARGET_CHANNEL_IDS:
            return

        # التأكد من وجود API
        if self.client is None:
            print("⚠️ OpenRouter client غير جاهز")
            return

        content = message.content.strip()

        if not content:
            return

        async with self.lock:

            channel_id = message.channel.id
            history = self.load_history(channel_id)

            # حفظ رسالة العضو
            history.append({
                "role": "user",
                "content": (
                    f"اسم العضو: {message.author.display_name}\n"
                    f"الرسالة: {content[:4000]}"
                )
            })

            history = self.trim_history(history)
            self.save_history(channel_id, history)

            try:

                async with message.channel.typing():

                    # تأخير طبيعي قبل الرد
                    await asyncio.sleep(3)

                    context = history[-self.CONTEXT_MESSAGES:]

                    api_messages = [
                        {
                            "role": "system",
                            "content": self.system_prompt
                        }
                    ] + context

                    # النموذج المجاني فقط
                    response = await asyncio.to_thread(
                        self.client.chat.completions.create,
                        model="openrouter/free",
                        messages=api_messages,
                        max_tokens=500,
                        temperature=0.5
                    )

                # استخراج الرد
                if not response.choices:
                    print("⚠️ OpenRouter لم يُرجع أي إجابة")
                    return

                answer = response.choices[0].message.content

                if not isinstance(answer, str) or not answer.strip():
                    print("⚠️ OpenRouter أعاد إجابة فارغة")
                    return

                answer = answer.strip()

                # حفظ إجابة الذكاء الاصطناعي
                history.append({
                    "role": "assistant",
                    "content": answer
                })

                history = self.trim_history(history)
                self.save_history(channel_id, history)

                # إرسال الإجابة إلى ديسكورد
                for part in self.split_message(answer):

                    await message.reply(
                        part,
                        mention_author=False
                    )

            except Exception as e:

                # الأخطاء في Railway فقط
                print(
                    f"❌ OpenRouter API error: "
                    f"{type(e).__name__}: {e}"
                )


# =====================================================
# تشغيل الملف
# =====================================================

async def setup(bot):
    await bot.add_cog(OpenRouterAutoChatCog(bot))
