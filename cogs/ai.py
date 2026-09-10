import os
import asyncio
import discord
from discord.ext import commands
from groq import Groq

class AIAutoChatCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        api_key = os.environ.get('GROQ_API_KEY') or os.environ.get('GEMINI_API_KEY')
        if not api_key:
            print("⚠️ تحذير: مفتاح API غير موجود في متغيرات البيئة!")
        
        self.groq_client = Groq(api_key=api_key)
        self.TARGET_CHANNEL_ID = 1546187533044424785
        self.lock = asyncio.Lock()

        # رسالة النظام الثابتة للتعريف بالشخصية والاسم "ضياء"
        self.system_prompt = {
            "role": "system",
            "content": """أنت مساعد ذكاء اصطناعي داخل سيرفر ديسكورد. تحدث باللغة العربية دائمًا وبأسلوب طبيعي وواضح. لا تستخدم اللغة الإنجليزية إلا إذا طلب المستخدم ذلك صراحة.

اسمك أنت هو: ضياء.
مطورك هو: ضياء.

مهم جدًا:
- إذا سألك أي شخص: "ما اسمك؟" أو "وش اسمك؟" أو "شو اسمك؟" أو "ما هو اسمك؟" أو "اسمك مين؟" أو أي سؤال مشابه عن اسمك، يجب أن تجيب بوضوح: "اسمي ضياء."
- إذا سألك أي شخص: "من طورك؟" أو "مين طورك؟" أو "من مطورك؟" أو "مين مطورك؟" أو "من برمجك؟" أو "مين اللي برمجك؟" أو أي سؤال مشابه عن المطور، يجب أن تجيب بوضوح: "المطور ضياء."
- لا تقل إن اسمك هو اسم الشخص الذي يتحدث معك.
- لا تخلط بين اسمك واسم المستخدم.
- لا تقل إن اسمك ذكاء اصطناعي أو AI. اسمك هو ضياء.
- عندما يُسأل عن مطورك، لا تذكر اسم أي شخص آخر. المطور هو ضياء.
- حافظ على سياق المحادثة وتحدث بشكل طبيعي وواضح."""

        }
        
        # ذاكرة مؤقتة تحفظ آخر الرسائل فقط لضمان السرعة وعدم الثقل
        self.conversation_history = []

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.channel.id != self.TARGET_CHANNEL_ID:
            return

        async with self.lock:
            async with message.channel.typing():
                try:
                    # إضافة رسالة المستخدم الجديدة للذاكرة
                    self.conversation_history.append({"role": "user", "content": message.content})
                    
                    # الاحتفاظ بآخر 10 رسائل فقط عشان يبقى البوت سريع وما يثقل
                    if len(self.conversation_history) > 10:
                        self.conversation_history = self.conversation_history[-10:]

                    # تجميع الرسائل مع رسالة النظام الأساسية للإرسال
                    payload_messages = [self.system_prompt] + self.conversation_history

                    chat_completion = await asyncio.to_thread(
                        self.groq_client.chat.completions.create,
                        model="llama-3.1-8b-instant",  # أسرع وأقوى موديل على Groq
                        messages=payload_messages
                    )
                    
                    answer = chat_completion.choices[0].message.content

                    # إضافة رد البوت للذاكرة عشان يربط الكلام ببعضه
                    self.conversation_history.append({"role": "assistant", "content": answer})

                    if len(answer) > 1900:
                        answer = answer[:1900] + "\n\n... (تم اختصار الرد لطوله)"

                    await message.reply(answer)

                except Exception as e:
                    print(f"خطأ في الذكاء الاصطناعي: {e}")
                    await message.reply("❌ حدث خطأ أثناء معالجة رد الذكاء الاصطناعي.")

async def setup(bot):
    await bot.add_cog(AIAutoChatCog(bot))
