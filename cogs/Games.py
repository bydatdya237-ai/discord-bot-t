import asyncio
import random
import time
from collections import defaultdict

import discord
from discord.ext import commands
from discord import ui
from pymongo import MongoClient


# =========================================================
# الإعدادات
# =========================================================

GAME_CHANNEL_ID = 1550797517237518417

# رتبة التحكم بالألعاب والإدارة
CONTROL_ROLE_ID = 1544078469657530578

# رتبة اللاعبين
PLAYER_ROLE_ID = 1544078847253811331

MIN_PLAYERS = 2
MAX_PLAYERS = 15

MONGO_URL = None


# =========================================================
# قاعدة البيانات
# =========================================================

# نأخذ Mongo من البيئة بطريقة آمنة
import os

MONGO_URL = os.environ.get("MONGO_URI")

mongo_client = MongoClient(MONGO_URL)
mongo_db = mongo_client["discord_bot_db"]

stats_collection = mongo_db["game_stats"]
game_history_collection = mongo_db["game_history"]


# =========================================================
# الألوان
# =========================================================

EMBED_COLOR = 0x8B5CF6
SUCCESS_COLOR = 0x22C55E
DANGER_COLOR = 0xEF4444
GOLD_COLOR = 0xF59E0B
INFO_COLOR = 0x3B82F6
DARK_COLOR = 0x111827


# =========================================================
# أسماء الألعاب
# =========================================================

GAMES = {
    "dice": "🎲 أعلى نرد",
    "speed": "⚡ أسرع إجابة",
    "bomb": "💣 القنبلة",
    "guess": "🔢 خمن الرقم",
    "escape": "🔐 الهروب من الغرفة",

    "liar": "🕵️ مين الكذاب؟",
    "king": "👑 ملك السيرفر",
    "territory": "🏴 السيطرة على المناطق",
    "cards": "🃏 ورق الحظ",
    "memory": "🧠 الذاكرة",
    "character": "🎭 خمن الشخصية",
    "auction": "💰 المزاد",
    "investigation": "🔎 التحقيق",
    "ship": "🚢 السفينة الغارقة",
    "battle": "⚔️ معركة اللاعبين",
    "secret": "🎯 الهدف السري",
    "words": "🧩 ترتيب الكلمات",
}


# =========================================================
# أدوات عامة
# =========================================================

def is_game_channel(message_or_interaction):
    channel = getattr(message_or_interaction, "channel", None)
    return channel and channel.id == GAME_CHANNEL_ID


def has_control_role(member):
    return any(role.id == CONTROL_ROLE_ID for role in member.roles)


def has_player_role(member):
    return any(role.id == PLAYER_ROLE_ID for role in member.roles)


def get_stats(user_id):
    data = stats_collection.find_one({"user_id": int(user_id)})

    if not data:
        data = {
            "user_id": int(user_id),
            "points": 0,
            "wins": 0,
            "games": 0,
            "actions": 0,
        }
        stats_collection.insert_one(data)

    return data


def add_points(user_id, amount):
    stats_collection.update_one(
        {"user_id": int(user_id)},
        {
            "$inc": {
                "points": int(amount),
            }
        },
        upsert=True,
    )


def add_game(user_id, won=False):
    update = {
        "$inc": {
            "games": 1,
        }
    }

    if won:
        update["$inc"]["wins"] = 1

    stats_collection.update_one(
        {"user_id": int(user_id)},
        update,
        upsert=True,
    )


def add_action(user_id):
    stats_collection.update_one(
        {"user_id": int(user_id)},
        {
            "$inc": {
                "actions": 1
            }
        },
        upsert=True,
    )


def remove_points(user_id, amount):
    data = get_stats(user_id)

    current = int(data.get("points", 0))

    if current < amount:
        return False

    result = stats_collection.update_one(
        {
            "user_id": int(user_id),
            "points": {"$gte": int(amount)}
        },
        {
            "$inc": {
                "points": -int(amount)
            }
        }
    )

    return result.modified_count > 0


def get_points(user_id):
    data = get_stats(user_id)
    return int(data.get("points", 0))


def leaderboard(limit=10):
    return list(
        stats_collection.find(
            {},
            {
                "user_id": 1,
                "points": 1,
                "wins": 1,
                "games": 1,
            },
        )
        .sort("points", -1)
        .limit(limit)
    )


# =========================================================
# مدير اللعبة
# =========================================================

class GameManager:
    active_game = None
    active_game_name = None
    active_game_obj = None

    @classmethod
    def running(cls):
        return cls.active_game is not None

    @classmethod
    def start(cls, game_obj, game_key):
        cls.active_game = game_key
        cls.active_game_name = GAMES.get(game_key, game_key)
        cls.active_game_obj = game_obj

    @classmethod
    def stop(cls):
        cls.active_game = None
        cls.active_game_name = None
        cls.active_game_obj = None


# =========================================================
# Base Game
# =========================================================

class BaseGame:
    def __init__(self, cog, channel):
        self.cog = cog
        self.channel = channel
        self.players = {}
        self.started = False
        self.finished = False
        self.protected = set()
        self.eliminated = set()

    async def add_player(self, member):
        if self.started:
            return False, "اللعبة بدأت بالفعل."

        if member.id in self.players:
            return False, "أنت داخل اللعبة بالفعل."

        if len(self.players) >= MAX_PLAYERS:
            return False, "اللعبة وصلت للحد الأقصى من اللاعبين."

        self.players[member.id] = member
        return True, "تم دخولك."

    def active_players(self):
        return [
            member
            for uid, member in self.players.items()
            if uid not in self.eliminated
        ]

    async def finish_player_stats(self, winners=None):
        winners = winners or set()

        for uid in self.players:
            add_game(uid, uid in winners)

            # نقطة مشاركة لكل لاعب
            add_points(uid, 1)

        for uid in winners:
            add_points(uid, 2)

    async def eliminate(self, user_id):
        if user_id in self.players:
            self.eliminated.add(user_id)

    async def finish(self):
        self.finished = True
        GameManager.stop()

    async def start_game(self):
        raise NotImplementedError


# =========================================================
# واجهة اللوبي
# =========================================================

