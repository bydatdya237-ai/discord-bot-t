import os
import asyncio
import random
import time
from datetime import datetime, timezone

import discord
from discord.ext import commands
from pymongo import MongoClient


# =========================================================
# SETTINGS
# =========================================================

GAME_CHANNEL_ID = 1545143660469813250
RESET_ROLE_ID = 1554555624057086024

MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    raise RuntimeError("MONGO_URI غير موجود في Environment Variables")

mongo = MongoClient(MONGO_URI)
db = mongo["discord_bot_db"]

events_collection = db["trial_game_events"]


# =========================================================
# GAME CONSTANTS
# =========================================================

GAME_NAME = "THE TRIAL"

MAX_ROUNDS = 5

REGISTRATION_TIME = 60

MIN_PLAYERS = 2

ROUND_1_TIME = 12
ROUND_2_TIME = 15
ROUND_3_TIME = 25
ROUND_4_TIME = 45
ROUND_5_TIME = 60


# =========================================================
# HELPERS
# =========================================================

def now_timestamp():
    return int(time.time())


def utc_now():
    return datetime.now(timezone.utc)


def player_name(guild, user_id):
    member = guild.get_member(int(user_id))

    if member:
        return member.display_name

    return f"Player {user_id}"


def get_player_ids(event):
    return [str(x) for x in event.get("players", [])]


def get_score(event, user_id):
    return int(event.get("scores", {}).get(str(user_id), 0))


def set_score(event, user_id, value):
    event.setdefault("scores", {})
    event["scores"][str(user_id)] = int(value)


def add_score(event, user_id, amount):
    current = get_score(event, user_id)
    set_score(event, user_id, current + amount)


def remove_player(event, user_id):
    uid = str(user_id)

    players = get_player_ids(event)

    if uid in players:
        players.remove(uid)

    event["players"] = players


def active_players(event):
    eliminated = set(str(x) for x in event.get("eliminated", []))

    return [
        str(x)
        for x in event.get("players", [])
        if str(x) not in eliminated
    ]


def sort_players(event):
    players = get_player_ids(event)

    return sorted(
        players,
        key=lambda uid: get_score(event, uid),
        reverse=True
    )


def save_event(event):
    event["updated_at"] = utc_now()

    events_collection.replace_one(
        {"_id": event["_id"]},
        event,
        upsert=True
    )


def load_active_event(guild_id):
    return events_collection.find_one(
        {
            "guild_id": int(guild_id),
            "status": {
                "$in": [
                    "registration",
                    "round_1",
                    "round_2",
                    "round_3",
                    "round_4",
                    "round_5",
                ]
            }
        }
    )


def delete_event(guild_id):
    events_collection.delete_many(
        {
            "guild_id": int(guild_id)
        }
    )


def make_event(guild_id):
    return {
        "_id": f"trial_{guild_id}",
        "guild_id": int(guild_id),

        "status": "registration",
        "round": 0,

        "players": [],
        "eliminated": [],

        "scores": {},

        "cards": {},

        "round_results": {},

        "round_1": {},
        "round_2": {},
        "round_3": {},
        "round_4": {},
        "round_5": {},

        "created_at": utc_now(),
        "updated_at": utc_now(),
    }


# =========================================================
# MAIN COG
# =========================================================

