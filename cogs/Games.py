import os
import asyncio
import random
import time

import discord
from discord.ext import commands
from pymongo import MongoClient


# =========================================================
# إعدادات النظام
# =========================================================

GAME_CHANNEL_ID = 1550797517237518417

ALLOWED_ROLE_ID = 1544078469657530578

MONGO_URI = os.environ.get("MONGO_URI")

if not MONGO_URI:
    raise RuntimeError("❌ MONGO_URI غير موجود في Environment Variables")

mongo_client = MongoClient(MONGO_URI)

db = mongo_client["discord_bot_db"]

GAME_STATS = db["game_stats"]


# =========================================================
# إعدادات عامة
# =========================================================

MIN_PLAYERS = 2
MAX_PLAYERS = 15

GAME_TIMEOUT = 600


# =========================================================
# دوال مساعدة
# =========================================================

def has_game_role(member: discord.Member) -> bool:
    return any(role.id == ALLOWED_ROLE_ID for role in member.roles)


def format_number(number: int) -> str:
    return f"{number:,}"


def get_stats(user_id: int):
    data = GAME_STATS.find_one({"user_id": user_id})

    if not data:
        data = {
            "user_id": user_id,
            "wins": 0,
            "games": 0,
            "points": 0
        }
        GAME_STATS.insert_one(data)

    return data


def add_game(user_id: int, win=False, points=0):
    GAME_STATS.update_one(
        {"user_id": user_id},
        {
            "$inc": {
                "games": 1,
                "wins": 1 if win else 0,
                "points": points
            },
            "$setOnInsert": {
                "user_id": user_id
            }
        },
        upsert=True
    )


# =========================================================
# Game Manager
# =========================================================

class GameManager:

    def __init__(self):
        self.active_game = None

    def is_active(self):
        return self.active_game is not None

    def start(self, game):
        self.active_game = game

    def stop(self):
        self.active_game = None


GAME_MANAGER = GameManager()


# =========================================================
# Base View
# =========================================================

class BaseGameView(discord.ui.View):

    def __init__(self, cog, timeout=GAME_TIMEOUT):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.message = None

    async def interaction_check(self, interaction: discord.Interaction):

        if interaction.channel_id != GAME_CHANNEL_ID:
            await interaction.response.send_message(
                "هذه اللعبة لا تعمل هنا.",
                ephemeral=True
            )
            return False

        if not has_game_role(interaction.user):
            await interaction.response.send_message(
                "❌ ليس لديك صلاحية استخدام ألعاب السيرفر.",
                ephemeral=True
            )
            return False

        return True


# =========================================================
# القائمة الرئيسية
# =========================================================

class GamesMenuView(BaseGameView):

    def __init__(self, cog):
        super().__init__(cog, timeout=180)

    @discord.ui.button(
        label="🎲 أعلى نرد",
        style=discord.ButtonStyle.primary,
        row=0
    )
    async def dice_game(self, interaction, button):

        await self.cog.create_game(
            interaction,
            DiceGame(self.cog)
        )

    @discord.ui.button(
        label="⚡ أسرع إجابة",
        style=discord.ButtonStyle.success,
        row=0
    )
    async def speed_game(self, interaction, button):

        await self.cog.create_game(
            interaction,
            SpeedGame(self.cog)
        )

    @discord.ui.button(
        label="💣 القنبلة",
        style=discord.ButtonStyle.danger,
        row=1
    )
    async def bomb_game(self, interaction, button):

        await self.cog.create_game(
            interaction,
            BombGame(self.cog)
        )

    @discord.ui.button(
        label="🔢 خمن الرقم",
        style=discord.ButtonStyle.primary,
        row=1
    )
    async def guess_game(self, interaction, button):

        await self.cog.create_game(
            interaction,
            GuessGame(self.cog)
        )

    @discord.ui.button(
        label="🔐 الهروب من الغرفة",
        style=discord.ButtonStyle.secondary,
        row=2
    )
    async def escape_game(self, interaction, button):

        await self.cog.create_game(
            interaction,
            EscapeGame(self.cog)
        )

    @discord.ui.button(
        label="🏆 الترتيب",
        style=discord.ButtonStyle.secondary,
        row=2
    )
    async def leaderboard(self, interaction, button):

        await self.cog.show_leaderboard(interaction)


# =========================================================
# Base Game
# =========================================================

