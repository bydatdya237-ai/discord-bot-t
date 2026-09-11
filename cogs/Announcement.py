import re
import discord
from discord.ext import commands


# =========================================================
# الإعدادات
# =========================================================

# الروم الذي يقرأ منه البوت رسالة التوب
SOURCE_CHANNEL_ID = 1544380230058115244

# الروم الذي يسمح فيه باستخدام -اعلن
COMMAND_ROOM_ID = 1547711993568305232

# الروم الذي يرسل فيه الإعلان
ANNOUNCEMENT_CHANNEL_ID = 1547571126736134144


# =========================================================
# الرتب المسموح لها باستخدام -اعلن
# =========================================================

ALLOWED_ROLE_IDS = {
    1544078469657530578,
    1545851911121666108,
    1544349016043692103,
    1544426415766896690,
}


# =========================================================
# الجوائز
# =========================================================

FIRST_GOLD = 450
FIRST_AI = 250_000

SECOND_GOLD = 250
SECOND_AI = 150_000

THIRD_GOLD = 100
THIRD_AI = 50_000


# =========================================================
# استخراج النص من الرسالة
# =========================================================

def get_message_text(message):
    texts = []

    # -----------------------------------------------------
    # محتوى الرسالة العادي
    # -----------------------------------------------------

    if message.content:
        texts.append(message.content)

    # -----------------------------------------------------
    # الـ Embeds
    # -----------------------------------------------------

    for embed in message.embeds:

        if embed.title:
            texts.append(embed.title)

        if embed.description:
            texts.append(embed.description)

        if embed.author and embed.author.name:
            texts.append(embed.author.name)

        if embed.footer and embed.footer.text:
            texts.append(embed.footer.text)

        for field in embed.fields:

            if field.name:
                texts.append(field.name)

            if field.value:
                texts.append(field.value)

    return "\n".join(texts)


# =========================================================
# استخراج أول 3 مراكز
# =========================================================

def extract_top_3(message):

    text = get_message_text(message)

    if not text:
        return None

    results = {}

    # -----------------------------------------------------
    # الشكل الأساسي:
    #
    # #`1` I <@!724763668037894155> I `1.50t`
    # #`2` I <@!1523454188330418339> I `287.25b`
    # #`3` I <@!1498403413157744852> I `62.25b`
    #
    # -----------------------------------------------------

    pattern = re.compile(
        r"#\s*`?\s*(1|2|3)\s*`?"
        r"\s*(?:I|\|)"
        r"\s*<@!?(\d+)>",
        re.IGNORECASE
    )

    for match in pattern.finditer(text):

        rank = int(match.group(1))
        user_id = int(match.group(2))

        if rank not in results:
            results[rank] = user_id

    # -----------------------------------------------------
    # طريقة احتياطية
    # -----------------------------------------------------

    if len(results) < 3:

        for line in text.splitlines():

            rank_match = re.search(
                r"#\s*`?\s*(1|2|3)\s*`?",
                line
            )

            mention_match = re.search(
                r"<@!?(\d+)>",
                line
            )

            if rank_match and mention_match:

                rank = int(rank_match.group(1))
                user_id = int(mention_match.group(1))

                if rank not in results:
                    results[rank] = user_id

    # -----------------------------------------------------
    # نتأكد أن المراكز الثلاثة موجودة
    # -----------------------------------------------------

    if (
        1 in results
        and 2 in results
        and 3 in results
    ):
        return results

    return None


# =========================================================
# التحقق من الرتب
# =========================================================

def has_allowed_role(member):

    return any(
        role.id in ALLOWED_ROLE_IDS
        for role in member.roles
    )


# =========================================================
# Announcement Cog
# =========================================================

class AnnouncementCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    # =====================================================
    # -اعلن
    # =====================================================

    @commands.command(name="اعلن")
    async def announce_top(self, ctx):

        # -------------------------------------------------
        # يجب أن يكون الأمر في الروم المحدد
        # -------------------------------------------------

        if ctx.channel.id != COMMAND_ROOM_ID:
            return

        # -------------------------------------------------
        # التحقق من الرتبة
        # -------------------------------------------------

        if not has_allowed_role(ctx.author):
            return

        # -------------------------------------------------
        # الحصول على روم التوب
        # -------------------------------------------------

        source_channel = self.bot.get_channel(
            SOURCE_CHANNEL_ID
        )

        if source_channel is None:

            await ctx.send(
                "❌ لم أستطع الوصول إلى روم التوب."
            )

            return

        # -------------------------------------------------
        # الحصول على روم الإعلان
        # -------------------------------------------------

        announcement_channel = self.bot.get_channel(
            ANNOUNCEMENT_CHANNEL_ID
        )

        if announcement_channel is None:

            await ctx.send(
                "❌ لم أستطع الوصول إلى روم الإعلان."
            )

            return

        # -------------------------------------------------
        # رسالة الانتظار
        # -------------------------------------------------

        loading_message = await ctx.send(
            "⏳ جاري قراءة التوب وتجهيز الإعلان..."
        )

        try:

            # =================================================
            # البحث في آخر 30 رسالة في روم التوب
            # =================================================

            top_data = None

            async for message in source_channel.history(
                limit=30
            ):

                data = extract_top_3(message)

                if data is not None:

                    top_data = data

                    break

            # =================================================
            # لم يجد رسالة التوب
            # =================================================

            if top_data is None:

                await loading_message.edit(
                    content=(
                        "❌ لم أجد رسالة التوب تحتوي على "
                        "المراكز الثلاثة الأولى."
                    )
                )

                return

            # =================================================
            # IDs الفائزين
            # =================================================

            first_id = top_data[1]
            second_id = top_data[2]
            third_id = top_data[3]

            # =================================================
            # الحصول على الأعضاء
            # =================================================

            first_member = ctx.guild.get_member(first_id)
            second_member = ctx.guild.get_member(second_id)
            third_member = ctx.guild.get_member(third_id)

            # =================================================
            # المنشن
            # =================================================

            first_mention = (
                first_member.mention
                if first_member
                else f"<@{first_id}>"
            )

            second_mention = (
                second_member.mention
                if second_member
                else f"<@{second_id}>"
            )

            third_mention = (
                third_member.mention
                if third_member
                else f"<@{third_id}>"
            )

            # =================================================
            # إنشاء الإعلان
            # =================================================

            embed = discord.Embed(
                title="🏆 توب السيرفر",
                description=(
                    "🎉 **نتائج التوب الحالية** 🎉\n\n"
                    "مبروك للفائزين وحظ أوفر للجميع في التوب القادم!"
                ),
                color=discord.Color.gold()
            )

            # =================================================
            # المركز الأول
            # =================================================

            embed.add_field(
                name="🥇 المركز الأول",
                value=(
                    f"{first_mention}\n\n"
                    f"🪙 **450 ذهب**\n"
                    f"💵 **250,000 Ai**"
                ),
                inline=False
            )

            # =================================================
            # المركز الثاني
            # =================================================

            embed.add_field(
                name="🥈 المركز الثاني",
                value=(
                    f"{second_mention}\n\n"
                    f"🪙 **250 ذهب**\n"
                    f"💵 **150,000 Ai**"
                ),
                inline=False
            )

            # =================================================
            # المركز الثالث
            # =================================================

            embed.add_field(
                name="🥉 المركز الثالث",
                value=(
                    f"{third_mention}\n\n"
                    f"🪙 **100 ذهب**\n"
                    f"💵 **50,000 Ai**"
                ),
                inline=False
            )

            # =================================================
            # الفوتر
            # =================================================

            embed.set_footer(
                text=f"تم الإعلان بواسطة {ctx.author.display_name}"
            )

            # =================================================
            # إرسال الإعلان
            # =================================================

            await announcement_channel.send(
                embed=embed
            )

            # =================================================
            # حذف أمر -اعلن
            # =================================================

            try:
                await ctx.message.delete()
            except:
                pass

            # =================================================
            # حذف رسالة الانتظار
            # =================================================

            try:
                await loading_message.delete()
            except:
                pass

        except Exception as e:

            print(
                f"❌ خطأ في AnnouncementCog: {e}"
            )

            try:

                await loading_message.edit(
                    content=(
                        "❌ حدث خطأ أثناء قراءة التوب."
                    )
                )

            except:
                pass


# =========================================================
# Setup
# =========================================================

async def setup(bot):

    await bot.add_cog(
        AnnouncementCog(bot)
    )
