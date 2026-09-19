import os
import asyncio
import random

import discord
from discord.ext import commands
from pymongo import MongoClient


# =========================================================
# إعدادات النظام
# =========================================================

GAME_CHANNEL_ID = 1550797517237518417

# رتبة التحكم بالألعاب والبوت
CONTROL_ROLE_ID = 1544078469657530578

# رتبة اللاعبين
PLAYER_ROLE_ID = 1544078847253811331

# عدد اللاعبين
MIN_PLAYERS = 2
MAX_PLAYERS = 15

# مدة الـ Lobby
LOBBY_TIMEOUT = 600


# =========================================================
# MongoDB
# =========================================================

MONGO_URI = os.environ.get("MONGO_URI")

if not MONGO_URI:
    raise RuntimeError(
        "❌ MONGO_URI غير موجود في Environment Variables"
    )

mongo_client = MongoClient(MONGO_URI)

db = mongo_client["discord_bot_db"]

GAME_STATS = db["game_stats"]


# =========================================================
# أدوات مساعدة
# =========================================================

def is_control_member(member: discord.Member) -> bool:
    return any(
        role.id == CONTROL_ROLE_ID
        for role in member.roles
    )


def is_player_member(member: discord.Member) -> bool:
    return any(
        role.id == PLAYER_ROLE_ID
        for role in member.roles
    )


def get_stats(user_id: int):

    data = GAME_STATS.find_one(
        {"user_id": user_id}
    )

    if data is None:

        data = {
            "user_id": user_id,
            "points": 0,
            "games": 0,
            "wins": 0
        }

        GAME_STATS.insert_one(data)

    return data


def add_stats(
    user_id: int,
    points: int = 0,
    games: int = 0,
    wins: int = 0
):

    GAME_STATS.update_one(
        {"user_id": user_id},
        {
            "$inc": {
                "points": points,
                "games": games,
                "wins": wins
            },
            "$setOnInsert": {
                "user_id": user_id
            }
        },
        upsert=True
    )


def reset_player(user_id: int):

    GAME_STATS.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "points": 0,
                "games": 0,
                "wins": 0
            }
        },
        upsert=True
    )


# =========================================================
# مدير الألعاب
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
# View أساسي
# =========================================================

class BaseView(discord.ui.View):

    def __init__(
        self,
        cog,
        timeout=LOBBY_TIMEOUT
    ):

        super().__init__(
            timeout=timeout
        )

        self.cog = cog


# =========================================================
# القائمة الرئيسية للألعاب
# =========================================================

class GamesSelectView(BaseView):

    def __init__(self, cog):

        super().__init__(
            cog,
            timeout=180
        )

        self.add_item(
            GamesSelect(cog)
        )


