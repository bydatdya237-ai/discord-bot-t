import os
import discord
from discord.ext import commands
from google import genai

class AIAutoChatCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        api_key = os.environ.get('GEMINI_API_KEY')
        self.gemini_client = genai.Client(api_key=api_key)
        
        # استبدل الأرقام تحت بـ "آيدي الروم" اللي تبي البوت يرد فيها تلقائياً بديسكورد
        self.TARGET_CHANNEL_ID = 123456789012345678

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.channel.id != self.TARGET_CHANNEL_ID:
            return

        async with message.channel.typing():
            try:
                response = self.gemini_client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=message.content,
                )
                
                answer = response.text

                if len(answer) > 1900:
                    answer = answer[:1900] + "\n\n... (تم اختصار الرد لطوله)"

                await message.reply(answer)

            except Exception as e:
                await message.reply("❌ حدث خطأ أثناء معالجة رد الذكاء الاصطناعي.")

async def setup(bot):
    await bot.add_cog(AIAutoChatCog(bot))

