import asyncio
import os
import random
from dataclasses import dataclass, field
from typing import Optional

import discord
from discord.ext import commands
from pymongo import MongoClient


# =========================================================
# الإعدادات
# =========================================================

GAME_CHANNEL_ID = 1550797517237518417

# رتبة التحكم بالألعاب فقط
CONTROL_ROLE_ID = 1544078469657530578

# رتبة اللاعبين
PLAYER_ROLE_ID = 1544078847253811331

# MongoDB
MONGO_URI = os.environ.get("MONGO_URI")
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["discord_bot_db"]

# مجموعة خاصة بالألعاب
stats_collection = db["game_stats"]


MIN_PLAYERS = 2
MAX_PLAYERS = 15

ROUND_TIME = 35

BOT_NAMES = [
    "Shadow",
    "Ghost",
    "Viper",
    "Raven",
    "Titan",
    "Phantom",
    "Wolf",
    "Nova",
    "Hunter",
    "Venom",
    "Blaze",
    "Storm",
    "Frost",
    "Reaper",
    "Specter",
]


# =========================================================
# أدوات عامة
# =========================================================

def is_game_channel():
    async def predicate(ctx):
        return ctx.channel.id == GAME_CHANNEL_ID

    return commands.check(predicate)


def has_control_role(member: discord.Member):
    return any(role.id == CONTROL_ROLE_ID for role in member.roles)


def get_points(user_id: int):
    data = stats_collection.find_one({"user_id": user_id})
    if not data:
        return 0
    return int(data.get("points", 0))


def add_points(user_id: int, amount: int):
    stats_collection.update_one(
        {"user_id": user_id},
        {"$inc": {"points": amount}},
        upsert=True
    )


def reset_player(user_id: int):
    stats_collection.update_one(
        {"user_id": user_id},
        {"$set": {"points": 0}},
        upsert=True
    )


def reset_all_points():
    stats_collection.update_many(
        {},
        {"$set": {"points": 0}}
    )


# =========================================================
# اللاعب
# =========================================================

@dataclass
class Player:
    id: int
    name: str
    member: Optional[discord.Member] = None
    is_bot: bool = False

    alive: bool = True
    hp: int = 100
    shield: int = 0
    score: int = 0

    territory: int = 0
    action: Optional[str] = None
    target: Optional[int] = None

    extra: dict = field(default_factory=dict)

    @property
    def mention(self):
        if self.member:
            return self.member.mention
        return f"🤖 **{self.name}**"


# =========================================================
# مدير الألعاب
# =========================================================

class GameManager:
    active_game = None

    @classmethod
    def running(cls):
        return cls.active_game is not None


# =========================================================
# اللعبة الأساسية
# =========================================================

class BaseGame:

    def __init__(self, cog, channel, players):
        self.cog = cog
        self.channel = channel
        self.players = players

        self.round = 0
        self.max_rounds = 6

        self.message = None
        self.finished = False

        self.actions = {}
        self.targets = {}

    def alive_players(self):
        return [
            p for p in self.players.values()
            if p.alive
        ]

    def real_players(self):
        return [
            p for p in self.players.values()
            if not p.is_bot
        ]

    def get_player(self, user_id):
        return self.players.get(user_id)

    def random_target(self, player, alive_only=True):
        choices = [
            p for p in self.players.values()
            if p.id != player.id
            and (p.alive if alive_only else True)
        ]

        return random.choice(choices) if choices else None

    async def send(self, content=None, embed=None, view=None):
        if self.message:
            try:
                await self.message.edit(
                    content=content,
                    embed=embed,
                    view=view
                )
                return
            except Exception:
                pass

        self.message = await self.channel.send(
            content=content,
            embed=embed,
            view=view
        )

    async def finish(self):
        self.finished = True

        if GameManager.active_game is self:
            GameManager.active_game = None

    async def award(self, player, amount):
        if player.is_bot:
            return

        add_points(player.id, amount)

    async def eliminate(self, player):
        player.alive = False
        player.action = None
        player.target = None

    def alive_text(self):
        lines = []

        for p in self.players.values():
            if p.alive:
                status = f"❤️ {p.hp}" if p.hp else "🟢"
                lines.append(f"{p.mention} — {status}")

        return "\n".join(lines) or "لا يوجد لاعبين."

    async def timeout_sleep(self, seconds):
        await asyncio.sleep(seconds)


# =========================================================
# أزرار اللعبة
# =========================================================

class ActionView(discord.ui.View):

    def __init__(self, game, actions):
        super().__init__(timeout=ROUND_TIME)
        self.game = game
        self.action_names = actions

        for action_key, label, emoji in actions:
            button = discord.ui.Button(
                label=label,
                emoji=emoji,
                style=discord.ButtonStyle.primary
            )

            async def callback(interaction, key=action_key):
                await self.choose(interaction, key)

            button.callback = callback
            self.add_item(button)

    async def choose(self, interaction, action):

        if interaction.channel.id != GAME_CHANNEL_ID:
            return

        player = self.game.get_player(interaction.user.id)

        if not player:
            await interaction.response.send_message(
                "❌ أنت لست داخل اللعبة.",
                ephemeral=True
            )
            return

        if not player.alive:
            await interaction.response.send_message(
                "💀 أنت مستبعد من هذه الجولة.",
                ephemeral=True
            )
            return

        if player.action is not None:
            await interaction.response.send_message(
                "⚠️ اخترت حركتك بالفعل.",
                ephemeral=True
            )
            return

        player.action = action

        # بعض الحركات تحتاج هدفًا
        if action in {"attack", "ally", "steal", "target"}:

            choices = [
                p for p in self.game.alive_players()
                if p.id != player.id
            ]

            if not choices:
                player.target = None
            else:
                view = TargetView(
                    self.game,
                    player,
                    action,
                    choices
                )

                await interaction.response.send_message(
                    "🎯 اختر الهدف:",
                    view=view,
                    ephemeral=True
                )
                return

        await interaction.response.send_message(
            f"✅ تم اختيار **{action}**.",
            ephemeral=True
        )

        await self.game.check_actions()


# =========================================================
# اختيار الهدف
# =========================================================

