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
# الجوائز الافتراضية
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
    # الشكل الأساسي
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
# Modal تحديد الجوائز
# =========================================================

class PrizeModal(discord.ui.Modal):

    def __init__(self, announcement_view):

        super().__init__(
            title="🏆 تحديد جوائز التوب"
        )

        self.announcement_view = announcement_view

        self.first_gold = discord.ui.TextInput(
            label="🥇 ذهب المركز الأول",
            placeholder="مثال: 450",
            default=str(
                announcement_view.first_gold
            ),
            required=True,
            max_length=20
        )

        self.first_ai = discord.ui.TextInput(
            label="🥇 Ai المركز الأول",
            placeholder="مثال: 250000",
            default=str(
                announcement_view.first_ai
            ),
            required=True,
            max_length=30
        )

        self.second_gold = discord.ui.TextInput(
            label="🥈 ذهب المركز الثاني",
            placeholder="مثال: 250",
            default=str(
                announcement_view.second_gold
            ),
            required=True,
            max_length=20
        )

        self.second_ai = discord.ui.TextInput(
            label="🥈 Ai المركز الثاني",
            placeholder="مثال: 150000",
            default=str(
                announcement_view.second_ai
            ),
            required=True,
            max_length=30
        )

        self.third_gold = discord.ui.TextInput(
            label="🥉 ذهب المركز الثالث",
            placeholder="مثال: 100",
            default=str(
                announcement_view.third_gold
            ),
            required=True,
            max_length=20
        )

        self.third_ai = discord.ui.TextInput(
            label="🥉 Ai المركز الثالث",
            placeholder="مثال: 50000",
            default=str(
                announcement_view.third_ai
            ),
            required=True,
            max_length=30
        )

        self.add_item(self.first_gold)
        self.add_item(self.first_ai)
        self.add_item(self.second_gold)
        self.add_item(self.second_ai)
        self.add_item(self.third_gold)
        self.add_item(self.third_ai)

    async def on_submit(self, interaction):

        try:

            first_gold = int(
                self.first_gold.value.replace(",", "")
            )

            first_ai = int(
                self.first_ai.value.replace(",", "")
            )

            second_gold = int(
                self.second_gold.value.replace(",", "")
            )

            second_ai = int(
                self.second_ai.value.replace(",", "")
            )

            third_gold = int(
                self.third_gold.value.replace(",", "")
            )

            third_ai = int(
                self.third_ai.value.replace(",", "")
            )

            if any(
                value < 0
                for value in [
                    first_gold,
                    first_ai,
                    second_gold,
                    second_ai,
                    third_gold,
                    third_ai
                ]
            ):
                await interaction.response.send_message(
                    "❌ لا يمكن أن تكون الجوائز أرقامًا سالبة.",
                    ephemeral=True
                )
                return

        except ValueError:

            await interaction.response.send_message(
                "❌ تأكد أن جميع الجوائز أرقام صحيحة.",
                ephemeral=True
            )

            return

        # -------------------------------------------------
        # حفظ الجوائز
        # -------------------------------------------------

        self.announcement_view.first_gold = first_gold
        self.announcement_view.first_ai = first_ai

        self.announcement_view.second_gold = second_gold
        self.announcement_view.second_ai = second_ai

        self.announcement_view.third_gold = third_gold
        self.announcement_view.third_ai = third_ai

        # -------------------------------------------------
        # تحديث رسالة الواجهة
        # -------------------------------------------------

        await interaction.response.edit_message(
            embed=self.announcement_view.create_setup_embed(),
            view=self.announcement_view
        )


# =========================================================
# واجهة إعلان التوب
# =========================================================

