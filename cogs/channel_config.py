import os
import discord
from discord.ext import commands
from pymongo import MongoClient

# 1. قائمة منسدلة متعددة الاختيارات للأوامر
class CommandSelect(discord.ui.Select):
    def __init__(self, bot):
        self.bot = bot
        options = []
        
        for command in bot.commands:
            if command.name in ["help", "تحديد-رومات"]:
                continue
            options.append(
                discord.SelectOption(
                    label=f"!{command.name}",
                    description=command.help or "تحديد روم مخصص لهذا الأمر",
                    emoji="⚙️"
                )
            )
            
        if not options:
            options.append(discord.SelectOption(label="لا توجد أوامر متاحة", value="none"))

        # السماح باختيار عدة أوامر مع بعض (الحد الأقصى عدد الأوامر المتوفرة أو 25 كحد أقصى لديسكورد)
        max_val = min(len(options), 25)
        super().__init__(placeholder="اختر أمراً أو عدة أوامر لتحديد روم لها...", min_values=1, max_values=max_val, options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_commands = [val.replace("!", "") for val in self.values]
        
        # حفظ الأوامر المختارة في الكلاس المؤقت لنقلها لخطوة التأكيد
        self.view.selected_commands = selected_commands
        
        await interaction.response.send_message(
            f"🎯 لقد اخترت الأوامر التالية:\n`" + ", ".join(f"!{c}" for c in selected_commands) + f"`\n\nالرجاء إرسال **آيدي الغرفة (Channel ID)** المستهدفة في الشات خلال دقيقة واحدة:",
            ephemeral=True
        )

        def check(m):
            return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id

        try:
            msg = await self.bot.wait_for('message', timeout=60.0, check=check)
            new_channel_id = msg.content.strip()
            
            if not new_channel_id.isdigit():
                await interaction.followup.send("❌ عذراً، يجب أن يكون آيدي الغرفة أرقاماً فقط. إلغاء العملية.", ephemeral=True)
                return

            self.view.target_channel_id = new_channel_id

            try:
                await msg.delete()
            except:
                pass

        except Exception as e:
            await interaction.followup.send("⏱️ انتهى الوقت المخصص ولم تقم بإرسال آيدي الغرفة.", ephemeral=True)
            return

        # إرسال زر التأكيد النهائي
        confirm_view = ConfirmView(self.bot, selected_commands, new_channel_id)
        await interaction.followup.send(
            f"⚠️ هل أنت متأكد من ربط هذه الأوامر بالغرفة <#{new_channel_id}>؟",
            view=confirm_view,
            ephemeral=True
        )

# 2. زر التأكيد النهائي للعملية
class ConfirmView(discord.ui.View):
    def __init__(self, bot, selected_commands, channel_id):
        super().__init__(timeout=30)
        self.bot = bot
        self.selected_commands = selected_commands
        self.channel_id = channel_id

    @discord.ui.button(label="تأكيد الربط", style=discord.ButtonStyle.green, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        mongo_url = os.environ.get('MONGO_URI')
        client = MongoClient(mongo_url)
        db = client['discord_db']
        collection = db['command_channels']

        # حفظ كل أمر تم تحديده في قاعدة البيانات مع نفس الروم
        for cmd in self.selected_commands:
            collection.update_one(
                {"guild_id": interaction.guild.id, "command_name": cmd},
                {"$set": {"channel_id": int(self.channel_id)}},
                upsert=True
            )

        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(
            content=f"✅ تمت الإفادة بنجاح! تم ربط الأوامر المحددة بالغرفة <#{self.channel_id}>.",
            view=self

        )

    @discord.ui.button(label="إلغاء", style=discord.ButtonStyle.red, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content="❌ تم إلغاء العملية.", view=self)

class CommandConfigView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=60)
        self.add_item(CommandSelect(bot))

class ChannelConfigCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="تحديد-رومات", help="فتح لوحة لتحديد الروم المخصص لأوامر متعددة دفعة واحدة")
    async def config_channels(self, ctx):
        if ctx.author.id != ctx.guild.owner_id:
            await ctx.send("❌ عذراً، هذا الأمر مخصص لصاحب السيرفر فقط!")
            return

        embed = discord.Embed(
            title="🛠️ نظام إدارة رومات الأوامر المتعددة",
            description="حدد الأوامر المطلوبة من القائمة أدناه (يمكنك اختيار أكثر من أمر)، ثم أرسل آيدي الروم لتأكيد الربط:",
            color=discord.Color.gold()
        )
        
        view = CommandConfigView(self.bot)
        await ctx.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(ChannelConfigCog(bot))