class TargetView(discord.ui.View):

    def __init__(self, game, player, action, targets):
        super().__init__(timeout=20)

        self.game = game
        self.player = player
        self.action = action

        options = []

        for target in targets[:25]:
            options.append(
                discord.SelectOption(
                    label=target.name[:100],
                    value=str(target.id),
                    emoji="🤖" if target.is_bot else "👤"
                )
            )

        select = discord.ui.Select(
            placeholder="اختر اللاعب...",
            options=options
        )

        async def callback(interaction):

            if interaction.user.id != self.player.id:
                await interaction.response.send_message(
                    "❌ هذا الاختيار ليس لك.",
                    ephemeral=True
                )
                return

            target_id = int(select.values[0])

            if target_id not in self.game.players:
                await interaction.response.send_message(
                    "❌ الهدف غير موجود.",
                    ephemeral=True
                )
                return

            self.player.target = target_id

            await interaction.response.edit_message(
                content=f"🎯 تم اختيار **{self.game.players[target_id].name}**.",
                view=None
            )

            await self.game.check_actions()

        select.callback = callback
        self.add_item(select)


# =========================================================
# اللعبة الأولى: معركة اللاعبين
# =========================================================

class BattleGame(BaseGame):

    name = "⚔️ معركة اللاعبين"

    def __init__(self, cog, channel, players):
        super().__init__(cog, channel, players)
        self.max_rounds = 8

    async def start(self):

        for p in self.players.values():
            p.hp = 100
            p.shield = 0
            p.alive = True

        await self.next_round()

    async def next_round(self):

        if self.finished:
            return

        alive = self.alive_players()

        if len(alive) <= 1:
            await self.end_game()
            return

        if self.round >= self.max_rounds:
            await self.end_game()
            return

        self.round += 1
        self.actions = {}

        for p in alive:
            p.action = None
            p.target = None

        # الذكاء الاصطناعي يختار
        for p in alive:
            if p.is_bot:
                self.bot_choose(p)

        embed = discord.Embed(
            title=f"⚔️ معركة اللاعبين — الجولة {self.round}",
            description=(
                "اختار حركتك!\n\n"
                "🗡️ هجوم — يسبب ضررًا\n"
                "🛡️ دفاع — يقلل الضرر\n"
                "💨 مراوغة — فرصة لتجنب الهجوم\n"
                "🤝 تحالف — يعطي حماية مؤقتة"
            )
        )

        status = []

        for p in alive:
            hearts = max(0, p.hp)
            status.append(
                f"{p.mention} — ❤️ {hearts}/100"
            )

        embed.add_field(
            name="👥 اللاعبين",
            value="\n".join(status),
            inline=False
        )

        view = ActionView(
            self,
            [
                ("attack", "هجوم", "🗡️"),
                ("defend", "دفاع", "🛡️"),
                ("dodge", "مراوغة", "💨"),
                ("ally", "تحالف", "🤝"),
            ]
        )

        await self.send(embed=embed, view=view)

        await self.check_actions()

    def bot_choose(self, bot):

        enemies = [
            p for p in self.alive_players()
            if p.id != bot.id
        ]

        if not enemies:
            bot.action = "defend"
            return

        if bot.hp <= 30:
            choices = ["defend", "dodge", "ally"]
        else:
            choices = [
                "attack",
                "attack",
                "defend",
                "dodge",
                "ally"
            ]

        bot.action = random.choice(choices)

        if bot.action in {"attack", "ally"}:
            target = random.choice(enemies)
            bot.target = target.id

    async def check_actions(self):

        if self.finished:
            return

        alive = self.alive_players()

        if all(p.action is not None for p in alive):
            await asyncio.sleep(1)
            await self.resolve_round()

    async def resolve_round(self):

        results = []

        # التحالف
        for p in self.alive_players():
            if p.action == "ally":
                p.shield += 20

                if p.target and p.target in self.players:
                    target = self.players[p.target]

                    if target.alive:
                        target.shield += 10

                        results.append(
                            f"🤝 {p.name} تحالف مع {target.name}"
                        )

        # الهجمات
        for p in self.alive_players():

            if p.action != "attack":
                continue

            target = self.players.get(p.target)

            if not target or not target.alive:
                continue

            damage = random.randint(18, 30)

            if target.action == "defend":
                damage //= 2

            elif target.action == "dodge":
                if random.random() < 0.55:
                    damage = 0

            if target.shield > 0:
                blocked = min(target.shield, damage)
                target.shield -= blocked
                damage -= blocked

            if damage > 0:
                target.hp -= damage

                results.append(
                    f"🗡️ {p.name} هاجم {target.name} "
                    f"وألحق **{damage} ضرر**"
                )

                if target.hp <= 0:
                    target.hp = 0
                    await self.eliminate(target)

                    results.append(
                        f"💀 {target.name} خرج من المعركة!"
                    )
                    await self.award(p, 2)

            else:
                results.append(
                    f"🛡️ {target.name} صد هجوم {p.name}"
                )

        # نقاط البقاء
        for p in self.alive_players():
            await self.award(p, 1)

        embed = discord.Embed(
            title=f"⚔️ نتائج الجولة {self.round}",
            description="\n".join(results) if results else "لا توجد أحداث."
        )

        embed.add_field(
            name="الحالة",
            value=self.alive_text(),
            inline=False
        )

        await self.send(embed=embed, view=None)

        await asyncio.sleep(3)
        await self.next_round()

    async def end_game(self):

        alive = self.alive_players()

        if alive:
            winner = max(
                alive,
                key=lambda p: p.hp
            )

            await self.award(winner, 10)

            text = (
                f"🏆 **{winner.name} فاز بالمعركة!**\n"
                f"⭐ حصل على +10 نقاط"
            )
        else:
            text = "💀 انتهت المعركة بدون فائز."

        embed = discord.Embed(
            title="🏁 انتهت معركة اللاعبين",
            description=text
        )

        await self.send(embed=embed, view=None)

        await self.finish()


# =========================================================
# اللعبة الثانية: السيطرة على المناطق
# =========================================================