class BaseGame:

    name = "لعبة"

    def __init__(self, cog):

        self.cog = cog

        self.players = {}

        self.message = None

        self.started = False

        self.finished = False

        self.lock = asyncio.Lock()

    def add_player(self, member):

        if member.id in self.players:
            return False

        if len(self.players) >= MAX_PLAYERS:
            return False

        self.players[member.id] = member

        return True

    def remove_player(self, user_id):

        self.players.pop(user_id, None)

    def player_mentions(self):

        if not self.players:
            return "لا يوجد لاعبين حتى الآن."

        return "\n".join(
            f"{index}. {member.mention}"
            for index, member in enumerate(
                self.players.values(),
                start=1
            )
        )

    def lobby_embed(self):

        embed = discord.Embed(
            title=f"🎮 {self.name}",
            description=(
                "اضغط **انضمام** للدخول إلى اللعبة.\n\n"
                f"👥 اللاعبين: **{len(self.players)}/{MAX_PLAYERS}**\n\n"
                "عندما يصل العدد إلى لاعبين أو أكثر "
                "يمكن بدء اللعبة."
            )
        )

        embed.add_field(
            name="👥 اللاعبون",
            value=self.player_mentions(),
            inline=False
        )

        return embed

    async def start_game(self, interaction):

        if len(self.players) < MIN_PLAYERS:

            await interaction.response.send_message(
                f"❌ تحتاج إلى {MIN_PLAYERS} لاعبين على الأقل.",
                ephemeral=True
            )

            return

        if self.started:

            await interaction.response.send_message(
                "اللعبة بدأت بالفعل.",
                ephemeral=True
            )

            return

        self.started = True

        await interaction.response.defer()

        await self.run()

    async def run(self):
        raise NotImplementedError

    async def finish(self):

        if self.finished:
            return

        self.finished = True

        GAME_MANAGER.stop()


# =========================================================
# Lobby View
# =========================================================

class GameLobbyView(BaseGameView):

    def __init__(self, cog, game):

        super().__init__(cog)

        self.game = game

    @discord.ui.button(
        label="🎮 انضمام",
        style=discord.ButtonStyle.success
    )
    async def join(self, interaction, button):

        if self.game.started:

            await interaction.response.send_message(
                "اللعبة بدأت بالفعل.",
                ephemeral=True
            )

            return

        if len(self.game.players) >= MAX_PLAYERS:

            await interaction.response.send_message(
                "❌ اللعبة ممتلئة.",
                ephemeral=True
            )

            return

        if self.game.add_player(interaction.user):

            await interaction.response.edit_message(
                embed=self.game.lobby_embed(),
                view=self
            )

        else:

            await interaction.response.send_message(
                "أنت داخل اللعبة بالفعل.",
                ephemeral=True
            )

    @discord.ui.button(
        label="🚀 بدء اللعبة",
        style=discord.ButtonStyle.primary
    )
    async def start(self, interaction, button):

        await self.game.start_game(interaction)

    @discord.ui.button(
        label="❌ إلغاء",
        style=discord.ButtonStyle.danger
    )
    async def cancel(self, interaction, button):

        await self.game.finish()

        await interaction.response.edit_message(
            embed=discord.Embed(
                title="❌ تم إلغاء اللعبة",
                description="تم إلغاء اللعبة من قبل أحد اللاعبين."
            ),
            view=None
        )


# =========================================================
# 🎲 لعبة أعلى نرد
# =========================================================

class DiceGame(BaseGame):

    name = "🎲 أعلى نرد"

    async def run(self):

        results = {}

        embed = discord.Embed(
            title=self.name,
            description=(
                "🎲 حان وقت النرد!\n\n"
                "كل لاعب لديه محاولة واحدة."
            )
        )

        view = DiceView(self)

        await self.message.edit(
            embed=embed,
            view=view
        )

    async def finish_rolls(self):

        if len(results := getattr(self, "results", {})) < len(self.players):

            return

        winner_id = max(
            results,
            key=results.get
        )

        winner = self.players[winner_id]

        text = []

        for user_id, number in results.items():

            member = self.players[user_id]

            text.append(
                f"{member.mention} → 🎲 **{number}**"
            )

        add_game(
            winner.id,
            win=True,
            points=100
        )

        for user_id in self.players:

            if user_id != winner.id:

                add_game(
                    user_id,
                    win=False,
                    points=20
                )

        embed = discord.Embed(
            title="🏆 انتهت لعبة أعلى نرد!",
            description=(
                f"👑 الفائز: {winner.mention}\n\n"
                + "\n".join(text)
            )
        )

        await self.message.edit(
            embed=embed,
            view=None
        )

        await self.finish()


