import asyncio
import io
import math
import random
import re
from datetime import datetime

import aiohttp
import discord
from discord.ext import commands

from PIL import Image, ImageDraw, ImageFont


# =========================================================
# الإعدادات
# =========================================================

GAME_CHANNEL_ID = 1550797517237518417
ADMIN_ROLE_ID = 1544078469657530578

COMMAND_PREFIX = "-"
COMMAND_NAME = "خمن-الدولة"

TOTAL_ROUNDS = 10
ROUND_SECONDS = 15

MAX_IMAGE_SIZE = 7_500_000

# خريطة العالم GeoJSON
WORLD_MAP_URL = (
    "https://raw.githubusercontent.com/datasets/geo-countries/"
    "master/data/countries.geojson"
)

# Wikimedia Commons
COMMONS_API = "https://commons.wikimedia.org/w/api.php"

# صورة افتراضية عند تعذر تحميل صورة الحساب
DEFAULT_AVATAR = (
    "https://cdn.discordapp.com/embed/avatars/0.png"
)


# =========================================================
# الدول الأساسية
# الاسم العربي + الإنجليزي + الإحداثيات التقريبية
# =========================================================

COUNTRIES = {
    "الأردن": ("Jordan", 31.24, 36.51),
    "السعودية": ("Saudi Arabia", 23.89, 45.08),
    "الإمارات": ("United Arab Emirates", 24.40, 54.30),
    "قطر": ("Qatar", 25.35, 51.18),
    "الكويت": ("Kuwait", 29.31, 47.48),
    "البحرين": ("Bahrain", 26.07, 50.55),
    "عمان": ("Oman", 20.50, 56.00),
    "اليمن": ("Yemen", 15.55, 47.60),
    "العراق": ("Iraq", 33.22, 43.68),
    "سوريا": ("Syria", 35.00, 38.00),
    "لبنان": ("Lebanon", 33.85, 35.86),
    "فلسطين": ("Palestine", 31.95, 35.23),
    "مصر": ("Egypt", 26.82, 30.80),
    "ليبيا": ("Libya", 26.33, 17.23),
    "تونس": ("Tunisia", 33.88, 9.54),
    "الجزائر": ("Algeria", 28.03, 1.66),
    "المغرب": ("Morocco", 31.79, -7.09),
    "السودان": ("Sudan", 15.50, 30.00),
    "الصومال": ("Somalia", 5.15, 46.20),
    "جيبوتي": ("Djibouti", 11.83, 42.59),
    "إثيوبيا": ("Ethiopia", 9.15, 40.49),
    "كينيا": ("Kenya", 0.02, 37.91),
    "تنزانيا": ("Tanzania", -6.37, 34.89),
    "أوغندا": ("Uganda", 1.37, 32.29),
    "نيجيريا": ("Nigeria", 9.08, 8.67),
    "غانا": ("Ghana", 7.95, -1.02),
    "جنوب أفريقيا": ("South Africa", -30.56, 22.94),
    "السنغال": ("Senegal", 14.50, -14.45),
    "الكاميرون": ("Cameroon", 7.37, 12.35),
    "الكونغو": ("Republic of the Congo", -0.23, 15.83),
    "أنغولا": ("Angola", -11.20, 17.87),

    "فرنسا": ("France", 46.23, 2.21),
    "ألمانيا": ("Germany", 51.16, 10.45),
    "إيطاليا": ("Italy", 41.87, 12.57),
    "إسبانيا": ("Spain", 40.46, -3.75),
    "البرتغال": ("Portugal", 39.40, -8.22),
    "بريطانيا": ("United Kingdom", 55.38, -3.44),
    "المملكة المتحدة": ("United Kingdom", 55.38, -3.44),
    "هولندا": ("Netherlands", 52.13, 5.29),
    "بلجيكا": ("Belgium", 50.50, 4.47),
    "سويسرا": ("Switzerland", 46.82, 8.23),
    "النمسا": ("Austria", 47.52, 14.55),
    "اليونان": ("Greece", 39.07, 21.82),
    "تركيا": ("Turkey", 38.96, 35.24),
    "النرويج": ("Norway", 60.47, 8.47),
    "السويد": ("Sweden", 60.13, 18.64),
    "فنلندا": ("Finland", 61.92, 25.75),
    "الدنمارك": ("Denmark", 56.26, 9.50),
    "بولندا": ("Poland", 51.92, 19.15),
    "التشيك": ("Czechia", 49.82, 15.47),
    "رومانيا": ("Romania", 45.94, 24.97),
    "بلغاريا": ("Bulgaria", 42.73, 25.49),
    "أوكرانيا": ("Ukraine", 48.38, 31.17),
    "روسيا": ("Russia", 61.52, 105.32),
    "آيسلندا": ("Iceland", 64.96, -19.02),
    "أيرلندا": ("Ireland", 53.14, -7.69),

    "الولايات المتحدة": ("United States", 37.09, -95.71),
    "أمريكا": ("United States", 37.09, -95.71),
    "كندا": ("Canada", 56.13, -106.35),
    "المكسيك": ("Mexico", 23.63, -102.55),
    "البرازيل": ("Brazil", -14.24, -51.93),
    "الأرجنتين": ("Argentina", -38.42, -63.62),
    "تشيلي": ("Chile", -35.68, -71.54),
    "بيرو": ("Peru", -9.19, -75.02),
    "كولومبيا": ("Colombia", 4.57, -74.30),
    "فنزويلا": ("Venezuela", 6.42, -66.59),
    "بوليفيا": ("Bolivia", -16.29, -63.59),
    "الإكوادور": ("Ecuador", -1.83, -78.18),
    "أوروغواي": ("Uruguay", -32.52, -55.77),
    "باراغواي": ("Paraguay", -23.44, -58.44),
    "كوستاريكا": ("Costa Rica", 9.75, -83.75),
    "بنما": ("Panama", 8.54, -80.78),

    "الصين": ("China", 35.86, 104.20),
    "اليابان": ("Japan", 36.20, 138.25),
    "كوريا الجنوبية": ("South Korea", 35.91, 127.77),
    "كوريا الشمالية": ("North Korea", 40.34, 127.51),
    "الهند": ("India", 20.59, 78.96),
    "باكستان": ("Pakistan", 30.38, 69.35),
    "أفغانستان": ("Afghanistan", 33.94, 67.71),
    "إيران": ("Iran", 32.43, 53.69),
    "العراق": ("Iraq", 33.22, 43.68),
    "بنغلاديش": ("Bangladesh", 23.68, 90.36),
    "نيبال": ("Nepal", 28.39, 84.12),
    "سريلانكا": ("Sri Lanka", 7.87, 80.77),
    "تايلاند": ("Thailand", 15.87, 100.99),
    "فيتنام": ("Vietnam", 14.06, 108.28),
    "الفلبين": ("Philippines", 12.88, 121.77),
    "إندونيسيا": ("Indonesia", -0.79, 113.92),
    "ماليزيا": ("Malaysia", 4.21, 101.98),
    "سنغافورة": ("Singapore", 1.35, 103.82),
    "منغوليا": ("Mongolia", 46.86, 103.85),

    "أستراليا": ("Australia", -25.27, 133.78),
    "نيوزيلندا": ("New Zealand", -40.90, 174.89),
    "فيجي": ("Fiji", -17.71, 178.07),
}