class TerritoryGame(BaseGame):

    name = "🏴 السيطرة على المناطق"

    TERRITORIES = [
        "🏰 القلعة",
        "🌲 الغابة",
        "⛰️ الجبل",
        "🏜️ الصحراء",
        "⚓ الميناء",
    ]

    def __init__(self, cog, channel, players):
        super().__init__(cog, channel, players)
        self.max_rounds = 7
        self.owners = {}

    async def start(self):

        for territory in range(len(self.TERRITORIES)):
            self.owners[territory] = random.choice(
                list(self.players.keys())
            )

        await self.next_round()

    def bot_choose(self, bot):

        actions = [
            "attack",
            "defend",
            "occupy"
        ]

        bot.action = random.choice(actions)

        bot.target = random.randrange(
            len(self.TERRITORIES)
        )

    async def next_round(self):

        if self.round >= self.max_rounds:
            await self.end_game()
            return

        self.round += 1

        for p in self.alive_players():
            p.action = None
            p.target = None

            if p.is_bot:
                self.bot_choose(p)

        owners = []

        for index, territory in enumerate(self.TERRITORIES):
            owner_id = self.owners.get(index)

            owner = self.players.get(owner_id)

            if owner:
                owners.append(
                    f"{territory} → {owner.name}"
                )

        embed = discord.Embed(
            title=f"🏴 السيطرة على المناطق — الجولة {self.round}",
            description=(
                "اختر حركتك.\n\n"
                "⚔️ هجوم — حاول أخذ منطقة\n"
                "🛡️ دفاع — تحصين منطقتك\n"
                "🏴 احتلال — محاولة السيطرة على منطقة"
            )
        )

        embed.add_field(
            name="🗺️ الخريطة",
            value="\n".join(owners),
            inline=False
        )

        view = ActionView(
            self,
            [
                ("attack", "هجوم", "⚔️"),
                ("defend", "تحصين", "🛡️"),
                ("target", "احتلال", "🏴"),
            ]
        )

        await self.send(embed=embed, view=view)
        await self.check_actions()

    async def check_actions(self):

        alive = self.alive_players()

        if all(p.action is not None for p in alive):
            await asyncio.sleep(1)
            await self.resolve()

    async def resolve(self):

        results = []

        for p in self.alive_players():

            if p.action == "defend":
                p.shield += 15

                results.append(
                    f"🛡️ {p.name} حصّن نفسه"
                )

            elif p.action in {"attack", "target"}:

                territory = p.target

                if territory is None:
                    territory = random.randrange(
                        len(self.TERRITORIES)
                    )

                old_owner_id = self.owners.get(territory)
                old_owner = self.players.get(old_owner_id)

                if old_owner and old_owner.id == p.id:
                    results.append(
                        f"🏴 {p.name} يسيطر بالفعل على "
                        f"{self.TERRITORIES[territory]}"
                    )
                    continue

                chance = random.random()

                if chance > 0.35:

                    self.owners[territory] = p.id

                    results.append(
                        f"🔥 {p.name} استولى على "
                        f"{self.TERRITORIES[territory]}!"
                    )

                    p.territory += 1
                    await self.award(p, 2)

                else:

                    results.append(
                        f"❌ {p.name} فشل في السيطرة على "
                        f"{self.TERRITORIES[territory]}"
                    )

        await self.send(
            embed=discord.Embed(
                title=f"⚔️ نتائج الجولة {self.round}",
                description="\n".join(results)
            ),
            view=None
        )

        await asyncio.sleep(3)
        await self.next_round()

    async def end_game(self):

        counts = {}

        for owner in self.owners.values():
            counts[owner] = counts.get(owner, 0) + 1

        if not counts:
            await self.finish()
            return

        winner_id = max(
            counts,
            key=counts.get
        )

        winner = self.players[winner_id]

        await self.award(winner, 10)

        await self.send(
            embed=discord.Embed(
                title="🏆 انتهت السيطرة على المناطق",
                description=(
                    f"👑 الفائز: **{winner.name}**\n"
                    f"🏴 المناطق: **{counts[winner_id]}**\n"
                    f"⭐ +10 نقاط"
                )
            ),
            view=None
        )

        await self.finish()


# =========================================================
# اللعبة الثالثة: الهدف السري
# =========================================================

class SecretTargetGame(BaseGame):

    name = "🎯 الهدف السري"

    def __init__(self, cog, channel, players):
        super().__init__(cog, channel, players)
        self.max_rounds = 7
        self.secret_targets = {}

    async def start(self):

        player_list = list(self.players.values())

        for p in player_list:

            choices = [
                x for x in player_list
                if x.id != p.id
            ]

            if choices:
                self.secret_targets[p.id] = random.choice(
                    choices
                ).id

        await self.next_round()

    def bot_choose(self, bot):

        target_id = self.secret_targets.get(bot.id)

        if target_id:
            bot.action = random.choice(
                ["target", "defend", "target"]
            )
            bot.target = target_id
        else:
            bot.action = "defend"

    async def next_round(self):

        if self.round >= self.max_rounds:
            await self.end_game()
            return

        self.round += 1

        for p in self.alive_players():
            p.action = None
            p.target = None

            if p.is_bot:
                self.bot_choose(p)

        embed = discord.Embed(
            title=f"🎯 الهدف السري — الجولة {self.round}",
            description=(
                "لكل لاعب هدف سري.\n"
                "حاول الوصول له قبل انتهاء الجولات!"
            )
        )

        view = ActionView(
            self,
            [
                ("target", "ملاحقة الهدف", "🎯"),
                ("defend", "حماية", "🛡️"),
                ("dodge", "اختفاء", "💨"),
            ]
        )

        await self.send(embed=embed, view=view)
        await self.check_actions()

    async def check_actions(self):

        alive = self.alive_players()

        if all(p.action is not None for p in alive):
            await asyncio.sleep(1)
            await self.resolve()

    async def resolve(self):

        results = []

        for p in self.alive_players():

            target_id = self.secret_targets.get(p.id)

            if p.action == "target":

                target = self.players.get(p.target)

                if target and target.id == target_id:

                    await self.award(p, 5)

                    results.append(
                        f"🎯 **{p.name} نجح في الوصول إلى هدفه السري!**"
                    )

                    # هدف جديد
                    choices = [
                        x for x in self.alive_players()
                        if x.id != p.id
                    ]

                    if choices:
                        self.secret_targets[p.id] = random.choice(
                            choices
                        ).id

                else:

                    results.append(
                        f"❌ {p.name} لم يصل لهدفه."
                    )

            elif p.action == "defend":

                p.shield += 20

                results.append(
                    f"🛡️ {p.name} اختار الحماية."
                )

            else:

                results.append(
                    f"💨 {p.name} اختفى."
                )

        await self.send(
            embed=discord.Embed(
                title=f"🎯 نتائج الجولة {self.round}",
                description="\n".join(results)
            ),
            view=None
        )

        await asyncio.sleep(3)
        await self.next_round()

    async def end_game(self):

        alive = self.alive_players()

        if alive:

            for p in alive:
                await self.award(p, 3)

            winner = max(
                alive,
                key=lambda p: get_points(p.id)
                if not p.is_bot else 0
            )

            text = (
                f"🏆 انتهى الهدف السري!\n"
                f"⭐ الناجون حصلوا على مكافأة المشاركة."
            )

        else:
            text = "🏁 انتهت اللعبة."

        await self.send(
            embed=discord.Embed(
                title="🏁 نهاية الهدف السري",
                description=text
            ),
            view=None
        )

        await self.finish()


