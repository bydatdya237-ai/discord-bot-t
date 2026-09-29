import asyncio
import discord
from discord.ext import commands


# =========================================================
# الإعدادات
# =========================================================

ALLOWED_ROLE_ID = 1544078469657530578

# مدة العملية الوهمية
HACK_DURATION = 45


class FakeHack(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="اختراق")
    @commands.guild_only()
    async def fake_hack(self, ctx, member: discord.Member = None):

        # =================================================
        # التحقق من الرتبة
        # =================================================

        allowed_role = ctx.guild.get_role(ALLOWED_ROLE_ID)

        if allowed_role is None or allowed_role not in ctx.author.roles:
            return

        # =================================================
        # التأكد من وجود شخص مستهدف
        # =================================================

        if member is None:
            await ctx.send(
                "❌ **طريقة الاستخدام:**\n"
                "`اختراق @الشخص`"
            )
            return

        # =================================================
        # بداية العملية الوهمية
        # =================================================

        message = await ctx.send(
            f"💻 **بدء عملية الاختراق لـ {member.mention}...**\n\n"
            "⚠️ جاري تهيئة النظام..."
        )

        stages = [
            ("🔐 جاري الاتصال بالنظام...", 7),
            ("🌐 جاري تجاوز جدار الحماية...", 7),
            ("📡 جاري الوصول إلى الخادم...", 7),
            ("🔎 جاري البحث عن البيانات...", 7),
            ("📂 جاري استخراج الملفات...", 7),
            ("⚡ جاري إنهاء العملية...", 7),
        ]

        # =================================================
        # مراحل الاختراق الوهمية
        # =================================================

        for stage, delay in stages:

            await asyncio.sleep(delay)

            try:
                await message.edit(
                    content=(
                        f"💻 **عملية اختراق وهمية لـ {member.mention}**\n\n"
                        f"{stage}"
                    )
                )

            except discord.NotFound:
                return

            except discord.HTTPException:
                pass

        # =================================================
        # النتيجة
        # =================================================

        await asyncio.sleep(3)

        try:
            await message.edit(
                content=(
                    f"✅ **تمت عملية الاختراق بنجاح!**\n\n"
                    f"🎯 الهدف: {member.mention}\n"
                    "📦 تم تجهيز البيانات المستخرجة.\n"
                    "📩 **سيتم إرسال البيانات على الخاص...**"
                )
            )

        except discord.NotFound:
            return

        # =================================================
        # إرسال رسالة للشخص المستهدف
        # =================================================

        try:
            await member.send(
                "🚨 **تنبيه أمني** 🚨\n\n"
                "💻 تم اختراق حسابك بنجاح!\n"
                "📂 جاري تجهيز البيانات...\n\n" 
            )

        except discord.Forbidden:
            # إذا كانت الخاصية مغلقة عند الشخص
            pass

        except discord.HTTPException:
            pass


# =========================================================
# تحميل الـ Cog
# =========================================================

async def setup(bot):
    await bot.add_cog(FakeHack(bot))