class DiceView(BaseGameView):

    def __init__(self, game):

        super().__init__(game.cog)

        self.game = game

    @discord.ui.button(
        label="🎲 ارمي النرد",
        style=discord.ButtonStyle.primary
    )
    async def roll(self, interaction, button):

        if interaction.user.id not in self.game.players:

            await interaction.response.send_message(
                "❌ أنت لست داخل اللعبة.",
                ephemeral=True
            )

            return

        if not hasattr(self.game, "results"):

            self.game.results = {}

        if interaction.user.id in self.game.results:

            await interaction.response.send_message(
                "لقد رميت النرد بالفعل.",
                ephemeral=True
            )

            return

        number = random.randint(1, 100)

        self.game.results[interaction.user.id] = number

        await interaction.response.send_message(
            f"🎲 نتيجتك: **{number}**",
            ephemeral=True
        )

        await self.game.finish_rolls()


# =========================================================
# ⚡ أسرع إجابة
# =========================================================

QUESTIONS = [

    {
        "q": "كم عدد أيام الأسبوع؟",
        "answers": ["5", "6", "7", "8"],
        "correct": "7"
    },

    {
        "q": "ما هو الكوكب المعروف بالكوكب الأحمر؟",
        "answers": ["المريخ", "الأرض", "الزهرة", "عطارد"],
        "correct": "المريخ"
    },

    {
        "q": "كم يساوي 10 × 10؟",
        "answers": ["50", "100", "150", "200"],
        "correct": "100"
    },

    {
        "q": "ما عاصمة الأردن؟",
        "answers": ["عمان", "إربد", "العقبة", "الزرقاء"],
        "correct": "عمان"
    },

    {
        "q": "كم عدد أشهر السنة؟",
        "answers": ["10", "11", "12", "13"],
        "correct": "12"
    }
]