# =========================================================
# اللعبة الرابعة: ملك السيرفر
# =========================================================

class KingGame(BaseGame):

    name = "👑 ملك السيرفر"

    def __init__(self, cog, channel, players):
        super().__init__(cog, channel, players)
        self.max_rounds = 6
        self.king_id = None
        self.votes = {}

    async def start(self):

        self.king_id = random.choice(
            list(self.players.keys())
        )

        await self.next_round()

    def bot_choose(self, bot):

        if bot.id == self.king_id:
            bot.action = random.choice(
                ["defend", "ally"]
            )
        else:
            bot.action = random.choice(
                ["attack", "target", "ally"]
            )

            king = self.players.get(self.king_id)

            if king:
                bot.target = king.id

    async def next_round(self):

        if self.round >= self.max_rounds:
            await self.end_game()
            return

        self.round += 1

        for p in self.alive_players():

            p.action = None
            p.target = None

            if p.is_bot:
                self.bot_choose(p)

        king = self.players.get(self.king_id)

        embed = discord.Embed(
            title=f"👑 ملك السيرفر — الجولة {self.round}",
            description=(
                "👑 هناك ملك حالي.\n"
                "حافظ على العرش أو حاول إسقاط الملك!"
            )
        )

        if king:
            embed.add_field(
                name="👑 الملك الحالي",
                value=king.mention,
                inline=False
            )

        view = ActionView(
            self,
            [
                ("attack", "مهاجمة الملك", "⚔️"),
                ("defend", "حماية", "🛡️"),
                ("ally", "تحالف", "🤝"),
            ]
        )

        await self.send(embed=embed, view=view)
        await self.check_actions()

    async def check_actions(self):

        alive = self.alive_players()

        if all(p.action is not None for p in alive):
            await asyncio.sleep(1)
            await self.resolve()

    async def resolve(self):

        king = self.players.get(self.king_id)

        attackers = [
            p for p in self.alive_players()
            if p.action == "attack"
            and p.target == self.king_id
        ]

        if king and attackers:

            chance = 0.25 + (
                0.15 * min(len(attackers), 3)
            )

            if random.random() < chance:

                old_king = king
                new_king = random.choice(attackers)

                self.king_id = new_king.id

                await self.award(new_king, 4)

                result = (
                    f"👑 **{new_king.name} استولى على العرش!**"
                )

            else:

                result = (
                    f"🛡️ {king.name} نجح في الدفاع عن العرش!"
                )

        else:

            result = "👑 الملك ما زال على العرش."

        await self.send(
            embed=discord.Embed(
                title=f"👑 نتائج الجولة {self.round}",
                description=result
            ),
            view=None
        )

        await asyncio.sleep(3)
        await self.next_round()

    async def end_game(self):

        king = self.players.get(self.king_id)

        if king:
            await self.award(king, 12)

            text = (
                f"👑 **{king.name} أنهى اللعبة وهو الملك!**\n"
                f"⭐ +12 نقاط"
            )
        else:
            text = "🏁 انتهت اللعبة."

        await self.send(
            embed=discord.Embed(
                title="🏆 نهاية ملك السيرفر",
                description=text
            ),
            view=None
        )

        await self.finish()


# =========================================================
# اللعبة الخامسة: السفينة الغارقة
# =========================================================