class LobbyView(ui.View):
    def __init__(self, game):
        super().__init__(timeout=300)
        self.game = game

    @ui.button(
        label="🎮 انضمام",
        style=discord.ButtonStyle.success
    )
    async def join(
        self,
        interaction: discord.Interaction,
        button: ui.Button
    ):
        if not is_game_channel(interaction):
            return

        member = interaction.user

        if not has_player_role(member) and not has_control_role(member):
            await interaction.response.send_message(
                "❌ تحتاج رتبة اللاعبين للدخول.",
                ephemeral=True
            )
            return

        success, msg = await self.game.add_player(member)

        if not success:
            await interaction.response.send_message(
                f"❌ {msg}",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"🎮 دخلت اللعبة!\n"
            f"👥 اللاعبين الآن: **{len(self.game.players)}**",
            ephemeral=True
        )

        await self.game.update_lobby()

    @ui.button(
        label="🚀 ابدأ اللعبة",
        style=discord.ButtonStyle.primary
    )
    async def start(
        self,
        interaction: discord.Interaction,
        button: ui.Button
    ):
        if not has_control_role(interaction.user):
            await interaction.response.send_message(
                "❌ هذا الزر للإدارة فقط.",
                ephemeral=True
            )
            return

        if self.game.started:
            await interaction.response.send_message(
                "❌ اللعبة بدأت بالفعل.",
                ephemeral=True
            )
            return

        if len(self.game.players) < MIN_PLAYERS:
            await interaction.response.send_message(
                f"❌ تحتاج على الأقل **{MIN_PLAYERS} لاعبين**.",
                ephemeral=True
            )
            return

        self.game.started = True

        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(
            view=self
        )

        await self.game.start_game()

    @ui.button(
        label="🛑 إلغاء",
        style=discord.ButtonStyle.danger
    )
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: ui.Button
    ):
        if not has_control_role(interaction.user):
            await interaction.response.send_message(
                "❌ هذا الزر للإدارة فقط.",
                ephemeral=True
            )
            return

        GameManager.stop()

        await interaction.response.edit_message(
            content="🛑 **تم إلغاء اللعبة.**",
            embed=None,
            view=None
        )


# =========================================================
# ألعاب
# =========================================================

class DiceGame(BaseGame):

    async def start_game(self):
        embed = discord.Embed(
            title="🎲🔥 أعلى نرد",
            description=(
                "كل لاعب سيرمي النرد مرة واحدة.\n\n"
                "🎲 أعلى رقم يفوز!\n"
                "⭐ المشاركة = +1 نقطة\n"
                "🏆 الفائز = +2 نقاط إضافية"
            ),
            color=GOLD_COLOR
        )

        msg = await self.channel.send(embed=embed)

        await asyncio.sleep(2)

        results = {}

        for uid in self.players:
            results[uid] = random.randint(1, 100)

        highest = max(results.values())
        winners = {
            uid for uid, value in results.items()
            if value == highest
        }

        lines = []

        for uid, value in results.items():
            lines.append(
                f"{self.players[uid].mention} → 🎲 **{value}**"
            )

        embed = discord.Embed(
            title="🎲💥 النتائج!",
            description="\n".join(lines),
            color=GOLD_COLOR
        )

        embed.add_field(
            name="🏆 الفائز",
            value=", ".join(
                self.players[uid].mention for uid in winners
            )
        )

        await msg.edit(embed=embed)

        await self.finish_player_stats(winners)

        await asyncio.sleep(4)
        await self.finish()


class SpeedGame(BaseGame):

    async def start_game(self):
        answers = [
            ("ما هو لون السماء؟", "ازرق"),
            ("كم عدد أيام الأسبوع؟", "7"),
            ("ما هو 5 + 5؟", "10"),
            ("ما هو عكس كلمة فوق؟", "تحت"),
            ("كم عدد أشهر السنة؟", "12"),
        ]

        question, answer = random.choice(answers)

        view = SpeedView(self, answer)

        embed = discord.Embed(
            title="⚡🔥 أسرع إجابة",
            description=(
                f"## ❓ {question}\n\n"
                "🏃 أسرع شخص يضغط على الزر ويجاوب بشكل صحيح يفوز!\n\n"
                "⭐ المشاركة = +1\n"
                "🏆 الفوز = +2 إضافية"
            ),
            color=INFO_COLOR
        )

        await self.channel.send(
            embed=embed,
            view=view
        )

        await asyncio.sleep(20)

        if not self.finished:
            await self.channel.send(
                f"⏰ **انتهى الوقت!**\n"
                f"الإجابة كانت: **{answer}**"
            )

            await self.finish_player_stats()
            await self.finish()


class SpeedView(ui.View):

    def __init__(self, game, answer):
        super().__init__(timeout=20)
        self.game = game
        self.answer = answer.lower().strip()
        self.done = False

    @ui.button(
        label="⚡ جاوب!",
        style=discord.ButtonStyle.success
    )
    async def answer_button(
        self,
        interaction: discord.Interaction,
        button: ui.Button
    ):
        if self.done:
            return

        if interaction.user.id not in self.game.players:
            await interaction.response.send_message(
                "❌ أنت لست داخل اللعبة.",
                ephemeral=True
            )
            return

        await interaction.response.send_modal(
            AnswerModal(self)
        )


class AnswerModal(ui.Modal, title="⚡ إجابتك"):

    answer = ui.TextInput(
        label="اكتب الإجابة",
        placeholder="اكتب إجابتك هنا..."
    )

    def __init__(self, view):
        super().__init__()
        self.game_view = view

    async def on_submit(self, interaction):
        if self.game_view.done:
            return

        if self.answer.value.lower().strip() != self.game_view.answer:
            await interaction.response.send_message(
                "❌ إجابة خاطئة!",
                ephemeral=True
            )
            return

        self.game_view.done = True
        self.game_view.stop()

        uid = interaction.user.id

        add_points(uid, 3)
        add_game(uid, True)

        for player_id in self.game_view.game.players:
            if player_id != uid:
                add_game(player_id, False)
                add_points(player_id, 1)

        await interaction.response.send_message(
            f"⚡🔥 **أسرع واحد!**\n"
            f"{interaction.user.mention} حصل على **3 نقاط**!",
        )

        await self.game_view.game.finish()


