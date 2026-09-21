import asyncio
import aiohttp
import discord
import io
import math
import random
import re

from discord.ext import commands


# =========================================================
# الإعدادات
# =========================================================

GAME_CHANNEL_ID = 1550797517237518417

# الرتبة التي تستطيع تشغيل اللعبة
ADMIN_ROLE_ID = 1544078469657530578

PREFIX = "-"

GAME_ROUNDS = 10
ROUND_TIME = 15

# نقاط أول 5 لاعبين حسب القرب
POINTS_TABLE = [10, 8, 6, 4, 2]

# Wikipedia API
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"

USER_AGENT = (
    "DiscordGuessCountryBot/1.0 "
    "(Discord bot; educational game)"
)


# =========================================================
# الأماكن
# =========================================================

LOCATIONS = [

    # الأردن
    {
        "country": "الأردن",
        "city": "عمّان",
        "lat": 31.9539,
        "lon": 35.9106,
    },
    {
        "country": "الأردن",
        "city": "البتراء",
        "lat": 30.3285,
        "lon": 35.4444,
    },

    # السعودية
    {
        "country": "السعودية",
        "city": "الرياض",
        "lat": 24.7136,
        "lon": 46.6753,
    },
    {
        "country": "السعودية",
        "city": "جدة",
        "lat": 21.5433,
        "lon": 39.1728,
    },

    # الإمارات
    {
        "country": "الإمارات",
        "city": "دبي",
        "lat": 25.2048,
        "lon": 55.2708,
    },
    {
        "country": "الإمارات",
        "city": "أبوظبي",
        "lat": 24.4539,
        "lon": 54.3773,
    },

    # مصر
    {
        "country": "مصر",
        "city": "القاهرة",
        "lat": 30.0444,
        "lon": 31.2357,
    },
    {
        "country": "مصر",
        "city": "الإسكندرية",
        "lat": 31.2001,
        "lon": 29.9187,
    },

    # تركيا
    {
        "country": "تركيا",
        "city": "إسطنبول",
        "lat": 41.0082,
        "lon": 28.9784,
    },
    {
        "country": "تركيا",
        "city": "أنقرة",
        "lat": 39.9334,
        "lon": 32.8597,
    },

    # فرنسا
    {
        "country": "فرنسا",
        "city": "باريس",
        "lat": 48.8566,
        "lon": 2.3522,
    },
    {
        "country": "فرنسا",
        "city": "ليون",
        "lat": 45.7640,
        "lon": 4.8357,
    },

    # إيطاليا
    {
        "country": "إيطاليا",
        "city": "روما",
        "lat": 41.9028,
        "lon": 12.4964,
    },
    {
        "country": "إيطاليا",
        "city": "ميلانو",
        "lat": 45.4642,
        "lon": 9.1900,
    },

    # إسبانيا
    {
        "country": "إسبانيا",
        "city": "مدريد",
        "lat": 40.4168,
        "lon": -3.7038,
    },
    {
        "country": "إسبانيا",
        "city": "برشلونة",
        "lat": 41.3874,
        "lon": 2.1686,
    },

    # المملكة المتحدة
    {
        "country": "المملكة المتحدة",
        "city": "لندن",
        "lat": 51.5074,
        "lon": -0.1278,
    },
    {
        "country": "المملكة المتحدة",
        "city": "مانشستر",
        "lat": 53.4808,
        "lon": -2.2426,
    },

    # ألمانيا
    {
        "country": "ألمانيا",
        "city": "برلين",
        "lat": 52.5200,
        "lon": 13.4050,
    },
    {
        "country": "ألمانيا",
        "city": "ميونخ",
        "lat": 48.1351,
        "lon": 11.5820,
    },

    # هولندا
    {
        "country": "هولندا",
        "city": "أمستردام",
        "lat": 52.3676,
        "lon": 4.9041,
    },

    # بلجيكا
    {
        "country": "بلجيكا",
        "city": "بروكسل",
        "lat": 50.8503,
        "lon": 4.3517,
    },

    # سويسرا
    {
        "country": "سويسرا",
        "city": "زيورخ",
        "lat": 47.3769,
        "lon": 8.5417,
    },

    # النمسا
    {
        "country": "النمسا",
        "city": "فيينا",
        "lat": 48.2082,
        "lon": 16.3738,
    },

    # اليونان
    {
        "country": "اليونان",
        "city": "أثينا",
        "lat": 37.9838,
        "lon": 23.7275,
    },

    # البرتغال
    {
        "country": "البرتغال",
        "city": "لشبونة",
        "lat": 38.7223,
        "lon": -9.1393,
    },

    # النرويج
    {
        "country": "النرويج",
        "city": "أوسلو",
        "lat": 59.9139,
        "lon": 10.7522,
    },

    # السويد
    {
        "country": "السويد",
        "city": "ستوكهولم",
        "lat": 59.3293,
        "lon": 18.0686,
    },

    # الدنمارك
    {
        "country": "الدنمارك",
        "city": "كوبنهاغن",
        "lat": 55.6761,
        "lon": 12.5683,
    },

    # فنلندا
    {
        "country": "فنلندا",
        "city": "هلسنكي",
        "lat": 60.1699,
        "lon": 24.9384,
    },

    # أيرلندا
    {
        "country": "أيرلندا",
        "city": "دبلن",
        "lat": 53.3498,
        "lon": -6.2603,
    },

    # الولايات المتحدة
    {
        "country": "الولايات المتحدة",
        "city": "نيويورك",
        "lat": 40.7128,
        "lon": -74.0060,
    },
    {
        "country": "الولايات المتحدة",
        "city": "لوس أنجلوس",
        "lat": 34.0522,
        "lon": -118.2437,
    },
    {
        "country": "الولايات المتحدة",
        "city": "سان فرانسيسكو",
        "lat": 37.7749,
        "lon": -122.4194,
    },

    # كندا
    {
        "country": "كندا",
        "city": "تورنتو",
        "lat": 43.6532,
        "lon": -79.3832,
    },
    {
        "country": "كندا",
        "city": "فانكوفر",
        "lat": 49.2827,
        "lon": -123.1207,
    },

    # المكسيك
    {
        "country": "المكسيك",
        "city": "مكسيكو سيتي",
        "lat": 19.4326,
        "lon": -99.1332,
    },

    # البرازيل
    {
        "country": "البرازيل",
        "city": "ريو دي جانيرو",
        "lat": -22.9068,
        "lon": -43.1729,
    },
    {
        "country": "البرازيل",
        "city": "ساو باولو",
        "lat": -23.5505,
        "lon": -46.6333,
    },

    # الأرجنتين
    {
        "country": "الأرجنتين",
        "city": "بوينس آيرس",
        "lat": -34.6037,
        "lon": -58.3816,
    },

    # تشيلي
    {
        "country": "تشيلي",
        "city": "سانتياغو",
        "lat": -33.4489,
        "lon": -70.6693,
    },

    # أستراليا
    {
        "country": "أستراليا",
        "city": "سيدني",
        "lat": -33.8688,
        "lon": 151.2093,
    },
    {
        "country": "أستراليا",
        "city": "ملبورن",
        "lat": -37.8136,
        "lon": 144.9631,
    },

    # نيوزيلندا
    {
        "country": "نيوزيلندا",
        "city": "أوكلاند",
        "lat": -36.8509,
        "lon": 174.7645,
    },

    # اليابان
    {
        "country": "اليابان",
        "city": "طوكيو",
        "lat": 35.6762,
        "lon": 139.6503,
    },
    {
        "country": "اليابان",
        "city": "كيوتو",
        "lat": 35.0116,
        "lon": 135.7681,
    },

    # كوريا الجنوبية
    {
        "country": "كوريا الجنوبية",
        "city": "سيول",
        "lat": 37.5665,
        "lon": 126.9780,
    },

    # الصين
    {
        "country": "الصين",
        "city": "بكين",
        "lat": 39.9042,
        "lon": 116.4074,
    },
    {
        "country": "الصين",
        "city": "شنغهاي",
        "lat": 31.2304,
        "lon": 121.4737,
    },

    # سنغافورة
    {
        "country": "سنغافورة",
        "city": "سنغافورة",
        "lat": 1.3521,
        "lon": 103.8198,
    },

    # الهند
    {
        "country": "الهند",
        "city": "نيودلهي",
        "lat": 28.6139,
        "lon": 77.2090,
    },

    # تايلاند
    {
        "country": "تايلاند",
        "city": "بانكوك",
        "lat": 13.7563,
        "lon": 100.5018,
    },

    # إندونيسيا
    {
        "country": "إندونيسيا",
        "city": "جاكرتا",
        "lat": -6.2088,
        "lon": 106.8456,
    },

    # جنوب أفريقيا
    {
        "country": "جنوب أفريقيا",
        "city": "كيب تاون",
        "lat": -33.9249,
        "lon": 18.4241,
    },

    # المغرب
    {
        "country": "المغرب",
        "city": "مراكش",
        "lat": 31.6295,
        "lon": -7.9811,
    },
    {
        "country": "المغرب",
        "city": "الدار البيضاء",
        "lat": 33.5731,
        "lon": -7.5898,
    },

    # تونس
    {
        "country": "تونس",
        "city": "تونس",
        "lat": 36.8065,
        "lon": 10.1815,
    },

    # لبنان
    {
        "country": "لبنان",
        "city": "بيروت",
        "lat": 33.8938,
        "lon": 35.5018,
    },
]