class ShipGame(BaseGame):

    name = "🚢 السفينة الغارقة"

    def __init__(self, cog, channel, players):
        super().__init__(cog, channel, players)
        self.max_rounds = 7
        self.ship_hp = 100

    async def start(self):
        await self.next_round()

    def bot_choose(self, bot):

        if self.ship_hp <= 30:
            bot.action = random.choice(
                ["defend", "ally"]
            )
        else:
            bot.action = random.choice(
                ["attack", "defend", "dodge"]
            )

    async def next_round(self):

        if self.round >= self.max_rounds:
            await self.end_game()
            return

        self.round += 1

        for p in self.alive_players():

            p.action = None
            p.target = None

            if p.is_bot:
                self.bot_choose(p)

        embed = discord.Embed(
            title=f"🚢 السفينة الغارقة — الجولة {self.round}",
            description=(
                f"❤️ سلامة السفينة: **{self.ship_hp}/100**\n\n"
                "قرر ماذا ستفعل لإنقاذ السفينة."
            )
        )

        view = ActionView(
            self,
            [
                ("defend", "إصلاح", "🔧"),
                ("ally", "مساعدة لاعب", "🤝"),
                ("dodge", "استكشاف", "🔭"),
                ("attack", "مخاطرة", "⚔️"),
            ]
        )

        await self.send(embed=embed, view=view)
        await self.check_actions()

    async def check_actions(self):

        if all(
            p.action is not None
            for p in self.alive_players()
        ):
            await asyncio.sleep(1)
            await self.resolve()

    async def resolve(self):

        results = []

        repairs = sum(
            1
            for p in self.alive_players()
            if p.action == "defend"
        )

        damage = random.randint(8, 25)

        self.ship_hp += repairs * 12
        self.ship_hp -= damage

        self.ship_hp = max(
            0,
            min(100, self.ship_hp)
        )

        results.append(
            f"🌊 العاصفة سببت **{damage} ضرر** للسفينة."
        )

        if repairs:
            results.append(
                f"🔧 تم إصلاح السفينة بمقدار **{repairs * 12}**."
            )

        for p in self.alive_players():

            if p.action == "dodge":
                await self.award(p, 1)

            elif p.action == "ally":
                await self.award(p, 2)

        if self.ship_hp <= 0:

            await self.send(
                embed=discord.Embed(
                    title="💥 غرقت السفينة!",
                    description="\n".join(results)
                ),
                view=None
            )

            await self.finish()
            return

        await self.send(
            embed=discord.Embed(
                title=f"🌊 نتيجة الجولة {self.round}",
                description="\n".join(results)
            ),
            view=None
        )

        await asyncio.sleep(3)
        await self.next_round()

    async def end_game(self):

        for p in self.alive_players():
            await self.award(p, 5)

        await self.send(
            embed=discord.Embed(
                title="🚢 نجت السفينة!",
                description=(
                    "🎉 انتهت الرحلة بنجاح!\n"
                    "⭐ جميع اللاعبين الناجين حصلوا على مكافأة."
                )
            ),
            view=None
        )

        await self.finish()


# =========================================================
# اللعبة السادسة: المزاد
# =========================================================

class AuctionGame(BaseGame):

    name = "💰 المزاد"

    def __init__(self, cog, channel, players):
        super().__init__(cog, channel, players)
        self.max_rounds = 5
        self.bids = {}
        self.item = None

    async def start(self):
        await self.next_round()

    def bot_choose(self, bot):

        bot.action = "bid"

        bot.extra["bid"] = random.randint(1, 10)

    async def next_round(self):

        if self.round >= self.max_rounds:
            await self.end_game()
            return

        self.round += 1
        self.bids = {}

        self.item = random.choice([
            "💎 جوهرة نادرة",
            "👑 تاج أسطوري",
            "⚡ بطاقة قوة",
            "🛡️ درع ذهبي",
            "🎁 صندوق غامض",
        ])

        for p in self.alive_players():

            p.action = None
            p.target = None

            if p.is_bot:
                self.bot_choose(p)

        embed = discord.Embed(
            title=f"💰 المزاد — الجولة {self.round}",
            description=(
                f"السلعة الحالية:\n"
                f"# {self.item}\n\n"
                "اختر مقدار المزايدة."
            )
        )

        view = AuctionView(self)

        await self.send(embed=embed, view=view)

    async def submit_bid(self, interaction, amount):

        player = self.players.get(
            interaction.user.id
        )

        if not player:
            await interaction.response.send_message(
                "❌ لست داخل اللعبة.",
                ephemeral=True
            )
            return

        if player.id in self.bids:
            await interaction.response.send_message(
                "⚠️ أنت زايدت بالفعل.",
                ephemeral=True
            )
            return

        self.bids[player.id] = amount

        await interaction.response.send_message(
            f"💰 مزايدتك: **{amount}**",
            ephemeral=True
        )

        await self.check_bids()

    async def check_bids(self):

        alive = self.alive_players()

        # البوتات
        for p in alive:

            if p.is_bot and p.id not in self.bids:
                self.bids[p.id] = p.extra.get(
                    "bid",
                    random.randint(1, 10)
                )

        if len(self.bids) >= len(alive):

            await asyncio.sleep(1)
            await self.resolve()

    async def resolve(self):

        if not self.bids:
            await self.next_round()
            return

        winner_id = max(
            self.bids,
            key=self.bids.get
        )

        winner = self.players[winner_id]
        amount = self.bids[winner_id]

        await self.award(winner, 3)

        await self.send(
            embed=discord.Embed(
                title="💰 انتهى المزاد",
                description=(
                    f"🏆 الفائز: **{winner.name}**\n"
                    f"💰 المزايدة: **{amount}**"
                )
            ),
            view=None
        )

        await asyncio.sleep(3)
        await self.next_round()

    async def end_game(self):

        winner = max(
            self.alive_players(),
            key=lambda p: get_points(p.id)
            if not p.is_bot else 0
        )

        if winner:
            await self.award(winner, 10)

        await self.send(
            embed=discord.Embed(
                title="🏆 انتهى المزاد الكبير",
                description=(
                    f"👑 أفضل لاعب: **{winner.name if winner else 'لا أحد'}**"
                )
            ),
            view=None
        )

        await self.finish()


class AuctionView(discord.ui.View):

    def __init__(self, game):
        super().__init__(timeout=30)
        self.game = game

        for amount in [1, 3, 5, 10]:

            button = discord.ui.Button(
                label=f"+{amount}",
                style=discord.ButtonStyle.success
            )

            async def callback(
                interaction,
                value=amount
            ):
                await self.game.submit_bid(
                    interaction,
                    value
                )

            button.callback = callback
            self.add_item(button)


# =========================================================
# اللعبة السابعة: الخائن
# =========================================================