class BombGame(BaseGame):

    async def start_game(self):
        current = list(self.players.keys())

        embed = discord.Embed(
            title="💣🔥 القنبلة",
            description=(
                "القنبلة تنتقل بين اللاعبين.\n"
                "كل جولة يتم اختيار لاعب عشوائيًا.\n\n"
                "💥 آخر لاعب تبقى يفوز!"
            ),
            color=DANGER_COLOR
        )

        await self.channel.send(embed=embed)

        while len(current) > 1:

            await asyncio.sleep(2)

            victim = random.choice(current)
            current.remove(victim)
            self.eliminated.add(victim)

            await self.channel.send(
                f"💣💥 **انفجرت القنبلة!**\n"
                f"❌ تم استبعاد {self.players[victim].mention}"
            )

        winner = current[0]

        add_points(winner, 3)

        await self.finish_player_stats({winner})

        await self.channel.send(
            f"🏆🔥 الفائز في القنبلة هو "
            f"{self.players[winner].mention}!\n"
            f"💰 حصل على **3 نقاط إضافية**."
        )

        await asyncio.sleep(3)
        await self.finish()


class GuessGame(BaseGame):

    async def start_game(self):
        self.number = random.randint(1, 100)

        embed = discord.Embed(
            title="🔢🧠 خمن الرقم",
            description=(
                "أنا اخترت رقمًا بين **1 و100**.\n\n"
                "أرسل تخمينك في الشات!\n"
                "كل لاعب لديه فرصة."
            ),
            color=EMBED_COLOR
        )

        await self.channel.send(embed=embed)

        def check(message):
            return (
                message.channel.id == self.channel.id
                and message.author.id in self.players
                and message.content.isdigit()
            )

        try:
            while not self.finished:
                message = await self.cog.bot.wait_for(
                    "message",
                    timeout=30,
                    check=check
                )

                guess = int(message.content)

                if guess == self.number:
                    add_points(message.author.id, 4)
                    add_game(message.author.id, True)

                    for uid in self.players:
                        if uid != message.author.id:
                            add_game(uid, False)
                            add_points(uid, 1)

                    await self.channel.send(
                        f"🎯🔥 **أصبت الرقم!**\n"
                        f"{message.author.mention} حصل على **4 نقاط**!"
                    )

                    await self.finish()
                    return

                if guess < self.number:
                    await self.channel.send(
                        f"⬆️ {message.author.mention} الرقم أكبر!"
                    )
                else:
                    await self.channel.send(
                        f"⬇️ {message.author.mention} الرقم أصغر!"
                    )

        except asyncio.TimeoutError:
            await self.channel.send(
                f"⏰ انتهى الوقت!\n"
                f"الرقم كان **{self.number}**."
            )

            await self.finish_player_stats()
            await self.finish()


class EscapeGame(BaseGame):

    async def start_game(self):
        rooms = [
            "🚪 غرفة حمراء",
            "🚪 غرفة زرقاء",
            "🚪 غرفة سوداء",
        ]

        correct = random.choice(rooms)

        view = EscapeView(self, correct)

        embed = discord.Embed(
            title="🔐🔥 الهروب من الغرفة",
            description=(
                "أمامك 3 غرف.\n"
                "غرفة واحدة فقط هي طريق النجاة!\n\n"
                "اختار بسرعة."
            ),
            color=DARK_COLOR
        )

        await self.channel.send(
            embed=embed,
            view=view
        )


class EscapeView(ui.View):

    def __init__(self, game, correct):
        super().__init__(timeout=20)
        self.game = game
        self.correct = correct

    async def choose(self, interaction, choice):
        if interaction.user.id not in self.game.players:
            await interaction.response.send_message(
                "❌ أنت لست داخل اللعبة.",
                ephemeral=True
            )
            return

        if choice == self.correct:
            add_points(interaction.user.id, 3)

            await interaction.response.send_message(
                "🚪✨ **نجحت بالهروب! +3 نقاط**"
            )
        else:
            add_points(interaction.user.id, 1)

            await interaction.response.send_message(
                "💥 وقعت في الفخ! +1 نقطة"
            )

        await self.game.finish_player_stats()
        await self.game.finish()

    @ui.button(label="🚪 الأحمر", style=discord.ButtonStyle.danger)
    async def red(self, interaction, button):
        await self.choose(interaction, "🚪 غرفة حمراء")

    @ui.button(label="🚪 الأزرق", style=discord.ButtonStyle.primary)
    async def blue(self, interaction, button):
        await self.choose(interaction, "🚪 غرفة زرقاء")

    @ui.button(label="🚪 الأسود", style=discord.ButtonStyle.secondary)
    async def black(self, interaction, button):
        await self.choose(interaction, "🚪 غرفة سوداء")


# =========================================================
# مين الكذاب
# =========================================================

class LiarGame(BaseGame):

    async def start_game(self):
        players = list(self.players.values())
        liar = random.choice(players)

        self.liar_id = liar.id

        embed = discord.Embed(
            title="🕵️🔥 مين الكذاب؟",
            description=(
                "كل لاعب سيحصل على معلومة.\n"
                "شخص واحد فقط حصل على معلومة مختلفة.\n\n"
                "💬 ناقشوا في الشات وحاولوا اكتشاف الكذاب!"
            ),
            color=EMBED_COLOR
        )

        await self.channel.send(embed=embed)

        for member in players:
            if member.id == self.liar_id:
                text = "🤫 أنت الكذاب! حاول تمثل أنك طبيعي."
            else:
                text = "🟢 أنت بريء. حاول اكتشاف الكذاب."

            try:
                await member.send(
                    f"🕵️ **مين الكذاب؟**\n{text}"
                )
            except:
                pass

        await asyncio.sleep(15)

        await self.channel.send(
            "🗳️ **انتهى وقت النقاش!**\n"
            "الكذاب كان: "
            f"{liar.mention}"
        )

        add_points(liar.id, 2)

        for uid in self.players:
            add_game(uid, uid == liar.id)
            add_points(uid, 1)

        await asyncio.sleep(3)
        await self.finish()


# =========================================================
# ملك السيرفر
# =========================================================