class AnnouncementView(discord.ui.View):

    def __init__(
        self,
        cog,
        ctx,
        top_data
    ):

        super().__init__(
            timeout=300
        )

        self.cog = cog
        self.ctx = ctx
        self.top_data = top_data

        # -------------------------------------------------
        # الجوائز الافتراضية
        # -------------------------------------------------

        self.first_gold = FIRST_GOLD
        self.first_ai = FIRST_AI

        self.second_gold = SECOND_GOLD
        self.second_ai = SECOND_AI

        self.third_gold = THIRD_GOLD
        self.third_ai = THIRD_AI

        self.finished = False

    # =====================================================
    # التحقق من صاحب العملية
    # =====================================================

    async def check_user(self, interaction):

        if interaction.user.id != self.ctx.author.id:

            await interaction.response.send_message(
                "❌ هذه الواجهة ليست لك.",
                ephemeral=True
            )

            return False

        return True

    # =====================================================
    # Embed الواجهة الرئيسية
    # =====================================================

    def create_setup_embed(self):

        first_id = self.top_data[1]
        second_id = self.top_data[2]
        third_id = self.top_data[3]

        embed = discord.Embed(
            title="✅ تم حفظ أسماء الفائزين",
            description=(
                "تم سحب المراكز الثلاثة الأولى من التوب بنجاح.\n\n"
                "يمكنك الآن تحديد الجوائز أو معاينة الإعلان "
                "قبل إرساله."
            ),
            color=discord.Color.gold()
        )

        embed.add_field(
            name="🥇 المركز الأول",
            value=f"<@{first_id}>",
            inline=False
        )

        embed.add_field(
            name="🥈 المركز الثاني",
            value=f"<@{second_id}>",
            inline=False
        )

        embed.add_field(
            name="🥉 المركز الثالث",
            value=f"<@{third_id}>",
            inline=False
        )

        embed.add_field(
            name="🎁 الجوائز الحالية",
            value=(
                f"🥇 **الأول:** {self.first_gold:,} ذهب — "
                f"{self.first_ai:,} Ai\n"
                f"🥈 **الثاني:** {self.second_gold:,} ذهب — "
                f"{self.second_ai:,} Ai\n"
                f"🥉 **الثالث:** {self.third_gold:,} ذهب — "
                f"{self.third_ai:,} Ai"
            ),
            inline=False
        )

        embed.set_footer(
            text=f"تم تجهيز الإعلان بواسطة {self.ctx.author.display_name}"
        )

        return embed

    # =====================================================
    # زر تحديد الجوائز
    # =====================================================

    @discord.ui.button(
        label="تحديد الجوائز",
        emoji="🎁",
        style=discord.ButtonStyle.primary
    )
    async def prizes_button(
        self,
        interaction,
        button
    ):

        if not await self.check_user(interaction):
            return

        await interaction.response.send_modal(
            PrizeModal(self)
        )

    # =====================================================
    # زر معاينة الإعلان
    # =====================================================

    @discord.ui.button(
        label="معاينة الإعلان",
        emoji="👀",
        style=discord.ButtonStyle.secondary
    )
    async def preview_button(
        self,
        interaction,
        button
    ):

        if not await self.check_user(interaction):
            return

        embed = self.create_announcement_embed()

        await interaction.response.send_message(
            content=(
                "👀 **هذه معاينة الإعلان فقط — لم يتم إرساله.**"
            ),
            embed=embed,
            ephemeral=True
        )

    # =====================================================
    # زر الإعلان
    # =====================================================

    @discord.ui.button(
        label="إعلان",
        emoji="✅",
        style=discord.ButtonStyle.success
    )
    async def announce_button(
        self,
        interaction,
        button
    ):

        if not await self.check_user(interaction):
            return

        if self.finished:
            return

        self.finished = True

        await interaction.response.defer(
            ephemeral=True
        )

        try:

            output_channel = self.cog.bot.get_channel(
                ANNOUNCE_OUTPUT_CHANNEL_ID
            )

            if output_channel is None:

                await interaction.followup.send(
                    "❌ لم أستطع الوصول إلى روم الإعلان.",
                    ephemeral=True
                )

                self.finished = False
                return

            embed = self.create_announcement_embed()

            member_role_mention = (
                f"<@&{MEMBER_ROLE_ID}>"
            )

            await output_channel.send(
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

            await interaction.followup.send(
                "✅ تم إرسال إعلان التوب بنجاح.",
                ephemeral=True
            )

            # -------------------------------------------------
            # تعطيل جميع الأزرار
            # -------------------------------------------------

            for item in self.children:
                item.disabled = True

            try:

                await interaction.message.edit(
                    content=(
                        "✅ **تم إرسال الإعلان بنجاح.**"
                    ),
                    embed=self.create_setup_embed(),
                    view=self
                )

            except:
                pass

        except Exception as e:

            print(
                f"❌ خطأ أثناء إرسال إعلان التوب: {e}"
            )

            self.finished = False

            await interaction.followup.send(
                "❌ حدث خطأ أثناء إرسال الإعلان.",
                ephemeral=True
            )

    # =====================================================
    # زر الإلغاء
    # =====================================================

    @discord.ui.button(
        label="إلغاء",
        emoji="❌",
        style=discord.ButtonStyle.danger
    )
    async def cancel_button(
        self,
        interaction,
        button
    ):

        if not await self.check_user(interaction):
            return

        if self.finished:
            return

        self.finished = True

        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(
            content="❌ **تم إلغاء عملية إعلان التوب.**",
            embed=None,
            view=self
        )

    # =====================================================
    # إنشاء Embed الإعلان النهائي
    # =====================================================

    def create_announcement_embed(self):

        first_id = self.top_data[1]
        second_id = self.top_data[2]
        third_id = self.top_data[3]

        first_mention = f"<@{first_id}>"
        second_mention = f"<@{second_id}>"
        third_mention = f"<@{third_id}>"

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
                f"{first_mention}\n\n"
                f"🪙 **{self.first_gold:,} ذهب**\n"
                f"💵 **{self.first_ai:,} Ai**"
            ),
            inline=False
        )

        # -------------------------------------------------
        # المركز الثاني
        # -------------------------------------------------

        embed.add_field(
            name="🥈 المركز الثاني",
            value=(
                f"{second_mention}\n\n"
                f"🪙 **{self.second_gold:,} ذهب**\n"
                f"💵 **{self.second_ai:,} Ai**"
            ),
            inline=False
        )

        # -------------------------------------------------
        # المركز الثالث
        # -------------------------------------------------

        embed.add_field(
            name="🥉 المركز الثالث",
            value=(
                f"{third_mention}\n\n"
                f"🪙 **{self.third_gold:,} ذهب**\n"
                f"💵 **{self.third_ai:,} Ai**"
            ),
            inline=False
        )

        embed.set_footer(
            text=f"تم الإعلان بواسطة {self.ctx.author.display_name}"
        )

        return embed


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
        # رسالة الانتظار
        # -------------------------------------------------

        loading_message = await ctx.send(
            "⏳ جاري قراءة التوب وتجهيز القائمة..."
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
            # حذف رسالة الانتظار
            # =================================================

            try:
                await loading_message.delete()
            except:
                pass

            # =================================================
            # إنشاء الواجهة
            # =================================================

            view = AnnouncementView(
                self,
                ctx,
                top_data
            )

            await ctx.send(
                embed=view.create_setup_embed(),
                view=view
            )

            # =================================================
            # حذف الأمر
            # =================================================

            try:
                await ctx.message.delete()
            except:
                pass

        except Exception as e:

            print(
                f"❌ خطأ في تجهيز AnnouncementCog: {e}"
            )

            try:

                await loading_message.edit(
                    content=(
                        "❌ حدث خطأ أثناء تجهيز إعلان التوب."
                    )
                )

            except:
                pass

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
    # إرسال الإعلان المباشر - خاص بأمر -ت
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
