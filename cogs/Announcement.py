import re
import discord
from discord.ext import commands


# =========================================================
# الإعدادات
# =========================================================

# روم مصدر رسالة التوب
SOURCE_CHANNEL_ID = 1544380230058115244

# الروم المسموح فيه استخدام الأمرين
COMMAND_ROOM_ID = 1547711993568305232

# روم إعلان -اعلن
ANNOUNCE_OUTPUT_CHANNEL_ID = 1544883370830602250

# روم إعلان -ت
T_OUTPUT_CHANNEL_ID = 1547711993568305232

# رتبة MEMBER
MEMBER_ROLE_ID = 1544078847253811331


# =========================================================
# الرتب المسموح لها باستخدام الأوامر
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
# استخراج النص من رسالة التوب
# =========================================================

def get_message_text(message):

    texts = []

    # -----------------------------------------------------
    # محتوى الرسالة العادي
    # -----------------------------------------------------

    if message.content:
        texts.append(message.content)

    # -----------------------------------------------------
    # قراءة الـ Embeds
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
# استخراج أول 3 مراكز من التوب
# =========================================================

def extract_top_3(message):

    text = get_message_text(message)

    if not text:
        return None

    results = {}

    # =====================================================
    # الشكل الأساسي:
    #
    # #`1` I <@!724763668037894155> I `1.50t`
    # #`2` I <@!1523454188330418339> I `287.25b`
    # #`3` I <@!1498403413157744852> I `62.25b`
    #
    # =====================================================

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

    # =====================================================
    # طريقة احتياطية
    # =====================================================

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

    # =====================================================
    # التأكد من وجود المراكز الثلاثة
    # =====================================================

    if (
        1 in results
        and 2 in results
        and 3 in results
    ):
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
# Announcement Cog
# =========================================================

class AnnouncementCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    # =====================================================
    # -اعلن
    # =====================================================

    @commands.command(name="اعلن")
    async def announce(self, ctx):

        # -------------------------------------------------
        # يجب أن يكون في روم الأوامر
        # -------------------------------------------------

        if ctx.channel.id != COMMAND_ROOM_ID:
            return

        # -------------------------------------------------
        # التحقق من الرتبة
        # -------------------------------------------------

        if not has_allowed_role(ctx.author):
            return

        await self.send_announcement(
            ctx,
            ANNOUNCE_OUTPUT_CHANNEL_ID
        )

    # =====================================================
    # -ت
    # =====================================================

    @commands.command(name="ت")
    async def announce_t(self, ctx):

        # -------------------------------------------------
        # يجب أن يكون في روم الأوامر
        # -------------------------------------------------

        if ctx.channel.id != COMMAND_ROOM_ID:
            return

        # -------------------------------------------------
        # التحقق من الرتبة
        # -------------------------------------------------

        if not has_allowed_role(ctx.author):
            return

        await self.send_announcement(
            ctx,
            T_OUTPUT_CHANNEL_ID
        )

    # =====================================================
    # إرسال الإعلان
    # =====================================================

    async def send_announcement(
        self,
        ctx,
        output_channel_id
    ):

        # -------------------------------------------------
        # الحصول على روم مصدر التوب
        # -------------------------------------------------

        source_channel = self.bot.get_channel(
            SOURCE_CHANNEL_ID
        )

        if source_channel is None:

            await ctx.send(
                "❌ لم أستطع الوصول إلى روم التوب.",
                delete_after=10
            )

            return

        # -------------------------------------------------
        # الحصول على روم الإعلان
        # -------------------------------------------------

        announcement_channel = self.bot.get_channel(
            output_channel_id
        )

        if announcement_channel is None:

            await ctx.send(
                "❌ لم أستطع الوصول إلى روم الإعلان.",
                delete_after=10
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
            # البحث في آخر 30 رسالة عن رسالة التوب
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
            # لم يتم العثور على التوب
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
            # منشن الفائزين
            # =================================================

            first_mention = f"<@{first_id}>"
            second_mention = f"<@{second_id}>"
            third_mention = f"<@{third_id}>"

            # =================================================
            # منشن رتبة MEMBER
            # =================================================

            member_role_mention = f"<@&{MEMBER_ROLE_ID}>"

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
                    "🪙 **450 ذهب**\n"
                    "💵 **250,000 Ai**"
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
                    "🪙 **250 ذهب**\n"
                    "💵 **150,000 Ai**"
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
                    "🪙 **100 ذهب**\n"
                    "💵 **50,000 Ai**"
                ),
                inline=False
            )

            embed.set_footer(
                text=f"تم الإعلان بواسطة {ctx.author.display_name}"
            )

            # =================================================
            # إرسال الإعلان
            # =================================================

            await announcement_channel.send(
                content=(
                    f"@everyone {member_role_mention}"
                ),
                embed=embed,
                allowed_mentions=discord.AllowedMentions(
                    everyone=True,
                    roles=True,
                    users=True
                )
            )

            # =================================================
            # حذف الأمر
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
                        "❌ حدث خطأ أثناء إرسال الإعلان."
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