# =========================================================
# إحداثيات تقريبية للدول
# =========================================================

COUNTRY_COORDS = {
    "الأردن": (31.24, 36.51),
    "السعودية": (23.89, 45.08),
    "الإمارات": (23.42, 53.85),
    "مصر": (26.82, 30.80),
    "تركيا": (38.96, 35.24),
    "فرنسا": (46.23, 2.21),
    "إيطاليا": (41.87, 12.57),
    "إسبانيا": (40.46, -3.75),
    "المملكة المتحدة": (55.38, -3.44),
    "ألمانيا": (51.17, 10.45),
    "هولندا": (52.13, 5.29),
    "بلجيكا": (50.50, 4.47),
    "سويسرا": (46.82, 8.23),
    "النمسا": (47.52, 14.55),
    "اليونان": (39.07, 21.82),
    "البرتغال": (39.40, -8.22),
    "النرويج": (60.47, 8.47),
    "السويد": (60.13, 18.64),
    "الدنمارك": (56.26, 9.50),
    "فنلندا": (61.92, 25.75),
    "أيرلندا": (53.14, -7.69),
    "الولايات المتحدة": (39.83, -98.58),
    "كندا": (56.13, -106.35),
    "المكسيك": (23.63, -102.55),
    "البرازيل": (-14.24, -51.93),
    "الأرجنتين": (-38.42, -63.62),
    "تشيلي": (-35.68, -71.54),
    "أستراليا": (-25.27, 133.78),
    "نيوزيلندا": (-40.90, 174.89),
    "اليابان": (36.20, 138.25),
    "كوريا الجنوبية": (35.91, 127.77),
    "الصين": (35.86, 104.20),
    "سنغافورة": (1.35, 103.82),
    "الهند": (20.59, 78.96),
    "تايلاند": (15.87, 100.99),
    "إندونيسيا": (-0.79, 113.92),
    "جنوب أفريقيا": (-30.56, 22.94),
    "المغرب": (31.79, -7.09),
    "تونس": (33.89, 9.54),
    "لبنان": (33.85, 35.86),
}


