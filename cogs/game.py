import asyncio
import discord
from discord.ext import commands
from discord import ui


# =========================================================
# الإعدادات
# =========================================================

# الروم الوحيد الذي تعمل فيه ألعاب الصور
GAME_ROOM_ID = 1545143660469813250

# الرتب الثلاث المسموح لها بإدارة اللعبة
ALLOWED_ROLE_IDS = {
    1544078469657530578,
    1545851911121666108,
    1544426415766896690,
}


# =========================================================
# جلسة اللعبة
# =========================================================

class GameSession:

    def __init__(self, creator_id):

        self.creator_id = creator_id

        # الأسئلة بالترتيب
        self.questions = []

        # نقاط اللاعبين
        self.scores = {}

        # حالة اللعبة
        self.is_running = False

        # حماية من التشغيل المتزامن
        self.starting = False

        # السؤال الحالي
        self.current_question_index = 0


# =========================================================
# Cog الألعاب
# =========================================================

class GameCog(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        # الألعاب الموجودة حسب الروم
        self.active_games = {}

        # قفل لكل روم لمنع السبام
        self.game_locks = {}

    # =====================================================
    # التحقق من الروم
    # =====================================================

    def is_game_room(self, ctx):

        return ctx.channel.id == GAME_ROOM_ID

    # =====================================================
    # التحقق من الرتب
    # =====================================================

    def has_allowed_role(self, member):

        if not isinstance(member, discord.Member):
            return False

        return any(
            role.id in ALLOWED_ROLE_IDS
            for role in member.roles
        )

    # =====================================================
    # الحصول على Lock للروم
    # =====================================================

    def get_lock(self, channel_id):

        if channel_id not in self.game_locks:

            self.game_locks[channel_id] = asyncio.Lock()

        return self.game_locks[channel_id]

    # =====================================================
    # إنشاء لعبة
    # =====================================================

    @commands.command(name="انشاء-لعبة")
    async def create_game(self, ctx):

        # الروم
        if not self.is_game_room(ctx):
            return

        # الرتب
        if not self.has_allowed_role(ctx.author):
            return

        lock = self.get_lock(ctx.channel.id)

        # إذا فيه عملية إنشاء جارية، تجاهل الأمر
        if lock.locked():
            return

        async with lock:

            channel_id = ctx.channel.id

            old_session = self.active_games.get(
                channel_id
            )

            # منع إنشاء لعبتين في نفس الروم
            if old_session:

                if (
                    old_session.is_running
                    or old_session.starting
                ):

                    await ctx.send(
                        "⚠️ توجد لعبة قيد التشغيل بالفعل!",
                        delete_after=5
                    )

                    return

                await ctx.send(
                    "⚠️ توجد جلسة لعبة جاهزة بالفعل في هذه الروم.",
                    delete_after=5
                )

                return

            # إنشاء جلسة جديدة
            session = GameSession(
                ctx.author.id
            )

            self.active_games[channel_id] = session

            embed = discord.Embed(
                title="🎮 لوحة التحكم بلعبة الصور",
                description=(
                    "تم تجهيز فعالية جديدة بنجاح! 🔥\n\n"

                    "🖼️ **إضافة سؤال**\n"
                    "اضغط الزر، ثم أرسل الصورة في الشات، "
                    "وبعدها اكتب الإجابة الصحيحة.\n\n"

                    "يمكنك إضافة عدد غير محدود من الأسئلة "
                    "وبدون أي وقت محدد.\n\n"

                    "▶️ **بدء اللعبة**\n"
                    "بعد الانتهاء من إضافة جميع الصور، "
                    "اكتب:\n"
                    "`-ابدا`\n\n"

                    "🏆 **ترتيب النقاط**\n"
                    "استخدم:\n"
                    "`-ت`\n\n"

                    "⏹️ **إنهاء**\n"
                    "ينهي اللعبة الحالية."
                ),
                color=discord.Color.blurple()
            )

            embed.set_footer(
                text=f"أنشئت بواسطة: {ctx.author.display_name}"
            )

            view = GameControlView(
                self,
                channel_id
            )

            await ctx.send(
                embed=embed,
                view=view
            )

            # حذف أمر الإداري
            try:

                await ctx.message.delete()

            except discord.HTTPException:
                pass

    # =====================================================
    # بدء اللعبة -ابدا
    # =====================================================

    @commands.command(name="ابدا")
    async def start_game_command(self, ctx):

        # الروم
        if not self.is_game_room(ctx):
            return

        # الرتب
        if not self.has_allowed_role(ctx.author):
            return

        lock = self.get_lock(ctx.channel.id)

        # =================================================
        # حماية السبام
        # أول إداري يدخل فقط
        # =================================================

        if lock.locked():
            return

        async with lock:

            session = self.active_games.get(
                ctx.channel.id
            )

            if not session:

                await ctx.send(
                    "⚠️ لا توجد لعبة جاهزة حالياً.",
                    delete_after=5
                )

                return

            # إذا بدأت اللعبة مسبقاً
            if session.is_running:
                return

            # إذا إداري آخر بدأها بنفس اللحظة
            if session.starting:
                return

            # لا توجد أسئلة
            if not session.questions:

                await ctx.send(
                    "⚠️ لم تتم إضافة أي أسئلة بعد.",
                    delete_after=5
                )

                return

            # قفل البداية فوراً
            session.starting = True

            session.is_running = True

            session.starting = False

            await ctx.send(
                "🚀 **بدأت فعاليتنا!**\n"
                "🔥 استعدوا للسؤال الأول..."
            )

        # تشغيل اللعبة خارج الـLock
        await self.run_game_loop(
            ctx.channel
        )

    # =====================================================
    # ترتيب النقاط -ت
    # =====================================================

    @commands.command(name="ت")
    async def leaderboard(self, ctx):

        # الروم
        if not self.is_game_room(ctx):
            return

        # الرتب
        if not self.has_allowed_role(ctx.author):
            return

        session = self.active_games.get(
            ctx.channel.id
        )

        if not session:

            await ctx.send(
                "⚠️ لا توجد فعالية حالية.",
                delete_after=5
            )

            return

        if not session.scores:

            await ctx.send(
                "🏆 لا توجد نقاط مسجلة حتى الآن!",
                delete_after=5
            )

            return

        sorted_scores = sorted(
            session.scores.items(),
            key=lambda item: item[1],
            reverse=True
        )

        medals = [
            "🥇",
            "🥈",
            "🥉"
        ]

        description = []

        for index, (user_id, points) in enumerate(
            sorted_scores[:10]
        ):

            member = ctx.guild.get_member(
                user_id
            )

            if member:

                name = member.mention

            else:

                name = f"<@{user_id}>"

            medal = (
                medals[index]
                if index < 3
                else "🔹"
            )

            description.append(
                f"{medal} {name} — **{points} نقطة**"
            )

        embed = discord.Embed(
            title="🏆 ترتيب اللاعبين الحالي",
            description="\n".join(description),
            color=discord.Color.gold()
        )

        embed.set_footer(
            text=f"عدد اللاعبين: {len(sorted_scores)}"
        )

        await ctx.send(
            embed=embed
        )

    # =====================================================
    # تشغيل اللعبة
    # =====================================================

    async def run_game_loop(self, channel):

        session = self.active_games.get(
            channel.id
        )

        if not session:
            return

        # =================================================
        # الأسئلة بالترتيب
        # =================================================

        for index, question in enumerate(
            session.questions
        ):

            if not session.is_running:
                break

            session.current_question_index = index

            # ---------------------------------------------
            # إرسال الصورة
            # ---------------------------------------------

            embed = discord.Embed(
                title=(
                    f"📸 السؤال "
                    f"({index + 1} من "
                    f"{len(session.questions)})"
                ),
                description=(
                    "⚡ أسرع واكتب الإجابة الصحيحة!\n\n"
                    "⏰ الوقت: **30 ثانية**"
                ),
                color=discord.Color.gold()
            )

            embed.set_image(
                url=question["image"]
            )

            await channel.send(
                embed=embed
            )

            # ---------------------------------------------
            # الإجابة
            # ---------------------------------------------

            correct_answer = (
                question["answer"]
                .strip()
                .casefold()
            )

            def check(message):

                return (
                    message.channel.id == channel.id
                    and not message.author.bot
                    and message.content.strip().casefold()
                    == correct_answer
                )

            try:

                message = await self.bot.wait_for(
                    "message",
                    timeout=30.0,
                    check=check
                )

                user_id = message.author.id

                session.scores[user_id] = (
                    session.scores.get(
                        user_id,
                        0
                    ) + 1
                )

                await channel.send(
                    f"🎉 كفو {message.author.mention}!\n"
                    f"✅ إجابة صحيحة! "
                    f"حصلت على **نقطة واحدة** 🏆"
                )

            except asyncio.TimeoutError:

                await channel.send(
                    "⏰ **انتهى وقت السؤال!**\n"
                    f"الإجابة الصحيحة كانت: "
                    f"`{question['answer']}`"
                )

            # فاصل بسيط
            if session.is_running:

                await asyncio.sleep(3)

        # =================================================
        # نهاية الفعالية
        # =================================================

        if session.is_running:

            await channel.send(
                "🏁 **انتهت فعاليتنا لليوم!**\n\n"
                "❤️ شكراً لحضوركم ومشاركتكم.\n"
                "⏳ **انتظروا النتائج...**"
            )

        # إيقاف الجلسة
        session.is_running = False
        session.starting = False

        # حذف الجلسة
        if self.active_games.get(channel.id) is session:

            del self.active_games[channel.id]

    # =====================================================
    # النتائج النهائية
    # =====================================================

    async def show_final_results(
        self,
        channel,
        session
    ):

        if not session.scores:

            await channel.send(
                "🏆 لا توجد نقاط مسجلة."
            )

            return

        sorted_scores = sorted(
            session.scores.items(),
            key=lambda item: item[1],
            reverse=True
        )

        medals = [
            "🥇",
            "🥈",
            "🥉"
        ]

        description = []

        for index, (user_id, points) in enumerate(
            sorted_scores[:10]
        ):

            member = channel.guild.get_member(
                user_id
            )

            if member:

                name = member.mention

            else:

                name = f"<@{user_id}>"

            medal = (
                medals[index]
                if index < 3
                else "🔹"
            )

            description.append(
                f"{medal} {name} — **{points} نقطة**"
            )

        embed = discord.Embed(
            title="🏆 النتائج النهائية!",
            description="\n".join(description),
            color=discord.Color.gold()
        )

        await channel.send(
            embed=embed
        )


# =========================================================
# لوحة التحكم
# =========================================================

class GameControlView(ui.View):

    def __init__(
        self,
        cog,
        channel_id
    ):

        super().__init__(
            timeout=None
        )

        self.cog = cog
        self.channel_id = channel_id

    # =====================================================
    # التحقق من الصلاحية
    # =====================================================

    async def check_permission(
        self,
        interaction
    ):

        if interaction.channel_id != GAME_ROOM_ID:

            await interaction.response.send_message(
                "❌ هذا الزر غير متاح هنا.",
                ephemeral=True
            )

            return False

        if not self.cog.has_allowed_role(
            interaction.user
        ):

            await interaction.response.send_message(
                "❌ ليس لديك صلاحية استخدام لوحة الألعاب.",
                ephemeral=True
            )

            return False

        return True

    # =====================================================
    # إضافة سؤال
    # =====================================================

    @ui.button(
        label="إضافة سؤال 🖼️",
        style=discord.ButtonStyle.primary
    )
    async def add_question(
        self,
        interaction: discord.Interaction,
        button: ui.Button
    ):

        if not await self.check_permission(
            interaction
        ):
            return

        session = self.cog.active_games.get(
            self.channel_id
        )

        if not session:

            await interaction.response.send_message(
                "❌ لا توجد جلسة لعبة حالياً.",
                ephemeral=True
            )

            return

        if session.is_running:

            await interaction.response.send_message(
                "❌ اللعبة بدأت بالفعل ولا يمكن إضافة أسئلة.",
                ephemeral=True
            )

            return

        # =================================================
        # فتح Modal للإجابة
        # =================================================

        modal = QuestionAnswerModal(
            self.cog,
            session,
            interaction.user.id
        )

        await interaction.response.send_modal(
            modal
        )

    # =====================================================
    # بدء اللعبة من الزر
    # =====================================================

    @ui.button(
        label="بدء اللعبة ▶️",
        style=discord.ButtonStyle.success
    )
    async def start_game_button(
        self,
        interaction: discord.Interaction,
        button: ui.Button
    ):

        if not await self.check_permission(
            interaction
        ):
            return

        lock = self.cog.get_lock(
            self.channel_id
        )

        if lock.locked():
            return

        async with lock:

            session = self.cog.active_games.get(
                self.channel_id
            )

            if not session:

                await interaction.response.send_message(
                    "❌ لا توجد جلسة لعبة.",
                    ephemeral=True
                )

                return

            if session.is_running:
                return

            if session.starting:
                return

            if not session.questions:

                await interaction.response.send_message(
                    "⚠️ أضف سؤالاً واحداً على الأقل.",
                    ephemeral=True
                )

                return

            session.starting = True
            session.is_running = True
            session.starting = False

            await interaction.response.send_message(
                "🚀 **بدأت فعاليتنا!**\n"
                "🔥 استعدوا للسؤال الأول..."
            )

        await self.cog.run_game_loop(
            interaction.channel
        )

    # =====================================================
    # إنهاء اللعبة
    # =====================================================

    @ui.button(
        label="إنهاء ⏹️",
        style=discord.ButtonStyle.danger
    )
    async def end_game(
        self,
        interaction: discord.Interaction,
        button: ui.Button
    ):

        if not await self.check_permission(
            interaction
        ):
            return

        session = self.cog.active_games.get(
            self.channel_id
        )

        if not session:

            await interaction.response.send_message(
                "❌ لا توجد لعبة حالياً.",
                ephemeral=True
            )

            return

        session.is_running = False
        session.starting = False

        if self.channel_id in self.cog.active_games:

            del self.cog.active_games[
                self.channel_id
            ]

        await interaction.response.send_message(
            "🛑 **تم إنهاء الفعالية وتصفير نقاطها.**"
        )

        try:

            await interaction.message.delete()

        except discord.HTTPException:
            pass


# =========================================================
# Modal إدخال الإجابة
# =========================================================

class QuestionAnswerModal(
    ui.Modal,
    title="إضافة سؤال"
):

    def __init__(
        self,
        cog,
        session,
        user_id
    ):

        super().__init__()

        self.cog = cog
        self.session = session
        self.user_id = user_id

        self.answer_input = ui.TextInput(
            label="الإجابة الصحيحة",
            placeholder="اكتب الإجابة الصحيحة للصورة...",
            required=True,
            max_length=200,
            style=discord.TextStyle.short
        )

        self.add_item(
            self.answer_input
        )

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        answer = self.answer_input.value.strip()

        if not answer:

            await interaction.response.send_message(
                "❌ يجب كتابة الإجابة.",
                ephemeral=True
            )

            return

        # إرسال رد فوري
        await interaction.response.send_message(
            "🖼️ **تم تجهيز السؤال!**\n\n"
            "الآن أرسل الصورة في هذا الروم.\n"
            "⏳ **لا يوجد وقت محدد، أرسلها متى ما تريد.**\n\n"
            "سيتم حفظ الصورة تلقائياً وربطها بالإجابة.",
            ephemeral=True
        )

        # =================================================
        # انتظار الصورة بدون أي Timeout
        # =================================================

        def image_check(message):

            return (
                message.channel.id == GAME_ROOM_ID
                and message.author.id == self.user_id
                and not message.author.bot
                and len(message.attachments) > 0
            )

        # انتظار بلا وقت محدد
        message = await self.cog.bot.wait_for(
            "message",
            check=image_check
        )

        attachment = message.attachments[0]

        # التأكد من أنها صورة
        if not attachment.content_type:

            await interaction.followup.send(
                "❌ الملف المرسل ليس صورة واضحة.\n"
                "أرسل صورة ثم حاول إضافة السؤال مرة أخرى.",
                ephemeral=True
            )

            return

        if not attachment.content_type.startswith(
            "image/"
        ):

            await interaction.followup.send(
                "❌ الملف المرسل ليس صورة.\n"
                "أرسل صورة فقط.",
                ephemeral=True
            )

            return

        # =================================================
        # حفظ السؤال
        # =================================================

        self.session.questions.append(
            {
                "image": attachment.url,
                "answer": answer
            }
        )

        question_number = len(
            self.session.questions
        )

        await interaction.followup.send(
            "✅ **تم حفظ السؤال بنجاح!**\n"
            f"🖼️ رقم السؤال: `{question_number}`\n"
            f"📚 إجمالي الأسئلة: `{question_number}`",
            ephemeral=True
        )


# =========================================================
# تحميل Cog
# =========================================================

async def setup(bot):

    await bot.add_cog(
        GameCog(bot)
    )