class KingGame(BaseGame):

    async def start_game(self):
        players = list(self.players.values())
        king = random.choice(players)

        embed = discord.Embed(
            title="👑🔥 ملك السيرفر",
            description=(
                f"تم اختيار الملك سرًا!\n\n"
                "👑 الملك يحصل على قوة إضافية.\n"
                "حاولوا اكتشافه قبل انتهاء الوقت!"
            ),
            color=GOLD_COLOR
        )

        await self.channel.send(embed=embed)

        try:
            await king.send(
                "👑 **أنت الملك!**\n"
                "لا تكشف نفسك."
            )
        except:
            pass

        await asyncio.sleep(15)

        add_points(king.id, 3)

        await self.channel.send(
            f"👑🔥 **انكشف الملك:** {king.mention}\n"
            f"حصل على **3 نقاط إضافية**."
        )

        await self.finish_player_stats({king.id})
        await self.finish()


# =========================================================
# السيطرة على المناطق
# =========================================================

class TerritoryGame(BaseGame):

    async def start_game(self):
        territories = [
            "🏜️ الصحراء",
            "🏙️ المدينة",
            "🏝️ الجزيرة",
            "🏔️ الجبل",
        ]

        owners = {}

        for territory in territories:
            owner = random.choice(list(self.players.values()))
            owners[territory] = owner

        lines = []

        for territory, owner in owners.items():
            add_points(owner.id, 2)
            lines.append(
                f"{territory} → {owner.mention}"
            )

        embed = discord.Embed(
            title="🏴🔥 السيطرة على المناطق",
            description="\n".join(lines),
            color=INFO_COLOR
        )

        embed.set_footer(
            text="كل منطقة تسيطر عليها = +2 نقاط"
        )

        await self.channel.send(embed=embed)

        winners = {
            owner.id for owner in owners.values()
        }

        await self.finish_player_stats(winners)
        await asyncio.sleep(3)
        await self.finish()


# =========================================================
# ورق الحظ
# =========================================================

class CardsGame(BaseGame):

    async def start_game(self):
        cards = [
            ("🃏 الذهب", 4),
            ("💀 الخسارة", 0),
            ("🍀 الحظ", 3),
            ("🔥 القوة", 2),
            ("💎 الماس", 5),
        ]

        lines = []

        for member in self.players.values():
            card, points = random.choice(cards)

            add_points(member.id, points + 1)

            lines.append(
                f"{member.mention} → {card} **+{points + 1}**"
            )

        embed = discord.Embed(
            title="🃏🔥 ورق الحظ",
            description="\n".join(lines),
            color=GOLD_COLOR
        )

        await self.channel.send(embed=embed)

        await self.finish_player_stats()
        await asyncio.sleep(4)
        await self.finish()


# =========================================================
# الذاكرة
# =========================================================

class MemoryGame(BaseGame):

    async def start_game(self):
        sequence = [
            random.randint(1, 9)
            for _ in range(5)
        ]

        embed = discord.Embed(
            title="🧠🔥 الذاكرة",
            description=(
                "احفظ الأرقام بسرعة!\n\n"
                f"## {' '.join(map(str, sequence))}\n\n"
                "سيختفي الرقم الآن..."
            ),
            color=EMBED_COLOR
        )

        msg = await self.channel.send(embed=embed)

        await asyncio.sleep(4)

        await msg.edit(
            embed=discord.Embed(
                title="🧠❓ ما هو التسلسل؟",
                description="أول لاعب يكتب التسلسل الصحيح يفوز!",
                color=INFO_COLOR
            )
        )

        correct = "".join(map(str, sequence))

        def check(message):
            return (
                message.channel.id == self.channel.id
                and message.author.id in self.players
            )

        try:
            while True:
                message = await self.cog.bot.wait_for(
                    "message",
                    timeout=20,
                    check=check
                )

                if message.content.replace(" ", "") == correct:
                    add_points(message.author.id, 4)

                    await self.channel.send(
                        f"🧠🔥 **ذاكرة خارقة!**\n"
                        f"{message.author.mention} +4 نقاط!"
                    )

                    await self.finish_player_stats(
                        {message.author.id}
                    )

                    await self.finish()
                    return

        except asyncio.TimeoutError:
            await self.channel.send(
                f"⏰ انتهى الوقت!\n"
                f"التسلسل كان: **{' '.join(map(str, sequence))}**"
            )

            await self.finish_player_stats()
            await self.finish()


# =========================================================
# خمن الشخصية
# =========================================================

class CharacterGame(BaseGame):

    async def start_game(self):
        characters = [
            ("🕷️", "شخصية ترتدي بدلة عنكبوت"),
            ("🦇", "شخصية ليلية مشهورة"),
            ("🧙", "شخصية تستخدم السحر"),
            ("🦸", "بطل خارق مشهور"),
            ("🤖", "شخصية آلية"),
        ]

        emoji, clue = random.choice(characters)

        embed = discord.Embed(
            title="🎭🔥 خمن الشخصية",
            description=(
                f"## 🔎 التلميح:\n{clue}\n\n"
                "اكتب اسم الشخصية في الشات!"
            ),
            color=EMBED_COLOR
        )

        await self.channel.send(embed=embed)

        # لعبة اختبارية تعتمد على أول إجابة صحيحة
        def check(message):
            return (
                message.channel.id == self.channel.id
                and message.author.id in self.players
            )

        try:
            message = await self.cog.bot.wait_for(
                "message",
                timeout=20,
                check=check
            )

            add_points(message.author.id, 2)

            await self.channel.send(
                f"🎭🔥 {message.author.mention} "
                f"أجاب أولًا وحصل على **2 نقاط**!"
            )

            await self.finish_player_stats(
                {message.author.id}
            )

        except asyncio.TimeoutError:
            await self.channel.send(
                f"⏰ انتهى الوقت!\n"
                f"الشخصية كانت مرتبطة بالرمز **{emoji}**."
            )

            await self.finish_player_stats()

        await self.finish()


# =========================================================
# المزاد
# =========================================================