class SpeedGame(BaseGame):

    name = "⚡ أسرع إجابة"

    async def run(self):

        self.round = 0

        self.scores = {
            user_id: 0
            for user_id in self.players
        }

        await self.next_question()

    async def next_question(self):

        if self.round >= len(QUESTIONS):

            await self.finish_game()

            return

        question = QUESTIONS[self.round]

        embed = discord.Embed(
            title="⚡ أسرع إجابة",
            description=(
                f"**السؤال {self.round + 1}/{len(QUESTIONS)}**\n\n"
                f"🧠 {question['q']}"
            )
        )

        embed.add_field(
            name="📊 النقاط",
            value="\n".join(
                f"{self.players[user_id].mention} — {score}"
                for user_id, score in self.scores.items()
            ),
            inline=False
        )

        self.current_question = question

        view = SpeedAnswerView(self)

        await self.message.edit(
            embed=embed,
            view=view
        )

    async def answer(self, interaction, answer):

        if answer == self.current_question["correct"]:

            self.scores[interaction.user.id] += 1

            await interaction.response.send_message(
                "✅ إجابة صحيحة! +1 نقطة",
                ephemeral=True
            )

            self.round += 1

            await asyncio.sleep(1)

            await self.next_question()

        else:

            await interaction.response.send_message(
                "❌ إجابة خاطئة!",
                ephemeral=True
            )

    async def finish_game(self):

        winner_id = max(
            self.scores,
            key=self.scores.get
        )

        winner = self.players[winner_id]

        ranking = sorted(
            self.scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        lines = []

        for index, (user_id, score) in enumerate(
            ranking,
            start=1
        ):

            lines.append(
                f"**{index}.** {self.players[user_id].mention} — "
                f"**{score}** نقطة"
            )

            add_game(
                user_id,
                win=user_id == winner_id,
                points=score * 25
            )

        embed = discord.Embed(
            title="🏆 انتهت أسرع إجابة!",
            description="\n".join(lines)
        )

        await self.message.edit(
            embed=embed,
            view=None
        )

        await self.finish()


class SpeedAnswerView(BaseGameView):

    def __init__(self, game):

        super().__init__(game.cog, timeout=20)

        self.game = game

        answers = game.current_question["answers"]

        for index, answer in enumerate(answers):

            button = discord.ui.Button(
                label=answer,
                style=discord.ButtonStyle.primary,
                row=index // 2
            )

            async def callback(
                interaction,
                answer=answer
            ):

                if interaction.user.id not in self.game.players:

                    await interaction.response.send_message(
                        "أنت لست داخل اللعبة.",
                        ephemeral=True
                    )

                    return

                await self.game.answer(
                    interaction,
                    answer
                )

            button.callback = callback

            self.add_item(button)


# =========================================================
# 💣 لعبة القنبلة
# =========================================================

class BombGame(BaseGame):

    name = "💣 القنبلة"

    async def run(self):

        self.alive = list(self.players.keys())

        self.holder = random.choice(self.alive)

        self.round_number = 1

        await self.bomb_round()

    async def bomb_round(self):

        if len(self.alive) <= 1:

            winner = self.players[self.alive[0]]

            add_game(
                winner.id,
                win=True,
                points=150
            )

            embed = discord.Embed(
                title="🏆 الناجي الأخير!",
                description=f"👑 الفائز: {winner.mention}"
            )

            await self.message.edit(
                embed=embed,
                view=None
            )

            await self.finish()

            return

        holder = self.players[self.holder]

        embed = discord.Embed(
            title="💣 القنبلة",
            description=(
                f"💣 القنبلة الآن مع {holder.mention}\n\n"
                "اضغط زر **تمرير القنبلة** واختر لاعبًا."
            )
        )

        embed.add_field(
            name="👥 اللاعبون",
            value="\n".join(
                self.players[user_id].mention
                for user_id in self.alive
            )
        )

        view = BombView(self)

        await self.message.edit(
            embed=embed,
            view=view
        )

    async def pass_bomb(self, interaction, target_id):

        if interaction.user.id != self.holder:

            await interaction.response.send_message(
                "❌ القنبلة ليست معك!",
                ephemeral=True
            )

            return

        if target_id not in self.alive:

            await interaction.response.send_message(
                "هذا اللاعب خرج من اللعبة.",
                ephemeral=True
            )

            return

        self.holder = target_id

        await interaction.response.defer()

        await asyncio.sleep(
            random.uniform(2, 5)
        )

        # احتمال انفجار القنبلة
        if random.random() < 0.25:

            eliminated = self.holder

            self.alive.remove(eliminated)

            member = self.players[eliminated]

            embed = discord.Embed(
                title="💥 انفجرت القنبلة!",
                description=(
                    f"💥 خرج {member.mention} من اللعبة!\n\n"
                    f"👥 المتبقون: **{len(self.alive)}**"
                )
            )

            await self.message.edit(
                embed=embed,
                view=None
            )

            await asyncio.sleep(2)

            if self.alive:

                self.holder = random.choice(self.alive)

            await self.bomb_round()

        else:

            await self.bomb_round()


class BombView(BaseGameView):

    def __init__(self, game):

        super().__init__(game.cog, timeout=30)

        self.game = game

        self.add_item(
            BombSelect(game)
        )


class BombSelect(discord.ui.Select):

    def __init__(self, game):

        self.game = game

        options = []

        for user_id in game.alive:

            member = game.players[user_id]

            options.append(
                discord.SelectOption(
                    label=member.display_name[:100],
                    value=str(user_id)
                )
            )

        super().__init__(
            placeholder="💣 اختر اللاعب الذي ستمرر له القنبلة...",
            options=options
        )

    async def callback(self, interaction):

        target_id = int(self.values[0])

        await self.game.pass_bomb(
            interaction,
            target_id
        )


# =========================================================
# 🔢 خمن الرقم
# =========================================================

class GuessGame(BaseGame):

    name = "🔢 خمن الرقم"

    async def run(self):

        self.number = random.randint(1, 100)

        self.attempts = {
            user_id: 0
            for user_id in self.players
        }

        embed = discord.Embed(
            title="🔢 خمن الرقم",
            description=(
                "البوت اختار رقمًا من **1 إلى 100**.\n\n"
                "كل لاعب لديه محاولات حتى يجد الرقم."
            )
        )

        view = GuessView(self)

        await self.message.edit(
            embed=embed,
            view=view
        )

    async def guess(self, interaction, number):

        self.attempts[interaction.user.id] += 1

        if number == self.number:

            attempts = self.attempts[interaction.user.id]

            add_game(
                interaction.user.id,
                win=True,
                points=max(
                    50,
                    200 - attempts * 20
                )
            )

            embed = discord.Embed(
                title="🏆 تم العثور على الرقم!",
                description=(
                    f"🎯 الرقم كان: **{self.number}**\n\n"
                    f"👑 الفائز: {interaction.user.mention}\n"
                    f"🔢 عدد محاولاته: **{attempts}**"
                )
            )

            await interaction.response.edit_message(
                embed=embed,
                view=None
            )

            await self.finish()

            return

        if number < self.number:

            message = "⬆️ الرقم أكبر."

        else:

            message = "⬇️ الرقم أصغر."

        await interaction.response.send_message(
            message,
            ephemeral=True
        )


class GuessModal(discord.ui.Modal):

    def __init__(self, game):

        super().__init__(
            title="🔢 خمن الرقم"
        )

        self.game = game

        self.number = discord.ui.TextInput(
            label="أدخل رقمًا من 1 إلى 100",
            placeholder="مثال: 57",
            required=True,
            max_length=3
        )

        self.add_item(self.number)

    async def on_submit(self, interaction):

        try:

            number = int(self.number.value)

        except ValueError:

            await interaction.response.send_message(
                "❌ يجب إدخال رقم صحيح.",
                ephemeral=True
            )

            return

        if not 1 <= number <= 100:

            await interaction.response.send_message(
                "❌ الرقم يجب أن يكون بين 1 و100.",
                ephemeral=True
            )

            return

        await self.game.guess(
            interaction,
            number
        )


class GuessView(BaseGameView):

    def __init__(self, game):

        super().__init__(game.cog)

        self.game = game

    @discord.ui.button(
        label="🔢 خمن",
        style=discord.ButtonStyle.primary
    )
    async def guess(self, interaction, button):

        if interaction.user.id not in self.game.players:

            await interaction.response.send_message(
                "❌ أنت لست داخل اللعبة.",
                ephemeral=True
            )

            return

        await interaction.response.send_modal(
            GuessModal(self.game)
        )


# =========================================================
# 🔐 الهروب من الغرفة
# =========================================================

class EscapeGame(BaseGame):

    name = "🔐 الهروب من الغرفة"

    async def run(self):

        self.stage = 1

        self.correct_answers = {
            1: "مفتاح",
            2: "247",
            3: "المرآة"
        }

        await self.update_room()

    async def update_room(self):

        if self.stage > 3:

            winners = list(self.players.values())

            for member in winners:

                add_game(
                    member.id,
                    win=True,
                    points=100
                )

            embed = discord.Embed(
                title="🎉 نجحتم في الهروب!",
                description=(
                    "🔐 تمكن جميع اللاعبين من حل الألغاز "
                    "والخروج من الغرفة!\n\n"
                    "🏆 جميع المشاركين حصلوا على **100 نقطة**."
                )
            )

            await self.message.edit(
                embed=embed,
                view=None
            )

            await self.finish()

            return

        if self.stage == 1:

            text = (
                "🔐 **الغرفة الأولى**\n\n"
                "الباب مغلق.\n"
                "أمامك عدة أشياء، لكن أحدها سيساعدك على فتح الباب.\n\n"
                "ما الشيء الذي تبحث عنه؟"
            )

            options = [
                "كتاب",
                "مفتاح",
                "كرسي",
                "مصباح"
            ]

        elif self.stage == 2:

            text = (
                "🔐 **الغرفة الثانية**\n\n"
                "وجدتم خزنة تحتاج إلى رقم مكون من 3 أرقام.\n\n"
                "🧩 التلميح:\n"
                "2 + 4 = 6\n"
                "2 × 4 = 8\n"
                "لكن الرمز المطلوب هو الرقم السري الموجود في اللغز."
            )

            options = [
                "124",
                "247",
                "428",
                "684"
            ]

        else:

            text = (
                "🔐 **الغرفة الأخيرة**\n\n"
                "أمامكم باب لا يفتح إلا إذا عرفتم الشيء "
                "الذي يعكس كل شيء أمامه.\n\n"
                "ما هو؟"
            )

            options = [
                "الباب",
                "الكتاب",
                "المرآة",
                "الساعة"
            ]

        embed = discord.Embed(
            title="🔐 الهروب من الغرفة",
            description=text
        )

        embed.set_footer(
            text=f"المرحلة {self.stage}/3"
        )

        view = EscapeView(
            self,
            options
        )

        await self.message.edit(
            embed=embed,
            view=view
        )

    async def answer(self, interaction, answer):

        correct = self.correct_answers[self.stage]

        if answer == correct:

            await interaction.response.send_message(
                "✅ صحيح! تقدمتوا للمرحلة التالية.",
                ephemeral=True
            )

            self.stage += 1

            await asyncio.sleep(1)

            await self.update_room()

        else:

            await interaction.response.send_message(
                "❌ إجابة خاطئة.",
                ephemeral=True
            )


class EscapeView(BaseGameView):

    def __init__(self, game, options):

        super().__init__(game.cog)

        self.game = game

        for index, option in enumerate(options):

            button = discord.ui.Button(
                label=option,
                style=discord.ButtonStyle.primary,
                row=index // 2
            )

            async def callback(
                interaction,
                option=option
            ):

                if interaction.user.id not in self.game.players:

                    await interaction.response.send_message(
                        "❌ أنت لست داخل اللعبة.",
                        ephemeral=True
                    )

                    return

                await self.game.answer(
                    interaction,
                    option
                )

            button.callback = callback

            self.add_item(button)


# =========================================================
# Cog الرئيسي
# =========================================================

class GamesCog(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

    # =====================================================
    # الأمر الرئيسي
    # =====================================================

    @commands.command(
        name="العاب-العب"
    )
    async def games(self, ctx):

        # -------------------------------------------------
        # الروم
        # -------------------------------------------------

        if ctx.channel.id != GAME_CHANNEL_ID:

            return

        # -------------------------------------------------
        # الرتبة
        # -------------------------------------------------

        if not isinstance(ctx.author, discord.Member):

            return

        if not has_game_role(ctx.author):

            await ctx.send(
                "❌ لا تملك رتبة السماح باستخدام ألعاب السيرفر.",
                delete_after=5
            )

            return

        # -------------------------------------------------
        # منع تشغيل لعبتين
        # -------------------------------------------------

        if GAME_MANAGER.is_active():

            await ctx.send(
                "🎮 **يوجد لعبة جارية بالفعل!**\n"
                "انتظر حتى تنتهي اللعبة الحالية.",
                delete_after=5
            )

            return

        # -------------------------------------------------
        # القائمة
        # -------------------------------------------------

        embed = discord.Embed(
            title="🎮 ألعاب السيرفر",
            description=(
                "اختر اللعبة التي تريد تشغيلها من الأسفل.\n\n"
                "⚠️ يمكن تشغيل **لعبة واحدة فقط** في نفس الوقت."
            )
        )

        embed.add_field(
            name="🎲 ألعاب الحظ",
            value="🎲 أعلى نرد\n💣 القنبلة",
            inline=True
        )

        embed.add_field(
            name="🧠 ألعاب الذكاء",
            value="⚡ أسرع إجابة\n🔢 خمن الرقم",
            inline=True
        )

        embed.add_field(
            name="🔐 ألعاب جماعية",
            value="🔐 الهروب من الغرفة",
            inline=True
        )

        embed.set_footer(
            text="اختر لعبة من الأزرار بالأسفل"
        )

        await ctx.send(
            embed=embed,
            view=GamesMenuView(self)
        )

    # =====================================================
    # إنشاء اللعبة
    # =====================================================

    async def create_game(self, interaction, game):

        if GAME_MANAGER.is_active():

            await interaction.response.send_message(
                "🎮 **يوجد لعبة جارية بالفعل!**",
                ephemeral=True
            )

            return

        GAME_MANAGER.start(game)

        embed = game.lobby_embed()

        view = GameLobbyView(
            self,
            game
        )

        await interaction.response.edit_message(
            embed=embed,
            view=view
        )

        game.message = await interaction.original_response()

    # =====================================================
    # الترتيب
    # =====================================================

    async def show_leaderboard(self, interaction):

        top = list(
            GAME_STATS.find(
                {}
            ).sort(
                "points",
                -1
            ).limit(10)
        )

        if not top:

            await interaction.response.send_message(
                "🏆 لا توجد بيانات ألعاب حتى الآن.",
                ephemeral=True
            )

            return

        lines = []

        for index, data in enumerate(
            top,
            start=1
        ):

            user_id = data["user_id"]

            try:

                member = interaction.guild.get_member(
                    user_id
                )

                name = (
                    member.mention
                    if member
                    else f"<@{user_id}>"
                )

            except Exception:

                name = f"<@{user_id}>"

            lines.append(
                f"**{index}.** {name}\n"
                f"└ 🏆 {format_number(data.get('points', 0))} نقطة "
                f"| 🎮 {data.get('games', 0)} لعبة "
                f"| 👑 {data.get('wins', 0)} فوز"
            )

        embed = discord.Embed(
            title="🏆 ترتيب ألعاب السيرفر",
            description="\n\n".join(lines)
        )

        await interaction.response.edit_message(
            embed=embed,
            view=GamesMenuView(self)
        )


# =========================================================
# setup
# =========================================================

async def setup(bot):

    await bot.add_cog(
        GamesCog(bot)
    )
