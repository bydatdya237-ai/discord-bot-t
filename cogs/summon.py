import discord
from discord.ext import commands


class SummonCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # الروم المسموح باستخدام أمر الاستدعاء فيه فقط
        self.COMMAND_ROOM_ID = 1546860236227215400

        # الرتب المسموح لها باستخدام الأمر
        self.ALLOWED_ROLE_IDS = {
            1544078469657530578,
            1545851911121666108
        }

    @commands.command(name="استدعاء")
    async def summon(self, ctx, member: discord.Member):

        # التأكد أن الأمر مستخدم في الروم المحدد
        if ctx.channel.id != self.COMMAND_ROOM_ID:
            await ctx.send(
                "❌ لا يمكنك استخدام أمر الاستدعاء في هذا الروم."
            )
            return

        # التأكد أن المستخدم لديه إحدى الرتبتين
        if not any(role.id in self.ALLOWED_ROLE_IDS for role in ctx.author.roles):
            await ctx.send(
                "❌ ليس لديك صلاحية لاستخدام أمر الاستدعاء!"
            )
            return

        # طلب ID الروم
        await ctx.send(
            "📍 **أرسل الآن ID الروم الذي يجب أن يتوجه إليه الشخص.**\n"
            "لديك 60 ثانية."
        )

        def check_channel(message):
            return (
                message.author.id == ctx.author.id
                and message.channel.id == ctx.channel.id
            )

        try:
            channel_message = await self.bot.wait_for(
                "message",
                timeout=60,
                check=check_channel
            )

            try:
                target_room_id = int(channel_message.content.strip())
            except ValueError:
                await ctx.send(
                    "❌ ID الروم غير صحيح. يجب أن ترسل أرقام ID الروم فقط."
                )
                return

        except asyncio.TimeoutError:
            await ctx.send("⏰ انتهى الوقت ولم يتم إدخال ID الروم.")
            return

        # محاولة جلب الروم
        try:
            target_channel = self.bot.get_channel(target_room_id)

            if target_channel is None:
                target_channel = await self.bot.fetch_channel(target_room_id)

        except discord.NotFound:
            await ctx.send("❌ لم يتم العثور على الروم بهذا الـ ID.")
            return

        except discord.Forbidden:
            await ctx.send("❌ البوت لا يملك صلاحية الوصول إلى هذا الروم.")
            return

        except discord.HTTPException:
            await ctx.send("❌ حدث خطأ أثناء جلب الروم.")
            return

        # طلب سبب الاستدعاء
        await ctx.send(
            "📝 **اكتب الآن سبب الاستدعاء.**\n"
            "لديك 60 ثانية."
        )

        try:
            reason_message = await self.bot.wait_for(
                "message",
                timeout=60,
                check=check_channel
            )

            reason = reason_message.content.strip()

            if not reason:
                await ctx.send("❌ يجب كتابة سبب الاستدعاء.")
                return

        except asyncio.TimeoutError:
            await ctx.send("⏰ انتهى الوقت ولم يتم إدخال سبب الاستدعاء.")
            return

        # تجهيز رسالة الاستدعاء
        embed = discord.Embed(
            title="🚨 تنبيه استدعاء رسمي",
            description="لقد تم استدعاؤك للتوجه إلى الروم المحدد.",
            color=discord.Color.red()
        )

        embed.add_field(
            name="📍 الروم المطلوب:",
            value=target_channel.mention,
            inline=False
        )

        embed.add_field(
            name="📝 سبب الاستدعاء:",
            value=reason,
            inline=False
        )

        embed.set_footer(
            text=f"بواسطة المشرف: {ctx.author.name}"
        )

        # إرسال الرسالة الخاصة للشخص
        try:
            await member.send(embed=embed)
            dm_status = "✉️ تم إرسال رسالة خاصة له."

        except discord.Forbidden:
            dm_status = "⚠️ تعذر إرسال رسالة خاصة، يرجى فتح الخاص."

        except discord.HTTPException:
            dm_status = "⚠️ حدث خطأ أثناء إرسال الرسالة الخاصة."

        # تأكيد العملية
        await ctx.send(
            f"✅ تم استدعاء {member.mention} بنجاح إلى {target_channel.mention}\n"
            f"{dm_status}"
        )

    @summon.error
    async def summon_error(self, ctx, error):

        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(
                "⚠️ الصيغة خاطئة. استخدم الأمر هكذا:\n"
                "`!استدعاء @الشخص`"
            )

        elif isinstance(error, commands.MemberNotFound):
            await ctx.send(
                "❌ لم أتمكن من العثور على هذا العضو."
            )


async def setup(bot):
    await bot.add_cog(SummonCog(bot))