# =========================================================
# أسماء الدول والاختصارات
# =========================================================

COUNTRY_ALIASES = {
    "الاردن": "الأردن",
    "أردن": "الأردن",

    "السعوديه": "السعودية",

    "الامارات": "الإمارات",
    "الامارات العربية المتحدة": "الإمارات",
    "الإمارات العربية المتحدة": "الإمارات",
    "دبي": "الإمارات",

    "مصر": "مصر",

    "تركيا": "تركيا",

    "فرنسا": "فرنسا",

    "ايطاليا": "إيطاليا",

    "اسبانيا": "إسبانيا",

    "بريطانيا": "المملكة المتحدة",
    "بريطانيا العظمى": "المملكة المتحدة",
    "انجلترا": "المملكة المتحدة",
    "إنجلترا": "المملكة المتحدة",
    "المملكة المتحده": "المملكة المتحدة",
    "uk": "المملكة المتحدة",
    "united kingdom": "المملكة المتحدة",

    "المانيا": "ألمانيا",

    "هولندا": "هولندا",
    "بلجيكا": "بلجيكا",
    "سويسرا": "سويسرا",
    "النمسا": "النمسا",
    "اليونان": "اليونان",
    "البرتغال": "البرتغال",
    "النرويج": "النرويج",
    "السويد": "السويد",
    "الدنمارك": "الدنمارك",
    "فنلندا": "فنلندا",

    "ايرلندا": "أيرلندا",

    "امريكا": "الولايات المتحدة",
    "أمريكا": "الولايات المتحدة",
    "الولايات المتحده": "الولايات المتحدة",
    "الولايات المتحدة الامريكية": "الولايات المتحدة",
    "الولايات المتحدة الأمريكية": "الولايات المتحدة",
    "usa": "الولايات المتحدة",
    "us": "الولايات المتحدة",
    "america": "الولايات المتحدة",

    "كندا": "كندا",
    "المكسيك": "المكسيك",
    "البرازيل": "البرازيل",

    "الارجنتين": "الأرجنتين",

    "تشيلي": "تشيلي",

    "استراليا": "أستراليا",

    "نيوزيلندا": "نيوزيلندا",

    "اليابان": "اليابان",
    "japan": "اليابان",

    "كوريا الجنوبية": "كوريا الجنوبية",
    "كوريا الجنوبيه": "كوريا الجنوبية",

    "الصين": "الصين",

    "سنغافورة": "سنغافورة",
    "سنغافوره": "سنغافورة",

    "الهند": "الهند",

    "تايلاند": "تايلاند",

    "اندونيسيا": "إندونيسيا",

    "جنوب افريقيا": "جنوب أفريقيا",

    "المغرب": "المغرب",
    "تونس": "تونس",
    "لبنان": "لبنان",
}