class AuctionGame(BaseGame):

    async def start_game(self):
        item = random.choice([
            "💎 ألماسة نادرة",
            "👑 تاج أسطوري",
            "🏆 كأس البطولة",
            "🪙 عملة ذهبية",
        ])

        embed = discord.Embed(
            title="💰🔥 المزاد",
            description=(
                f"السلعة: **{item}**\n\n"
                "كل لاعب يرسل رقمًا يمثل عرضه.\n"
                "أعلى عرض يفوز!"
            ),
            color=GOLD_COLOR
        )

        await self.channel.send(embed=embed)

        bids = {}

        def check(message):
            return (
                message.channel.id == self.channel.id
                and message.author.id in self.players
                and message.content.isdigit()
            )

        end = time.time() + 20

        while time.time() < end:
            try:
                message = await self.cog.bot.wait_for(
                    "message",
                    timeout=max(0.1, end - time.time()),
                    check=check
                )

                bid = int(message.content)

                if bid > 0:
                    bids[message.author.id] = bid

            except asyncio.TimeoutError:
                break

        if bids:
            winner = max(bids, key=bids.get)

            add_points(winner, 4)

            await self.channel.send(
                f"💰👑 أعلى مزايدة:\n"
                f"{self.players[winner].mention}\n"
                f"💵 العرض: **{bids[winner]}**\n"
                f"⭐ +4 نقاط"
            )

            await self.finish_player_stats({winner})
        else:
            await self.channel.send(
                "💰 لم يقدم أحد مزايدة!"
            )
            await self.finish_player_stats()

        await self.finish()


# =========================================================
# التحقيق
# =========================================================

class InvestigationGame(BaseGame):

    async def start_game(self):
        suspect = random.choice(
            list(self.players.values())
        )

        try:
            await suspect.send(
                "🔎 **أنت المشتبه به!**\n"
                "حاول الدفاع عن نفسك."
            )
        except:
            pass

        embed = discord.Embed(
            title="🔎🔥 التحقيق",
            description=(
                "هناك مشتبه به بينكم!\n\n"
                "ناقشوا وحاولوا معرفة من هو.\n"
                "بعد انتهاء الوقت سيتم كشفه."
            ),
            color=DANGER_COLOR
        )

        await self.channel.send(embed=embed)

        await asyncio.sleep(15)

        await self.channel.send(
            f"🚨 **تم كشف المشتبه به:** "
            f"{suspect.mention}"
        )

        add_points(suspect.id, 3)

        await self.finish_player_stats({suspect.id})
        await self.finish()


# =========================================================
# السفينة الغارقة
# =========================================================

class ShipGame(BaseGame):

    async def start_game(self):
        spots = [
            "🛟 قارب النجاة",
            "🚪 الباب",
            "🪵 الطوف",
        ]

        correct = random.choice(spots)

        view = ShipView(self, correct)

        embed = discord.Embed(
            title="🚢🌊 السفينة الغارقة",
            description=(
                "السفينة تغرق!\n\n"
                "اختار مكان النجاة قبل انتهاء الوقت!"
            ),
            color=INFO_COLOR
        )

        await self.channel.send(
            embed=embed,
            view=view
        )


class ShipView(ui.View):

    def __init__(self, game, correct):
        super().__init__(timeout=20)
        self.game = game
        self.correct = correct

    async def select_spot(self, interaction, choice):
        if interaction.user.id not in self.game.players:
            await interaction.response.send_message(
                "❌ أنت لست لاعبًا.",
                ephemeral=True
            )
            return

        if choice == self.correct:
            add_points(interaction.user.id, 3)

            await interaction.response.send_message(
                "🛟🌊 **نجوت! +3 نقاط**"
            )

            await self.game.finish_player_stats(
                {interaction.user.id}
            )
        else:
            add_points(interaction.user.id, 1)

            await interaction.response.send_message(
                "🌊❌ لم تنجُ... +1 نقطة"
            )

            await self.game.finish_player_stats()

        await self.game.finish()

    @ui.button(
        label="🛟 القارب",
        style=discord.ButtonStyle.success
    )
    async def boat(self, interaction, button):
        await self.select_spot(
            interaction,
            "🛟 قارب النجاة"
        )

    @ui.button(
        label="🚪 الباب",
        style=discord.ButtonStyle.primary
    )
    async def door(self, interaction, button):
        await self.select_spot(
            interaction,
            "🚪 الباب"
        )

    @ui.button(
        label="🪵 الطوف",
        style=discord.ButtonStyle.secondary
    )
    async def raft(self, interaction, button):
        await self.select_spot(
            interaction,
            "🪵 الطوف"
        )


# =========================================================
# معركة اللاعبين
# =========================================================

class BattleGame(BaseGame):

    async def start_game(self):
        players = list(self.players.values())
        random.shuffle(players)

        lines = []

        while len(players) > 1:
            a = players.pop(0)
            b = players.pop(0)

            winner = random.choice([a, b])

            lines.append(
                f"⚔️ {a.mention} VS {b.mention}\n"
                f"🏆 الفائز: {winner.mention}"
            )

            add_points(winner.id, 2)

        if players:
            champion = players[0]
        else:
            champion = None

        if champion:
            add_points(champion.id, 3)

            lines.append(
                f"\n👑 **البطل النهائي:** "
                f"{champion.mention}"
            )

            winners = {champion.id}
        else:
            winners = set()

        embed = discord.Embed(
            title="⚔️🔥 معركة اللاعبين",
            description="\n\n".join(lines),
            color=DANGER_COLOR
        )

        await self.channel.send(embed=embed)

        await self.finish_player_stats(winners)
        await asyncio.sleep(4)
        await self.finish()


# =========================================================
# الهدف السري
# =========================================================

class SecretTargetGame(BaseGame):

    async def start_game(self):
        players = list(self.players.values())

        if len(players) < 2:
            await self.finish()
            return

        targets = players.copy()
        random.shuffle(targets)

        assignments = {}

        for index, player in enumerate(players):
            target = targets[index]

            if target.id == player.id:
                target = targets[(index + 1) % len(targets)]

            assignments[player.id] = target.id

            try:
                await player.send(
                    f"🎯 **هدفك السري:** "
                    f"{target.display_name}\n\n"
                    "لا تخبر أحدًا!"
                )
            except:
                pass

        await self.channel.send(
            embed=discord.Embed(
                title="🎯🕵️ الهدف السري",
                description=(
                    "تم إرسال هدف سري لكل لاعب بالخاص.\n\n"
                    "أمامكم وقت قصير لتنفيذ المهمة."
                ),
                color=EMBED_COLOR
            )
        )

        await asyncio.sleep(15)

        for uid in self.players:
            add_points(uid, 1)

        await self.channel.send(
            "🎯 انتهت الجولة!\n"
            "كل لاعب حصل على **نقطة مشاركة**."
        )

        await self.finish_player_stats()
        await self.finish()