class TraitorGame(BaseGame):

    name = "🕵️ الخائن"

    def __init__(self, cog, channel, players):
        super().__init__(cog, channel, players)
        self.max_rounds = 6
        self.traitor_id = None
        self.votes = {}

    async def start(self):

        self.traitor_id = random.choice(
            list(self.players.keys())
        )

        await self.next_round()

    def bot_choose(self, bot):

        others = [
            p for p in self.alive_players()
            if p.id != bot.id
        ]

        if not others:
            bot.action = "defend"
            return

        bot.action = "target"

        # الخائن يحاول توجيه الشك لشخص آخر
        target = random.choice(others)
        bot.target = target.id

    async def next_round(self):

        if self.round >= self.max_rounds:
            await self.end_game()
            return

        self.round += 1
        self.votes = {}

        for p in self.alive_players():

            p.action = None
            p.target = None

            if p.is_bot:
                self.bot_choose(p)

        embed = discord.Embed(
            title=f"🕵️ الخائن — الجولة {self.round}",
            description=(
                "هناك خائن بينكم.\n"
                "حاول اكتشافه قبل نهاية اللعبة!"
            )
        )

        view = ActionView(
            self,
            [
                ("target", "اتهام لاعب", "👉"),
                ("defend", "حماية نفسك", "🛡️"),
            ]
        )

        await self.send(embed=embed, view=view)
        await self.check_actions()

    async def check_actions(self):

        alive = self.alive_players()

        if all(
            p.action is not None
            for p in alive
        ):
            await asyncio.sleep(1)
            await self.resolve()

    async def resolve(self):

        votes = {}

        for p in self.alive_players():

            if p.action == "target" and p.target:

                votes[p.target] = (
                    votes.get(p.target, 0) + 1
                )

        if votes:

            target_id = max(
                votes,
                key=votes.get
            )

            target = self.players[target_id]

            if target.id == self.traitor_id:

                for p in self.alive_players():
                    await self.award(p, 3)

                await self.send(
                    embed=discord.Embed(
                        title="🎉 تم كشف الخائن!",
                        description=(
                            f"🕵️ الخائن كان **{target.name}**!"
                        )
                    ),
                    view=None
                )

                await self.finish()
                return

            else:

                await self.eliminate(target)

                result = (
                    f"❌ تم اتهام **{target.name}** خطأً!"
                )

                if target.id == self.traitor_id:
                    result = (
                        f"🎉 تم كشف الخائن: **{target.name}**!"
                    )

        else:

            result = "🤷 لم يتم الاتفاق على أحد."

        await self.send(
            embed=discord.Embed(
                title=f"🕵️ نتائج الجولة {self.round}",
                description=result
            ),
            view=None
        )

        await asyncio.sleep(3)
        await self.next_round()

    async def end_game(self):

        traitor = self.players.get(
            self.traitor_id
        )

        if traitor and traitor.alive:

            await self.award(traitor, 15)

            text = (
                f"🕵️ **الخائن فاز!**\n"
                f"الخائن كان: **{traitor.name}**\n"
                f"⭐ +15 نقاط"
            )

        else:

            text = "🎉 اللاعبون نجحوا في كشف الخائن!"

        await self.send(
            embed=discord.Embed(
                title="🏁 نهاية لعبة الخائن",
                description=text
            ),
            view=None
        )

        await self.finish()


# =========================================================
# تخريب اللعبة
# =========================================================

class SabotageView(discord.ui.View):

    def __init__(self, game, owner):
        super().__init__(timeout=30)

        self.game = game
        self.owner = owner

        buttons = [
            ("☢️", "نووي", 10, "nuke"),
            ("💥", "انفجار", 5, "bomb"),
            ("🎯", "هدف", 3, "target"),
            ("🛡️", "درع", 4, "shield"),
        ]

        for emoji, label, cost, action in buttons:

            button = discord.ui.Button(
                label=f"{label} ({cost})",
                emoji=emoji,
                style=discord.ButtonStyle.danger
            )

            async def callback(
                interaction,
                action=action,
                cost=cost
            ):

                if interaction.user.id != self.owner.id:
                    await interaction.response.send_message(
                        "❌ هذه القائمة ليست لك.",
                        ephemeral=True
                    )
                    return

                await self.execute(
                    interaction,
                    action,
                    cost
                )

            button.callback = callback
            self.add_item(button)

    async def execute(self, interaction, action, cost):

        points = get_points(self.owner.id)

        if points < cost:
            await interaction.response.send_message(
                f"❌ تحتاج **{cost} نقطة**.\n"
                f"رصيدك: **{points}**",
                ephemeral=True
            )
            return

        players = self.game.alive_players()

        if not players:
            return

        reset_amount = -cost

        stats_collection.update_one(
            {"user_id": self.owner.id},
            {"$inc": {"points": reset_amount}},
            upsert=True
        )

        if action == "nuke":

            for p in players:
                if p.id != self.owner.id:
                    p.hp = max(1, p.hp - 35)

            text = (
                "☢️ **تم تفعيل الحدث النووي داخل اللعبة!**\n"
                "تم تخفيض صحة جميع الخصوم."
            )

        elif action == "bomb":

            targets = [
                p for p in players
                if p.id != self.owner.id
            ]

            if targets:
                target = random.choice(targets)
                target.hp = max(
                    1,
                    target.hp - 30
                )

                text = (
                    f"💥 تم استهداف **{target.name}** "
                    "داخل اللعبة!"
                )
            else:
                text = "❌ لا يوجد هدف."

        elif action == "target":

            targets = [
                p for p in players
                if p.id != self.owner.id
            ]

            if targets:
                target = random.choice(targets)

                target.hp = max(
                    1,
                    target.hp - 20
                )

                text = (
                    f"🎯 تم تنفيذ حركة الهدف على "
                    f"**{target.name}**!"
                )
            else:
                text = "❌ لا يوجد هدف."

        else:

            self.owner_player = self.game.players.get(
                self.owner.id
            )

            if self.owner_player:
                self.owner_player.shield += 40

            text = (
                "🛡️ حصلت على **40 درع** داخل اللعبة!"
            )

        await interaction.response.send_message(
            text,
            ephemeral=False
        )


# =========================================================
# لوبي الألعاب
# =========================================================