class GamesSelect(discord.ui.Select):

    def __init__(self, cog):

        self.cog = cog

        options = [

            discord.SelectOption(
                label="أعلى نرد",
                description="ارمِ النرد وحاول الحصول على أعلى رقم",
                emoji="🎲",
                value="dice"
            ),

            discord.SelectOption(
                label="أسرع إجابة",
                description="كن أسرع لاعب في اختيار الإجابة الصحيحة",
                emoji="⚡",
                value="speed"
            ),

            discord.SelectOption(
                label="القنبلة",
                description="مرر القنبلة وحاول ألا تنفجر معك",
                emoji="💣",
                value="bomb"
            ),

            discord.SelectOption(
                label="خمن الرقم",
                description="حاول معرفة الرقم السري",
                emoji="🔢",
                value="guess"
            ),

            discord.SelectOption(
                label="الهروب من الغرفة",
                description="حل الألغاز مع اللاعبين واهرب",
                emoji="🔐",
                value="escape"
            )

        ]

        super().__init__(
            placeholder="🎮 اختر اللعبة التي تريد تشغيلها...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        if interaction.channel_id != GAME_CHANNEL_ID:
            return

        if not isinstance(
            interaction.user,
            discord.Member
        ):
            return

        if not is_control_member(
            interaction.user
        ):

            await interaction.response.send_message(
                "❌ ليس لديك صلاحية تشغيل الألعاب.",
                ephemeral=True
            )

            return

        if GAME_MANAGER.is_active():

            await interaction.response.send_message(
                "🎮 **يوجد لعبة جارية بالفعل!**",
                ephemeral=True
            )

            return

        value = self.values[0]

        if value == "dice":
            game = DiceGame(self.cog)

        elif value == "speed":
            game = SpeedGame(self.cog)

        elif value == "bomb":
            game = BombGame(self.cog)

        elif value == "guess":
            game = GuessGame(self.cog)

        elif value == "escape":
            game = EscapeGame(self.cog)

        else:
            return

        await self.cog.start_game(
            interaction,
            game
        )


# =========================================================
# Base Game
# =========================================================

class BaseGame:

    name = "لعبة"

    description = ""

    def __init__(self, cog):

        self.cog = cog

        self.players = {}

        self.message = None

        self.started = False

        self.finished = False

    # -----------------------------------------------------

    def add_player(
        self,
        member: discord.Member
    ):

        if member.id in self.players:
            return False

        if len(self.players) >= MAX_PLAYERS:
            return False

        self.players[
            member.id
        ] = member

        return True

    # -----------------------------------------------------

    def player_list(self):

        if not self.players:

            return "لا يوجد لاعبين حتى الآن."

        return "\n".join(
            f"**{index}.** {member.mention}"
            for index, member in enumerate(
                self.players.values(),
                start=1
            )
        )

    # -----------------------------------------------------

    def lobby_embed(self):

        embed = discord.Embed(
            title=f"🎮 {self.name}",
            description=(
                f"{self.description}\n\n"
                "اضغط **انضمام** للدخول إلى اللعبة.\n"
                "بعد دخول اللاعبين يستطيع المشرف بدء اللعبة."
            )
        )

        embed.add_field(
            name="👥 اللاعبين",
            value=(
                f"**{len(self.players)}/{MAX_PLAYERS}**"
            ),
            inline=True
        )

        embed.add_field(
            name="📋 القائمة",
            value=self.player_list(),
            inline=False
        )

        embed.set_footer(
            text="اللاعبون يحتاجون رتبة المشاركة"
        )

        return embed

    # -----------------------------------------------------

    async def finish(self):

        if self.finished:
            return

        self.finished = True

        GAME_MANAGER.stop()

    # -----------------------------------------------------

    async def run(self):

        raise NotImplementedError


# =========================================================
# Lobby View
# =========================================================

class GameLobbyView(BaseView):

    def __init__(
        self,
        cog,
        game
    ):

        super().__init__(
            cog,
            timeout=LOBBY_TIMEOUT
        )

        self.game = game

    # -----------------------------------------------------

    @discord.ui.button(
        label="انضمام",
        emoji="🎮",
        style=discord.ButtonStyle.success
    )
    async def join(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if interaction.channel_id != GAME_CHANNEL_ID:
            return

        if not isinstance(
            interaction.user,
            discord.Member
        ):
            return

        if self.game.started:

            await interaction.response.send_message(
                "❌ اللعبة بدأت بالفعل.",
                ephemeral=True
            )

            return

        if not is_player_member(
            interaction.user
        ):

            await interaction.response.send_message(
                "❌ تحتاج رتبة المشاركة حتى تنضم إلى الألعاب.",
                ephemeral=True
            )

            return

        if interaction.user.id in self.game.players:

            await interaction.response.send_message(
                "✅ أنت داخل اللعبة بالفعل.",
                ephemeral=True
            )

            return

        if len(self.game.players) >= MAX_PLAYERS:

            await interaction.response.send_message(
                "❌ اللعبة وصلت للحد الأقصى من اللاعبين.",
                ephemeral=True
            )

            return

        self.game.add_player(
            interaction.user
        )

        await interaction.response.edit_message(
            embed=self.game.lobby_embed(),
            view=self
        )

    # -----------------------------------------------------

    @discord.ui.button(
        label="بدء اللعبة",
        emoji="🚀",
        style=discord.ButtonStyle.primary
    )
    async def start(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not isinstance(
            interaction.user,
            discord.Member
        ):
            return

        if not is_control_member(
            interaction.user
        ):

            await interaction.response.send_message(
                "❌ فقط رتبة التحكم تستطيع بدء اللعبة.",
                ephemeral=True
            )

            return

        if len(self.game.players) < MIN_PLAYERS:

            await interaction.response.send_message(
                f"❌ تحتاج إلى {MIN_PLAYERS} لاعبين على الأقل.",
                ephemeral=True
            )

            return

        if self.game.started:

            await interaction.response.send_message(
                "❌ اللعبة بدأت بالفعل.",
                ephemeral=True
            )

            return

        self.game.started = True

        await interaction.response.defer()

        await self.game.run()

    # -----------------------------------------------------

    @discord.ui.button(
        label="إلغاء اللعبة",
        emoji="❌",
        style=discord.ButtonStyle.danger
    )
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not isinstance(
            interaction.user,
            discord.Member
        ):
            return

        if not is_control_member(
            interaction.user
        ):

            await interaction.response.send_message(
                "❌ فقط رتبة التحكم تستطيع إلغاء اللعبة.",
                ephemeral=True
            )

            return

        await self.game.finish()

        await interaction.response.edit_message(
            embed=discord.Embed(
                title="❌ تم إلغاء اللعبة",
                description=(
                    "تم إلغاء اللعبة من قبل الإدارة."
                )
            ),
            view=None
        )


# =========================================================
# 🎲 أعلى نرد
# =========================================================

class DiceGame(BaseGame):

    name = "🎲 أعلى نرد"

    description = (
        "كل لاعب يرمي النرد مرة واحدة.\n"
        "صاحب أعلى نتيجة يفوز."
    )

    async def run(self):

        self.results = {}

        embed = discord.Embed(
            title="🎲 أعلى نرد",
            description=(
                "اضغط الزر بالأسفل وارمِ النرد.\n\n"
                "كل لاعب لديه **محاولة واحدة فقط**."
            )
        )

        self.view = DiceView(
            self
        )

        await self.message.edit(
            embed=embed,
            view=self.view
        )

    async def finish_rolls(self):

        if len(self.results) < len(
            self.players
        ):
            return

        winner_id = max(
            self.results,
            key=self.results.get
        )

        winner = self.players[
            winner_id
        ]

        lines = []

        for user_id, number in sorted(
            self.results.items(),
            key=lambda x: x[1],
            reverse=True
        ):

            lines.append(
                f"{self.players[user_id].mention} "
                f"→ 🎲 **{number}**"
            )

        for user_id in self.players:

            add_stats(
                user_id,
                points=20
            )

        add_stats(
            winner.id,
            points=100,
            wins=1
        )

        for user_id in self.players:

            add_stats(
                user_id,
                games=1
            )

        embed = discord.Embed(
            title="🏆 انتهت لعبة أعلى نرد!",
            description=(
                f"👑 الفائز: {winner.mention}\n\n"
                + "\n".join(lines)
            )
        )

        await self.message.edit(
            embed=embed,
            view=None
        )

        await self.finish()


class DiceView(BaseView):

    def __init__(
        self,
        game
    ):

        super().__init__(
            game.cog,
            timeout=120
        )

        self.game = game

    @discord.ui.button(
        label="ارمِ النرد",
        emoji="🎲",
        style=discord.ButtonStyle.primary
    )
    async def roll(
        self,
        interaction,
        button
    ):

        if interaction.user.id not in self.game.players:

            await interaction.response.send_message(
                "❌ أنت لست داخل اللعبة.",
                ephemeral=True
            )

            return

        if interaction.user.id in self.game.results:

            await interaction.response.send_message(
                "❌ لقد رميت النرد بالفعل.",
                ephemeral=True
            )

            return

        number = random.randint(
            1,
            100
        )

        self.game.results[
            interaction.user.id
        ] = number

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
        "question": "كم عدد أيام الأسبوع؟",
        "answers": [
            "5",
            "6",
            "7",
            "8"
        ],
        "correct": "7"
    },

    {
        "question": "ما عاصمة الأردن؟",
        "answers": [
            "عمان",
            "إربد",
            "العقبة",
            "الزرقاء"
        ],
        "correct": "عمان"
    },

    {
        "question": "كم يساوي 10 × 10؟",
        "answers": [
            "50",
            "100",
            "150",
            "200"
        ],
        "correct": "100"
    },

    {
        "question": "ما هو الكوكب الأحمر؟",
        "answers": [
            "الأرض",
            "المريخ",
            "الزهرة",
            "عطارد"
        ],
        "correct": "المريخ"
    },

    {
        "question": "كم عدد أشهر السنة؟",
        "answers": [
            "10",
            "11",
            "12",
            "13"
        ],
        "correct": "12"
    }

]


class SpeedGame(BaseGame):

    name = "⚡ أسرع إجابة"

    description = (
        "أجب بأسرع ما يمكنك.\n"
        "كل إجابة صحيحة تمنحك نقطة."
    )

    async def run(self):

        self.scores = {
            user_id: 0
            for user_id in self.players
        }

        self.round = 0

        await self.next_question()

    async def next_question(self):

        if self.round >= len(QUESTIONS):

            await self.finish_game()

            return

        self.current_question = QUESTIONS[
            self.round
        ]

        embed = discord.Embed(
            title="⚡ أسرع إجابة",
            description=(
                f"### السؤال {self.round + 1}/"
                f"{len(QUESTIONS)}\n\n"
                f"🧠 **{self.current_question['question']}**"
            )
        )

        embed.add_field(
            name="🏆 النقاط",
            value="\n".join(
                f"{self.players[user_id].mention} "
                f"→ **{score}**"
                for user_id, score in self.scores.items()
            ),
            inline=False
        )

        view = SpeedView(
            self
        )

        await self.message.edit(
            embed=embed,
            view=view
        )

    async def answer(
        self,
        interaction,
        answer
    ):

        if answer == self.current_question["correct"]:

            self.scores[
                interaction.user.id
            ] += 1

            await interaction.response.send_message(
                "✅ إجابة صحيحة! **+1**",
                ephemeral=True
            )

            self.round += 1

            await asyncio.sleep(
                0.8
            )

            await self.next_question()

        else:

            await interaction.response.send_message(
                "❌ إجابة خاطئة.",
                ephemeral=True
            )

    async def finish_game(self):

        winner_id = max(
            self.scores,
            key=self.scores.get
        )

        ranking = sorted(
            self.scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        lines = []

        for index, (
            user_id,
            score
        ) in enumerate(
            ranking,
            start=1
        ):

            lines.append(
                f"**{index}.** "
                f"{self.players[user_id].mention} "
                f"→ **{score} نقطة**"
            )

            add_stats(
                user_id,
                games=1,
                points=score * 25,
                wins=(
                    1
                    if user_id == winner_id
                    else 0
                )
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


class SpeedView(BaseView):

    def __init__(
        self,
        game
    ):

        super().__init__(
            game.cog,
            timeout=30
        )

        self.game = game

        for index, answer in enumerate(
            game.current_question["answers"]
        ):

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
                        "❌ أنت لست داخل اللعبة.",
                        ephemeral=True
                    )

                    return

                await self.game.answer(
                    interaction,
                    answer
                )

            button.callback = callback

            self.add_item(
                button
            )


# =========================================================
# 💣 القنبلة
# =========================================================

class BombGame(BaseGame):

    name = "💣 القنبلة"

    description = (
        "القنبلة تنتقل بين اللاعبين.\n"
        "إذا انفجرت معك تخرج من اللعبة."
    )

    async def run(self):

        self.alive = list(
            self.players.keys()
        )

        self.holder = random.choice(
            self.alive
        )

        await self.update_bomb()

    async def update_bomb(self):

        if len(self.alive) <= 1:

            winner = self.players[
                self.alive[0]
            ]

            add_stats(
                winner.id,
                points=150,
                games=1,
                wins=1
            )

            embed = discord.Embed(
                title="🏆 انتهت لعبة القنبلة!",
                description=(
                    f"👑 الناجي الأخير: "
                    f"{winner.mention}\n\n"
                    "💰 حصل على **150 نقطة**."
                )
            )

            await self.message.edit(
                embed=embed,
                view=None
            )

            await self.finish()

            return

        holder = self.players[
            self.holder
        ]

        embed = discord.Embed(
            title="💣 القنبلة",
            description=(
                f"💣 القنبلة مع الآن: "
                f"{holder.mention}\n\n"
                "يجب على حامل القنبلة اختيار لاعب "
                "لتمريرها إليه."
            )
        )

        embed.add_field(
            name="👥 اللاعبين المتبقين",
            value="\n".join(
                self.players[user_id].mention
                for user_id in self.alive
            )
        )

        await self.message.edit(
            embed=embed,
            view=BombView(self)
        )

    async def pass_bomb(
        self,
        interaction,
        target_id
    ):

        if interaction.user.id != self.holder:

            await interaction.response.send_message(
                "❌ القنبلة ليست معك.",
                ephemeral=True
            )

            return

        if target_id not in self.alive:

            await interaction.response.send_message(
                "❌ هذا اللاعب خرج من اللعبة.",
                ephemeral=True
            )

            return

        self.holder = target_id

        await interaction.response.defer()

        await asyncio.sleep(
            random.uniform(
                1.5,
                3
            )
        )

        exploded = random.random() < 0.25

        if exploded:

            eliminated = self.holder

            self.alive.remove(
                eliminated
            )

            member = self.players[
                eliminated
            ]

            add_stats(
                eliminated,
                games=1
            )

            embed = discord.Embed(
                title="💥 انفجرت القنبلة!",
                description=(
                    f"💣 خرج {member.mention} "
                    "من اللعبة!\n\n"
                    f"👥 المتبقون: "
                    f"**{len(self.alive)}**"
                )
            )

            await self.message.edit(
                embed=embed,
                view=None
            )

            await asyncio.sleep(
                1.5
            )

            if self.alive:

                self.holder = random.choice(
                    self.alive
                )

            await self.update_bomb()

        else:

            await self.update_bomb()


class BombView(BaseView):

    def __init__(
        self,
        game
    ):

        super().__init__(
            game.cog,
            timeout=60
        )

        self.game = game

        self.add_item(
            BombSelect(game)
        )


class BombSelect(discord.ui.Select):

    def __init__(
        self,
        game
    ):

        self.game = game

        options = []

        for user_id in game.alive:

            member = game.players[
                user_id
            ]

            options.append(
                discord.SelectOption(
                    label=member.display_name[:100],
                    value=str(user_id)
                )
            )

        super().__init__(
            placeholder="💣 اختر لاعبًا لتمرير القنبلة...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(
        self,
        interaction
    ):

        target_id = int(
            self.values[0]
        )

        await self.game.pass_bomb(
            interaction,
            target_id
        )


# =========================================================
# 🔢 خمن الرقم
# =========================================================

class GuessGame(BaseGame):

    name = "🔢 خمن الرقم"

    description = (
        "البوت اختار رقمًا من 1 إلى 100.\n"
        "أول لاعب يجده يفوز."
    )

    async def run(self):

        self.number = random.randint(
            1,
            100
        )

        self.attempts = {
            user_id: 0
            for user_id in self.players
        }

        embed = discord.Embed(
            title="🔢 خمن الرقم",
            description=(
                "لقد اخترت رقمًا سريًا من **1 إلى 100**.\n\n"
                "اضغط **خمن** وأدخل رقمك."
            )
        )

        await self.message.edit(
            embed=embed,
            view=GuessView(self)
        )

    async def guess(
        self,
        interaction,
        number
    ):

        self.attempts[
            interaction.user.id
        ] += 1

        if number == self.number:

            attempts = self.attempts[
                interaction.user.id
            ]

            points = max(
                50,
                200 - (
                    attempts * 20
                )
            )

            add_stats(
                interaction.user.id,
                points=points,
                games=1,
                wins=1
            )

            embed = discord.Embed(
                title="🏆 تم العثور على الرقم!",
                description=(
                    f"🎯 الرقم هو: **{self.number}**\n\n"
                    f"👑 الفائز: "
                    f"{interaction.user.mention}\n"
                    f"🔢 المحاولات: **{attempts}**\n"
                    f"⭐ النقاط: **{points}**"
                )
            )

            await interaction.response.edit_message(
                embed=embed,
                view=None
            )

            await self.finish()

            return

        if number < self.number:

            text = "⬆️ الرقم أكبر."

        else:

            text = "⬇️ الرقم أصغر."

        await interaction.response.send_message(
            text,
            ephemeral=True
        )


class GuessModal(discord.ui.Modal):

    def __init__(
        self,
        game
    ):

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

        self.add_item(
            self.number
        )

    async def on_submit(
        self,
        interaction
    ):

        try:

            number = int(
                self.number.value
            )

        except ValueError:

            await interaction.response.send_message(
                "❌ أدخل رقمًا صحيحًا.",
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


class GuessView(BaseView):

    def __init__(
        self,
        game
    ):

        super().__init__(
            game.cog
        )

        self.game = game

    @discord.ui.button(
        label="خمن",
        emoji="🔢",
        style=discord.ButtonStyle.primary
    )
    async def guess(
        self,
        interaction,
        button
    ):

        if interaction.user.id not in self.game.players:

            await interaction.response.send_message(
                "❌ أنت لست داخل اللعبة.",
                ephemeral=True
            )

            return

        await interaction.response.send_modal(
            GuessModal(
                self.game
            )
        )


# =========================================================
# 🔐 الهروب من الغرفة
# =========================================================

class EscapeGame(BaseGame):

    name = "🔐 الهروب من الغرفة"

    description = (
        "تعاونوا لحل 3 ألغاز والهروب من الغرفة."
    )

    async def run(self):

        self.stage = 1

        self.answers = {
            1: "مفتاح",
            2: "247",
            3: "المرآة"
        }

        await self.update_room()

    async def update_room(self):

        if self.stage > 3:

            for user_id in self.players:

                add_stats(
                    user_id,
                    points=100,
                    games=1,
                    wins=1
                )

            embed = discord.Embed(
                title="🎉 نجحتم في الهروب!",
                description=(
                    "🔐 تم حل جميع الألغاز!\n\n"
                    "🏆 جميع اللاعبين حصلوا على "
                    "**100 نقطة**."
                )
            )

            await self.message.edit(
                embed=embed,
                view=None
            )

            await self.finish()

            return

        if self.stage == 1:

            question = (
                "🔐 **الغرفة الأولى**\n\n"
                "الباب مغلق.\n"
                "ما الشيء الذي تحتاجه لفتحه؟"
            )

            options = [
                "كتاب",
                "مفتاح",
                "كرسي",
                "مصباح"
            ]

        elif self.stage == 2:

            question = (
                "🔐 **الغرفة الثانية**\n\n"
                "وجدتم خزنة مكونة من 3 أرقام.\n\n"
                "🧩 التلميح يقودكم إلى الرمز الصحيح."
            )

            options = [
                "124",
                "247",
                "428",
                "684"
            ]

        else:

            question = (
                "🔐 **الغرفة الأخيرة**\n\n"
                "شيء يعكس كل شيء أمامه.\n\n"
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
            description=question
        )

        embed.set_footer(
            text=f"المرحلة {self.stage}/3"
        )

        await self.message.edit(
            embed=embed,
            view=EscapeView(
                self,
                options
            )
        )

    async def answer(
        self,
        interaction,
        answer
    ):

        if answer == self.answers[
            self.stage
        ]:

            await interaction.response.send_message(
                "✅ إجابة صحيحة!",
                ephemeral=True
            )

            self.stage += 1

            await asyncio.sleep(
                0.8
            )

            await self.update_room()

        else:

            await interaction.response.send_message(
                "❌ إجابة خاطئة، حاولوا مرة أخرى.",
                ephemeral=True
            )


class EscapeView(BaseView):

    def __init__(
        self,
        game,
        options
    ):

        super().__init__(
            game.cog
        )

        self.game = game

        for index, option in enumerate(
            options
        ):

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

            self.add_item(
                button
            )


# =========================================================
# Cog
# =========================================================

class GamesCog(commands.Cog):

    def __init__(
        self,
        bot
    ):

        self.bot = bot

    # =====================================================
    # -العاب-العب
    # =====================================================

    @commands.command(
        name="العاب-العب"
    )
    async def games_play(
        self,
        ctx
    ):

        # خارج روم الألعاب = تجاهل كامل
        if ctx.channel.id != GAME_CHANNEL_ID:
            return

        if not isinstance(
            ctx.author,
            discord.Member
        ):
            return

        # فقط رتبة التحكم تستطيع فتح قائمة الألعاب
        if not is_control_member(
            ctx.author
        ):

            return

        if GAME_MANAGER.is_active():

            await ctx.send(
                "🎮 **يوجد لعبة جارية بالفعل!**\n"
                "انتظر حتى تنتهي اللعبة الحالية.",
                delete_after=5
            )

            return

        embed = discord.Embed(
            title="🎮 ألعاب السيرفر",
            description=(
                "اختر اللعبة التي تريد تشغيلها "
                "من القائمة الموجودة بالأسفل.\n\n"
                "👑 **الإدارة:** تستطيع تشغيل الألعاب.\n"
                "👥 **اللاعبون:** يستطيعون الانضمام "
                "بعد بدء الـLobby."
            )
        )

        embed.add_field(
            name="🎲 ألعاب الحظ",
            value=(
                "🎲 أعلى نرد\n"
                "💣 القنبلة"
            ),
            inline=True
        )

        embed.add_field(
            name="🧠 ألعاب الذكاء",
            value=(
                "⚡ أسرع إجابة\n"
                "🔢 خمن الرقم"
            ),
            inline=True
        )

        embed.add_field(
            name="🔐 ألعاب جماعية",
            value="🔐 الهروب من الغرفة",
            inline=True
        )

        await ctx.send(
            embed=embed,
            view=GamesSelectView(self)
        )

    # =====================================================
    # بدء اللعبة
    # =====================================================

    async def start_game(
        self,
        interaction,
        game
    ):

        if GAME_MANAGER.is_active():

            await interaction.response.send_message(
                "🎮 **يوجد لعبة جارية بالفعل!**",
                ephemeral=True
            )

            return

        GAME_MANAGER.start(
            game
        )

        # نغلق قائمة الاختيار
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="🎮 تم اختيار اللعبة",
                description=(
                    f"تم اختيار **{game.name}**.\n\n"
                    "جاري إنشاء Lobby اللعبة..."
                )
            ),
            view=None
        )

        # رسالة جديدة خاصة باللعبة
        embed = game.lobby_embed()

        message = await interaction.channel.send(
            content=(
                f"🎮 **بدأت لعبة {game.name}!**\n"
                "يمكن للاعبين الآن الانضمام."
            ),
            embed=embed,
            view=GameLobbyView(
                self,
                game
            )
        )

        game.message = message

    # =====================================================
    # -تصفير-لاعب
    # =====================================================

    @commands.command(
        name="تصفير-لاعب"
    )
    async def reset_player_command(
        self,
        ctx,
        member: discord.Member = None
    ):

        if ctx.channel.id != GAME_CHANNEL_ID:
            return

        if not isinstance(
            ctx.author,
            discord.Member
        ):
            return

        if not is_control_member(
            ctx.author
        ):
            return

        if member is None:

            await ctx.send(
                "❌ الاستخدام الصحيح:\n"
                "`-تصفير-لاعب @الشخص`",
                delete_after=7
            )

            return

        reset_player(
            member.id
        )

        await ctx.send(
            f"🧹 تم تصفير إحصائيات "
            f"{member.mention} بالكامل.",
            delete_after=5
        )

    # =====================================================
    # -اضافة-نقاط
    # =====================================================

    @commands.command(
        name="اضافة-نقاط"
    )
    async def add_points_command(
        self,
        ctx,
        member: discord.Member = None,
        points: int = None
    ):

        if ctx.channel.id != GAME_CHANNEL_ID:
            return

        if not isinstance(
            ctx.author,
            discord.Member
        ):
            return

        if not is_control_member(
            ctx.author
        ):
            return

        if member is None or points is None:

            await ctx.send(
                "❌ الاستخدام الصحيح:\n"
                "`-اضافة-نقاط @الشخص 500`",
                delete_after=7
            )

            return

        if points <= 0:

            await ctx.send(
                "❌ يجب أن تكون النقاط أكبر من صفر.",
                delete_after=5
            )

            return

        add_stats(
            member.id,
            points=points
        )

        await ctx.send(
            f"⭐ تمت إضافة **{points:,}** نقطة "
            f"إلى {member.mention}.",
            delete_after=5
        )

    # =====================================================
    # -تصفير-نقاط
    # =====================================================

    @commands.command(
        name="تصفير-نقاط"
    )
    async def reset_points_command(
        self,
        ctx
    ):

        if ctx.channel.id != GAME_CHANNEL_ID:
            return

        if not isinstance(
            ctx.author,
            discord.Member
        ):
            return

        if not is_control_member(
            ctx.author
        ):
            return

        GAME_STATS.update_many(
            {},
            {
                "$set": {
                    "points": 0
                }
            }
        )

        await ctx.send(
            "🧹 تم تصفير **نقاط جميع اللاعبين**.",
            delete_after=5
        )

    # =====================================================
    # -توب-العاب
    # =====================================================

    @commands.command(
        name="توب-العاب"
    )
    async def top_games(
        self,
        ctx
    ):

        if ctx.channel.id != GAME_CHANNEL_ID:
            return

        if not isinstance(
            ctx.author,
            discord.Member
        ):
            return

        if not is_control_member(
            ctx.author
        ):
            return

        top = list(
            GAME_STATS.find({})
            .sort(
                "points",
                -1
            )
            .limit(10)
        )

        if not top:

            await ctx.send(
                "🏆 لا توجد إحصائيات حتى الآن.",
                delete_after=5
            )

            return

        lines = []

        for index, data in enumerate(
            top,
            start=1
        ):

            user_id = data[
                "user_id"
            ]

            member = ctx.guild.get_member(
                user_id
            )

            if member:

                name = member.mention

            else:

                name = f"<@{user_id}>"

            lines.append(
                f"**{index}.** {name}\n"
                f"└ ⭐ {data.get('points', 0):,} "
                f"نقطة | 🏆 {data.get('wins', 0)} "
                f"فوز | 🎮 {data.get('games', 0)} لعبة"
            )

        embed = discord.Embed(
            title="🏆 توب ألعاب السيرفر",
            description="\n\n".join(lines)
        )

        await ctx.send(
            embed=embed
        )


# =========================================================
# setup
# =========================================================

async def setup(bot):

    await bot.add_cog(
        GamesCog(bot)
    )