# =========================================================
# ترتيب الكلمات
# =========================================================

class WordsGame(BaseGame):

    async def start_game(self):
        sentences = [
            ["ديسكورد", "نحب", "نلعب"],
            ["اليوم", "اللعبة", "حماسية"],
            ["النقاط", "تجمع", "باللعب"],
            ["الفائز", "يحصل", "على", "نقاط"],
        ]

        words = random.choice(sentences)
        shuffled = words.copy()
        random.shuffle(shuffled)

        embed = discord.Embed(
            title="🧩🔥 ترتيب الكلمات",
            description=(
                "رتب الكلمات لتكوين الجملة الصحيحة:\n\n"
                f"## {' | '.join(shuffled)}\n\n"
                "⚡ أول إجابة صحيحة = 4 نقاط!"
            ),
            color=INFO_COLOR
        )

        await self.channel.send(embed=embed)

        correct = " ".join(words)

        def check(message):
            return (
                message.channel.id == self.channel.id
                and message.author.id in self.players
            )

        try:
            while True:
                message = await self.cog.bot.wait_for(
                    "message",
                    timeout=20,
                    check=check
                )

                if message.content.strip() == correct:
                    add_points(message.author.id, 4)

                    await self.channel.send(
                        f"🧩🔥 **إجابة صحيحة!**\n"
                        f"{message.author.mention} +4 نقاط!"
                    )

                    await self.finish_player_stats(
                        {message.author.id}
                    )

                    await self.finish()
                    return

        except asyncio.TimeoutError:
            await self.channel.send(
                f"⏰ انتهى الوقت!\n"
                f"الترتيب الصحيح: **{correct}**"
            )

            await self.finish_player_stats()
            await self.finish()


# =========================================================
# السيطرة على اللعبة
# =========================================================

GAME_CLASSES = {
    "dice": DiceGame,
    "speed": SpeedGame,
    "bomb": BombGame,
    "guess": GuessGame,
    "escape": EscapeGame,
    "liar": LiarGame,
    "king": KingGame,
    "territory": TerritoryGame,
    "cards": CardsGame,
    "memory": MemoryGame,
    "character": CharacterGame,
    "auction": AuctionGame,
    "investigation": InvestigationGame,
    "ship": ShipGame,
    "battle": BattleGame,
    "secret": SecretTargetGame,
    "words": WordsGame,
}


# =========================================================
# قائمة الألعاب
# =========================================================

