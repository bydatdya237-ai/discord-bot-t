import os
import discord
from discord.ext import commands
from pymongo import MongoClient

# 1. قائمة منسدلة لاختيار الأمر المراد تحديد روم له
class CommandSelect(discord.ui.Select):
    def __init__(self, bot):
        self.bot = bot
        options = []
        
        # جلب جميع الأوامر المسجلة في البوت تلقائياً (حتى لو أضيفت مستقبلاً)
        for command in bot.commands:
            # استثناء أوامر النظام الداخلية إن وجدت
            if command.name in ["help"]:
                continue
            options.append(
                discord.SelectOption(
                    label=f"!{command.name}",
                    description=command.help or "تحديد روم مخصص لهذا الأمر",
                    emoji="⚙️"
                )
            )
            
        # لو ما فيه أوامر كفاية
        if not options:
            options.append(discord.SelectOption(label="لا توجد أوامر متاحة", value="none"))

        super().__init__(placeholder="اختر الأمر الذي تريد تحديد روم له...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_command = self.values[0].replace("!", "")
        
        # نطلب منه إرسال آيدي الغرفة أو منشنها في الراتش (أو نفتح له مودال، لكن الأسهل يكتب الآيدي بالرسالة أو نستخدم Modal)
        await interaction.response.send_message(
            f"🎯 لقد اخترت الأمر **`!{selected_command}`**.\nالرجاء إرسال **آيدي الغرفة (Channel ID)** الجديدة المخصصة لهذا الأمر في الشات خلال دقيقة واحدة:",
            ephemeral=True
        )

        def check(m):
            return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id

        try:
            msg = await self.bot.wait_for('message', timeout=60.0, check=check)
            new_channel_id = msg.content.strip()
            
            # تحقق بسيط لو أدخل آيدي رقمي
            if not new_channel_id.isdigit():
                await interaction.followup.send("❌ عذراً، يجب أن يكون آيدي الغرفة أرقاماً فقط. إلغاء العملية.", ephemeral=True)
                return

            # حفظ التعديل في قاعدة البيانات
            mongo_url = os.environ.get('MONGO_URI')
            client = MongoClient(mongo_url)
            db = client['discord_db']
            collection = db['command_channels']

            collection.update_one(
                {"guild_id": interaction.guild.id, "command_name": selected_command},
                {"$set": {"channel_id": int(new_channel_id)}},
                upsert=True
            )

            await interaction.followup.send(f"✅ تم بنجاح ربط الأمر **`!{selected_command}`** بالغرفة <#{new_channel_id}>!", ephemeral=True)
            
            # محاولة حذف رسالة الآيدي لتنظيف الشات (اختياري)
            try:
                await msg.delete()
            except:
                pass

        except Exception as e:
            await interaction.followup.send("⏱️ انتهى الوقت المخصص ولم تقم بإرسال آيدي الغرفة.", ephemeral=True)

class CommandConfigView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=60)
        self.add_item(CommandSelect(bot))

class ChannelConfigCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="تحديد-رومات", help="فتح لوحة لتحديد الروم المخصص لكل أمر")
    async def config_channels(self, ctx):
        # التحقق أن المستخدم هو صاحب السيرفر فقط
        if ctx.author.id != ctx.guild.owner_id:
            await ctx.send("❌ عذراً، هذا الأمر مخصص لصاحب السيرفر فقط!")
            return

        embed = discord.Embed(
            title="🛠️ نظام إدارة رومات الأوامر",
            description="اختر الأمر من القائمة المنسدلة أدناه لتحديد الروم المخصص له:",
            color=discord.Color.gold()
        )
        
        view = CommandConfigView(self.bot)
        await ctx.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(ChannelConfigCog(bot))