# =========================================================
# أسماء بديلة
# =========================================================

ALIASES = {
    "السعوديه": "السعودية",
    "الامارات": "الإمارات",
    "الامارات العربيه المتحده": "الإمارات",
    "سلطنه عمان": "عمان",
    "مصر": "مصر",
    "امريكا": "الولايات المتحدة",
    "الولايات المتحده": "الولايات المتحدة",
    "امريكا": "الولايات المتحدة",
    "انجلترا": "بريطانيا",
    "انجلترا": "بريطانيا",
    "بريطانيا العظمى": "بريطانيا",
    "روسيا الاتحاديه": "روسيا",
    "اليابان": "اليابان",
    "كوريا": "كوريا الجنوبية",
    "كوريا الجنوبيه": "كوريا الجنوبية",
    "جنوب افريقيا": "جنوب أفريقيا",
    "سوريا": "سوريا",
    "لبنان": "لبنان",
    "فلسطين": "فلسطين",
}


# =========================================================
# النقاط
# =========================================================

POINTS_TABLE = [10, 8, 6, 4, 2, 1]


# =========================================================
# أدوات عامة
# =========================================================

def normalize(text: str) -> str:
    text = text.strip().lower()

    replacements = {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ى": "ي",
        "ة": "ه",
        "ؤ": "و",
        "ئ": "ي",
    }

    for a, b in replacements.items():
        text = text.replace(a, b)

    text = re.sub(r"[\u064B-\u065F\u0670]", "", text)
    text = re.sub(r"[^a-z0-9\u0600-\u06FF\s]", "", text)
    text = re.sub(r"\s+", " ", text)

    return text


