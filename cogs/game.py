import asyncio
import discord
from discord.ext import commands
from discord import ui


# =========================================================
# الإعدادات
# =========================================================

# روم تجهيز اللعبة وإضافة الصور والأسئلة
SETUP_ROOM_ID = 1548289588211097710

# روم تشغيل اللعبة
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

        # الألعاب الموجودة
        self.active_games = {}

        # قفل لكل روم
        self.game_locks = {}

    # =====================================================
    # التحقق من روم التجهيز
    # =====================================================

    def is_setup_room(self, ctx):

        return ctx.channel.id == SETUP_ROOM_ID

    # =====================================================
    # التحقق من روم اللعبة
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
    # الحصول على Lock
    # =====================================================

    def get_lock(self, channel_id):

        if channel_id not in self.game_locks:

            self.game_locks[channel_id] = asyncio.Lock()

        return self.game_locks[channel_id]

    # =====================================================
    # إنشاء لعبة
    # يعمل في روم التجهيز
    # =====================================================

    @commands.command(name="انشاء-لعبة")
    async def create_game(self, ctx):

        # لازم يكون في روم التجهيز
        if not self.is_setup_room(ctx):
            return

        # الرتب
        if not self.has_allowed_role(ctx.author):
            return

        lock = self.get_lock(SETUP_ROOM_ID)

        # إذا فيه عملية جارية
        if lock.locked():
            return

        async with lock:

            # إذا فيه فعالية موجودة
            old_session = self.active_games.get(
                GAME_ROOM_ID
            )

            # منع إنشاء لعبة جديدة قبل -انهي
            if old_session:

                if old_session.is_running:

                    await ctx.send(
                        "⚠️ توجد لعبة قيد التشغيل بالفعل!",
                        delete_after=5
                    )

                    return

                await ctx.send(
                    "⚠️ توجد فعالية محفوظة حالياً.\n"
                    "استخدم `-انهي` من روم اللعبة لمسح الصور "
                    "والنقاط ثم أنشئ فعالية جديدة.",
                    delete_after=7
                )

                return

            # إنشاء جلسة جديدة
            session = GameSession(
                ctx.author.id
            )

            # تخزين الجلسة مرتبطة بروم اللعبة
            self.active_games[GAME_ROOM_ID] = session

            embed = discord.Embed(
                title="🎮 لوحة التحكم بلعبة الصور",
                description=(
                    "تم تجهيز فعالية جديدة بنجاح! 🔥\n\n"

                    "🖼️ **إضافة سؤال**\n"
                    "اضغط الزر، ثم أرسل الصورة في هذا الروم، "
                    "وبعدها يتم حفظ الإجابة والصورة.\n\n"

                    "يمكنك إضافة عدد غير محدود من الأسئلة "
                    "وبدون أي وقت محدد.\n\n"

                    "⚠️ **مهم:**\n"
                    "لا تحذف الصور من روم التجهيز، "
                    "لأن البوت يحتاج رابط الصورة أثناء اللعبة.\n\n"

                    "▶️ **بدء اللعبة**\n"
                    "بعد الانتهاء من إضافة جميع الصور، "
                    "اذهب إلى روم اللعبة واستخدم:\n"
                    "`-ابدا`\n\n"

                    "🏆 **ترتيب النقاط**\n"
                    "في روم اللعبة استخدم:\n"
                    "`-ط`\n\n"

                    "🗑️ **إنهاء ومسح الفعالية**\n"
                    "في روم اللعبة استخدم:\n"
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

            # حذف أمر الإداري
            try:

                await ctx.message.delete()

            except discord.HTTPException:
                pass

    # =====================================================
    # بدء اللعبة -ابدا
    # يعمل فقط في روم اللعبة
    # =====================================================

    @commands.command(name="ابدا")
    async def start_game_command(self, ctx):

        # لازم يكون في روم اللعبة
        if not self.is_game_room(ctx):
            return

        # الرتب
        if not self.has_allowed_role(ctx.author):
            return

        lock = self.get_lock(GAME_ROOM_ID)

        # حماية السبام
        if lock.locked():
            return

        async with lock:

            session = self.active_games.get(
                GAME_ROOM_ID
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

            # قفل البداية
            session.starting = True

            session.is_running = True

            session.current_question_index = 0

            session.starting = False

            await ctx.send(
                "🚀 **بدأت فعاليتنا!**\n\n"
                f"📚 عدد الأسئلة: **{len(session.questions)}**\n"
                "🔥 استعدوا للسؤال الأول..."
            )

        # تشغيل اللعبة
        await self.run_game_loop(
            ctx.channel
        )

    # =====================================================
    # ترتيب النقاط -ط
    # يعمل فقط في روم اللعبة
    # =====================================================

    @commands.command(name="ط")
    async def leaderboard(self, ctx):

        # لازم يكون في روم اللعبة
        if not self.is_game_room(ctx):
            return

        # الرتب
        if not self.has_allowed_role(ctx.author):
            return

        session = self.active_games.get(
            GAME_ROOM_ID
        )

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
    # إنهاء ومسح الفعالية -انهي
    # يعمل فقط في روم اللعبة
    # =====================================================

    @commands.command(name="انهي")
    async def finish_game_command(self, ctx):

        # لازم يكون في روم اللعبة
        if not self.is_game_room(ctx):
            return

        # الرتب
        if not self.has_allowed_role(ctx.author):
            return

        lock = self.get_lock(GAME_ROOM_ID)

        # حماية
        if lock.locked():
            return

        async with lock:

            session = self.active_games.get(
                GAME_ROOM_ID
            )

            if not session:

                await ctx.send(
                    "⚠️ لا توجد فعالية محفوظة حالياً.",
                    delete_after=5
                )

                return

            # إيقاف اللعبة
            session.is_running = False
            session.starting = False

            # حفظ العدد
            questions_count = len(
                session.questions
            )

            players_count = len(
                session.scores
            )

            # مسح الأسئلة والنقاط
            session.questions.clear()
            session.scores.clear()

            # مسح الجلسة
            if self.active_games.get(
                GAME_ROOM_ID
            ) is session:

                del self.active_games[
                    GAME_ROOM_ID
                ]

            await ctx.send(
                "🗑️ **تم إنهاء الفعالية بنجاح!**\n\n"
                f"🖼️ تم مسح **{questions_count}** سؤال.\n"
                f"🏆 تم مسح نقاط **{players_count}** لاعب.\n\n"
                "✅ أصبح بالإمكان إنشاء فعالية جديدة."
            )

            # حذف الأمر
            try:

                await ctx.message.delete()

            except discord.HTTPException:
                pass

    # =====================================================
    # تشغيل اللعبة
    # =====================================================

    async def run_game_loop(self, channel):

        session = self.active_games.get(
            GAME_ROOM_ID
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

            question_number = index + 1

            total_questions = len(
                session.questions
            )

            embed = discord.Embed(
                title=(
                    f"📸 السؤال {question_number}"
                    f" من {total_questions}"
                ),
                description=(
                    "⚡ أسرع واكتب الإجابة الصحيحة!\n\n"
                    "⏰ الوقت: **15 ثانية**\n\n"
                    f"📌 **السؤال رقم {question_number}**"
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
                    timeout=15.0,
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
                    f"✅ إجابة صحيحة!\n"
                    f"🏆 حصلت على **نقطة واحدة**.\n\n"
                    f"📊 مجموع نقاطك: "
                    f"**{session.scores[user_id]}**"
                )

            except asyncio.TimeoutError:

                await channel.send(
                    "⏰ **انتهى وقت السؤال!**\n"
                    f"❌ لم يتمكن أحد من الإجابة.\n"
                    f"✅ الإجابة الصحيحة كانت: "
                    f"`{question['answer']}`"
                )

            # ---------------------------------------------
            # فاصل بين الأسئلة
            # ---------------------------------------------

            if session.is_running:

                if question_number < total_questions:

                    await channel.send(
                        "⏳ **استعدوا للسؤال التالي...**"
                    )

                    await asyncio.sleep(7)

        # =================================================
        # نهاية الفعالية
        # =================================================

        if session.is_running:

            await channel.send(
                "🏁 **انتهت فعاليتنا لليوم!**\n\n"
                "❤️ شكراً لحضوركم ومشاركتكم.\n"
                "🏆 **النتائج ما زالت محفوظة.**\n"
                "📊 استخدموا `-ط` لعرض الترتيب."
            )

        # إيقاف اللعبة فقط
        # لا نحذف الأسئلة ولا النقاط
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

        # زر الإضافة يعمل في روم التجهيز
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

        # أزرار التشغيل تعمل في روم اللعبة
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
    # إضافة سؤال
    # يعمل فقط في روم التجهيز
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

        # إضافة الأسئلة فقط في روم التجهيز
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

        # فتح Modal
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
    # يعمل فقط في روم اللعبة
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

        # لازم يكون في روم اللعبة
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
                "🚀 **بدأت فعاليتنا!**\n\n"
                f"📚 عدد الأسئلة: **{len(session.questions)}**\n"
                "🔥 استعدوا للسؤال الأول..."
            )

        await self.cog.run_game_loop(
            interaction.channel
        )

    # =====================================================
    # إنهاء اللعبة من الزر
    # يعمل فقط في روم اللعبة
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

        # لازم يكون في روم اللعبة
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

        # إيقاف اللعبة
        session.is_running = False
        session.starting = False

        questions_count = len(
            session.questions
        )

        players_count = len(
            session.scores
        )

        # مسح الأسئلة والنقاط
        session.questions.clear()
        session.scores.clear()

        if GAME_ROOM_ID in self.cog.active_games:

            del self.cog.active_games[
                GAME_ROOM_ID
            ]

        await interaction.response.send_message(
            "🗑️ **تم إنهاء الفعالية بنجاح!**\n\n"
            f"🖼️ تم مسح **{questions_count}** سؤال.\n"
            f"🏆 تم مسح نقاط **{players_count}** لاعب.\n\n"
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

        # التأكد أن العملية من روم التجهيز
        if interaction.channel_id != SETUP_ROOM_ID:

            await interaction.response.send_message(
                "❌ إضافة الأسئلة متاحة فقط في روم التجهيز.",
                ephemeral=True
            )

            return

        answer = self.answer_input.value.strip()

        if not answer:

            await interaction.response.send_message(
                "❌ يجب كتابة الإجابة.",
                ephemeral=True
            )

            return

        # رد فوري
        await interaction.response.send_message(
            "🖼️ **تم تجهيز السؤال!**\n\n"
            "الآن أرسل الصورة في هذا الروم.\n"
            "⏳ **لا يوجد وقت محدد، أرسلها متى ما تريد.**\n\n"
            "⚠️ **مهم:** لا تحذف الصورة بعد إرسالها، "
            "لأن البوت سيستخدم رابطها أثناء اللعبة.",
            ephemeral=True
        )

        # =================================================
        # انتظار الصورة بدون Timeout
        # =================================================

        def image_check(message):

            return (
                message.channel.id == SETUP_ROOM_ID
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

        # التأكد أنها صورة
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
            f"📚 إجمالي الأسئلة: `{question_number}`\n\n"
            "🔒 اترك الصورة في روم التجهيز ولا تحذفها.",
            ephemeral=True
        )


# =========================================================
# تحميل Cog
# =========================================================

async def setup(bot):

    await bot.add_cog(
        GameCog(bot)
    )
