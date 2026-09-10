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

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.channel.id != self.TARGET_CHANNEL_ID:
            return

        async with self.lock:
            async with message.channel.typing():
                try:
                    chat_completion = self.groq_client.chat.completions.create(
                        model="openai/gpt-oss-20b",
                        messages=[
                            {"role": "user", "content": message.content}
                        ]
                    )
                    
                    answer = chat_completion.choices[0].message.content

                    if len(answer) > 1900:
                        answer = answer[:1900] + "\n\n... (تم اختصار الرد لطوله)"

                    await message.reply(answer)

                except Exception as e:
                    print(f"خطأ في الذكاء الاصطناعي: {e}")
                    await message.reply("❌ حدث خطأ أثناء معالجة رد الذكاء الاصطناعي.")

async def setup(bot):
    await bot.add_cog(AIAutoChatCog(bot))