# =========================================================
# أسماء اللاعبين الوهميين
# =========================================================

FAKE_NAMES = [
    "أحمد الوهمي",
    "محمد الوهمي",
    "سعيد الوهمي",
    "راكان الوهمي",
    "فهد الوهمي",
    "سلطان الوهمي",
    "خالد الوهمي",
    "مجهول 01",
    "مجهول 02",
    "مجهول 03",
]


# =========================================================
# أدوات عامة
# =========================================================

def normalize_text(text: str) -> str:

    text = str(text).lower().strip()

    replacements = {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ٱ": "ا",
        "ى": "ي",
        "ة": "ه",
        "ؤ": "و",
        "ئ": "ي",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(
        r"[\u064B-\u065F\u0670]",
        "",
        text,
    )

    text = re.sub(
        r"[^\w\s\u0600-\u06FF-]",
        "",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text


def get_country_from_guess(text: str):

    normalized = normalize_text(text)

    for alias, country in COUNTRY_ALIASES.items():

        if normalize_text(alias) == normalized:
            return country

    for country in COUNTRY_COORDS:

        if normalize_text(country) == normalized:
            return country

    return None


def haversine_distance(
    lat1,
    lon1,
    lat2,
    lon2,
):

    radius = 6371.0

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)

    delta_phi = math.radians(
        lat2 - lat1
    )

    delta_lambda = math.radians(
        lon2 - lon1
    )

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1)
        * math.cos(phi2)
        * math.sin(delta_lambda / 2) ** 2
    )

    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a),
    )

    return radius * c


def format_distance(distance):

    if distance < 1:
        return f"{distance * 1000:.0f} متر"

    if distance < 100:
        return f"{distance:.1f} كم"

    return f"{distance:,.0f} كم"


# =========================================================
# واجهة اللعبة
# =========================================================