class LobbyView(discord.ui.View):

    def __init__(self, cog, channel, game_type):
        super().__init__(timeout=300)

        self.cog = cog
        self.channel = channel
        self.game_type = game_type

        self.players = {}

    async def refresh(self, interaction=None):

        lines = []

        if not self.players:
            lines.append("لا يوجد لاعبين حتى الآن.")

        else:
            for p in self.players.values():

                icon = "🤖" if p.is_bot else "👤"

                lines.append(
                    f"{icon} {p.name}"
                )

        embed = discord.Embed(
            title=f"🎮 تجهيز لعبة {self.game_type}",
            description="\n".join(lines)
        )

        embed.add_field(
            name="👥 العدد",
            value=f"{len(self.players)}/{MAX_PLAYERS}"
        )

        embed.set_footer(
            text="انضم أو أضف لاعبين وهميين ثم ابدأ اللعبة."
        )

        if interaction:
            await interaction.response.edit_message(
                embed=embed,
                view=self
            )

        else:
            return embed

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

        if interaction.user.id in self.players:
            await interaction.response.send_message(
                "⚠️ أنت داخل اللعبة بالفعل.",
                ephemeral=True
            )
            return

        if len(self.players) >= MAX_PLAYERS:
            await interaction.response.send_message(
                "❌ اللعبة ممتلئة.",
                ephemeral=True
            )
            return

        member = interaction.user

        player = Player(
            id=member.id,
            name=member.display_name,
            member=member,
            is_bot=False
        )

        self.players[player.id] = player

        await self.refresh(interaction)

    @discord.ui.button(
        label="إضافة لاعب وهمي",
        emoji="🤖",
        style=discord.ButtonStyle.primary
    )
    async def add_bot(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not has_control_role(interaction.user):
            await interaction.response.send_message(
                "❌ هذا الزر للإدارة فقط.",
                ephemeral=True
            )
            return

        if len(self.players) >= MAX_PLAYERS:
            await interaction.response.send_message(
                "❌ اللعبة ممتلئة.",
                ephemeral=True
            )
            return

        used_names = {
            p.name
            for p in self.players.values()
            if p.is_bot
        }

        available = [
            name
            for name in BOT_NAMES
            if name not in used_names
        ]

        if not available:
            name = f"Bot-{len(used_names) + 1}"
        else:
            name = random.choice(available)

        fake_id = -(
            len(
                [
                    p for p in self.players.values()
                    if p.is_bot
                ]
            ) + 1
        )

        bot_player = Player(
            id=fake_id,
            name=name,
            is_bot=True
        )

        self.players[fake_id] = bot_player

        await self.refresh(interaction)

    @discord.ui.button(
        label="بدء اللعبة",
        emoji="🚀",
        style=discord.ButtonStyle.success
    )
    async def start(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not has_control_role(interaction.user):
            await interaction.response.send_message(
                "❌ الإدارة فقط تستطيع بدء اللعبة.",
                ephemeral=True
            )
            return

        if len(self.players) < MIN_PLAYERS:
            await interaction.response.send_message(
                f"❌ تحتاج على الأقل **{MIN_PLAYERS} لاعبين**.",
                ephemeral=True
            )
            return

        if GameManager.running():
            await interaction.response.send_message(
                "❌ توجد لعبة تعمل بالفعل.",
                ephemeral=True
            )
            return

        await interaction.response.defer()

        self.stop()

        game_class = self.cog.GAME_CLASSES.get(
            self.game_type
        )

        if not game_class:
            await interaction.followup.send(
                "❌ حدث خطأ: اللعبة غير موجودة."
            )
            return

        game = game_class(
            self.cog,
            self.channel,
            self.players
        )

        GameManager.active_game = game

        await game.start()

    @discord.ui.button(
        label="إلغاء",
        emoji="🛑",
        style=discord.ButtonStyle.danger
    )
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not has_control_role(interaction.user):
            await interaction.response.send_message(
                "❌ الإدارة فقط.",
                ephemeral=True
            )
            return

        self.stop()

        await interaction.response.edit_message(
            content="🛑 تم إلغاء اللوبي.",
            embed=None,
            view=None
        )


# =========================================================
# قائمة الألعاب
# =========================================================

class GameSelect(discord.ui.Select):

    def __init__(self, cog):

        self.cog = cog

        options = [
            discord.SelectOption(
                label="معركة اللاعبين",
                value="⚔️ معركة اللاعبين",
                emoji="⚔️"
            ),
            discord.SelectOption(
                label="السيطرة على المناطق",
                value="🏴 السيطرة على المناطق",
                emoji="🏴"
            ),
            discord.SelectOption(
                label="الهدف السري",
                value="🎯 الهدف السري",
                emoji="🎯"
            ),
            discord.SelectOption(
                label="ملك السيرفر",
                value="👑 ملك السيرفر",
                emoji="👑"
            ),
            discord.SelectOption(
                label="السفينة الغارقة",
                value="🚢 السفينة الغارقة",
                emoji="🚢"
            ),
            discord.SelectOption(
                label="المزاد",
                value="💰 المزاد",
                emoji="💰"
            ),
            discord.SelectOption(
                label="الخائن",
                value="🕵️ الخائن",
                emoji="🕵️"
            ),
        ]

        super().__init__(
            placeholder="🎮 اختر اللعبة...",
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
                "❌ توجد لعبة تعمل بالفعل.",
                ephemeral=True
            )
            return

        game_type = self.values[0]

        view = LobbyView(
            self.cog,
            interaction.channel,
            game_type
        )

        await interaction.response.edit_message(
            embed=await view.refresh(),
            view=view
        )


class GameSelectView(discord.ui.View):

    def __init__(self, cog):
        super().__init__(timeout=120)
        self.add_item(GameSelect(cog))


# =========================================================
# Cog
# =========================================================

class GamesCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

        self.GAME_CLASSES = {
            "⚔️ معركة اللاعبين": BattleGame,
            "🏴 السيطرة على المناطق": TerritoryGame,
            "🎯 الهدف السري": SecretTargetGame,
            "👑 ملك السيرفر": KingGame,
            "🚢 السفينة الغارقة": ShipGame,
            "💰 المزاد": AuctionGame,
            "🕵️ الخائن": TraitorGame,
        }

    # -----------------------------------------------------
    # الألعاب
    # -----------------------------------------------------

    @commands.command(name="العاب-العب")
    @is_game_channel()
    async def games_play(self, ctx):

        if not has_control_role(ctx.author):
            return

        if GameManager.running():
            await ctx.send(
                "❌ توجد لعبة تعمل حاليًا.\n"
                "انتظر انتهائها قبل بدء لعبة جديدة."
            )
            return

        embed = discord.Embed(
            title="🎮 مركز الألعاب التفاعلية",
            description=(
                "اختر اللعبة من القائمة بالأسفل.\n\n"
                "🎮 **انضمام:** للاعبين الحقيقيين\n"
                "🤖 **إضافة لاعب وهمي:** للإدارة\n"
                "🚀 **بدء اللعبة:** يبدأ الجولة\n"
                "🛑 **إلغاء:** يلغي اللوبي"
            )
        )

        embed.add_field(
            name="🎮 الألعاب",
            value="\n".join(
                f"• {name}"
                for name in self.GAME_CLASSES.keys()
            ),
            inline=False
        )

        embed.add_field(
            name="🛠️ أوامر الإدارة",
            value=(
                "`-تصفير-لاعب @شخص`\n"
                "`-نقاط-نقط @شخص`\n"
                "`-تصفير-نقاط`\n"
                "`-توب-العاب`"
            ),
            inline=False
        )

        await ctx.send(
            embed=embed,
            view=GameSelectView(self)
        )

    # -----------------------------------------------------
    # تخريب
    # -----------------------------------------------------

    @commands.command(name="تخريب")
    @is_game_channel()
    async def sabotage(self, ctx):

        game = GameManager.active_game

        if not game:
            return

        player = game.get_player(ctx.author.id)

        if not player:
            return

        embed = discord.Embed(
            title="💣 متجر التخريب",
            description=(
                "استخدم نقاطك لشراء أحداث داخل اللعبة.\n\n"
                "☢️ نووي — **10 نقاط**\n"
                "💥 انفجار — **5 نقاط**\n"
                "🎯 هدف — **3 نقاط**\n"
                "🛡️ درع — **4 نقاط**"
            )
        )

        embed.set_footer(
            text=f"رصيدك: {get_points(ctx.author.id)} نقطة"
        )

        await ctx.send(
            embed=embed,
            view=SabotageView(
                game,
                ctx.author
            )
        )

    # -----------------------------------------------------
    # محفظتي
    # -----------------------------------------------------

    @commands.command(name="محفظتي")
    @is_game_channel()
    async def wallet(self, ctx):

        points = get_points(ctx.author.id)

        embed = discord.Embed(
            title="💰 محفظتي",
            description=(
                f"👤 اللاعب: {ctx.author.mention}\n\n"
                f"⭐ نقاط الألعاب: **{points}**"
            )
        )

        await ctx.send(embed=embed)

    # -----------------------------------------------------
    # أعلى نقاط
    # -----------------------------------------------------

    @commands.command(name="اعلى-نقاط")
    @is_game_channel()
    async def top_points(self, ctx):

        data = list(
            stats_collection.find(
                {"points": {"$gt": 0}}
            ).sort(
                "points",
                -1
            ).limit(10)
        )

        if not data:
            await ctx.send(
                "📭 لا توجد نقاط مسجلة حتى الآن."
            )
            return

        lines = []

        for index, item in enumerate(data, 1):

            user_id = item["user_id"]
            points = item.get("points", 0)

            member = ctx.guild.get_member(
                user_id
            )

            name = (
                member.display_name
                if member
                else f"عضو {user_id}"
            )

            lines.append(
                f"**{index}.** {name} — ⭐ {points}"
            )

        embed = discord.Embed(
            title="🏆 أعلى نقاط الألعاب",
            description="\n".join(lines)
        )

        await ctx.send(embed=embed)

    # -----------------------------------------------------
    # تصفير لاعب
    # -----------------------------------------------------

    @commands.command(name="تصفير-لاعب")
    @is_game_channel()
    async def reset_player_command(
        self,
        ctx,
        member: discord.Member = None
    ):

        if not has_control_role(ctx.author):
            return

        if member is None:
            await ctx.send(
                "❌ الاستخدام:\n"
                "`-تصفير-لاعب @الشخص`"
            )
            return

        reset_player(member.id)

        await ctx.send(
            f"🧹 تم تصفير نقاط **{member.display_name}**."
        )

    # -----------------------------------------------------
    # إضافة نقطة
    # -----------------------------------------------------

    @commands.command(name="نقاط-نقط")
    @is_game_channel()
    async def add_one_point(
        self,
        ctx,
        member: discord.Member = None
    ):

        if not has_control_role(ctx.author):
            return

        if member is None:
            await ctx.send(
                "❌ الاستخدام:\n"
                "`-نقاط-نقط @الشخص`"
            )
            return

        add_points(member.id, 1)

        await ctx.send(
            f"⭐ تمت إضافة **1 نقطة** إلى "
            f"**{member.display_name}**."
        )

    # -----------------------------------------------------
    # تصفير جميع النقاط
    # -----------------------------------------------------

    @commands.command(name="تصفير-نقاط")
    @is_game_channel()
    async def reset_all(
        self,
        ctx
    ):

        if not has_control_role(ctx.author):
            return

        reset_all_points()

        await ctx.send(
            "🧹 تم تصفير **جميع نقاط الألعاب**."
        )

    # -----------------------------------------------------
    # توب الألعاب
    # -----------------------------------------------------

    @commands.command(name="توب-العاب")
    @is_game_channel()
    async def games_top(
        self,
        ctx
    ):

        data = list(
            stats_collection.find(
                {"points": {"$gt": 0}}
            ).sort(
                "points",
                -1
            ).limit(10)
        )

        if not data:
            await ctx.send(
                "🏆 لا توجد نتائج حتى الآن."
            )
            return

        lines = []

        for index, item in enumerate(data, 1):

            member = ctx.guild.get_member(
                item["user_id"]
            )

            if not member:
                continue

            lines.append(
                f"**{index}.** "
                f"{member.display_name} "
                f"— ⭐ {item.get('points', 0)}"
            )

        embed = discord.Embed(
            title="🏆 توب الألعاب",
            description="\n".join(lines)
        )

        await ctx.send(embed=embed)

    # -----------------------------------------------------
    # معالجة أخطاء القناة
    # -----------------------------------------------------

    @commands.Cog.listener()
    async def on_command_error(
        self,
        ctx,
        error
    ):

        if isinstance(
            error,
            commands.CheckFailure
        ):
            return


# =========================================================
# تحميل الـ Cog
# =========================================================

async def setup(bot):
    await bot.add_cog(
        GamesCog(bot)
    )
