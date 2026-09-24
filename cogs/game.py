import os
import asyncio

import discord
from discord.ext import commands
from discord import ui

from motor.motor_asyncio import AsyncIOMotorClient


# =========================================================
# الإعدادات العامة
# =========================================================

GAME_NAME = "خمن الماركة من الصورة"

MONGO_URI = os.getenv("MONGO_URI")

mongo_client = None
db = None
website_command_settings = None

if MONGO_URI:
    mongo_client = AsyncIOMotorClient(MONGO_URI)
    db = mongo_client["discord_bot_db"]
    website_command_settings = db["website_command_settings"]


# =========================================================
# أسماء الأوامر في الموقع
# =========================================================

COMMAND_CREATE = "انشاء-لعبة"
COMMAND_EDIT = "تعديل"
COMMAND_START = "ابدا"
COMMAND_LEADERBOARD = "ط"
COMMAND_RESET = "دن"
COMMAND_FINISH = "انهي"


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

        self.game_name = GAME_NAME

        self.control_message = None


# =========================================================
# Cog الألعاب
# =========================================================

class GameCog(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        self.active_games = {}

        self.game_locks = {}


    # =====================================================
    # Mongo - اختلاف نوع guild_id
    # =====================================================

    def guild_id_variants(self, guild_id):

        variants = [str(guild_id)]

        try:
            variants.append(int(guild_id))
        except Exception:
            pass

        return variants


    # =====================================================
    # جلب إعداد الأمر من الموقع
    # =====================================================

    async def get_command_setting(
        self,
        guild_id,
        command_name
    ):

        if website_command_settings is None:
            return None

        guild_ids = self.guild_id_variants(
            guild_id
        )

        # النظام الجديد
        setting = await website_command_settings.find_one(
            {
                "guild_id": {
                    "$in": guild_ids
                },
                "command_name": str(
                    command_name
                )
            }
        )

        if setting:
            return setting

        # دعم البيانات القديمة
        setting = await website_command_settings.find_one(
            {
                "guild_id": {
                    "$in": guild_ids
                },
                "name": str(
                    command_name
                )
            }
        )

        return setting


    # =====================================================
    # فحص صلاحية الأمر من الموقع
    #
    # إذا لا يوجد إعداد:
    # الأمر متاح لأي عضو في السيرفر
    #
    # إذا يوجد إعداد:
    # يتم تطبيق enabled + roles + channels
    # =====================================================

    async def has_command_permission(
        self,
        member,
        command_name,
        channel_id=None
    ):

        if not isinstance(
            member,
            discord.Member
        ):

            return False


        # السيرفر
        guild = member.guild

        setting = await self.get_command_setting(
            guild.id,
            command_name
        )


        # =================================================
        # لا يوجد إعداد في الموقع
        #
        # يعني الأمر مفتوح لأي عضو
        # =================================================

        if setting is None:

            return True


        # =================================================
        # الأمر مغلق من الموقع
        # =================================================

        if not setting.get(
            "enabled",
            False
        ):

            return False


        # =================================================
        # الرتب
        # =================================================

        role_ids = setting.get(
            "role_ids",
            []
        )


        # إذا الموقع حدد رتب
        if role_ids:

            allowed_role_ids = {
                str(role_id)
                for role_id in role_ids
            }

            user_role_ids = {
                str(role.id)
                for role in member.roles
            }

            if not allowed_role_ids.intersection(
                user_role_ids
            ):

                return False


        # =================================================
        # الرومات
        # =================================================

        channel_ids = setting.get(
            "channel_ids",
            []
        )


        # إذا الموقع حدد رومات
        if channel_ids and channel_id is not None:

            allowed_channel_ids = {
                str(channel)
                for channel in channel_ids
            }

            if str(channel_id) not in allowed_channel_ids:

                return False


        return True


    # =====================================================
    # صلاحية زر مرتبط بأمر
    # =====================================================

    async def check_button_permission(
        self,
        interaction,
        command_name
    ):

        allowed = await self.has_command_permission(
            interaction.user,
            command_name,
            interaction.channel_id
        )

        if not allowed:

            await interaction.response.send_message(
                "❌ ليس لديك صلاحية استخدام هذا الأمر.",
                ephemeral=True
            )

            return False

        return True


    # =====================================================
    # قفل العمليات
    # =====================================================

    def get_lock(
        self,
        channel_id
    ):

        if channel_id not in self.game_locks:

            self.game_locks[channel_id] = asyncio.Lock()

        return self.game_locks[channel_id]


    # =====================================================
    # Embed لوحة التحكم
    # =====================================================

    def create_control_embed(
        self,
        session,
        creator_name
    ):

        embed = discord.Embed(
            title=f"🎮 {session.game_name}",
            description=(
                "تم تجهيز فعالية جديدة بنجاح! 🔥\n\n"

                "🖼️ **إضافة سؤال**\n"
                "اضغط الزر، ثم أرسل صورة الماركة في الروم "
                "المسموح من الموقع، وبعدها يتم حفظ الإجابة والصورة.\n\n"

                "يمكنك إضافة عدد غير محدود من الصور.\n\n"

                "⚠️ **مهم:**\n"
                "لا تحذف الصور من روم التجهيز، "
                "لأن البوت يحتاج رابط الصورة أثناء اللعبة.\n\n"

                "✏️ **تعديل اسم اللعبة**\n"
                "استخدم الأمر:\n"
                "`تعديل`\n\n"

                "▶️ **بدء اللعبة**\n"
                "استخدم:\n"
                "`ابدا`\n\n"

                "🏆 **ترتيب النقاط**\n"
                "استخدم:\n"
                "`ط`\n\n"

                "🔄 **تصفير النقاط فقط**\n"
                "استخدم:\n"
                "`دن`\n\n"

                "🗑️ **إنهاء وحذف الفعالية**\n"
                "استخدم:\n"
                "`انهي`"
            ),
            color=discord.Color.blurple()
        )

        embed.set_footer(
            text=f"أنشئت بواسطة: {creator_name}"
        )

        return embed


    # =====================================================
    # تحديث لوحة التحكم
    # =====================================================

    async def update_control_message(
        self,
        session,
        guild
    ):

        if not session.control_message:
            return

        try:

            creator = guild.get_member(
                session.creator_id
            )

            creator_name = (
                creator.display_name
                if creator
                else "غير معروف"
            )

            embed = self.create_control_embed(
                session,
                creator_name
            )

            await session.control_message.edit(
                embed=embed
            )

        except (
            discord.NotFound,
            discord.HTTPException
        ):

            pass


    # =====================================================
    # إنشاء اللعبة
    # =====================================================

    @commands.command(
        name=COMMAND_CREATE
    )
    async def create_game(
        self,
        ctx
    ):

        if ctx.guild is None:
            return

        allowed = await self.has_command_permission(
            ctx.author,
            COMMAND_CREATE,
            ctx.channel.id
        )

        if not allowed:
            return


        lock = self.get_lock(
            ctx.channel.id
        )

        if lock.locked():
            return


        async with lock:

            # منع وجود أكثر من فعالية
            old_session = self.active_games.get(
                ctx.guild.id
            )

            if old_session:

                if old_session.is_running:

                    await ctx.send(
                        "⚠️ توجد لعبة قيد التشغيل بالفعل!",
                        delete_after=5
                    )

                    return

                await ctx.send(
                    "⚠️ توجد فعالية محفوظة حالياً.\n"
                    "استخدم `انهي` لحذفها ثم أنشئ فعالية جديدة.",
                    delete_after=7
                )

                return


            session = GameSession(
                ctx.author.id
            )

            self.active_games[
                ctx.guild.id
            ] = session


            embed = self.create_control_embed(
                session,
                ctx.author.display_name
            )


            view = GameControlView(
                self,
                ctx.guild.id
            )


            message = await ctx.send(
                embed=embed,
                view=view
            )


            session.control_message = message


            try:

                await ctx.message.delete()

            except discord.HTTPException:

                pass


    # =====================================================
    # تعديل اسم اللعبة
    # =====================================================

    @commands.command(
        name=COMMAND_EDIT,
        aliases=["تعديل-اسم"]
    )
    async def edit_game_name(
        self,
        ctx,
        *,
        new_name: str = None
    ):

        if ctx.guild is None:
            return


        allowed = await self.has_command_permission(
            ctx.author,
            COMMAND_EDIT,
            ctx.channel.id
        )

        if not allowed:
            return


        session = self.active_games.get(
            ctx.guild.id
        )


        if not session:

            await ctx.send(
                "⚠️ لا توجد فعالية محفوظة حالياً.\n"
                "استخدم `انشاء-لعبة` أولاً.",
                delete_after=5
            )

            return


        if session.is_running:

            await ctx.send(
                "⚠️ لا يمكنك تعديل اسم اللعبة أثناء تشغيلها.",
                delete_after=5
            )

            return


        if new_name:

            new_name = new_name.strip()


            if not new_name:

                await ctx.send(
                    "❌ اسم اللعبة لا يمكن أن يكون فارغًا.",
                    delete_after=5
                )

                return


            if len(new_name) > 100:

                await ctx.send(
                    "❌ اسم اللعبة طويل جدًا.\n"
                    "الحد الأقصى 100 حرف.",
                    delete_after=5
                )

                return


            old_name = session.game_name

            session.game_name = new_name


            await self.update_control_message(
                session,
                ctx.guild
            )


            await ctx.send(
                "✅ **تم تعديل اسم اللعبة بنجاح!**\n\n"
                f"📝 الاسم السابق:\n"
                f"**{old_name}**\n\n"
                f"🎮 الاسم الجديد:\n"
                f"**{new_name}**",
                delete_after=8
            )


            try:

                await ctx.message.delete()

            except discord.HTTPException:

                pass

            return


        embed = discord.Embed(
            title="✏️ تعديل اسم اللعبة",
            description=(
                f"الاسم الحالي:\n"
                f"**{session.game_name}**\n\n"
                "اضغط الزر بالأسفل لفتح نافذة تعديل الاسم."
            ),
            color=discord.Color.orange()
        )


        view = EditNameView(
            self,
            session
        )


        await ctx.send(
            embed=embed,
            view=view,
            delete_after=30
        )


        try:

            await ctx.message.delete()

        except discord.HTTPException:

            pass


    # =====================================================
    # بدء اللعبة
    # =====================================================

    @commands.command(
        name=COMMAND_START
    )
    async def start_game_command(
        self,
        ctx
    ):

        if ctx.guild is None:
            return


        allowed = await self.has_command_permission(
            ctx.author,
            COMMAND_START,
            ctx.channel.id
        )

        if not allowed:
            return


        lock = self.get_lock(
            ctx.channel.id
        )

        if lock.locked():
            return


        async with lock:

            session = self.active_games.get(
                ctx.guild.id
            )


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
                f"🚀 **بدأت لعبة {session.game_name}!**\n\n"
                f"📚 عدد الصور: **{len(session.questions)}**\n"
                "🔥 استعدوا للصورة الأولى..."
            )


        await self.run_game_loop(
            ctx.channel
        )


    # =====================================================
    # ترتيب النقاط
    # =====================================================

    @commands.command(
        name=COMMAND_LEADERBOARD
    )
    async def leaderboard(
        self,
        ctx
    ):

        if ctx.guild is None:
            return


        allowed = await self.has_command_permission(
            ctx.author,
            COMMAND_LEADERBOARD,
            ctx.channel.id
        )

        if not allowed:
            return


        session = self.active_games.get(
            ctx.guild.id
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


        for index, (
            user_id,
            points
        ) in enumerate(
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
    # تصفير النقاط
    # =====================================================

    @commands.command(
        name=COMMAND_RESET
    )
    async def reset_scores(
        self,
        ctx
    ):

        if ctx.guild is None:
            return


        allowed = await self.has_command_permission(
            ctx.author,
            COMMAND_RESET,
            ctx.channel.id
        )

        if not allowed:
            return


        lock = self.get_lock(
            ctx.channel.id
        )


        if lock.locked():
            return


        async with lock:

            session = self.active_games.get(
                ctx.guild.id
            )


            if not session:

                await ctx.send(
                    "⚠️ لا توجد فعالية محفوظة حالياً.",
                    delete_after=5
                )

                return


            players_count = len(
                session.scores
            )


            session.scores.clear()


            await ctx.send(
                "🔄 **تم تصفير النقاط بنجاح!**\n\n"
                f"🏆 تم تصفير نقاط **{players_count}** لاعب.\n"
                "🖼️ الصور والأسئلة **لم يتم حذفها**.\n\n"
                "✅ يمكنك بدء اللعبة من جديد باستخدام `ابدا`."
            )


            try:

                await ctx.message.delete()

            except discord.HTTPException:

                pass


    # =====================================================
    # إنهاء اللعبة
    # =====================================================

    @commands.command(
        name=COMMAND_FINISH
    )
    async def finish_game_command(
        self,
        ctx
    ):

        if ctx.guild is None:
            return


        allowed = await self.has_command_permission(
            ctx.author,
            COMMAND_FINISH,
            ctx.channel.id
        )

        if not allowed:
            return


        lock = self.get_lock(
            ctx.channel.id
        )


        if lock.locked():
            return


        async with lock:

            session = self.active_games.get(
                ctx.guild.id
            )


            if not session:

                await ctx.send(
                    "⚠️ لا توجد فعالية محفوظة حالياً.",
                    delete_after=5
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


            if self.active_games.get(
                ctx.guild.id
            ) is session:

                del self.active_games[
                    ctx.guild.id
                ]


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
    # تشغيل اللعبة
    # =====================================================

    async def run_game_loop(
        self,
        channel
    ):

        guild = channel.guild

        session = self.active_games.get(
            guild.id
        )


        if not session:
            return


        for index, question in enumerate(
            session.questions
        ):

            if not session.is_running:
                break


            session.current_question_index = index


            question_number = index + 1

            total_questions = len(
                session.questions
            )


            question_start_time = (
                asyncio.get_running_loop().time()
            )


            embed = discord.Embed(
                title=(
                    f"🖼️ {session.game_name} | "
                    f"السؤال {question_number} من "
                    f"{total_questions}"
                ),
                description=(
                    "⚡ **خمن الماركة من الصورة!**\n\n"
                    "⏰ **مدة السؤال: 15 ثانية**\n\n"
                    "🏆 أول إجابة صحيحة تحصل على نقطة!"
                ),
                color=discord.Color.gold()
            )


            embed.set_image(
                url=question["image"]
            )


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


            try:

                message = await self.bot.wait_for(
                    "message",
                    timeout=15.0,
                    check=check
                )


                elapsed = (
                    asyncio.get_running_loop().time()
                    - question_start_time
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
                    "✅ **إجابة صحيحة!**\n"
                    "🏆 حصلت على **نقطة واحدة**.\n"
                    f"📊 مجموع نقاطك: "
                    f"**{session.scores[user_id]}**"
                )


                remaining_time = max(
                    0,
                    15.0 - elapsed
                )


                if remaining_time > 0:

                    await asyncio.sleep(
                        remaining_time
                    )


            except asyncio.TimeoutError:

                await channel.send(
                    "⏰ **انتهى وقت السؤال!**\n"
                    "❌ لم يتمكن أحد من الإجابة.\n"
                    f"✅ الماركة الصحيحة كانت: "
                    f"`{question['answer']}`"
                )


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


        if session.is_running:

            await channel.send(
                f"🏁 **انتهت لعبة {session.game_name}!**\n\n"
                "❤️ شكراً لحضوركم ومشاركتكم.\n"
                "🏆 **النتائج ما زالت محفوظة.**\n"
                "📊 استخدموا `ط` لعرض الترتيب.\n"
                "🔄 استخدموا `دن` لتصفير النقاط وإعادة اللعب."
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


        medals = [
            "🥇",
            "🥈",
            "🥉"
        ]


        description = []


        for index, (
            user_id,
            points
        ) in enumerate(
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
            title=(
                f"🏆 النتائج النهائية - "
                f"{session.game_name}"
            ),
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
        guild_id
    ):

        super().__init__(
            timeout=None
        )

        self.cog = cog
        self.guild_id = guild_id


    # =====================================================
    # إضافة سؤال
    #
    # الصلاحية من أمر انشاء-لعبة
    # =====================================================

    @ui.button(
        label="إضافة سؤال 🖼️",
        style=discord.ButtonStyle.primary
    )
    async def add_question(
        self,
        interaction,
        button
    ):

        if not await self.cog.check_button_permission(
            interaction,
            COMMAND_CREATE
        ):

            return


        session = self.cog.active_games.get(
            self.guild_id
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


        modal = QuestionAnswerModal(
            self.cog,
            session,
            interaction.user.id
        )


        await interaction.response.send_modal(
            modal
        )


    # =====================================================
    # بدء اللعبة
    # =====================================================

    @ui.button(
        label="بدء اللعبة ▶️",
        style=discord.ButtonStyle.success
    )
    async def start_game_button(
        self,
        interaction,
        button
    ):

        if not await self.cog.check_button_permission(
            interaction,
            COMMAND_START
        ):

            return


        lock = self.cog.get_lock(
            interaction.channel.id
        )


        if lock.locked():
            return


        async with lock:

            session = self.cog.active_games.get(
                self.guild_id
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
            session.current_question_index = 0
            session.starting = False


            await interaction.response.send_message(
                f"🚀 **بدأت لعبة {session.game_name}!**\n\n"
                f"📚 عدد الصور: **{len(session.questions)}**\n"
                "🔥 استعدوا للصورة الأولى..."
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
        interaction,
        button
    ):

        if not await self.cog.check_button_permission(
            interaction,
            COMMAND_FINISH
        ):

            return


        session = self.cog.active_games.get(
            self.guild_id
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


        if self.guild_id in self.cog.active_games:

            del self.cog.active_games[
                self.guild_id
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
# View تعديل الاسم
# =========================================================

class EditNameView(ui.View):

    def __init__(
        self,
        cog,
        session
    ):

        super().__init__(
            timeout=30
        )

        self.cog = cog
        self.session = session


    @ui.button(
        label="✏️ تعديل اسم اللعبة",
        style=discord.ButtonStyle.primary
    )
    async def edit_name_button(
        self,
        interaction,
        button
    ):

        if not await self.cog.check_button_permission(
            interaction,
            COMMAND_EDIT
        ):

            return


        session = self.cog.active_games.get(
            interaction.guild.id
        )


        if not session:

            await interaction.response.send_message(
                "❌ الفعالية لم تعد موجودة.",
                ephemeral=True
            )

            return


        if session.is_running:

            await interaction.response.send_message(
                "❌ لا يمكنك تعديل الاسم أثناء تشغيل اللعبة.",
                ephemeral=True
            )

            return


        modal = EditGameNameModal(
            self.cog,
            session
        )


        await interaction.response.send_modal(
            modal
        )


# =========================================================
# Modal تعديل اسم اللعبة
# =========================================================

class EditGameNameModal(
    ui.Modal,
    title="تعديل اسم اللعبة"
):

    def __init__(
        self,
        cog,
        session
    ):

        super().__init__()

        self.cog = cog
        self.session = session


        self.name_input = ui.TextInput(
            label="اسم اللعبة الجديد",
            placeholder="اكتب اسم اللعبة الجديد...",
            default=session.game_name,
            required=True,
            min_length=1,
            max_length=100,
            style=discord.TextStyle.short
        )


        self.add_item(
            self.name_input
        )


    async def on_submit(
        self,
        interaction
    ):

        # إعادة فحص الصلاحية قبل تنفيذ التعديل
        allowed = await self.cog.has_command_permission(
            interaction.user,
            COMMAND_EDIT,
            interaction.channel_id
        )


        if not allowed:

            await interaction.response.send_message(
                "❌ ليس لديك صلاحية استخدام هذا الأمر.",
                ephemeral=True
            )

            return


        new_name = self.name_input.value.strip()


        if not new_name:

            await interaction.response.send_message(
                "❌ يجب كتابة اسم للعبة.",
                ephemeral=True
            )

            return


        old_name = self.session.game_name

        self.session.game_name = new_name


        await self.cog.update_control_message(
            self.session,
            interaction.guild
        )


        await interaction.response.send_message(
            "✅ **تم تعديل اسم اللعبة بنجاح!**\n\n"
            f"📝 الاسم السابق:\n"
            f"**{old_name}**\n\n"
            f"🎮 الاسم الجديد:\n"
            f"**{new_name}**",
            ephemeral=True
        )


# =========================================================
# Modal إضافة سؤال
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
            label="الماركة الصحيحة",
            placeholder="اكتب اسم الماركة صاحبة الصورة...",
            required=True,
            max_length=200,
            style=discord.TextStyle.short
        )


        self.add_item(
            self.answer_input
        )


    async def on_submit(
        self,
        interaction
    ):

        # إعادة فحص الصلاحية قبل متابعة العملية
        allowed = await self.cog.has_command_permission(
            interaction.user,
            COMMAND_CREATE,
            interaction.channel_id
        )


        if not allowed:

            await interaction.response.send_message(
                "❌ ليس لديك صلاحية إضافة أسئلة.",
                ephemeral=True
            )

            return


        answer = self.answer_input.value.strip()


        if not answer:

            await interaction.response.send_message(
                "❌ يجب كتابة اسم الماركة.",
                ephemeral=True
            )

            return


        await interaction.response.send_message(
            "🖼️ **تم تجهيز السؤال!**\n\n"
            "الآن أرسل صورة الماركة في هذا الروم.\n"
            "⏳ **لا يوجد وقت محدد، أرسلها متى ما تريد.**\n\n"
            "⚠️ **مهم:** لا تحذف الصورة بعد إرسالها، "
            "لأن البوت سيستخدم رابطها أثناء اللعبة.",
            ephemeral=True
        )


        def image_check(message):

            return (
                message.guild is not None
                and message.guild.id == interaction.guild.id
                and message.channel.id == interaction.channel_id
                and message.author.id == self.user_id
                and not message.author.bot
                and len(message.attachments) > 0
            )


        try:

            message = await self.cog.bot.wait_for(
                "message",
                check=image_check
            )

        except asyncio.CancelledError:

            return


        # إعادة فحص الصلاحية بعد إرسال الصورة
        allowed = await self.cog.has_command_permission(
            interaction.user,
            COMMAND_CREATE,
            interaction.channel_id
        )


        if not allowed:

            await interaction.followup.send(
                "❌ لم تعد لديك صلاحية إضافة الأسئلة.",
                ephemeral=True
            )

            return


        attachment = message.attachments[0]


        if not attachment.content_type:

            await interaction.followup.send(
                "❌ الملف المرسل ليس صورة واضحة.\n"
                "أرسل صورة ثم حاول إضافة الماركة مرة أخرى.",
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
            "✅ **تم حفظ الصورة بنجاح!**\n"
            f"🖼️ رقم السؤال: `{question_number}`\n"
            f"📚 إجمالي الصور: `{question_number}`\n\n"
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
