import discord
from discord.ext import commands

class SummonCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # آي دي الروم الجديد اللي حددته للاستدعاء
        self.TARGET_ROOM_ID = 1546860236227215400  

    @commands.command(name="استدعاء")
    @commands.has_permissions(manage_messages=True) # شرط: المشرف أو الإداري فقط يقدر يستعمله
    async def summon(self, ctx, member: discord.Member):
        try:
            # جلب الروم المستهدف باستخدام الأي دي الجديد
            channel = self.bot.get_channel(self.TARGET_ROOM_ID)
            
            if not channel:
                await ctx.send("❌ عذراً، لم يتم العثور على روم الاستدعاء المحدد.")
                return

            # تجهيز رسالة الاستدعاء المرتبة
            embed = discord.Embed(
                title="🚨 تنبيه استدعاء رسمي",
                description=f"لقد تم استدعاؤك للتواجد في الروم المخصص.",
                color=discord.Color.red()
            )
            embed.add_field(name="الروم المطلوب:", value=channel.mention, inline=False)
            embed.set_footer(text=f"بواسطة المشرف: {ctx.author.name}")

            # محاولة إرسال رسالة خاصة للشخص المستدعى
            dm_status = ""
            try:
                await member.send(embed=embed)
                dm_status = "✉️ (تم إرسال رسالة خاصة له)"
            except:
                dm_status = "⚠️ (تعذر إرسال رسالة خاصة، يرجى فتح الخاص)"

            # الرد في الروم العام بتأكيد العملية
            await ctx.send(f"تم استدعاء {member.mention} بنجاح إلى {channel.mention} {dm_status}")

        except Exception as e:
            print(f"خطأ في أمر الاستدعاء: {e}")
            await ctx.send("❌ حدث خطأ أثناء تنفيذ أمر الاستدعاء.")

    @summon.error
    async def summon_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ ليس لديك صلاحية لاستخدام أمر الاستدعاء!")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("⚠️ الصيغة خاطئة. استخدم الأمر هكذا: `!استدعاء @الشخص`")

async def setup(bot):
    await bot.add_cog(SummonCog(bot))