class GuessCountryView(discord.ui.View):

    def __init__(
        self,
        cog,
        game,
    ):

        super().__init__(timeout=None)

        self.cog = cog
        self.game = game

    @discord.ui.button(
        label="➕ إضافة لاعب وهمي",
        style=discord.ButtonStyle.secondary,
        custom_id="guess_country_add_fake",
    )
    async def add_fake(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        if not self.game["running"]:

            await interaction.response.send_message(
                "❌ اللعبة انتهت.",
                ephemeral=True,
            )

            return

        # صاحب اللعبة أو الإدارة
        if interaction.user.id != self.game["owner_id"]:

            role = interaction.guild.get_role(
                ADMIN_ROLE_ID
            )

            if (
                role is None
                or role not in interaction.user.roles
            ):

                await interaction.response.send_message(
                    "❌ فقط صاحب اللعبة يستطيع إضافة لاعب وهمي.",
                    ephemeral=True,
                )

                return

        await interaction.response.defer(
            ephemeral=True
        )

        fake_name = self.cog.add_fake_player(
            self.game
        )

        if fake_name is None:

            await interaction.followup.send(
                "❌ لا يوجد لاعب وهمي متاح.",
                ephemeral=True,
            )

            return

        await interaction.followup.send(
            f"✅ تمت إضافة **{fake_name}** للعبة.",
            ephemeral=True,
        )

        try:

            await self.game["channel"].send(
                f"🤖 انضم اللاعب الوهمي **{fake_name}** إلى اللعبة!"
            )

        except Exception:
            pass


# =========================================================
# Cog
# =========================================================

class GuessCountryCog(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        # لعبة واحدة لكل روم
        self.games = {}

        self.session = None

    # =====================================================
    # إنشاء جلسة HTTP
    # =====================================================

    async def get_session(self):

        if (
            self.session is None
            or self.session.closed
        ):

            timeout = aiohttp.ClientTimeout(
                total=20,
                connect=8,
            )

            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "application/json",
                },
            )

        return self.session

    # =====================================================
    # إغلاق الجلسة
    # =====================================================

    async def cog_unload(self):

        if (
            self.session
            and not self.session.closed
        ):

            await self.session.close()

    # =====================================================
    # فحص الروم
    # =====================================================

    def valid_channel(self, ctx):

        return (
            ctx.channel.id
            == GAME_CHANNEL_ID
        )

    # =====================================================
    # جلب صورة من Wikipedia
    # =====================================================

    async def get_wikipedia_image(
        self,
        location,
    ):

        session = await self.get_session()

        lat = location["lat"]
        lon = location["lon"]

        radiuses = [
            5000,
            10000,
            20000,
        ]

        for radius in radiuses:

            params = {
                "action": "query",
                "format": "json",
                "formatversion": "2",

                "generator": "geosearch",

                "ggscoord": (
                    f"{lat}|{lon}"
                ),

                "ggsradius": radius,

                "ggslimit": 30,

                "ggsnamespace": 0,

                "prop": (
                    "coordinates|pageimages"
                ),

                "piprop": "thumbnail",

                "pithumbsize": 1200,

                "pilimit": 30,
            }

            try:

                async with session.get(
                    WIKIPEDIA_API,
                    params=params,
                ) as response:

                    if response.status != 200:
                        continue

                    data = await response.json(
                        content_type=None
                    )

            except Exception as e:

                print(
                    "Wikipedia API error:",
                    type(e).__name__,
                    e,
                )

                continue

            query = data.get(
                "query",
                {},
            )

            pages = query.get(
                "pages",
                [],
            )

            if not pages:
                continue

            random.shuffle(pages)

            for page in pages:

                thumbnail = page.get(
                    "thumbnail"
                )

                if not thumbnail:
                    continue

                image_url = thumbnail.get(
                    "source"
                )

                if not image_url:
                    continue

                width = thumbnail.get(
                    "width",
                    0,
                )

                height = thumbnail.get(
                    "height",
                    0,
                )

                if (
                    width < 300
                    or height < 200
                ):
                    continue

                # تحميل الصورة فعلياً
                try:

                    async with session.get(
                        image_url
                    ) as image_response:

                        if (
                            image_response.status
                            != 200
                        ):
                            continue

                        content_type = (
                            image_response.headers.get(
                                "Content-Type",
                                "",
                            )
                        )

                        if not content_type.startswith(
                            "image/"
                        ):
                            continue

                        image_bytes = (
                            await image_response.read()
                        )

                        if len(image_bytes) < 10_000:
                            continue

                        # Discord يسمح بحجم أكبر،
                        # لكن نخلي الصورة آمنة
                        if len(image_bytes) > 8_000_000:
                            continue

                        return {
                            "bytes": image_bytes,
                            "title": page.get(
                                "title",
                                "مكان",
                            ),
                            "source": image_url,
                        }

                except Exception as e:

                    print(
                        "Image download error:",
                        type(e).__name__,
                        e,
                    )

                    continue

        return None

    # =====================================================
    # اختيار مكان لديه صورة
    # =====================================================

    async def get_round_image(
        self,
        locations,
    ):

        shuffled = list(locations)

        random.shuffle(
            shuffled
        )

        for location in shuffled:

            image = await self.get_wikipedia_image(
                location
            )

            if image:

                return (
                    location,
                    image,
                )

        return (
            None,
            None,
        )

    # =====================================================
    # إضافة لاعب وهمي
    # =====================================================

    def add_fake_player(
        self,
        game,
    ):

        used_names = set(
            game["fake_names"]
        )

        available = [
            name
            for name in FAKE_NAMES
            if name not in used_names
        ]

        if not available:
            return None

        name = random.choice(
            available
        )

        game["fake_names"].add(
            name
        )

        game["players"][name] = {
            "name": name,
            "user_id": None,
            "fake": True,
            "score": 0,
            "guess": None,
            "guess_country": None,
            "distance": None,
            "round_score": 0,
        }

        # إذا تمت الإضافة أثناء الجولة
        # نعطيه تخميناً فورياً
        if (
            game["round_active"]
            and game["current_location"]
        ):

            fake_country = random.choice(
                list(
                    COUNTRY_COORDS.keys()
                )
            )

            game["players"][name][
                "guess_country"
            ] = fake_country

            fake_lat, fake_lon = (
                COUNTRY_COORDS[
                    fake_country
                ]
            )

            distance = haversine_distance(
                game["current_location"]["lat"],
                game["current_location"]["lon"],
                fake_lat,
                fake_lon,
            )

            game["players"][name][
                "distance"
            ] = distance

        return name

    # =====================================================
    # رسالة البداية
    # =====================================================

    async def send_start_message(
        self,
        game,
    ):

        channel = game["channel"]

        embed = discord.Embed(
            title="🌍 خمن الدولة",
            description=(
                "🎮 **بدأت اللعبة!**\n\n"
                f"👤 صاحب اللعبة: "
                f"<@{game['owner_id']}>\n"
                f"🔢 عدد الجولات: "
                f"**{GAME_ROUNDS}**\n"
                f"⏱️ وقت الجولة: "
                f"**{ROUND_TIME} ثانية**\n\n"
                "📸 ستظهر صورة لمكان حقيقي.\n"
                "✍️ اكتب اسم الدولة التي تعتقد أن الصورة فيها.\n\n"
                "🏆 كلما كان تخمينك أقرب، "
                "تحصل على نقاط أكثر."
            ),
        )

        embed.set_footer(
            text="خمن الدولة • 10 جولات"
        )

        view = GuessCountryView(
            self,
            game,
        )

        game["view"] = view

        await channel.send(
            embed=embed,
            view=view,
        )

    # =====================================================
    # بدء الجولة
    # =====================================================

    async def start_round(
        self,
        game,
    ):

        if not game["running"]:
            return

        if game["round"] > GAME_ROUNDS:

            await self.finish_game(
                game
            )

            return

        # مهم جداً لمنع مؤقت الجولة القديمة
        game["active_round_number"] = (
            game["round"]
        )

        channel = game["channel"]

        # ==============================================
        # تصفير بيانات الجولة
        # ==============================================

        for player in game["players"].values():

            player["guess"] = None
            player["guess_country"] = None
            player["distance"] = None
            player["round_score"] = 0

        # ==============================================
        # الأماكن المتبقية
        # ==============================================

        available_locations = [
            location
            for location in LOCATIONS
            if location["city"]
            not in game["used_cities"]
        ]

        if not available_locations:

            available_locations = LOCATIONS.copy()

        # ==============================================
        # الحصول على صورة
        # ==============================================

        location, image = (
            await self.get_round_image(
                available_locations
            )
        )

        # محاولة ثانية
        if (
            location is None
            or image is None
        ):

            location, image = (
                await self.get_round_image(
                    LOCATIONS
                )
            )

        # فشل نهائي
        if (
            location is None
            or image is None
        ):

            print(
                "❌ لم يتم العثور على أي صورة صالحة."
            )

            await channel.send(
                "❌ تعذر الحصول على صورة للجولة حالياً."
            )

            game["running"] = False
            game["round_active"] = False

            await self.finish_game(
                game
            )

            return

        game["current_location"] = location
        game["current_image"] = image

        game["used_cities"].add(
            location["city"]
        )

        game["round_active"] = True

        # ==============================================
        # اللاعبون الوهميون
        # ==============================================

        for player in game["players"].values():

            if not player["fake"]:
                continue

            fake_country = random.choice(
                list(
                    COUNTRY_COORDS.keys()
                )
            )

            player["guess_country"] = (
                fake_country
            )

            fake_lat, fake_lon = (
                COUNTRY_COORDS[
                    fake_country
                ]
            )

            player["distance"] = (
                haversine_distance(
                    location["lat"],
                    location["lon"],
                    fake_lat,
                    fake_lon,
                )
            )

        # ==============================================
        # Embed الصورة
        # ==============================================

        embed = discord.Embed(
            title=(
                f"🌍 خمن الدولة "
                f"— الجولة "
                f"{game['round']}/{GAME_ROUNDS}"
            ),
            description=(
                "📸 **أين التقطت هذه الصورة؟**\n\n"
                "✍️ اكتب اسم الدولة في الشات.\n\n"
                f"⏱️ لديك **{ROUND_TIME} ثانية**."
            ),
        )

        embed.set_image(
            url="attachment://location.jpg"
        )

        embed.set_footer(
            text="اكتب اسم الدولة فقط"
        )

        # ==============================================
        # إرسال الصورة
        # ==============================================

        try:

            # الإصلاح الأساسي:
            # تحويل bytes إلى ملف في الذاكرة
            image_file = io.BytesIO(
                image["bytes"]
            )

            image_file.seek(0)

            file = discord.File(
                fp=image_file,
                filename="location.jpg",
            )

            await channel.send(
                embed=embed,
                file=file,
            )

        except Exception as e:

            print(
                "❌ Discord image upload error:",
                type(e).__name__,
                e,
            )

            game["round_active"] = False

            # لا نرسل سبام للاعبين
            # نحاول مكاناً آخر
            await self.start_round(
                game
            )

            return

        # ==============================================
        # المؤقت
        # ==============================================

        current_round = (
            game["active_round_number"]
        )

        await asyncio.sleep(
            ROUND_TIME
        )

        if not game["running"]:
            return

        if not game["round_active"]:
            return

        if (
            game["active_round_number"]
            != current_round
        ):
            return

        await self.finish_round(
            game
        )

    # =====================================================
    # إنهاء الجولة
    # =====================================================

    async def finish_round(
        self,
        game,
    ):

        if not game["running"]:
            return

        if not game["round_active"]:
            return

        game["round_active"] = False

        channel = game["channel"]

        location = (
            game["current_location"]
        )

        # ==============================================
        # حساب المسافة للاعبين الحقيقيين
        # ==============================================

        for player in game["players"].values():

            if player["fake"]:
                continue

            guess_country = (
                player.get(
                    "guess_country"
                )
            )

            if not guess_country:
                continue

            coords = COUNTRY_COORDS.get(
                guess_country
            )

            if not coords:
                continue

            guess_lat, guess_lon = coords

            player["distance"] = (
                haversine_distance(
                    location["lat"],
                    location["lon"],
                    guess_lat,
                    guess_lon,
                )
            )

        # ==============================================
        # ترتيب حسب المسافة
        # ==============================================

        guessed_players = [
            player
            for player in game["players"].values()
            if player.get("distance") is not None
        ]

        guessed_players.sort(
            key=lambda player:
            player["distance"]
        )

        # ==============================================
        # توزيع النقاط
        # ==============================================

        for index, player in enumerate(
            guessed_players
        ):

            if index < len(
                POINTS_TABLE
            ):

                points = POINTS_TABLE[
                    index
                ]

            else:

                points = 1

            player["round_score"] = (
                points
            )

            player["score"] += points

        # ==============================================
        # النتائج
        # ==============================================

        players_sorted = sorted(
            game["players"].values(),
            key=lambda player: (
                -player["score"],
                player["name"],
            ),
        )

        lines = []

        for player in players_sorted:

            name = player["name"]

            country = (
                player["guess_country"]
                if player["guess_country"]
                else "لم يجب"
            )

            distance = player.get(
                "distance"
            )

            if distance is None:

                distance_text = "—"

            else:

                distance_text = (
                    format_distance(
                        distance
                    )
                )

            round_points = player.get(
                "round_score",
                0,
            )

            total = player["score"]

            lines.append(
                f"**{name}**\n"
                f"↳ 🌍 {country}\n"
                f"↳ 📏 {distance_text}\n"
                f"↳ ⭐ +{round_points}"
                f" | المجموع: **{total}**"
            )

        results_text = "\n\n".join(
            lines
        )

        # حماية من تجاوز حد Discord
        if len(results_text) > 3900:

            results_text = (
                results_text[:3890]
                + "\n..."
            )

        embed = discord.Embed(
            title=(
                f"📊 نتيجة الجولة "
                f"{game['round']}"
            ),
            description=results_text,
        )

        embed.add_field(
            name="📍 الدولة الصحيحة",
            value=(
                f"**{location['country']}**"
            ),
            inline=False,
        )

        embed.add_field(
            name="🏙️ المنطقة",
            value=location["city"],
            inline=True,
        )

        embed.add_field(
            name="📌 الإحداثيات",
            value=(
                f"{location['lat']:.4f}, "
                f"{location['lon']:.4f}"
            ),
            inline=True,
        )

        map_url = (
            "https://www.openstreetmap.org/"
            f"?mlat={location['lat']}"
            f"&mlon={location['lon']}"
            f"#map=12/"
            f"{location['lat']}/"
            f"{location['lon']}"
        )

        embed.add_field(
            name="🗺️ الخريطة",
            value=(
                f"[فتح موقع الجولة]({map_url})"
            ),
            inline=False,
        )

        await channel.send(
            embed=embed
        )

        # ==============================================
        # الجولة التالية
        # ==============================================

        game["round"] += 1

        if (
            game["round"]
            > GAME_ROUNDS
        ):

            await asyncio.sleep(2)

            await self.finish_game(
                game
            )

            return

        await asyncio.sleep(2)

        await self.start_round(
            game
        )

    # =====================================================
    # نهاية اللعبة
    # =====================================================

    async def finish_game(
        self,
        game,
    ):

        # منع التنفيذ مرتين
        if game.get(
            "finished",
            False,
        ):

            return

        game["finished"] = True
        game["running"] = False
        game["round_active"] = False

        channel = game["channel"]

        players = list(
            game["players"].values()
        )

        players.sort(
            key=lambda player:
            player["score"],
            reverse=True,
        )

        lines = []

        medals = [
            "🥇",
            "🥈",
            "🥉",
        ]

        for index, player in enumerate(
            players
        ):

            if index < 3:

                prefix = medals[
                    index
                ]

            else:

                prefix = (
                    f"**{index + 1}.**"
                )

            lines.append(
                f"{prefix} "
                f"{player['name']} — "
                f"**{player['score']} نقطة**"
            )

        leaderboard = "\n".join(
            lines
        )

        if not leaderboard:

            leaderboard = (
                "لا توجد نتائج."
            )

        if len(leaderboard) > 3900:

            leaderboard = (
                leaderboard[:3890]
                + "\n..."
            )

        winner = (
            players[0]
            if players
            else None
        )

        embed = discord.Embed(
            title=(
                "🏆 انتهت لعبة "
                "خمن الدولة!"
            ),
            description=(
                "🔥 **النتائج النهائية**\n\n"
                f"{leaderboard}"
            ),
        )

        if winner:

            embed.add_field(
                name="👑 الفائز",
                value=(
                    f"**{winner['name']}**\n"
                    f"⭐ {winner['score']} نقطة"
                ),
                inline=False,
            )

        embed.set_footer(
            text=(
                "يمكن تشغيل لعبة جديدة "
                "باستخدام -خمن-الدولة"
            )
        )

        try:

            await channel.send(
                embed=embed
            )

        except Exception as e:

            print(
                "Finish message error:",
                type(e).__name__,
                e,
            )

        # حذف اللعبة من الذاكرة
        self.games.pop(
            channel.id,
            None,
        )

    # =====================================================
    # استقبال إجابات اللاعبين
    # =====================================================

    @commands.Cog.listener()
    async def on_message(
        self,
        message,
    ):

        if message.author.bot:
            return

        game = self.games.get(
            message.channel.id
        )

        if not game:
            return

        if not game["running"]:
            return

        if not game["round_active"]:
            return

        # اللاعب الحقيقي فقط
        player = game["players"].get(
            message.author.id
        )

        if not player:
            return

        # منع تغيير الإجابة
        if (
            player["guess_country"]
            is not None
        ):

            return

        content = (
            message.content.strip()
        )

        if not content:
            return

        # تجاهل أوامر البوت
        if content.startswith(
            PREFIX
        ):

            return

        country = get_country_from_guess(
            content
        )

        if country is None:

            try:

                await message.reply(
                    "❌ ما تعرفت على الدولة.\n"
                    "اكتب اسم دولة واضح مثل: "
                    "**الأردن** أو **اليابان**.",
                    delete_after=3,
                )

            except Exception:
                pass

            return

        player["guess"] = content

        player["guess_country"] = (
            country
        )

        try:

            await message.add_reaction(
                "✅"
            )

        except Exception:
            pass

    # =====================================================
    # الأمر الرئيسي
    # =====================================================

    @commands.command(
        name="خمن-الدولة"
    )
    async def guess_country(
        self,
        ctx,
        *args,
    ):

        # -----------------------------------------------
        # الروم
        # -----------------------------------------------

        if not self.valid_channel(
            ctx
        ):

            return

        # -----------------------------------------------
        # استخدام خاطئ
        # -----------------------------------------------

        if args:

            await ctx.send(
                "❌ **خطأ في طريقة الاستخدام**\n\n"
                "الطريقة الصحيحة:\n"
                "`-خمن-الدولة`"
            )

            return

        # -----------------------------------------------
        # الرتبة
        # -----------------------------------------------

        role = ctx.guild.get_role(
            ADMIN_ROLE_ID
        )

        if (
            role is None
            or role not in ctx.author.roles
        ):

            await ctx.send(
                "❌ ما عندك صلاحية تشغيل "
                "لعبة خمن الدولة."
            )

            return

        # -----------------------------------------------
        # منع لعبة ثانية
        # -----------------------------------------------

        if ctx.channel.id in self.games:

            await ctx.send(
                "⚠️ **يوجد لعبة خمن الدولة "
                "جارية بالفعل.**\n"
                "انتظر حتى تنتهي اللعبة الحالية."
            )

            return

        # -----------------------------------------------
        # إنشاء اللعبة
        # -----------------------------------------------

        game = {

            "channel": ctx.channel,

            "owner_id": ctx.author.id,

            "running": True,

            "finished": False,

            "round_active": False,

            "round": 1,

            "active_round_number": 1,

            "players": {},

            "fake_names": set(),

            "used_cities": set(),

            "current_location": None,

            "current_image": None,

            "view": None,
        }

        # اللاعب الأساسي
        game["players"][
            ctx.author.id
        ] = {

            "name": ctx.author.mention,

            "user_id": ctx.author.id,

            "fake": False,

            "score": 0,

            "guess": None,

            "guess_country": None,

            "distance": None,

            "round_score": 0,
        }

        self.games[
            ctx.channel.id
        ] = game

        try:

            await self.send_start_message(
                game
            )

            await asyncio.sleep(2)

            await self.start_round(
                game
            )

        except Exception as e:

            print(
                "❌ Guess Country error:",
                type(e).__name__,
                e,
            )

            self.games.pop(
                ctx.channel.id,
                None,
            )

            try:

                await ctx.send(
                    "❌ حدث خطأ أثناء تشغيل اللعبة. "
                    "راجع لوق البوت."
                )

            except Exception:
                pass

    # =====================================================
    # إيقاف اللعبة
    # =====================================================

    @commands.command(
        name="ايقاف-خمن-الدولة"
    )
    async def stop_guess_country(
        self,
        ctx,
    ):

        if not self.valid_channel(
            ctx
        ):

            return

        role = ctx.guild.get_role(
            ADMIN_ROLE_ID
        )

        if (
            role is None
            or role not in ctx.author.roles
        ):

            return

        game = self.games.get(
            ctx.channel.id
        )

        if not game:

            await ctx.send(
                "ℹ️ لا توجد لعبة شغالة حالياً."
            )

            return

        game["running"] = False
        game["round_active"] = False

        self.games.pop(
            ctx.channel.id,
            None,
        )

        await ctx.send(
            "🛑 تم إيقاف لعبة "
            "**خمن الدولة**."
        )


# =========================================================
# Setup
# =========================================================

async def setup(bot):

    await bot.add_cog(
        GuessCountryCog(bot)
    )