def canonical_country(text: str):
    value = normalize(text)

    for country in COUNTRIES:
        if normalize(country) == value:
            return country

    for alias, country in ALIASES.items():
        if normalize(alias) == value:
            return country

    # إن كتب اللاعب الاسم الإنجليزي
    for arabic, data in COUNTRIES.items():
        english = data[0]

        if normalize(english) == value:
            return arabic

    return None


def haversine(lat1, lon1, lat2, lon2):
    radius = 6371.0

    p1 = math.radians(lat1)
    p2 = math.radians(lat2)

    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)

    a = (
        math.sin(dp / 2) ** 2
        + math.cos(p1)
        * math.cos(p2)
        * math.sin(dl / 2) ** 2
    )

    return radius * 2 * math.asin(math.sqrt(a))


def format_distance(distance):
    if distance < 1000:
        return f"{distance:,.0f} كم"

    return f"{distance:,.0f} كم"


# =========================================================
# اللعبة
# =========================================================

class GuessCountryGame:

    def __init__(self, cog, channel):
        self.cog = cog
        self.channel = channel

        self.running = True
        self.round = 0

        self.current_country = None
        self.current_image = None

        self.round_active = False

        # player_id -> data
        self.players = {}

        self.used_countries = set()

        self.fake_counter = 0

    # -----------------------------------------------------
    # إضافة لاعب حقيقي
    # -----------------------------------------------------

    def add_player(self, member):

        if member.id in self.players:
            return False

        self.players[member.id] = {
            "member": member,
            "name": member.display_name,
            "mention": member.mention,
            "avatar": str(member.display_avatar.url),
            "is_fake": False,
            "guess": None,
            "distance": None,
            "round_points": 0,
            "total_points": 0,
        }

        return True

    # -----------------------------------------------------
    # إضافة لاعب وهمي
    # -----------------------------------------------------

    def add_fake_player(self):

        self.fake_counter += 1

        fake_id = f"fake_{self.fake_counter}"

        names = [
            "Player AI",
            "GeoBot",
            "المتخمين",
            "Player X",
            "اللاعب الوهمي",
            "GuessBot",
        ]

        name = random.choice(names)

        # حتى لا تتكرر الأسماء كثيرًا
        name = f"{name} {self.fake_counter}"

        self.players[fake_id] = {
            "member": None,
            "name": name,
            "mention": name,
            "avatar": DEFAULT_AVATAR,
            "is_fake": True,
            "guess": None,
            "distance": None,
            "round_points": 0,
            "total_points": 0,
        }

        # إذا كانت الجولة بدأت بالفعل
        if self.round_active and self.current_country:

            self.make_fake_guess(self.players[fake_id])

        return fake_id

    # -----------------------------------------------------
    # تخمين اللاعب الوهمي
    # -----------------------------------------------------

    def make_fake_guess(self, player):

        countries = list(COUNTRIES.keys())

        # نحاول ألا يختار الإجابة الصحيحة دائمًا
        choices = [
            country
            for country in countries
            if country != self.current_country
        ]

        if not choices:
            choices = countries

        guess = random.choice(choices)

        player["guess"] = guess

        target = COUNTRIES[self.current_country]
        guessed = COUNTRIES[guess]

        player["distance"] = haversine(
            target[1],
            target[2],
            guessed[1],
            guessed[2],
        )

    # -----------------------------------------------------
    # بداية الجولة
    # -----------------------------------------------------

    async def start_round(self):

        if not self.running:
            return

        self.round += 1

        if self.round > TOTAL_ROUNDS:
            await self.finish_game()
            return

        self.round_active = True

        # اختيار دولة جديدة
        available = [
            country
            for country in COUNTRIES
            if country not in self.used_countries
        ]

        if not available:
            self.used_countries.clear()
            available = list(COUNTRIES.keys())

        self.current_country = random.choice(available)
        self.used_countries.add(self.current_country)

        # تحميل صورة الدولة
        image_data = await self.cog.get_country_image(
            COUNTRIES[self.current_country][0]
        )

        if not image_data:
            self.round_active = False

            await self.channel.send(
                "⚠️ تعذر الحصول على صورة لهذه الجولة، "
                "سأحاول دولة أخرى."
            )

            # لا نستهلك الجولة
            self.round -= 1

            await asyncio.sleep(2)

            if self.running:
                await self.start_round()

            return

        self.current_image = image_data

        # تصفير تخمينات الجولة
        for player in self.players.values():
            player["guess"] = None
            player["distance"] = None
            player["round_points"] = 0

            if player["is_fake"]:
                self.make_fake_guess(player)

        filename = image_data["filename"]

        embed = discord.Embed(
            title="🌍 خمن الدولة",
            description=(
                f"**الجولة {self.round}/{TOTAL_ROUNDS}**\n\n"
                "🖼️ انظر إلى الصورة وخمّن الدولة.\n"
                f"⏱️ لديك **{ROUND_SECONDS} ثانية**.\n\n"
                "اكتب اسم الدولة فقط."
            ),
            color=discord.Color.blurple(),
            timestamp=datetime.utcnow(),
        )

        embed.set_image(url=f"attachment://{filename}")

        file = discord.File(
            io.BytesIO(image_data["bytes"]),
            filename=filename,
        )

        await self.channel.send(
            embed=embed,
            file=file,
        )

        # عداد الوقت
        await asyncio.sleep(ROUND_SECONDS)

        if not self.running:
            return

        if not self.round_active:
            return

        await self.finish_round()

    # -----------------------------------------------------
    # انتهاء الجولة
    # -----------------------------------------------------

    async def finish_round(self):

        if not self.running:
            return

        if not self.round_active:
            return

        self.round_active = False

        # جمع اللاعبين الذين خمنوا
        guessed_players = [
            player
            for player in self.players.values()
            if player["guess"] is not None
            and player["distance"] is not None
        ]

        # ترتيب حسب المسافة
        guessed_players.sort(
            key=lambda p: p["distance"]
        )

        # إعطاء النقاط
        for index, player in enumerate(guessed_players):

            if index < len(POINTS_TABLE):
                points = POINTS_TABLE[index]
            else:
                points = 1

            player["round_points"] = points
            player["total_points"] += points

        # اللاعبين الذين لم يخمنوا
        for player in self.players.values():

            if player["guess"] is None:
                player["round_points"] = 0

        # إنشاء خريطة النتائج
        map_bytes = await self.cog.create_result_map(
            self
        )

        correct_arabic = self.current_country

        correct_data = COUNTRIES[
            correct_arabic
        ]

        embed = discord.Embed(
            title=f"🗺️ نتيجة الجولة {self.round}",
            description=(
                f"🎯 **الإجابة الصحيحة:** "
                f"🇺🇳 **{correct_arabic}**\n\n"
                "📍 المسافة محسوبة بين مركز الدولة التي "
                "اختارها اللاعب ومركز الدولة الصحيحة."
            ),
            color=discord.Color.green(),
        )

        filename = f"result_{self.round}.png"

        embed.set_image(
            url=f"attachment://{filename}"
        )

        file = discord.File(
            io.BytesIO(map_bytes),
            filename=filename,
        )

        # -------------------------------------------------
        # تفاصيل اللاعبين
        # -------------------------------------------------

        lines = []

        sorted_players = sorted(
            self.players.values(),
            key=lambda p: p["total_points"],
            reverse=True,
        )

        for player in sorted_players:

            name = player["name"]

            if player["guess"]:

                distance = format_distance(
                    player["distance"]
                )

                lines.append(
                    f"**{name}** — "
                    f"{player['guess']} "
                    f"→ {distance} "
                    f"— **+{player['round_points']}** "
                    f"({player['total_points']} نقطة)"
                )

            else:

                lines.append(
                    f"**{name}** — ❌ لم يخمّن "
                    f"— **{player['total_points']} نقطة**"
                )

        if lines:

            text = "\n".join(lines)

            if len(text) > 3900:
                text = text[:3890] + "\n..."

            embed.add_field(
                name="📊 نتائج اللاعبين",
                value=text,
                inline=False,
            )

        embed.add_field(
            name="📌 ملاحظة",
            value=(
                "الدائرة الموجودة على الخريطة تمثل "
                "الدولة التي اختارها اللاعب، والخط يوضح "
                "المسافة إلى الإجابة الصحيحة."
            ),
            inline=False,
        )

        await self.channel.send(
            embed=embed,
            file=file,
        )

        # الجولة الأخيرة
        if self.round >= TOTAL_ROUNDS:

            await asyncio.sleep(3)

            await self.finish_game()

            return

        # الجولة التالية
        await asyncio.sleep(4)

        if self.running:
            await self.start_round()

    # -----------------------------------------------------
    # إنهاء اللعبة
    # -----------------------------------------------------

    async def finish_game(self):

        if not self.running:
            return

        self.running = False
        self.round_active = False

        players = sorted(
            self.players.values(),
            key=lambda p: p["total_points"],
            reverse=True,
        )

        embed = discord.Embed(
            title="🏆 انتهت لعبة خمن الدولة!",
            description=(
                f"تم الانتهاء من **{TOTAL_ROUNDS} جولات**.\n\n"
                "🏆 **الترتيب النهائي:**"
            ),
            color=discord.Color.gold(),
        )

        if players:

            lines = []

            medals = ["🥇", "🥈", "🥉"]

            for index, player in enumerate(players):

                medal = (
                    medals[index]
                    if index < 3
                    else f"**{index + 1}.**"
                )

                lines.append(
                    f"{medal} **{player['name']}** — "
                    f"**{player['total_points']} نقطة**"
                )

            text = "\n".join(lines)

            if len(text) > 3900:
                text = text[:3890] + "\n..."

            embed.add_field(
                name="📊 النتائج",
                value=text,
                inline=False,
            )

            winner = players[0]

            embed.add_field(
                name="👑 الفائز",
                value=(
                    f"**{winner['name']}**\n"
                    f"حقق **{winner['total_points']} نقطة**."
                ),
                inline=False,
            )

        await self.channel.send(embed=embed)

        self.cog.games.pop(
            self.channel.id,
            None,
        )


