import os
import discord
from discord.ext import commands
from google import genai

class AIAutoChatCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            print("⚠️ تحذير: مفتاح GEMINI_API_KEY غير موجود في متغيرات البيئة!")
        
        self.gemini_client = genai.Client(api_key=api_key)
        self.TARGET_CHANNEL_ID = 1547418557032308830

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.channel.id != self.TARGET_CHANNEL_ID:
            return

        async with message.channel.typing():
            try:
                response = self.gemini_client.models.generate_content(
                    model='gemini-3.5-flash',
                    contents=message.content,
                )
                
                answer = response.text

                if len(answer) > 1900:
                    answer = answer[:1900] + "\n\n... (تم اختصار الرد لطوله)"

                await message.reply(answer)

            except Exception as e:
                print(f"خطأ في الذكاء الاصطناعي: {e}")
                await message.reply("❌ حدث خطأ أثناء معالجة رد الذكاء الاصطناعي.")

async def setup(bot):
    await bot.add_cog(AIAutoChatCog(bot))
