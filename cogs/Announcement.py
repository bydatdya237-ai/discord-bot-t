import re
import discord
from discord.ext import commands


# =========================================================
# الإعدادات
# =========================================================

# الروم الذي يرسل فيه بوت التوب
SOURCE_CHANNEL_ID = 1544380230058115244

# الروم المسموح فيه استخدام -اعلن
COMMAND_ROOM_ID = 1547711993568305232

# الروم الذي سيتم إرسال الإعلان فيه
ANNOUNCEMENT_CHANNEL_ID = 1547571126736134144


# الرتب المسموح لها باستخدام -اعلن
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
# استخراج أول 3 أشخاص من رسالة التوب
# =========================================================

def extract_top_3(message):
    """
    يبحث داخل رسالة التوب عن:
    #1 <@!USER_ID>
    #2 <@!USER_ID>
    #3 <@!USER_ID>

    ويرجع IDs الأشخاص الثلاثة.
    """

    text = message.content or ""

    # إذا كانت الرسالة Embed فقط
    if not text and message.embeds:
        parts = []

        for embed in message.embeds:
            if embed.title:
                parts.append(embed.title)

            if embed.description:
                parts.append(embed.description)

            for field in embed.fields:
                parts.append(field.name)
                parts.append(field.value)

        text = "\n".join(parts)

    # البحث عن رقم المركز + المنشن
    pattern = r"#`?([1-3])`?\s*[|I]\s*<@!?(\d+)>"

    results = {}

    for match in re.finditer(pattern, text, re.IGNORECASE):
        rank = int(match.group(1))
        user_id = int(match.group(2))

        if rank in (1, 2, 3):
            results[rank] = user_id

    # طريقة احتياطية إذا كان تنسيق البوت مختلف قليلًا
    if len(results) < 3:

        lines = text.splitlines()

        for line in lines:

            # مثال:
            # #`1` I <@!724763668037894155> I `1.50t`

            rank_match = re.search(
                r"#`?([1-3])`?",
                line
            )

            mention_match = re.search(
                r"<@!?(\d+)>",
                line
            )

            if rank_match and mention_match:
                rank = int(rank_match.group(1))
                user_id = int(mention_match.group(1))

                if rank in (1, 2, 3):
                    results[rank] = user_id

    if all(rank in results for rank in (1, 2, 3)):
        return results

    return None


# =========================================================
# التحقق من الرتبة
# =========================================================

def has_allowed_role(member):
    return any(
        role.id in ALLOWED_ROLE_IDS
        for role in member.roles
    )


# =========================================================
# الكوج
# =========================================================

class AnnouncementCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    # =====================================================
    # أمر -اعلن
    # =====================================================

    @commands.command(name="اعلن")
    async def announce_top(self, ctx):

        # -------------------------------------------------
        # الروم المسموح فقط
        # -------------------------------------------------

        if ctx.channel.id != COMMAND_ROOM_ID:
            return

        # -------------------------------------------------
        # التحقق من الرتبة
        # -------------------------------------------------

        if not has_allowed_role(ctx.author):
            return

        # -------------------------------------------------
        # الحصول على روم مصدر التوب
        # -------------------------------------------------

        source_channel = self.bot.get_channel(SOURCE_CHANNEL_ID)

        if source_channel is None:

            await ctx.send(
                "❌ لم أستطع العثور على روم التوب."
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
                "❌ لم أستطع العثور على روم الإعلان."
            )

            return

        # -------------------------------------------------
        # رسالة انتظار
        # -------------------------------------------------

        loading_message = await ctx.send(
            "⏳ جاري قراءة التوب وتجهيز الإعلان..."
        )

        try:

            # -------------------------------------------------
            # قراءة آخر رسائل روم التوب
            # -------------------------------------------------

            top_message = None

            async for message in source_channel.history(
                limit=30
            ):

                # نتجاهل الرسائل الفارغة
                if not message.content and not message.embeds:
                    continue

                # محاولة استخراج التوب
                top_data = extract_top_3(message)

                if top_data:
                    top_message = message
                    break

            # -------------------------------------------------
            # إذا لم نجد التوب
            # -------------------------------------------------

            if top_message is None:

                await loading_message.edit(
                    content=(
                        "❌ لم أجد رسالة توب تحتوي على "
                        "المراكز الثلاثة الأولى."
                    )
                )

                return

            # -------------------------------------------------
            # استخراج الأشخاص
            # -------------------------------------------------

            top_data = extract_top_3(top_message)

            if not top_data:

                await loading_message.edit(
                    content="❌ حدث خطأ أثناء قراءة بيانات التوب."
                )

                return

            first_id = top_data[1]
            second_id = top_data[2]
            third_id = top_data[3]

            # -------------------------------------------------
            # جلب الأعضاء من السيرفر
            # -------------------------------------------------

            first_member = ctx.guild.get_member(first_id)
            second_member = ctx.guild.get_member(second_id)
            third_member = ctx.guild.get_member(third_id)

            # -------------------------------------------------
            # تجهيز أسماء العرض
            # -------------------------------------------------

            first_name = (
                first_member.mention
                if first_member
                else f"<@{first_id}>"
            )

            second_name = (
                second_member.mention
                if second_member
                else f"<@{second_id}>"
            )

            third_name = (
                third_member.mention
                if third_member
                else f"<@{third_id}>"
            )

            # -------------------------------------------------
            # إنشاء الإعلان
            # -------------------------------------------------

            embed = discord.Embed(
                title="🏆 توب السيرفر",
                description=(
                    "🎉 **نتائج التوب الحالية** 🎉\n\n"
                    "مبروك للفائزين وحظ أوفر للجميع في التوب القادم!"
                ),
                color=discord.Color.gold()
            )

            # -------------------------------------------------
            # المركز الأول
            # -------------------------------------------------

            embed.add_field(
                name="🥇 المركز الأول",
                value=(
                    f"{first_name}\n\n"
                    f"💰 **الجائزة:**\n"
                    f"🪙 {FIRST_GOLD} ذهب\n"
                    f"💵 {FIRST_AI:,} Ai"
                ),
                inline=False
            )

            # -------------------------------------------------
            # المركز الثاني
            # -------------------------------------------------

            embed.add_field(
                name="🥈 المركز الثاني",
                value=(
                    f"{second_name}\n\n"
                    f"💰 **الجائزة:**\n"
                    f"🪙 {SECOND_GOLD} ذهب\n"
                    f"💵 {SECOND_AI:,} Ai"
                ),
                inline=False
            )

            # -------------------------------------------------
            # المركز الثالث
            # -------------------------------------------------

            embed.add_field(
                name="🥉 المركز الثالث",
                value=(
                    f"{third_name}\n\n"
                    f"💰 **الجائزة:**\n"
                    f"🪙 {THIRD_GOLD} ذهب\n"
                    f"💵 {THIRD_AI:,} Ai"
                ),
                inline=False
            )

            # -------------------------------------------------
            # الفوتر
            # -------------------------------------------------

            embed.set_footer(
                text=f"تم الإعلان بواسطة {ctx.author.display_name}"
            )

            # -------------------------------------------------
            # إرسال الإعلان
            # -------------------------------------------------

            await announcement_channel.send(
                embed=embed
            )

            # -------------------------------------------------
            # حذف رسالة الأمر
            # -------------------------------------------------

            try:
                await ctx.message.delete()
            except:
                pass

            # -------------------------------------------------
            # حذف رسالة الانتظار
            # -------------------------------------------------

            await loading_message.delete()

        except Exception as e:

            print(
                f"❌ خطأ في أمر -اعلن: {e}"
            )

            try:
                await loading_message.edit(
                    content=(
                        "❌ حدث خطأ أثناء تجهيز الإعلان."
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