# =========================================================
# زر إضافة لاعب وهمي
# =========================================================

class GuessCountryView(discord.ui.View):

    def __init__(self, game):
        super().__init__(timeout=None)

        self.game = game

    @discord.ui.button(
        label="إضافة لاعب وهمي",
        emoji="🤖",
        style=discord.ButtonStyle.secondary,
    )
    async def add_fake(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        if not self.game.running:

            await interaction.response.send_message(
                "❌ انتهت اللعبة.",
                ephemeral=True,
            )

            return

        self.game.add_fake_player()

        count = len(self.game.players)

        await interaction.response.send_message(
            f"🤖 تم إضافة لاعب وهمي.\n"
            f"👥 عدد اللاعبين الآن: **{count}**",
            ephemeral=True,
        )


# =========================================================
# Cog
# =========================================================

class GuessCountry(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        self.games = {}

        self.session = None

        self.world_geojson = None

    # -----------------------------------------------------
    # Session
    # -----------------------------------------------------

    async def get_session(self):

        if self.session is None or self.session.closed:

            timeout = aiohttp.ClientTimeout(
                total=20,
                connect=7,
            )

            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers={
                    "User-Agent": (
                        "Discord Guess Country Bot/1.0 "
                        "(educational game)"
                    )
                },
            )

        return self.session

    # -----------------------------------------------------
    # HTTP JSON
    # -----------------------------------------------------

    async def get_json(self, url, params=None):

        try:

            session = await self.get_session()

            async with session.get(
                url,
                params=params,
            ) as response:

                if response.status != 200:
                    return None

                return await response.json(
                    content_type=None
                )

        except Exception as e:

            print(
                f"[GuessCountry] JSON error: {e}"
            )

            return None

    # -----------------------------------------------------
    # تحميل صورة
    # -----------------------------------------------------

    async def download_image(self, url):

        try:

            session = await self.get_session()

            async with session.get(url) as response:

                if response.status != 200:
                    return None

                content = await response.content.read(
                    MAX_IMAGE_SIZE + 1
                )

                if len(content) > MAX_IMAGE_SIZE:
                    return None

                if len(content) < 10_000:
                    return None

                return content

        except Exception as e:

            print(
                f"[GuessCountry] image error: {e}"
            )

            return None

    # -----------------------------------------------------
    # البحث عن صورة دولة
    # -----------------------------------------------------

    async def get_country_image(self, country_name):

        queries = [
            f"{country_name} landmark",
            f"{country_name} city",
            f"{country_name} street",
            f"{country_name} travel",
            country_name,
        ]

        random.shuffle(queries)

        # نستخدم عدة محاولات
        for query in queries:

            params = {
                "action": "query",
                "format": "json",
                "formatversion": "2",
                "list": "search",
                "srsearch": query,
                "srnamespace": 6,
                "srlimit": 20,
            }

            data = await self.get_json(
                COMMONS_API,
                params,
            )

            if not data:
                continue

            results = data.get(
                "query",
                {}
            ).get(
                "search",
                []
            )

            if not results:
                continue

            random.shuffle(results)

            # نستبعد الصور الواضحة أنها أعلام/خرائط
            bad_words = [
                "flag",
                "map",
                "coat of arms",
                "outline",
                "location map",
                "blank map",
            ]

            candidates = []

            for item in results:

                title = item.get(
                    "title",
                    ""
                )

                low = title.lower()

                if any(
                    word in low
                    for word in bad_words
                ):
                    continue

                candidates.append(item)

            if not candidates:
                candidates = results

            candidates = candidates[:10]

            pageids = "|".join(
                str(item["pageid"])
                for item in candidates
                if item.get("pageid")
            )

            if not pageids:
                continue

            params2 = {
                "action": "query",
                "format": "json",
                "formatversion": "2",
                "pageids": pageids,
                "prop": "imageinfo|info",
                "inprop": "url",
                "iiprop": "url|mime|size",
                "iiurlwidth": 1200,
            }

            data2 = await self.get_json(
                COMMONS_API,
                params2,
            )

            if not data2:
                continue

            pages = data2.get(
                "query",
                {}
            ).get(
                "pages",
                []
            )

            random.shuffle(pages)

            for page in pages:

                imageinfo = page.get(
                    "imageinfo",
                    []
                )

                if not imageinfo:
                    continue

                info = imageinfo[0]

                mime = info.get(
                    "mime",
                    ""
                ).lower()

                if mime not in (
                    "image/jpeg",
                    "image/png",
                    "image/webp",
                ):
                    continue

                url = (
                    info.get("thumburl")
                    or info.get("url")
                )

                if not url:
                    continue

                image_bytes = await self.download_image(
                    url
                )

                if not image_bytes:
                    continue

                ext = {
                    "image/jpeg": "jpg",
                    "image/png": "png",
                    "image/webp": "webp",
                }.get(mime, "jpg")

                return {
                    "bytes": image_bytes,
                    "filename": f"country.{ext}",
                    "source": url,
                }

        return None

    # -----------------------------------------------------
    # تحميل خريطة العالم
    # -----------------------------------------------------

    async def get_world_geojson(self):

        if self.world_geojson:
            return self.world_geojson

        try:

            session = await self.get_session()

            async with session.get(
                WORLD_MAP_URL
            ) as response:

                if response.status != 200:
                    return None

                self.world_geojson = await response.json()

                return self.world_geojson

        except Exception as e:

            print(
                f"[GuessCountry] map error: {e}"
            )

            return None

    # -----------------------------------------------------
    # تحويل الإحداثيات إلى الخريطة
    # -----------------------------------------------------

    @staticmethod
    def project(lat, lon, width, height):

        # إسقاط equirectangular
        x = (lon + 180) / 360 * width

        y = (
            (90 - lat) / 180
            * height
        )

        return int(x), int(y)

    # -----------------------------------------------------
    # حساب centroid بسيط
    # -----------------------------------------------------

    @staticmethod
    def polygon_centroid(points):

        if not points:
            return None

        x = sum(
            p[0]
            for p in points
        ) / len(points)

        y = sum(
            p[1]
            for p in points
        ) / len(points)

        return x, y

    # -----------------------------------------------------
    # رسم الخريطة
    # -----------------------------------------------------

    async def create_result_map(self, game):

        WIDTH = 1400
        HEIGHT = 750

        image = Image.new(
            "RGB",
            (WIDTH, HEIGHT),
            (16, 20, 28),
        )

        draw = ImageDraw.Draw(image)

        # -------------------------------------------------
        # خريطة العالم
        # -------------------------------------------------

        geo = await self.get_world_geojson()

        if geo:

            for feature in geo.get(
                "features",
                []
            ):

                geometry = feature.get(
                    "geometry"
                )

                if not geometry:
                    continue

                geom_type = geometry.get(
                    "type"
                )

                coordinates = geometry.get(
                    "coordinates",
                    []
                )

                polygons = []

                if geom_type == "Polygon":

                    polygons = [
                        coordinates
                    ]

                elif geom_type == "MultiPolygon":

                    for polygon in coordinates:
                        polygons.append(polygon)

                for polygon in polygons:

                    if not polygon:
                        continue

                    outer = polygon[0]

                    points = []

                    for lon, lat in outer:

                        x, y = self.project(
                            lat,
                            lon,
                            WIDTH,
                            HEIGHT,
                        )

                        points.append(
                            (x, y)
                        )

                    if len(points) >= 3:

                        draw.polygon(
                            points,
                            fill=(36, 43, 55),
                            outline=(70, 80, 95),
                        )

        # -------------------------------------------------
        # عنوان
        # -------------------------------------------------

        try:
            font_big = ImageFont.truetype(
                "DejaVuSans-Bold.ttf",
                34,
            )

            font_small = ImageFont.truetype(
                "DejaVuSans.ttf",
                22,
            )

        except Exception:

            font_big = ImageFont.load_default()
            font_small = ImageFont.load_default()

        title = (
            f"نتائج الجولة {game.round} — "
            f"الإجابة: {game.current_country}"
        )

        draw.text(
            (40, 25),
            title,
            fill=(255, 255, 255),
            font=font_big,
        )

        # -------------------------------------------------
        # إحداثيات الإجابة الصحيحة
        # -------------------------------------------------

        correct = COUNTRIES[
            game.current_country
        ]

        correct_x, correct_y = self.project(
            correct[1],
            correct[2],
            WIDTH,
            HEIGHT,
        )

        # -------------------------------------------------
        # رسم كل لاعب
        # -------------------------------------------------

        for player in game.players.values():

            if not player["guess"]:
                continue

            guessed = COUNTRIES.get(
                player["guess"]
            )

            if not guessed:
                continue

            guess_x, guess_y = self.project(
                guessed[1],
                guessed[2],
                WIDTH,
                HEIGHT,
            )

            # الخط
            draw.line(
                (
                    guess_x,
                    guess_y,
                    correct_x,
                    correct_y,
                ),
                fill=(240, 190, 60),
                width=4,
            )

        # -------------------------------------------------
        # دائرة الإجابة الصحيحة
        # -------------------------------------------------

        draw.ellipse(
            (
                correct_x - 18,
                correct_y - 18,
                correct_x + 18,
                correct_y + 18,
            ),
            fill=(220, 50, 50),
            outline=(255, 255, 255),
            width=4,
        )

        draw.text(
            (
                correct_x + 24,
                correct_y - 14,
            ),
            "الإجابة",
            fill=(255, 255, 255),
            font=font_small,
        )

        # -------------------------------------------------
        # صور اللاعبين
        # -------------------------------------------------

        for player in game.players.values():

            if not player["guess"]:
                continue

            guessed = COUNTRIES.get(
                player["guess"]
            )

            if not guessed:
                continue

            x, y = self.project(
                guessed[1],
                guessed[2],
                WIDTH,
                HEIGHT,
            )

            avatar = await self.get_avatar(
                player["avatar"]
            )

            if avatar:

                avatar = avatar.resize(
                    (64, 64)
                )

                mask = Image.new(
                    "L",
                    (64, 64),
                    0,
                )

                mask_draw = ImageDraw.Draw(
                    mask
                )

                mask_draw.ellipse(
                    (0, 0, 64, 64),
                    fill=255,
                )

                image.paste(
                    avatar,
                    (
                        x - 32,
                        y - 32,
                    ),
                    mask,
                )

                draw.ellipse(
                    (
                        x - 34,
                        y - 34,
                        x + 34,
                        y + 34,
                    ),
                    outline=(255, 255, 255),
                    width=3,
                )

            else:

                draw.ellipse(
                    (
                        x - 15,
                        y - 15,
                        x + 15,
                        y + 15,
                    ),
                    fill=(70, 150, 255),
                    outline=(255, 255, 255),
                    width=3,
                )

            # اسم اللاعب
            label = player["name"]

            if len(label) > 15:
                label = label[:15]

            draw.text(
                (
                    x + 38,
                    y - 12,
                ),
                label,
                fill=(255, 255, 255),
                font=font_small,
            )

        # -------------------------------------------------
        # حفظ الصورة بالذاكرة
        # -------------------------------------------------

        output = io.BytesIO()

        image.save(
            output,
            format="PNG",
            optimize=True,
        )

        output.seek(0)

        return output.getvalue()

    # -----------------------------------------------------
    # صورة حساب Discord
    # -----------------------------------------------------

    async def get_avatar(self, url):

        try:

            data = await self.download_image(
                url
            )

            if not data:
                return None

            avatar = Image.open(
                io.BytesIO(data)
            ).convert("RGBA")

            return avatar

        except Exception:
            return None

    # -----------------------------------------------------
    # Command
    # -----------------------------------------------------

    @commands.command(
        name=COMMAND_NAME
    )
    async def guess_country(
        self,
        ctx,
        *args
    ):

        # -------------------------------------------------
        # الروم الصحيح
        # -------------------------------------------------

        if ctx.channel.id != GAME_CHANNEL_ID:
            return

        # -------------------------------------------------
        # استخدام خاطئ
        # -------------------------------------------------

        if args:

            await ctx.send(
                "❌ استخدام الأمر غير صحيح.\n\n"
                f"✅ الاستخدام الصحيح:\n"
                f"`{COMMAND_PREFIX}{COMMAND_NAME}`"
            )

            return

        # -------------------------------------------------
        # منع تشغيل لعبتين
        # -------------------------------------------------

        if ctx.channel.id in self.games:

            await ctx.send(
                "⚠️ توجد لعبة **خمن الدولة** جارية بالفعل."
            )

            return

        # -------------------------------------------------
        # صلاحية التشغيل
        # -------------------------------------------------

        role = ctx.guild.get_role(
            ADMIN_ROLE_ID
        )

        if role is None or role not in ctx.author.roles:

            await ctx.send(
                "❌ ليس لديك صلاحية تشغيل اللعبة."
            )

            return

        # -------------------------------------------------
        # إنشاء اللعبة
        # -------------------------------------------------

        game = GuessCountryGame(
            self,
            ctx.channel,
        )

        game.add_player(
            ctx.author
        )

        self.games[
            ctx.channel.id
        ] = game

        embed = discord.Embed(
            title="🌍 خمن الدولة",
            description=(
                "🎮 **بدأت اللعبة!**\n\n"
                f"عدد الجولات: **{TOTAL_ROUNDS}**\n"
                f"وقت كل جولة: **{ROUND_SECONDS} ثانية**\n\n"
                "🖼️ ستظهر لك صورة من دولة عشوائية.\n"
                "✍️ اكتب اسم الدولة التي تتوقعها.\n\n"
                "بعد الجولة ستظهر خريطة توضح:\n"
                "🔵 تخمينات اللاعبين\n"
                "🔴 الدولة الصحيحة\n"
                "📏 المسافة بين كل تخمين والإجابة."
            ),
            color=discord.Color.blurple(),
        )

        view = GuessCountryView(
            game
        )

        await ctx.send(
            embed=embed,
            view=view,
        )

        await asyncio.sleep(2)

        if game.running:
            await game.start_round()

    # -----------------------------------------------------
    # استقبال التخمينات
    # -----------------------------------------------------

    @commands.Cog.listener()
    async def on_message(self, message):

        if message.author.bot:
            return

        if message.channel.id != GAME_CHANNEL_ID:
            return

        game = self.games.get(
            message.channel.id
        )

        if not game:
            return

        if not game.running:
            return

        if not game.round_active:
            return

        # لا نتعامل مع أوامر البوت على أنها تخمين
        if message.content.startswith(
            COMMAND_PREFIX
        ):
            return

        player = game.players.get(
            message.author.id
        )

        if not player:
            return

        # اللاعب لا يغير تخمينه
        if player["guess"] is not None:
            return

        guess = canonical_country(
            message.content
        )

        if not guess:

            try:

                await message.reply(
                    "❌ ما تعرفت على الدولة.\n"
                    "اكتب اسم دولة واضح، مثل: `اليابان`"
                )

            except Exception:
                pass

            return

        player["guess"] = guess

        target = COUNTRIES[
            game.current_country
        ]

        guessed = COUNTRIES[
            guess
        ]

        player["distance"] = haversine(
            target[1],
            target[2],
            guessed[1],
            guessed[2],
        )

        try:

            await message.add_reaction("✅")

        except Exception:
            pass

    # -----------------------------------------------------
    # إغلاق
    # -----------------------------------------------------

    def cog_unload(self):

        if self.session and not self.session.closed:

            asyncio.create_task(
                self.session.close()
            )


# =========================================================
# setup
# =========================================================

async def setup(bot):

    await bot.add_cog(
        GuessCountry(bot)
    )
