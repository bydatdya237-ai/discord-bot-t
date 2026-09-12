import asyncio
import discord
from discord.ext import commands
from discord import ui


# =========================================================
# الإعدادات
# =========================================================

GAME_NAME = "خمن الدولة من العلم"

SETUP_ROOM_ID = 1548289588211097710
GAME_ROOM_ID = 1545143660469813250

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
        self.questions = []
        self.scores = {}
        self.is_running = False
        self.starting = False
        self.current_question_index = 0


# =========================================================
# Cog الألعاب
# =========================================================

class GameCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.active_games = {}
        self.game_locks = {}

    # =====================================================
    # التحقق من الروم
    # =====================================================

    def is_setup_room(self, ctx):
        return ctx.channel.id == SETUP_ROOM_ID

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
    # قفل العمليات
    # =====================================================

    def get_lock(self, channel_id):

        if channel_id not in self.game_locks:
            self.game_locks[channel_id] = asyncio.Lock()

        return self.game_locks[channel_id]

    # =====================================================
    # إنشاء اللعبة
    # =====================================================

    @commands.command(name="انشاء-لعبة")
    async def create_game(self, ctx):

        if not self.is_setup_room(ctx):
            return

        if not self.has_allowed_role(ctx.author):
            return

        lock = self.get_lock(SETUP_ROOM_ID)

        if lock.locked():
            return

        async with lock:

            old_session = self.active_games.get(GAME_ROOM_ID)

            if old_session:

                if old_session.is_running:

                    await ctx.send(
                        "⚠️ توجد لعبة قيد التشغيل بالفعل!",
                        delete_after=5
                    )

                    return

                await ctx.send(
                    "⚠️ توجد فعالية محفوظة حالياً.\n"
                    "استخدم `-انهي` من روم اللعبة "
                    "لحذفها ثم أنشئ فعالية جديدة.",
                    delete_after=7
                )

                return

            session = GameSession(ctx.author.id)

            self.active_games[GAME_ROOM_ID] = session

            embed = discord.Embed(
                title=f"🎮 {GAME_NAME}",
                description=(
                    "تم تجهيز فعالية جديدة بنجاح! 🔥\n\n"

                    "🖼️ **إضافة سؤال**\n"
                    "اضغط الزر، ثم أرسل صورة العلم في هذا الروم، "
                    "وبعدها يتم حفظ الإجابة والصورة.\n\n"

                    "يمكنك إضافة عدد غير محدود من الأعلام.\n\n"

                    "⚠️ **مهم:**\n"
                    "لا تحذف الصور من روم التجهيز، "
                    "لأن البوت يحتاج رابط الصورة أثناء اللعبة.\n\n"

                    "▶️ **بدء اللعبة**\n"
                    "بعد الانتهاء من إضافة جميع الصور، "
                    "اذهب إلى روم اللعبة واستخدم:\n"
                    "`-ابدا`\n\n"

                    "🏆 **ترتيب النقاط**\n"
                    "استخدم:\n"
                    "`-ط`\n\n"

                    "🔄 **تصفير النقاط فقط**\n"
                    "استخدم:\n"
                    "`-دن`\n\n"

                    "🗑️ **إنهاء وحذف الفعالية**\n"
                    "استخدم:\n"
                    "`-انهي`"
                ),
                color=discord.Color.blurple()
            )

            embed.set_footer(
                text=f"أنشئت بواسطة: {ctx.author.display_name}"
            )

            view = GameControlView(
                self,
                GAME_ROOM_ID
            )

            await ctx.send(
                embed=embed,
                view=view
            )

            try:
                await ctx.message.delete()

            except discord.HTTPException:
                pass

    # =====================================================
    # بدء اللعبة
    # =====================================================

    @commands.command(name="ابدا")
    async def start_game_command(self, ctx):

        if not self.is_game_room(ctx):
            return

        if not self.has_allowed_role(ctx.author):
            return

        lock = self.get_lock(GAME_ROOM_ID)

        if lock.locked():
            return

        async with lock:

            session = self.active_games.get(GAME_ROOM_ID)

            if not session:

                await ctx.send(
                    "⚠️ لا توجد لعبة جاهزة حالياً.",
                    delete_after=5
                )

                return

            if session.is_running:
                return

            if session.starting:
                return

            if not session.questions:

                await ctx.send(
                    "⚠️ لم تتم إضافة أي أسئلة بعد.",
                    delete_after=5
                )

                return

            session.starting = True
            session.is_running = True
            session.current_question_index = 0
            session.starting = False

            await ctx.send(
                f"🚀 **بدأت لعبة {GAME_NAME}!**\n\n"
                f"📚 عدد الأعلام: **{len(session.questions)}**\n"
                "🔥 استعدوا للعلم الأول..."
            )

        await self.run_game_loop(ctx.channel)

    # =====================================================
    # ترتيب النقاط
    # =====================================================

    @commands.command(name="ط")
    async def leaderboard(self, ctx):

        if not self.is_game_room(ctx):
            return

        if not self.has_allowed_role(ctx.author):
            return

        session = self.active_games.get(GAME_ROOM_ID)

        if not session:

            await ctx.send(
                "⚠️ لا توجد فعالية محفوظة حالياً.",
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

        medals = ["🥇", "🥈", "🥉"]

        description = []

        for index, (user_id, points) in enumerate(
            sorted_scores[:10]
        ):

            member = ctx.guild.get_member(user_id)

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

        await ctx.send(embed=embed)

    # =====================================================
    # تصفير النقاط فقط
    # =====================================================

    @commands.command(name="دن")
    async def reset_scores(self, ctx):

        if not self.is_game_room(ctx):
            return

        if not self.has_allowed_role(ctx.author):
            return

        lock = self.get_lock(GAME_ROOM_ID)

        if lock.locked():
            return

        async with lock:

            session = self.active_games.get(GAME_ROOM_ID)

            if not session:

                await ctx.send(
                    "⚠️ لا توجد فعالية محفوظة حالياً.",
                    delete_after=5
                )

                return

            players_count = len(session.scores)

            session.scores.clear()

            await ctx.send(
                "🔄 **تم تصفير النقاط بنجاح!**\n\n"
                f"🏆 تم تصفير نقاط **{players_count}** لاعب.\n"
                "🖼️ الأعلام والأسئلة **لم يتم حذفها**.\n\n"
                "✅ يمكنك بدء اللعبة من جديد باستخدام `-ابدا`."
            )

            try:
                await ctx.message.delete()

            except discord.HTTPException:
                pass

    # =====================================================
    # إنهاء اللعبة بالكامل
    # =====================================================

    @commands.command(name="انهي")
    async def finish_game_command(self, ctx):

        if not self.is_game_room(ctx):
            return

        if not self.has_allowed_role(ctx.author):
            return

        lock = self.get_lock(GAME_ROOM_ID)

        if lock.locked():
            return

        async with lock:

            session = self.active_games.get(GAME_ROOM_ID)

            if not session:

                await ctx.send(
                    "⚠️ لا توجد فعالية محفوظة حالياً.",
                    delete_after=5
                )

                return

            session.is_running = False
            session.starting = False

            questions_count = len(session.questions)
            players_count = len(session.scores)

            session.questions.clear()
            session.scores.clear()

            if self.active_games.get(GAME_ROOM_ID) is session:
                del self.active_games[GAME_ROOM_ID]

            await ctx.send(
                "🗑️ **تم إنهاء الفعالية بنجاح!**\n\n"
                f"🖼️ تم حذف **{questions_count}** سؤال.\n"
                f"🏆 تم تصفير نقاط **{players_count}** لاعب.\n\n"
                "✅ أصبح بإمكانك إنشاء فعالية جديدة."
            )

            try:
                await ctx.message.delete()

            except discord.HTTPException:
                pass

    # =====================================================
    # تشغيل الأسئلة
    # =====================================================

    async def run_game_loop(self, channel):

        session = self.active_games.get(GAME_ROOM_ID)

        if not session:
            return

        for index, question in enumerate(session.questions):

            if not session.is_running:
                break

            session.current_question_index = index

            question_number = index + 1
            total_questions = len(session.questions)

            # -------------------------------------------------
            # وقت بداية السؤال
            # -------------------------------------------------

            question_start_time = asyncio.get_running_loop().time()

            # -------------------------------------------------
            # Embed السؤال
            # -------------------------------------------------

            embed = discord.Embed(
                title=(
                    f"🏳️ {GAME_NAME} | "
                    f"السؤال {question_number} من {total_questions}"
                ),
                description=(
                    "⚡ **خمن الدولة من العلم!**\n\n"
                    "⏰ **مدة السؤال: 15 ثانية**\n\n"
                    "🏆 أول إجابة صحيحة تحصل على نقطة!"
                ),
                color=discord.Color.gold()
            )

            embed.set_image(
                url=question["image"]
            )

            # -------------------------------------------------
            # إرسال السؤال
            # -------------------------------------------------

            await channel.send(
                embed=embed
            )

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

            answered_correctly = False

            # -------------------------------------------------
            # انتظار الإجابة
            # -------------------------------------------------

            try:

                message = await self.bot.wait_for(
                    "message",
                    timeout=15.0,
                    check=check
                )

                # -------------------------------------------------
                # حساب كم مضى من وقت السؤال
                # -------------------------------------------------

                elapsed = (
                    asyncio.get_running_loop().time()
                    - question_start_time
                )

                # -------------------------------------------------
                # تسجيل النقطة
                # -------------------------------------------------

                user_id = message.author.id

                session.scores[user_id] = (
                    session.scores.get(user_id, 0) + 1
                )

                answered_correctly = True

                await channel.send(
                    f"🎉 كفو {message.author.mention}!\n"
                    "✅ **إجابة صحيحة!**\n"
                    "🏆 حصلت على **نقطة واحدة**.\n"
                    f"📊 مجموع نقاطك: "
                    f"**{session.scores[user_id]}**"
                )

                # -------------------------------------------------
                # حساب الوقت المتبقي من الـ15 ثانية
                # -------------------------------------------------

                remaining_time = max(
                    0,
                    15.0 - elapsed
                )

                # -------------------------------------------------
                # انتظار باقي وقت السؤال
                # -------------------------------------------------

                if remaining_time > 0:

                    await asyncio.sleep(
                        remaining_time
                    )

            except asyncio.TimeoutError:

                # -------------------------------------------------
                # انتهت الـ15 ثانية بدون إجابة صحيحة
                # -------------------------------------------------

                await channel.send(
                    "⏰ **انتهى وقت السؤال!**\n"
                    "❌ لم يتمكن أحد من الإجابة.\n"
                    f"✅ الدولة الصحيحة كانت: "
                    f"`{question['answer']}`"
                )

            # -----------------------------------------------------
            # حماية إضافية:
            # التأكد أن 15 ثانية كاملة مرت قبل السؤال التالي
            # -----------------------------------------------------

            total_elapsed = (
                asyncio.get_running_loop().time()
                - question_start_time
            )

            remaining_after_processing = max(
                0,
                15.0 - total_elapsed
            )

            if remaining_after_processing > 0:

                await asyncio.sleep(
                    remaining_after_processing
                )

            # -----------------------------------------------------
            # هنا فقط ينتقل للسؤال التالي
            # -----------------------------------------------------

        # =====================================================
        # نهاية جميع الأسئلة
        # =====================================================

        if session.is_running:

            await channel.send(
                f"🏁 **انتهت لعبة {GAME_NAME}!**\n\n"
                "❤️ شكراً لحضوركم ومشاركتكم.\n"
                "🏆 **النتائج ما زالت محفوظة.**\n"
                "📊 استخدموا `-ط` لعرض الترتيب.\n"
                "🔄 استخدموا `-دن` لتصفير النقاط وإعادة اللعب."
            )

        session.is_running = False
        session.starting = False

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

        medals = ["🥇", "🥈", "🥉"]

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
            title=f"🏆 النتائج النهائية - {GAME_NAME}",
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

    def __init__(self, cog, channel_id):

        super().__init__(
            timeout=None
        )

        self.cog = cog
        self.channel_id = channel_id

    # =====================================================
    # فحص الصلاحيات
    # =====================================================

    async def check_permission(
        self,
        interaction
    ):

        if interaction.channel_id == SETUP_ROOM_ID:

            if not self.cog.has_allowed_role(
                interaction.user
            ):

                await interaction.response.send_message(
                    "❌ ليس لديك صلاحية استخدام لوحة الألعاب.",
                    ephemeral=True
                )

                return False

            return True

        if interaction.channel_id == GAME_ROOM_ID:

            if not self.cog.has_allowed_role(
                interaction.user
            ):

                await interaction.response.send_message(
                    "❌ ليس لديك صلاحية استخدام لوحة الألعاب.",
                    ephemeral=True
                )

                return False

            return True

        await interaction.response.send_message(
            "❌ هذا الزر غير متاح هنا.",
            ephemeral=True
        )

        return False

    # =====================================================
    # زر إضافة سؤال
    # =====================================================

    @ui.button(
        label="إضافة سؤال 🖼️",
        style=discord.ButtonStyle.primary
    )
    async def add_question(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if interaction.channel_id != SETUP_ROOM_ID:

            await interaction.response.send_message(
                "❌ إضافة الأسئلة متاحة فقط في روم التجهيز.",
                ephemeral=True
            )

            return

        if not await self.check_permission(
            interaction
        ):
            return

        session = self.cog.active_games.get(
            GAME_ROOM_ID
        )

        if not session:

            await interaction.response.send_message(
                "❌ لا توجد جلسة لعبة حالياً.\n"
                "استخدم `-انشاء-لعبة` أولاً.",
                ephemeral=True
            )

            return

        if session.is_running:

            await interaction.response.send_message(
                "❌ اللعبة بدأت بالفعل ولا يمكن إضافة أسئلة.",
                ephemeral=True
            )

            return

        modal = QuestionAnswerModal(
            self.cog,
            session,
            interaction.user.id
        )

        await interaction.response.send_modal(
            modal
        )

    # =====================================================
    # زر بدء اللعبة
    # =====================================================

    @ui.button(
        label="بدء اللعبة ▶️",
        style=discord.ButtonStyle.success
    )
    async def start_game_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if interaction.channel_id != GAME_ROOM_ID:

            await interaction.response.send_message(
                "❌ بدء اللعبة متاح فقط في روم اللعبة.",
                ephemeral=True
            )

            return

        if not await self.check_permission(
            interaction
        ):
            return

        lock = self.cog.get_lock(
            GAME_ROOM_ID
        )

        if lock.locked():
            return

        async with lock:

            session = self.cog.active_games.get(
                GAME_ROOM_ID
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
                    "⚠️ أضف سؤالاً واحداً على الأقل "
                    "من روم التجهيز.",
                    ephemeral=True
                )

                return

            session.starting = True
            session.is_running = True
            session.current_question_index = 0
            session.starting = False

            await interaction.response.send_message(
                f"🚀 **بدأت لعبة {GAME_NAME}!**\n\n"
                f"📚 عدد الأعلام: **{len(session.questions)}**\n"
                "🔥 استعدوا للعلم الأول..."
            )

        await self.cog.run_game_loop(
            interaction.channel
        )

    # =====================================================
    # زر إنهاء
    # =====================================================

    @ui.button(
        label="إنهاء ⏹️",
        style=discord.ButtonStyle.danger
    )
    async def end_game(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if interaction.channel_id != GAME_ROOM_ID:

            await interaction.response.send_message(
                "❌ إنهاء اللعبة متاح فقط في روم اللعبة.",
                ephemeral=True
            )

            return

        if not await self.check_permission(
            interaction
        ):
            return

        session = self.cog.active_games.get(
            GAME_ROOM_ID
        )

        if not session:

            await interaction.response.send_message(
                "❌ لا توجد لعبة حالياً.",
                ephemeral=True
            )

            return

        session.is_running = False
        session.starting = False

        questions_count = len(
            session.questions
        )

        players_count = len(
            session.scores
        )

        session.questions.clear()
        session.scores.clear()

        if GAME_ROOM_ID in self.cog.active_games:

            del self.cog.active_games[
                GAME_ROOM_ID
            ]

        await interaction.response.send_message(
            "🗑️ **تم إنهاء الفعالية بنجاح!**\n\n"
            f"🖼️ تم حذف **{questions_count}** سؤال.\n"
            f"🏆 تم تصفير نقاط **{players_count}** لاعب.\n\n"
            "✅ أصبح بالإمكان إنشاء فعالية جديدة."
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
            label="الدولة الصحيحة",
            placeholder="اكتب اسم الدولة صاحبة العلم...",
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

        if interaction.channel_id != SETUP_ROOM_ID:

            await interaction.response.send_message(
                "❌ إضافة الأسئلة متاحة فقط في روم التجهيز.",
                ephemeral=True
            )

            return

        answer = self.answer_input.value.strip()

        if not answer:

            await interaction.response.send_message(
                "❌ يجب كتابة اسم الدولة.",
                ephemeral=True
            )

            return

        await interaction.response.send_message(
            "🖼️ **تم تجهيز العلم!**\n\n"
            "الآن أرسل صورة العلم في هذا الروم.\n"
            "⏳ **لا يوجد وقت محدد، أرسلها متى ما تريد.**\n\n"
            "⚠️ **مهم:** لا تحذف الصورة بعد إرسالها، "
            "لأن البوت سيستخدم رابطها أثناء اللعبة.",
            ephemeral=True
        )

        def image_check(message):

            return (
                message.channel.id == SETUP_ROOM_ID
                and message.author.id == self.user_id
                and not message.author.bot
                and len(message.attachments) > 0
            )

        message = await self.cog.bot.wait_for(
            "message",
            check=image_check
        )

        attachment = message.attachments[0]

        if not attachment.content_type:

            await interaction.followup.send(
                "❌ الملف المرسل ليس صورة واضحة.\n"
                "أرسل صورة ثم حاول إضافة العلم مرة أخرى.",
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

        self.session.questions.append({
            "image": attachment.url,
            "answer": answer
        })

        question_number = len(
            self.session.questions
        )

        await interaction.followup.send(
            "✅ **تم حفظ العلم بنجاح!**\n"
            f"🏳️ رقم السؤال: `{question_number}`\n"
            f"📚 إجمالي الأعلام: `{question_number}`\n\n"
            "🔒 اترك الصورة في روم التجهيز ولا تحذفها.",
            ephemeral=True
        )


# =========================================================
# Setup
# =========================================================

async def setup(bot):
    await bot.add_cog(
        GameCog(bot)
    )