class GamesSelect(ui.Select):

    def __init__(self, cog):

        self.cog = cog

        options = []

        for key, name in GAMES.items():
            options.append(
                discord.SelectOption(
                    label=name[:100],
                    value=key
                )
            )

        super().__init__(
            placeholder="🎮 اختر اللعبة التي تريد تشغيلها...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction):

        if not has_control_role(interaction.user):
            await interaction.response.send_message(
                "❌ هذا الأمر للإدارة فقط.",
                ephemeral=True
            )
            return

        if GameManager.running():
            await interaction.response.send_message(
                "🎮 يوجد لعبة جارية بالفعل!",
                ephemeral=True
            )
            return

        key = self.values[0]

        game_class = GAME_CLASSES[key]

        game = game_class(
            self.cog,
            interaction.channel
        )

        GameManager.start(game, key)

        await interaction.response.edit_message(
            content=(
                f"🎮🔥 **تم اختيار اللعبة:** "
                f"{GAMES[key]}"
            ),
            embed=None,
            view=None
        )

        await asyncio.sleep(1)

        embed = discord.Embed(
            title=f"🎮🔥 بدأت لعبة {GAMES[key]}!",
            description=(
                "## 👥 افتحوا اللوبي وادخلوا اللعبة!\n\n"
                f"👤 الحد الأدنى: **{MIN_PLAYERS}**\n"
                f"👥 الحد الأقصى: **{MAX_PLAYERS}**\n\n"
                "⭐ كل مشاركة تعطيك نقاط.\n"
                "🏆 الفوز يعطي نقاط إضافية."
            ),
            color=EMBED_COLOR
        )

        await interaction.channel.send(
            embed=embed,
            view=LobbyView(game)
        )

        game.lobby_message = None


class GamesMenuView(ui.View):

    def __init__(self, cog):
        super().__init__(timeout=180)
        self.add_item(GamesSelect(cog))


# =========================================================
# التخريب
# =========================================================

SABOTAGE_ITEMS = {
    "nuke": {
        "name": "☢️ النووي",
        "price": 10,
        "description": "يستبعد جميع اللاعبين من الجولة.",
    },
    "bomb": {
        "name": "💥 التفجير",
        "price": 5,
        "description": "يستبعد لاعبًا واحدًا.",
    },
    "target": {
        "name": "🎯 الاستهداف",
        "price": 3,
        "description": "يستهدف لاعبًا ويخرجه من الجولة.",
    },
    "shield": {
        "name": "🛡️ الحماية",
        "price": 4,
        "description": "تحمي نفسك من تخريب واحد.",
    },
}


class SabotageView(ui.View):

    def __init__(self, cog):
        super().__init__(timeout=60)
        self.cog = cog

    @ui.button(
        label="☢️ النووي — 10",
        style=discord.ButtonStyle.danger
    )
    async def nuke(self, interaction, button):

        await self.cog.use_sabotage(
            interaction,
            "nuke"
        )

    @ui.button(
        label="💥 تفجير — 5",
        style=discord.ButtonStyle.danger
    )
    async def bomb(self, interaction, button):

        await self.cog.use_sabotage(
            interaction,
            "bomb"
        )

    @ui.button(
        label="🎯 استهداف — 3",
        style=discord.ButtonStyle.primary
    )
    async def target(self, interaction, button):

        await self.cog.use_sabotage(
            interaction,
            "target"
        )

    @ui.button(
        label="🛡️ حماية — 4",
        style=discord.ButtonStyle.success
    )
    async def shield(self, interaction, button):

        await self.cog.use_sabotage(
            interaction,
            "shield"
        )


# =========================================================
# Cog
# =========================================================

class Games(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    # -----------------------------------------------------
    # -العاب-العب
    # -----------------------------------------------------

    @commands.command(name="العاب-العب")
    async def play_games(self, ctx):

        if ctx.channel.id != GAME_CHANNEL_ID:
            return

        if not has_control_role(ctx.author):
            return

        if GameManager.running():

            embed = discord.Embed(
                title="🎮⛔ لعبة جارية",
                description=(
                    f"يوجد الآن لعبة شغالة:\n\n"
                    f"## {GameManager.active_game_name}\n\n"
                    "⏳ انتظر حتى تنتهي اللعبة."
                ),
                color=DANGER_COLOR
            )

            await ctx.send(embed=embed)
            return

        embed = discord.Embed(
            title="🎮🔥 مركز الألعاب",
            description=(
                "## اختر اللعبة التي تريد تشغيلها 👇\n\n"
                "🎯 كل لعبة لها طريقة لعب مختلفة.\n"
                "⭐ المشاركة = نقاط.\n"
                "🏆 الفوز = نقاط إضافية.\n\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "### 🛠️ أوامر الإدارة\n"
                "`-نقاط-نقط @شخص` → إعطاء نقطة\n"
                "`-تصفير-لاعب @شخص` → تصفير لاعب\n"
                "`-تصفير-نقاط` → تصفير جميع النقاط\n"
                "`-توب-العاب` → عرض توب الألعاب\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "### 💰 أوامر اللاعبين\n"
                "`-محفظتي` → عرض نقاطك\n"
                "`-اعلى-نقاط` → أعلى اللاعبين\n"
                "`-تخريب` → متجر التخريب أثناء اللعبة"
            ),
            color=EMBED_COLOR
        )

        embed.set_footer(
            text="🔥 اختر لعبة وخلّ الحماس يبدأ!"
        )

        await ctx.send(
            embed=embed,
            view=GamesMenuView(self)
        )

    # -----------------------------------------------------
    # -محفظتي
    # -----------------------------------------------------

    @commands.command(name="محفظتي")
    async def wallet(self, ctx):

        if ctx.channel.id != GAME_CHANNEL_ID:
            return

        data = get_stats(ctx.author.id)

        points = data.get("points", 0)
        wins = data.get("wins", 0)
        games = data.get("games", 0)

        embed = discord.Embed(
            title="💰 محفظتك",
            description=(
                f"👤 اللاعب: {ctx.author.mention}\n\n"
                f"⭐ النقاط: **{points}**\n"
                f"🏆 الانتصارات: **{wins}**\n"
                f"🎮 الألعاب: **{games}**"
            ),
            color=GOLD_COLOR
        )

        await ctx.send(embed=embed)

    # -----------------------------------------------------
    # -اعلى-نقاط
    # -----------------------------------------------------

    @commands.command(name="اعلى-نقاط")
    async def top_points(self, ctx):

        if ctx.channel.id != GAME_CHANNEL_ID:
            return

        rows = leaderboard(10)

        if not rows:
            await ctx.send(
                "📊 لا توجد نقاط حتى الآن."
            )
            return

        lines = []

        medals = [
            "🥇",
            "🥈",
            "🥉",
        ]

        for index, row in enumerate(rows, start=1):

            user = self.bot.get_user(
                int(row["user_id"])
            )

            name = (
                user.mention
                if user
                else f"<@{row['user_id']}>"
            )

            prefix = (
                medals[index - 1]
                if index <= 3
                else f"**{index}.**"
            )

            lines.append(
                f"{prefix} {name} — ⭐ **{row.get('points', 0)}**"
            )

        embed = discord.Embed(
            title="🏆🔥 أعلى نقاط",
            description="\n".join(lines),
            color=GOLD_COLOR
        )

        embed.set_footer(
            text="استمر باللعب لتدخل التوب!"
        )

        await ctx.send(embed=embed)

    # -----------------------------------------------------
    # -نقاط-نقط
    # -----------------------------------------------------

    @commands.command(name="نقاط-نقط")
    async def add_one_point(
        self,
        ctx,
        member: discord.Member
    ):

        if ctx.channel.id != GAME_CHANNEL_ID:
            return

        if not has_control_role(ctx.author):
            return

        add_points(member.id, 1)

        await ctx.send(
            f"⭐ تم إضافة **نقطة واحدة** إلى "
            f"{member.mention}."
        )

    # -----------------------------------------------------
    # -تصفير-لاعب
    # -----------------------------------------------------

    @commands.command(name="تصفير-لاعب")
    async def reset_player(
        self,
        ctx,
        member: discord.Member
    ):

        if ctx.channel.id != GAME_CHANNEL_ID:
            return

        if not has_control_role(ctx.author):
            return

        stats_collection.update_one(
            {"user_id": member.id},
            {
                "$set": {
                    "points": 0,
                    "wins": 0,
                    "games": 0,
                    "actions": 0,
                }
            },
            upsert=True
        )

        await ctx.send(
            f"🧹 تم تصفير إحصائيات {member.mention}."
        )

    # -----------------------------------------------------
    # -تصفير-نقاط
    # -----------------------------------------------------

    @commands.command(name="تصفير-نقاط")
    async def reset_points(self, ctx):

        if ctx.channel.id != GAME_CHANNEL_ID:
            return

        if not has_control_role(ctx.author):
            return

        stats_collection.update_many(
            {},
            {
                "$set": {
                    "points": 0
                }
            }
        )

        await ctx.send(
            "🧹🔥 **تم تصفير نقاط جميع اللاعبين.**"
        )

    # -----------------------------------------------------
    # -توب-العاب
    # -----------------------------------------------------

    @commands.command(name="توب-العاب")
    async def game_top(self, ctx):

        if ctx.channel.id != GAME_CHANNEL_ID:
            return

        if not has_control_role(ctx.author):
            return

        rows = leaderboard(15)

        lines = []

        for index, row in enumerate(rows, 1):

            user = self.bot.get_user(
                int(row["user_id"])
            )

            name = (
                user.mention
                if user
                else f"<@{row['user_id']}>"
            )

            lines.append(
                f"**{index}.** {name}\n"
                f"⭐ {row.get('points', 0)} | "
                f"🏆 {row.get('wins', 0)} فوز | "
                f"🎮 {row.get('games', 0)} لعبة"
            )

        embed = discord.Embed(
            title="🏆🎮 توب الألعاب",
            description="\n\n".join(lines) or "لا يوجد لاعبين.",
            color=GOLD_COLOR
        )

        await ctx.send(embed=embed)

    # -----------------------------------------------------
    # -تخريب
    # -----------------------------------------------------

    @commands.command(name="تخريب")
    async def sabotage(self, ctx):

        if ctx.channel.id != GAME_CHANNEL_ID:
            return

        if not GameManager.running():

            embed = discord.Embed(
                title="🛠️ تخريب",
                description=(
                    "❌ ما تقدر تستخدم التخريب الآن.\n\n"
                    "لازم تكون فيه **فعالية أو لعبة شغالة**."
                ),
                color=DANGER_COLOR
            )

            await ctx.send(embed=embed)
            return

        embed = discord.Embed(
            title="💀🔥 متجر التخريب",
            description=(
                "استخدم النقاط لتخريب اللعبة!\n\n"
                "☢️ **النووي — 10 نقاط**\n"
                "يفجر الجولة ويستبعد جميع اللاعبين.\n\n"
                "💥 **التفجير — 5 نقاط**\n"
                "يستبعد لاعبًا.\n\n"
                "🎯 **الاستهداف — 3 نقاط**\n"
                "يستهدف لاعبًا ويخرجه.\n\n"
                "🛡️ **الحماية — 4 نقاط**\n"
                "تحمي نفسك من تخريب واحد."
            ),
            color=DANGER_COLOR
        )

        embed.set_footer(
            text="⚠️ التخريب يعمل فقط أثناء اللعبة"
        )

        await ctx.send(
            embed=embed,
            view=SabotageView(self)
        )

    # -----------------------------------------------------
    # تنفيذ التخريب
    # -----------------------------------------------------

    async def use_sabotage(
        self,
        interaction,
        action
    ):

        if interaction.channel.id != GAME_CHANNEL_ID:
            await interaction.response.send_message(
                "❌ هذا الأمر غير متاح هنا.",
                ephemeral=True
            )
            return

        game = GameManager.active_game_obj

        if game is None:
            await interaction.response.send_message(
                "❌ لا توجد لعبة شغالة.",
                ephemeral=True
            )
            return

        user_id = interaction.user.id

        # الحماية
        if action == "shield":

            price = SABOTAGE_ITEMS["shield"]["price"]

            if not remove_points(user_id, price):
                await interaction.response.send_message(
                    "❌ ما عندك نقاط كافية.",
                    ephemeral=True
                )
                return

            game.protected.add(user_id)
            add_action(user_id)

            await interaction.response.send_message(
                "🛡️🔥 **تم تفعيل الحماية!**\n"
                "أنت محمي من تخريب واحد."
            )

            return

        # النووي
        if action == "nuke":

            price = SABOTAGE_ITEMS["nuke"]["price"]

            if not remove_points(user_id, price):
                await interaction.response.send_message(
                    f"❌ تحتاج **{price} نقاط**.",
                    ephemeral=True
                )
                return

            add_action(user_id)

            for uid in list(game.players.keys()):
                if uid != user_id:
                    game.eliminated.add(uid)

            await interaction.response.send_message(
                "☢️💥 **تم تفجير النووي!**\n"
                "🔥 تم استبعاد جميع اللاعبين من الجولة!"
            )

            await interaction.channel.send(
                f"☢️ **كارثة نووية!**\n"
                f"المستخدم: {interaction.user.mention}\n"
                f"💸 تم خصم **{price} نقاط**."
            )

            await asyncio.sleep(2)

            if not game.finished:
                await game.finish()

            return

        # التخريب الذي يحتاج اختيار لاعب
        if action in ("bomb", "target"):

            price = SABOTAGE_ITEMS[action]["price"]

            if not remove_points(user_id, price):
                await interaction.response.send_message(
                    f"❌ تحتاج **{price} نقاط**.",
                    ephemeral=True
                )
                return

            add_action(user_id)

            members = [
                m for uid, m in game.players.items()
                if uid != user_id
                and uid not in game.eliminated
            ]

            if not members:

                await interaction.response.send_message(
                    "❌ لا يوجد لاعب آخر يمكن استهدافه.",
                    ephemeral=True
                )

                add_points(user_id, price)
                return

            view = TargetView(
                self,
                interaction.user,
                members,
                action
            )

            await interaction.response.send_message(
                "🎯 اختر اللاعب الذي تريد استهدافه:",
                view=view,
                ephemeral=True
            )


# =========================================================
# اختيار هدف التخريب
# =========================================================

class TargetView(ui.View):

    def __init__(
        self,
        cog,
        attacker,
        members,
        action
    ):
        super().__init__(timeout=30)

        self.cog = cog
        self.attacker = attacker
        self.action = action

        options = [
            discord.SelectOption(
                label=member.display_name[:100],
                value=str(member.id)
            )
            for member in members
        ]

        self.select = ui.Select(
            placeholder="🎯 اختر الضحية...",
            options=options
        )

        self.select.callback = self.callback
        self.add_item(self.select)

    async def callback(self, interaction):

        if interaction.user.id != self.attacker.id:
            await interaction.response.send_message(
                "❌ هذه القائمة ليست لك.",
                ephemeral=True
            )
            return

        game = GameManager.active_game_obj

        if game is None:
            await interaction.response.send_message(
                "❌ اللعبة انتهت.",
                ephemeral=True
            )
            return

        target_id = int(self.select.values[0])

        if target_id in game.protected:

            game.protected.remove(target_id)

            await interaction.response.edit_message(
                content=(
                    "🛡️ **تم صد التخريب!**\n"
                    "اللاعب كان محميًا."
                ),
                view=None
            )

            return

        target = game.players.get(target_id)

        if not target:
            await interaction.response.edit_message(
                content="❌ اللاعب غير موجود.",
                view=None
            )
            return

        game.eliminated.add(target_id)

        if self.action == "bomb":
            text = (
                f"💥🔥 **تم التفجير!**\n"
                f"{target.mention} تم استبعاده!"
            )
        else:
            text = (
                f"🎯💀 **تم الاستهداف!**\n"
                f"{target.mention} خرج من الجولة!"
            )

        await interaction.response.edit_message(
            content="✅ تم تنفيذ التخريب!",
            view=None
        )

        await interaction.channel.send(text)


# =========================================================
# Setup
# =========================================================

async def setup(bot):
    await bot.add_cog(Games(bot))