class TrialGame(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.running_tasks = {}

    # =====================================================
    # CHANNEL CHECK
    # =====================================================

    async def cog_check(self, ctx):

        if ctx.channel.id != GAME_CHANNEL_ID:
            return False

        return True

    # =====================================================
    # EMBED
    # =====================================================

    def embed(
        self,
        title,
        description,
        color=0x9B59B6
    ):
        embed = discord.Embed(
            title=title,
            description=description,
            color=color
        )

        embed.set_footer(
            text="THE TRIAL • 5 Rounds"
        )

        return embed

    # =====================================================
    # COMMAND: توم
    # =====================================================

    @commands.command(name="توم")
    async def show_commands(self, ctx):

        embed = self.embed(
            "🎮 أوامر THE TRIAL",
            """
**بلش-1**
يبدأ فعالية THE TRIAL ويفتح التسجيل.

**توم**
يعرض أوامر اللعبة.

**تصفير**
يمسح الفعالية الحالية بالكامل ويعيد اللعبة من البداية.
هذا الأمر متاح فقط لرتبة الإدارة المحددة.

━━━━━━━━━━━━━━━━━━

### 🏆 نظام اللعبة

**الجولة 1 — ⚠️ منطقة الخطر**
اختيارات + ذاكرة + ألغاز + مخاطر.

**الجولة 2 — 🧠 الذاكرة المستحيلة**
تذكر رموز وترتيبها تحت ضغط الوقت.

**الجولة 3 — 🎲 المخاطرة**
تقرر هل تحافظ على نقاطك أو تخاطر بمضاعفتها.

**الجولة 4 — 🕵️ الخائن**
تحقيق واستنتاج وتصويت.

**الجولة 5 — ☠️ النهاية**
Final Boss يجمع السرعة والتفكير والمخاطرة.

━━━━━━━━━━━━━━━━━━

🎟️ التسجيل يتم من خلال الزر الموجود في رسالة البداية.

💾 جميع النتائج محفوظة في MongoDB.
            """
        )

        await ctx.send(embed=embed)

    # =====================================================
    # COMMAND: تصفير
    # =====================================================

    @commands.command(name="تصفير")
    async def reset_game(self, ctx):

        role = ctx.guild.get_role(RESET_ROLE_ID)

        if role is None or role not in ctx.author.roles:

            await ctx.send(
                "❌ هذا الأمر مخصص للرتبة المحددة فقط.",
                delete_after=5
            )

            return

        active = load_active_event(ctx.guild.id)

        if not active:

            await ctx.send(
                "ℹ️ لا توجد فعالية حالية لتصفيتها.",
                delete_after=5
            )

            return

        delete_event(ctx.guild.id)

        task = self.running_tasks.pop(ctx.guild.id, None)

        if task and not task.done():
            task.cancel()

        await ctx.send(
            "🧹 **تم تصفير THE TRIAL بالكامل.**\n\n"
            "يمكن الآن بدء فعالية جديدة باستخدام `بلش-1`."
        )

    # =====================================================
    # COMMAND: بلش-1
    # =====================================================

    @commands.command(name="بلش-1")
    async def start_game(self, ctx):

        active = load_active_event(ctx.guild.id)

        if active:

            await ctx.send(
                "⚠️ توجد فعالية قائمة بالفعل.\n"
                "استخدم `تصفير` لإلغائها إذا كنت تملك صلاحية التصفير.",
                delete_after=8
            )

            return

        event = make_event(ctx.guild.id)

        save_event(event)

        view = RegistrationView(
            self,
            ctx.guild.id
        )

        embed = self.embed(
            "⚔️ THE TRIAL",
            """
# 🎟️ التسجيل مفتوح

خمس جولات.

كل جولة أصعب من السابقة.

قد تكون متصدرًا في الجولة الأولى...
ثم تخسر كل شيء في الجولة الخامسة.

### القواعد

• لكل لاعب فرصة واحدة للتسجيل.
• لا يمكنك دخول اللعبة بعد بدء الجولة الأولى.
• النتائج والنقاط محفوظة.
• عدد المشاركين يؤثر على صعوبة بعض الاختبارات.

⏳ **التسجيل سيستمر لمدة دقيقة واحدة.**

👥 **المسجلون الآن: 0**

اضغط الزر بالأسفل للدخول.
            """
        )

        message = await ctx.send(
            embed=embed,
            view=view
        )

        view.message = message

        task = asyncio.create_task(
            self.registration_timer(
                ctx.guild.id,
                message
            )
        )

        self.running_tasks[ctx.guild.id] = task

    # =====================================================
    # REGISTRATION TIMER
    # =====================================================

    async def registration_timer(
        self,
        guild_id,
        message
    ):

        try:

            await asyncio.sleep(REGISTRATION_TIME)

            event = load_active_event(guild_id)

            if not event:
                return

            if event["status"] != "registration":
                return

            if len(event["players"]) < MIN_PLAYERS:

                event["status"] = "cancelled"

                save_event(event)

                await message.edit(
                    embed=self.embed(
                        "❌ تم إلغاء الفعالية",
                        "لم يصل عدد المشاركين إلى الحد الأدنى."
                    ),
                    view=None
                )

                return

            event["status"] = "starting"

            save_event(event)

            await message.edit(
                embed=self.embed(
                    "🔒 التسجيل مغلق",
                    f"""
👥 عدد المشاركين: **{len(event["players"])}**

تم إغلاق التسجيل.

استعدوا...

## الجولة الأولى قادمة.
                    """
                ),
                view=None
            )

            await asyncio.sleep(4)

            await self.round_1(guild_id, message.channel)

        except asyncio.CancelledError:
            return

        except Exception as e:
            print("Trial registration error:", repr(e))

    # =====================================================
    # ROUND 1
    # =====================================================

    async def round_1(self, guild_id, channel):

        event = load_active_event(guild_id)

        if not event:
            return

        event["status"] = "round_1"
        event["round"] = 1

        save_event(event)

        players = active_players(event)

        # -----------------------------------------------
        # PHASE 1
        # -----------------------------------------------

        await channel.send(
            embed=self.embed(
                "⚠️ الجولة الأولى — منطقة الخطر",
                f"""
عدد اللاعبين:

# {len(players)}

هذه الجولة لن تعتمد على السرعة فقط.

ستمرون بعدة اختبارات.

كل خطأ له ثمن.

**لا تثقوا بالاختيار السهل.**
                """
            )
        )

        await asyncio.sleep(5)

        # -----------------------------------------------
        # DANGER CHOICE
        # -----------------------------------------------

        danger_count = max(
            2,
            min(
                5,
                len(players) // 8 + 2
            )
        )

        safe_numbers = random.sample(
            list(range(1, 10)),
            9 - danger_count
        )

        danger_numbers = [
            x for x in range(1, 10)
            if x not in safe_numbers
        ]

        selected = {}

        for uid in players:

            view = NumberChoiceView(
                uid,
                self,
                timeout=ROUND_1_TIME
            )

            msg = await channel.send(
                f"<@{uid}> لديك **{ROUND_1_TIME} ثانية** لاختيار رقم.",
                view=view
            )

            view.message = msg

            try:
                await view.wait()
            except Exception:
                pass

            if view.choice is not None:
                selected[uid] = view.choice

            try:
                await msg.delete()
            except Exception:
                pass

        survivors = []

        for uid in players:

            choice = selected.get(uid)

            if choice in danger_numbers:

                add_score(event, uid, -25)

            else:

                survivors.append(uid)
                add_score(event, uid, 25)

        # Make sure not everyone gets removed
        if len(survivors) < 2 and len(players) >= 2:

            survivors = players[:]

            for uid in survivors:
                add_score(event, uid, 20)

        event["round_1"]["danger_numbers"] = danger_numbers
        event["round_1"]["survivors"] = survivors

        save_event(event)

        await channel.send(
            embed=self.embed(
                "⚠️ نتيجة الاختبار الأول",
                f"""
نجا:

# {len(survivors)} لاعب

لكن هذا كان مجرد البداية.

المرحلة التالية تعتمد على الذاكرة.
                """
            )
        )

        await asyncio.sleep(4)

        # -----------------------------------------------
        # MEMORY
        # -----------------------------------------------

        symbols = [
            "🍎",
            "🐺",
            "🔥",
            "💎",
            "🟣",
            "🐍",
            "👑",
            "🌙",
            "⚡",
            "🎯",
            "🦅",
            "☠️",
            "⭐",
        ]

        length = min(
            6 + len(players) // 8,
            12
        )

        sequence = random.sample(symbols, length)

        sequence_text = " ".join(sequence)

        await channel.send(
            embed=self.embed(
                "🧠 ذاكرة الخطر",
                f"""
احفظ الترتيب.

ستظهر الرموز لمدة قصيرة فقط.

# {sequence_text}

⏳ ركز...
                """
            )
        )

        await asyncio.sleep(3)

        try:

            last_message = channel.last_message

            if last_message:
                await last_message.edit(
                    embed=self.embed(
                        "🧠 اختفت الرموز",
                        """
اكتب الرموز بالترتيب.

مثال:

🍎 🐺 🔥 ...

لديك وقت محدود.
                        """
                    )
                )

        except Exception:
            pass

        memory_answers = {}

        def normalize(text):
            return " ".join(text.strip().split())

        def memory_check(message):

            if message.channel.id != channel.id:
                return False

            if message.author.id not in [
                int(x) for x in survivors
            ]:
                return False

            return True

        try:

            end_time = time.time() + 18

            while time.time() < end_time:

                remaining = end_time - time.time()

                if remaining <= 0:
                    break

                try:

                    msg = await self.bot.wait_for(
                        "message",
                        timeout=remaining,
                        check=memory_check
                    )

                except asyncio.TimeoutError:
                    break

                uid = str(msg.author.id)

                if uid in memory_answers:
                    continue

                memory_answers[uid] = normalize(msg.content)

        except Exception:
            pass

        correct = normalize(sequence_text)

        memory_survivors = []

        for uid in survivors:

            answer = memory_answers.get(uid, "")

            if answer == correct:

                memory_survivors.append(uid)

                add_score(event, uid, 75)

            else:

                add_score(event, uid, -20)

        if len(memory_survivors) < 2:

            ranked = sorted(
                survivors,
                key=lambda uid: get_score(event, uid),
                reverse=True
            )

            memory_survivors = ranked[
                :min(2, len(ranked))
            ]

        event["round_1"]["memory_survivors"] = memory_survivors

        # -----------------------------------------------
        # PUZZLE
        # -----------------------------------------------

        await channel.send(
            embed=self.embed(
                "🧩 المرحلة الأخيرة — لا تتسرع",
                """
آخر اختبار في الجولة الأولى.

أمامكم لغز.

فكر قبل أن ترسل.

من يحل بشكل صحيح يحصل على مكافأة كبيرة.
                """
            )
        )

        await asyncio.sleep(3)

        puzzles = [
            ("2، 6، 12، 20، ؟", "30"),
            ("3، 6، 12، 24، ؟", "48"),
            ("1، 4، 9، 16، ؟", "25"),
            ("5، 10، 20، 40، ؟", "80"),
            ("7، 14، 28، 56، ؟", "112"),
        ]

        puzzle, answer = random.choice(puzzles)

        await channel.send(
            embed=self.embed(
                "🧩 السؤال",
                f"""
# {puzzle}

أرسل الإجابة.

⏳ لديك **20 ثانية**.
                """
            )
        )

        def puzzle_check(message):

            return (
                message.channel.id == channel.id
                and message.author.id in [
                    int(x)
                    for x in memory_survivors
                ]
            )

        puzzle_answers = {}

        end = time.time() + 20

        while time.time() < end:

            remaining = end - time.time()

            try:

                msg = await self.bot.wait_for(
                    "message",
                    timeout=remaining,
                    check=puzzle_check
                )

            except asyncio.TimeoutError:
                break

            uid = str(msg.author.id)

            if uid not in puzzle_answers:
                puzzle_answers[uid] = msg.content.strip()

        final_r1 = []

        for uid in memory_survivors:

            if puzzle_answers.get(uid) == answer:

                add_score(event, uid, 100)

                final_r1.append(uid)

            else:

                add_score(event, uid, -35)

        # Prevent impossible wipeout
        if not final_r1:

            final_r1 = sorted(
                memory_survivors,
                key=lambda uid: get_score(event, uid),
                reverse=True
            )[:min(3, len(memory_survivors))]

        event["round_1"]["final_survivors"] = final_r1

        # Give cards
        ranked = sorted(
            final_r1,
            key=lambda uid: get_score(event, uid),
            reverse=True
        )

        cards = ["ذهبية", "فضية", "برونزية"]

        for index, uid in enumerate(ranked[:3]):

            event["cards"][uid] = cards[index]

        save_event(event)

        await channel.send(
            embed=self.embed(
                "⚠️ نهاية الجولة الأولى",
                f"""
## الناجون: {len(final_r1)}

تم منح أفضل الناجين بطاقات خاصة.

لكن لا تفرحوا...

**الجولة الثانية أصعب.**
                """
            )
        )

        await asyncio.sleep(5)

        await self.round_2(guild_id, channel)

    # =====================================================
    # ROUND 2
    # =====================================================

    async def round_2(self, guild_id, channel):

        event = load_active_event(guild_id)

        if not event:
            return

        event["status"] = "round_2"
        event["round"] = 2

        save_event(event)

        players = active_players(event)

        if not players:
            await self.finish_game(guild_id, channel)
            return

        await channel.send(
            embed=self.embed(
                "🧠 الجولة الثانية — الذاكرة المستحيلة",
                f"""
الناجون:

# {len(players)}

هذه المرة الذاكرة لن تكون بسيطة.

كل لاعب سيحصل على ترتيب مختلف.

**ركز جيدًا.**
                """
            )
        )

        await asyncio.sleep(4)

        base_symbols = [
            "🍎",
            "🐺",
            "🔥",
            "💎",
            "🟣",
            "🐍",
            "👑",
            "🌙",
            "⚡",
            "🎯",
            "🦅",
            "☠️",
            "⭐",
            "🍀",
            "🔷",
        ]

        sequences = {}

        for uid in players:

            length = min(
                7 + len(players) // 5,
                13
            )

            seq = random.sample(
                base_symbols,
                length
            )

            sequences[uid] = seq

        # Send individual sequences
        for uid in players:

            seq = sequences[uid]

            try:

                dm = await self.bot.fetch_user(
                    int(uid)
                )

                await dm.send(
                    embed=self.embed(
                        "🧠 اختبار الذاكرة",
                        f"""
احفظ هذا الترتيب:

# {" ".join(seq)}

ستحتاجه في الجولة.

لا ترسله لأحد.
                        """
                    )
                )

            except Exception:

                pass

        await channel.send(
            embed=self.embed(
                "🧠 تم إرسال الاختبارات",
                """
تم إرسال اختبار خاص لكل لاعب.

افحص رسائلك الخاصة.

إذا لم تستطع استقبال الرسائل الخاصة،
سيتم استخدام قناة اللعبة كخطة بديلة.
                """
            )
        )

        await asyncio.sleep(8)

        # Ask sequence through DM
        results = {}

        for uid in players:

            seq = sequences[uid]

            try:

                dm = await self.bot.fetch_user(
                    int(uid)
                )

                await dm.send(
                    "🧠 أرسل الرموز بالترتيب خلال 20 ثانية."
                )

                def check(message):

                    return (
                        message.author.id == int(uid)
                    )

                msg = await self.bot.wait_for(
                    "message",
                    timeout=20,
                    check=check
                )

                answer = " ".join(
                    msg.content.strip().split()
                )

                expected = " ".join(seq)

                if answer == expected:

                    results[uid] = True

                else:

                    results[uid] = False

            except Exception:

                results[uid] = False

        for uid in players:

            if results.get(uid):

                add_score(event, uid, 150)

            else:

                add_score(event, uid, -50)

        # Eliminate bottom players
        ranked = sorted(
            players,
            key=lambda uid: get_score(event, uid),
            reverse=True
        )

        keep_count = max(
            3,
            int(len(ranked) * 0.75)
        )

        keep_count = min(
            keep_count,
            len(ranked)
        )

        survivors = ranked[:keep_count]

        for uid in ranked[keep_count:]:

            if uid not in event["eliminated"]:

                event["eliminated"].append(uid)

        event["round_2"]["survivors"] = survivors

        save_event(event)

        await channel.send(
            embed=self.embed(
                "🧠 نهاية الجولة الثانية",
                f"""
تم تقليص المتنافسين.

👥 المتبقون:

# {len(survivors)}

النقاط أصبحت أهم الآن.

والجولة القادمة قد تقلب كل شيء.
                """
            )
        )

        await asyncio.sleep(5)

        await self.round_3(guild_id, channel)

    # =====================================================
    # ROUND 3
    # =====================================================

    async def round_3(self, guild_id, channel):

        event = load_active_event(guild_id)

        if not event:
            return

        event["status"] = "round_3"
        event["round"] = 3

        save_event(event)

        players = active_players(event)

        await channel.send(
            embed=self.embed(
                "🎲 الجولة الثالثة — المخاطرة",
                """
هنا لا توجد إجابة صحيحة دائمًا.

أنت تقرر.

هل تحافظ على نقاطك؟

أم تخاطر؟

## القرار لك.
                """
            )
        )

        await asyncio.sleep(4)

        for uid in players:

            view = GambleView(
                uid,
                self,
                timeout=ROUND_3_TIME
            )

            try:

                await channel.send(
                    f"<@{uid}> اختر قرارك:",
                    view=view
                )

                await view.wait()

                choice = view.choice

            except Exception:

                choice = "safe"

            current = get_score(event, uid)

            if choice == "safe":

                add_score(event, uid, 50)

            elif choice == "risk":

                roll = random.randint(
                    1,
                    100
                )

                if roll <= 40:

                    gain = max(
                        100,
                        int(current * 0.35)
                    )

                    add_score(
                        event,
                        uid,
                        gain
                    )

                else:

                    loss = max(
                        80,
                        int(current * 0.30)
                    )

                    add_score(
                        event,
                        uid,
                        -loss
                    )

            elif choice == "all":

                roll = random.randint(
                    1,
                    100
                )

                if roll <= 25:

                    gain = max(
                        250,
                        int(current * 0.75)
                    )

                    add_score(
                        event,
                        uid,
                        gain
                    )

                else:

                    add_score(
                        event,
                        uid,
                        -max(
                            150,
                            int(current * 0.60)
                        )
                    )

        ranked = sorted(
            players,
            key=lambda uid: get_score(event, uid),
            reverse=True
        )

        # Keep 60%
        keep_count = max(
            3,
            int(len(ranked) * 0.60)
        )

        keep_count = min(
            keep_count,
            len(ranked)
        )

        survivors = ranked[:keep_count]

        for uid in ranked[keep_count:]:

            if uid not in event["eliminated"]:

                event["eliminated"].append(uid)

        event["round_3"]["survivors"] = survivors

        save_event(event)

        await channel.send(
            embed=self.embed(
                "🎲 نهاية المخاطرة",
                f"""
بعض اللاعبين ضاعفوا تقدمهم.

وبعضهم خسر كل ما جمعه.

👥 المتبقون:

# {len(survivors)}

لكن الآن تبدأ الجولة الأخطر...
                """
            )
        )

        await asyncio.sleep(5)

        await self.round_4(guild_id, channel)

    # =====================================================
    # ROUND 4
    # =====================================================

    async def round_4(self, guild_id, channel):

        event = load_active_event(guild_id)

        if not event:
            return

        event["status"] = "round_4"
        event["round"] = 4

        save_event(event)

        players = active_players(event)

        if len(players) <= 3:

            await self.round_5(
                guild_id,
                channel
            )

            return

        await channel.send(
            embed=self.embed(
                "🕵️ الجولة الرابعة — الخائن",
                f"""
من بين:

# {len(players)} لاعبين

هناك خائن.

الخائن يعرف نفسه.

البقية لا يعرفون شيئًا.

ستحصلون على وقت للنقاش.

ثم سيبدأ التصويت.
                """
            )
        )

        await asyncio.sleep(5)

        traitor_count = 1

        if len(players) >= 10:
            traitor_count = 2

        traitors = random.sample(
            players,
            traitor_count
        )

        # Tell traitors privately
        for uid in traitors:

            try:

                user = await self.bot.fetch_user(
                    int(uid)
                )

                await user.send(
                    embed=self.embed(
                        "🕵️ أنت الخائن",
                        """
أنت الخائن.

لا تخبر أحدًا.

حاول أن تجعل الآخرين يصوتون ضد شخص بريء.

إذا نجحت، ستحصل على مكافأة كبيرة.
                        """,
                        color=0xE74C3C
                    )
                )

            except Exception:
                pass

        await channel.send(
            embed=self.embed(
                "🔎 التحقيق بدأ",
                """
أمامكم الآن وقت للنقاش.

حاولوا معرفة الخائن.

لا توجد معلومات مجانية.

## انتبهوا لمن يغير رأيه كثيرًا.
                """
            )
        )

        await asyncio.sleep(
            ROUND_4_TIME
        )

        # Voting
        await channel.send(
            embed=self.embed(
                "🗳️ التصويت",
                """
اكتب:

`اتهام @الشخص`

كل لاعب لديه تصويت واحد.
                """
            )
        )

        votes = {}

        def vote_check(message):

            if message.channel.id != channel.id:
                return False

            if message.author.id not in [
                int(x)
                for x in players
            ]:
                return False

            if not message.content.startswith("اتهام"):
                return False

            return True

        end = time.time() + 25

        while time.time() < end:

            try:

                msg = await self.bot.wait_for(
                    "message",
                    timeout=max(
                        1,
                        end - time.time()
                    ),
                    check=vote_check
                )

            except asyncio.TimeoutError:
                break

            voter = str(msg.author.id)

            if voter in votes:
                continue

            mentioned = msg.mentions

            if not mentioned:
                continue

            target = str(
                mentioned[0].id
            )

            if target not in players:
                continue

            if target == voter:
                continue

            votes[voter] = target

        vote_counts = {}

        for target in votes.values():

            vote_counts[target] = (
                vote_counts.get(target, 0) + 1
            )

        if vote_counts:

            accused = max(
                vote_counts,
                key=vote_counts.get
            )

        else:

            accused = random.choice(
                players
            )

        if accused in traitors:

            # Citizens win
            for uid in players:

                if uid == accused:

                    add_score(
                        event,
                        uid,
                        -200
                    )

                else:

                    add_score(
                        event,
                        uid,
                        120
                    )

            result_text = (
                f"🎯 تم اكتشاف الخائن: <@{accused}>"
            )

            event["round_4"]["citizens_win"] = True

        else:

            # Traitors win
            for uid in players:

                if uid in traitors:

                    add_score(
                        event,
                        uid,
                        300
                    )

                else:

                    add_score(
                        event,
                        uid,
                        -80
                    )

            result_text = (
                "💀 الخائن نجا.\n"
                f"تم اتهام <@{accused}> بالخطأ."
            )

            event["round_4"]["citizens_win"] = False

        event["round_4"]["traitors"] = traitors
        event["round_4"]["accused"] = accused

        ranked = sorted(
            players,
            key=lambda uid: get_score(event, uid),
            reverse=True
        )

        keep_count = min(
            5,
            len(ranked)
        )

        survivors = ranked[:keep_count]

        for uid in ranked[keep_count:]:

            if uid not in event["eliminated"]:

                event["eliminated"].append(uid)

        event["round_4"]["survivors"] = survivors

        save_event(event)

        await channel.send(
            embed=self.embed(
                "🕵️ نهاية الجولة الرابعة",
                f"""
{result_text}

## المتأهلون للنهائي:

{len(survivors)}

☠️ الآن لا توجد جولة سهلة.
                """
            )
        )

        await asyncio.sleep(6)

        await self.round_5(
            guild_id,
            channel
        )

    # =====================================================
    # ROUND 5
    # =====================================================

    async def round_5(self, guild_id, channel):

        event = load_active_event(guild_id)

        if not event:
            return

        event["status"] = "round_5"
        event["round"] = 5

        save_event(event)

        players = active_players(event)

        if not players:

            await self.finish_game(
                guild_id,
                channel
            )

            return

        await channel.send(
            embed=self.embed(
                "☠️ الجولة الخامسة — FINAL BOSS",
                f"""
# FINAL 5

المتأهلون:

{len(players)}

كل ما حدث قبل هذه اللحظة مهم.

لكن لا أحد يضمن الفوز.

## ثلاث مراحل.

من ينهار أولًا... يخرج.
                """
            )
        )

        await asyncio.sleep(5)

        # -----------------------------------------------
        # FINAL PHASE 1
        # -----------------------------------------------

        await channel.send(
            embed=self.embed(
                "☠️ المرحلة الأولى",
                """
السؤال:

`4، 9، 16، 25، 36، ؟`

لديكم **15 ثانية**.

الإجابة:
49
                """
            )
        )

        answers = {}

        def final_check(message):

            return (
                message.channel.id == channel.id
                and message.author.id in [
                    int(x)
                    for x in players
                ]
            )

        end = time.time() + 15

        while time.time() < end:

            try:

                msg = await self.bot.wait_for(
                    "message",
                    timeout=max(
                        1,
                        end - time.time()
                    ),
                    check=final_check
                )

            except asyncio.TimeoutError:
                break

            uid = str(msg.author.id)

            if uid not in answers:
                answers[uid] = msg.content.strip()

        for uid in players:

            if answers.get(uid) == "49":

                add_score(
                    event,
                    uid,
                    200
                )

            else:

                add_score(
                    event,
                    uid,
                    -100
                )

        save_event(event)

        # -----------------------------------------------
        # FINAL PHASE 2
        # -----------------------------------------------

        await channel.send(
            embed=self.embed(
                "⚡ المرحلة الثانية",
                """
سيظهر رقم.

لديك خياران:

🛡️ آمن
🎲 مخاطرة

لكن هذه المرة...

المخاطرة قد تضاعف **كل نقاطك**.

أمامك 20 ثانية.
                """
            )
        )

        final_decisions = {}

        for uid in players:

            view = FinalChoiceView(
                uid,
                self,
                timeout=20
            )

            msg = await channel.send(
                f"<@{uid}> اختر:",
                view=view
            )

            await view.wait()

            final_decisions[uid] = (
                view.choice or "safe"
            )

        for uid, choice in final_decisions.items():

            current = get_score(
                event,
                uid
            )

            if choice == "safe":

                add_score(
                    event,
                    uid,
                    100
                )

            else:

                if random.randint(
                    1,
                    100
                ) <= 45:

                    set_score(
                        event,
                        uid,
                        max(
                            0,
                            current * 2
                        )
                    )

                else:

                    set_score(
                        event,
                        uid,
                        max(
                            0,
                            current // 2
                        )
                    )

        save_event(event)

        # -----------------------------------------------
        # FINAL PHASE 3
        # -----------------------------------------------

        ranked = sorted(
            players,
            key=lambda uid: get_score(event, uid),
            reverse=True
        )

        await channel.send(
            embed=self.embed(
                "☠️ المرحلة الأخيرة",
                """
آخر اختبار.

الآن السرعة مهمة.

لكن التفكير أهم.

لديك 20 ثانية.

أكمل السلسلة:

`1 - 1 - 2 - 3 - 5 - 8 - ?`

أرسل الرقم.
                """
            )
        )

        final_answers = {}

        end = time.time() + 20

        while time.time() < end:

            try:

                msg = await self.bot.wait_for(
                    "message",
                    timeout=max(
                        1,
                        end - time.time()
                    ),
                    check=final_check
                )

            except asyncio.TimeoutError:
                break

            uid = str(msg.author.id)

            if uid not in final_answers:

                final_answers[uid] = (
                    msg.content.strip()
                )

        for uid in players:

            if final_answers.get(uid) == "13":

                add_score(
                    event,
                    uid,
                    500
                )

            else:

                add_score(
                    event,
                    uid,
                    -200
                )

        save_event(event)

        await asyncio.sleep(3)

        await self.finish_game(
            guild_id,
            channel
        )

    # =====================================================
    # FINISH
    # =====================================================

    async def finish_game(
        self,
        guild_id,
        channel
    ):

        event = events_collection.find_one(
            {
                "_id": f"trial_{guild_id}"
            }
        )

        if not event:
            return

        event["status"] = "finished"

        event["round"] = 5

        save_event(event)

        players = get_player_ids(event)

        ranked = sorted(
            players,
            key=lambda uid: get_score(event, uid),
            reverse=True
        )

        if not ranked:

            await channel.send(
                "❌ لم يوجد فائز."
            )

            return

        winner = ranked[0]

        event["winner"] = winner

        save_event(event)

        lines = []

        medals = [
            "🥇",
            "🥈",
            "🥉",
            "4️⃣",
            "5️⃣",
            "6️⃣",
            "7️⃣",
            "8️⃣",
            "9️⃣",
            "🔟",
        ]

        for index, uid in enumerate(
            ranked[:10]
        ):

            medal = (
                medals[index]
                if index < len(medals)
                else f"#{index + 1}"
            )

            lines.append(
                f"{medal} <@{uid}> — "
                f"**{get_score(event, uid)} نقطة**"
            )

        await channel.send(
            embed=self.embed(
                "🏆 THE TRIAL — انتهت الفعالية",
                f"""
# 👑 البطل

<@{winner}>

**{get_score(event, winner)} نقطة**

━━━━━━━━━━━━━━━━━━

## 📊 الترتيب النهائي

{chr(10).join(lines)}

━━━━━━━━━━━━━━━━━━

👥 عدد المشاركين:
**{len(players)}**

⚔️ عدد الجولات:
**5**

لقد انتهت المحاكمة.
                """,
                color=0xF1C40F
            )
        )


# =========================================================
# REGISTRATION VIEW
# =========================================================

class RegistrationView(discord.ui.View):

    def __init__(
        self,
        cog,
        guild_id
    ):

        super().__init__(
            timeout=REGISTRATION_TIME + 5
        )

        self.cog = cog
        self.guild_id = guild_id
        self.message = None

    @discord.ui.button(
        label="🎟️ تسجيل",
        style=discord.ButtonStyle.success,
        custom_id="trial_register"
    )
    async def register(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if interaction.channel.id != GAME_CHANNEL_ID:

            await interaction.response.send_message(
                "❌ هذه اللعبة لها روم محدد.",
                ephemeral=True
            )

            return

        event = load_active_event(
            self.guild_id
        )

        if not event:

            await interaction.response.send_message(
                "❌ لا توجد فعالية حاليًا.",
                ephemeral=True
            )

            return

        if event["status"] != "registration":

            await interaction.response.send_message(
                "🔒 التسجيل مغلق.",
                ephemeral=True
            )

            return

        uid = str(
            interaction.user.id
        )

        if uid in get_player_ids(event):

            await interaction.response.send_message(
                "⚠️ أنت مسجل بالفعل.",
                ephemeral=True
            )

            return

        event["players"].append(uid)

        event["scores"][uid] = 0

        save_event(event)

        await interaction.response.send_message(
            "✅ تم تسجيلك في THE TRIAL.",
            ephemeral=True
        )

        if self.message:

            try:

                embed = self.cog.embed(
                    "⚔️ THE TRIAL",
                    f"""
# 🎟️ التسجيل مفتوح

خمس جولات.

كل جولة أصعب من السابقة.

👥 **المسجلون الآن: {len(event["players"])}**

⏳ التسجيل مستمر...
                    """
                )

                await self.message.edit(
                    embed=embed,
                    view=self
                )

            except Exception:
                pass


# =========================================================
# NUMBER CHOICE
# =========================================================

class NumberChoiceView(discord.ui.View):

    def __init__(
        self,
        user_id,
        cog,
        timeout
    ):

        super().__init__(
            timeout=timeout
        )

        self.user_id = int(user_id)
        self.cog = cog
        self.choice = None

        for number in range(1, 10):

            self.add_item(
                NumberButton(
                    number,
                    self.user_id,
                    self
                )
            )


class NumberButton(
    discord.ui.Button
):

    def __init__(
        self,
        number,
        user_id,
        parent_view
    ):

        super().__init__(
            label=str(number),
            style=discord.ButtonStyle.secondary
        )

        self.number = number
        self.user_id = user_id
        self.parent_view = parent_view

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        if interaction.user.id != self.user_id:

            await interaction.response.send_message(
                "❌ هذا الاختيار ليس لك.",
                ephemeral=True
            )

            return

        self.parent_view.choice = self.number

        await interaction.response.send_message(
            f"تم اختيار الرقم **{self.number}**.",
            ephemeral=True
        )

        self.parent_view.stop()


# =========================================================
# GAMBLE VIEW
# =========================================================

class GambleView(discord.ui.View):

    def __init__(
        self,
        user_id,
        cog,
        timeout
    ):

        super().__init__(
            timeout=timeout
        )

        self.user_id = int(user_id)
        self.cog = cog
        self.choice = None

    async def choose(
        self,
        interaction,
        choice
    ):

        if interaction.user.id != self.user_id:

            await interaction.response.send_message(
                "❌ هذا القرار ليس لك.",
                ephemeral=True
            )

            return

        self.choice = choice

        await interaction.response.send_message(
            "🎲 تم تسجيل قرارك.",
            ephemeral=True
        )

        self.stop()

    @discord.ui.button(
        label="🛡️ آمن +50",
        style=discord.ButtonStyle.success
    )
    async def safe(
        self,
        interaction,
        button
    ):

        await self.choose(
            interaction,
            "safe"
        )

    @discord.ui.button(
        label="🎲 مخاطرة",
        style=discord.ButtonStyle.primary
    )
    async def risk(
        self,
        interaction,
        button
    ):

        await self.choose(
            interaction,
            "risk"
        )

    @discord.ui.button(
        label="☠️ كل شيء",
        style=discord.ButtonStyle.danger
    )
    async def all_in(
        self,
        interaction,
        button
    ):

        await self.choose(
            interaction,
            "all"
        )


# =========================================================
# FINAL CHOICE
# =========================================================

class FinalChoiceView(discord.ui.View):

    def __init__(
        self,
        user_id,
        cog,
        timeout
    ):

        super().__init__(
            timeout=timeout
        )

        self.user_id = int(user_id)
        self.cog = cog
        self.choice = None

    async def choose(
        self,
        interaction,
        choice
    ):

        if interaction.user.id != self.user_id:

            await interaction.response.send_message(
                "❌ هذا القرار ليس لك.",
                ephemeral=True
            )

            return

        self.choice = choice

        await interaction.response.send_message(
            "⚔️ تم تسجيل قرارك.",
            ephemeral=True
        )

        self.stop()

    @discord.ui.button(
        label="🛡️ آمن",
        style=discord.ButtonStyle.success
    )
    async def safe(
        self,
        interaction,
        button
    ):

        await self.choose(
            interaction,
            "safe"
        )

    @discord.ui.button(
        label="☠️ مخاطرة ×2",
        style=discord.ButtonStyle.danger
    )
    async def risk(
        self,
        interaction,
        button
    ):

        await self.choose(
            interaction,
            "risk"
        )


# =========================================================
# SETUP
# =========================================================

async def setup(bot):

    await bot.add_cog(
        TrialGame(bot)
    )
