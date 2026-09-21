import asyncio
import math
import random
import unicodedata

import aiohttp
import discord
from discord.ext import commands
import folium


# =========================================================
# الإعدادات
# =========================================================

GAME_CHANNEL_ID = 1550797517237518417

COMMAND_PREFIX = "-"

ROUNDS = 10
ROUND_TIME = 15

# رتبة الإدارة المسموح لها بالتحكم في اللعبة
ADMIN_ROLE_ID = 1544078469657530578

# =========================================================
# أماكن اللعبة
# =========================================================
# البوت يختار من هذه الأماكن، ثم يبحث تلقائياً عن صورة
# قريبة من الإحداثيات في Wikimedia Commons.
#
# لا تحتاج تضيف الصور بنفسك.
# =========================================================

LOCATIONS = [
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

    # بريطانيا
    {
        "country": "بريطانيا",
        "city": "لندن",
        "lat": 51.5074,
        "lon": -0.1278,
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

    # كندا
    {
        "country": "كندا",
        "city": "تورونتو",
        "lat": 43.6532,
        "lon": -79.3832,
    },
    {
        "country": "كندا",
        "city": "فانكوفر",
        "lat": 49.2827,
        "lon": -123.1207,
    },

    # البرازيل
    {
        "country": "البرازيل",
        "city": "ريو دي جانيرو",
        "lat": -22.9068,
        "lon": -43.1729,
    },

    # الأرجنتين
    {
        "country": "الأرجنتين",
        "city": "بوينس آيرس",
        "lat": -34.6037,
        "lon": -58.3816,
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

    # تركيا
    {
        "country": "تركيا",
        "city": "إسطنبول",
        "lat": 41.0082,
        "lon": 28.9784,
    },

    # الإمارات
    {
        "country": "الإمارات",
        "city": "دبي",
        "lat": 25.2048,
        "lon": 55.2708,
    },

    # السعودية
    {
        "country": "السعودية",
        "city": "الرياض",
        "lat": 24.7136,
        "lon": 46.6753,
    },

    # الأردن
    {
        "country": "الأردن",
        "city": "عمّان",
        "lat": 31.9539,
        "lon": 35.9106,
    },

    # مصر
    {
        "country": "مصر",
        "city": "القاهرة",
        "lat": 30.0444,
        "lon": 31.2357,
    },

    # المغرب
    {
        "country": "المغرب",
        "city": "مراكش",
        "lat": 31.6295,
        "lon": -7.9811,
    },

    # جنوب أفريقيا
    {
        "country": "جنوب أفريقيا",
        "city": "كيب تاون",
        "lat": -33.9249,
        "lon": 18.4241,
    },

    # اليونان
    {
        "country": "اليونان",
        "city": "أثينا",
        "lat": 37.9838,
        "lon": 23.7275,
    },

    # هولندا
    {
        "country": "هولندا",
        "city": "أمستردام",
        "lat": 52.3676,
        "lon": 4.9041,
    },

    # البرتغال
    {
        "country": "البرتغال",
        "city": "لشبونة",
        "lat": 38.7223,
        "lon": -9.1393,
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

    # كوريا الجنوبية
    {
        "country": "كوريا الجنوبية",
        "city": "سيول",
        "lat": 37.5665,
        "lon": 126.9780,
    },

    # تايلاند
    {
        "country": "تايلاند",
        "city": "بانكوك",
        "lat": 13.7563,
        "lon": 100.5018,
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

    # فنلندا
    {
        "country": "فنلندا",
        "city": "هلسنكي",
        "lat": 60.1699,
        "lon": 24.9384,
    },

    # المكسيك
    {
        "country": "المكسيك",
        "city": "مكسيكو سيتي",
        "lat": 19.4326,
        "lon": -99.1332,
    },
]


# =========================================================
# أسماء اللاعبين الوهميين
# =========================================================

FAKE_NAMES = [
    "لاعب تجريبي",
    "المنافس الوهمي",
    "المحترف",
    "الصياد",
    "الرحالة",
    "المستكشف",
    "الذكي",
    "ملك الخرائط",
]


# =========================================================
# دوال مساعدة
# =========================================================

def normalize_text(text: str):
    """تنظيف النص العربي للمقارنة."""

    text = text.strip().lower()

    text = unicodedata.normalize("NFKD", text)

    replacements = {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ة": "ه",
        "ى": "ي",
        "ـ": "",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return text


def calculate_distance(lat1, lon1, lat2, lon2):
    """حساب المسافة بالكيلومتر باستخدام Haversine."""

    earth_radius = 6371.0

    lat1 = math.radians(lat1)
    lon1 = math.radians(lon1)
    lat2 = math.radians(lat2)
    lon2 = math.radians(lon2)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return earth_radius * c


# =========================================================
# Wikimedia
# =========================================================

async def get_wikimedia_image(location):
    """
    يبحث عن صورة في Wikimedia Commons قريبة من المكان.
    """

    url = "https://commons.wikimedia.org/w/api.php"

    params = {
        "action": "query",
        "generator": "geosearch",
        "ggsprimary": "all",
        "ggsnamespace": 6,
        "ggsradius": 10000,
        "ggscoord": f"{location['lat']}|{location['lon']}",
        "ggslimit": 20,
        "prop": "imageinfo",
        "iiprop": "url|mime",
        "iiurlwidth": 1200,
        "format": "json",
    }

    timeout = aiohttp.ClientTimeout(total=15)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:

            async with session.get(url, params=params) as response:

                if response.status != 200:
                    return None

                data = await response.json()

                pages = data.get("query", {}).get("pages", {})

                candidates = []

                for page in pages.values():

                    image_info = page.get("imageinfo")

                    if not image_info:
                        continue

                    info = image_info[0]

                    mime = info.get("mime", "")

                    if not mime.startswith("image/"):
                        continue

                    image_url = (
                        info.get("thumburl")
                        or info.get("url")
                    )

                    if image_url:
                        candidates.append(image_url)

                if not candidates:
                    return None

                return random.choice(candidates)

    except Exception as error:

        print(
            f"[GuessCountry] Wikimedia error: {error}"
        )

        return None


# =========================================================
# إنشاء الخريطة
# =========================================================

def create_map(round_data, results):

    game_map = folium.Map(
        location=[
            round_data["lat"],
            round_data["lon"],
        ],
        zoom_start=2,
    )

    # الموقع الصحيح
    folium.Marker(
        [
            round_data["lat"],
            round_data["lon"],
        ],
        tooltip=f"الموقع الصحيح: {round_data['country']}",
        popup=f"الموقع الصحيح: {round_data['city']} - {round_data['country']}",
        icon=folium.Icon(
            color="red",
            icon="flag",
        ),
    ).add_to(game_map)

    # تخمينات اللاعبين
    for result in results:

        if result.get("lat") is None:
            continue

        player_location = [
            result["lat"],
            result["lon"],
        ]

        folium.Marker(
            player_location,
            tooltip=(
                f"{result['name']} - "
                f"{result['guess']}"
            ),
        ).add_to(game_map)

        folium.PolyLine(
            locations=[
                player_location,
                [
                    round_data["lat"],
                    round_data["lon"],
                ],
            ],
            weight=3,
            opacity=0.7,
        ).add_to(game_map)

    return game_map


# =========================================================
# View التحكم باللعبة
# =========================================================

class GuessCountryView(discord.ui.View):

    def __init__(self, cog, owner_id):

        super().__init__(timeout=None)

        self.cog = cog
        self.owner_id = owner_id

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

        # فقط صاحب اللعبة يستطيع إضافة لاعب وهمي
        if interaction.user.id != self.owner_id:

            await interaction.response.send_message(
                "❌ فقط صاحب اللعبة يستطيع إضافة لاعب وهمي.",
                ephemeral=True,
            )

            return

        if not self.cog.active_game:

            await interaction.response.send_message(
                "❌ لا توجد لعبة شغالة حالياً.",
                ephemeral=True,
            )

            return

        name = self.cog.add_fake_player()

        await interaction.response.send_message(
            f"🤖 تمت إضافة اللاعب الوهمي **{name}**.",
            ephemeral=True,
        )


# =========================================================
# Cog
# =========================================================

class GuessCountry(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        self.active_game = False

        self.game_channel = None

        self.owner_id = None

        self.current_round = 0

        self.selected_locations = []

        self.current_location = None

        # اللاعبون الحقيقيون
        self.players = {}

        # اللاعبون الوهميون
        self.fake_players = {}

        # تخمينات الجولة الحالية
        self.current_guesses = {}

        # النتائج النهائية
        self.scores = {}

    # =====================================================
    # التحقق من الروم
    # =====================================================

    def valid_channel(self, ctx):

        return ctx.channel.id == GAME_CHANNEL_ID

    # =====================================================
    # إضافة لاعب وهمي
    # =====================================================

    def add_fake_player(self):

        available_names = [
            name
            for name in FAKE_NAMES
            if name not in self.fake_players
        ]

        if not available_names:

            name = f"لاعب وهمي {len(self.fake_players) + 1}"

        else:

            name = random.choice(
                available_names
            )

        self.fake_players[name] = {
            "name": name,
            "score": 0,
        }

        self.scores[name] = 0

        return name

    # =====================================================
    # بدء اللعبة
    # =====================================================

    @commands.command(
        name="خمن-الدولة"
    )
    async def start_game(self, ctx):

        if not self.valid_channel(ctx):

            return

        if self.active_game:

            await ctx.send(
                "⚠️ **يوجد لعبة شغالة بالفعل!**\n"
                "انتظر حتى تنتهي اللعبة الحالية."
            )

            return

        self.active_game = True

        self.owner_id = ctx.author.id

        self.game_channel = ctx.channel

        self.current_round = 0

        self.players = {}

        self.fake_players = {}

        self.current_guesses = {}

        self.scores = {}

        # إضافة صاحب اللعبة
        self.players[ctx.author.id] = {
            "name": ctx.author.display_name,
            "score": 0,
        }

        self.scores[ctx.author.id] = 0

        # اختيار الجولات بدون تكرار
        self.selected_locations = random.sample(
            LOCATIONS,
            min(ROUNDS, len(LOCATIONS)),
        )

        embed = discord.Embed(
            title="🌍 خمن الدولة",
            description=(
                "🎮 **بدأت اللعبة!**\n\n"
                f"👤 اللاعب الأساسي: {ctx.author.mention}\n"
                f"🔢 عدد الجولات: **{len(self.selected_locations)}**\n"
                f"⏱️ وقت كل جولة: **{ROUND_TIME} ثانية**\n\n"
                "📸 سيظهر لكم مكان حقيقي من العالم، "
                "وعليكم معرفة الدولة.\n\n"
                "🤖 تستطيع إضافة لاعب وهمي من الزر "
                "للتجربة."
            ),
            color=discord.Color.blue(),
        )

        view = GuessCountryView(
            self,
            ctx.author.id,
        )

        await ctx.send(
            embed=embed,
            view=view,
        )

        await asyncio.sleep(2)

        await self.start_next_round()

    # =====================================================
    # الجولة
    # =====================================================

    async def start_next_round(self):

        if not self.active_game:

            return

        if (
            self.current_round
            >= len(self.selected_locations)
        ):

            await self.finish_game()

            return

        self.current_guesses = {}

        self.current_location = (
            self.selected_locations[
                self.current_round
            ]
        )

        # الحصول على الصورة
        image_url = await get_wikimedia_image(
            self.current_location
        )

        if not image_url:

            await self.game_channel.send(
                "⚠️ تعذر الحصول على صورة لهذه الجولة، "
                "سيتم الانتقال لمكان آخر."
            )

            self.current_round += 1

            await self.start_next_round()

            return

        embed = discord.Embed(
            title=(
                f"🌍 الجولة "
                f"{self.current_round + 1}/"
                f"{len(self.selected_locations)}"
            ),
            description=(
                "📸 **خمن الدولة من الصورة!**\n\n"
                f"⏱️ أمامك **{ROUND_TIME} ثانية**.\n"
                "✍️ اكتب اسم الدولة في الشات."
            ),
            color=discord.Color.blurple(),
        )

        embed.set_image(
            url=image_url
        )

        embed.set_footer(
            text="خمن الدولة من الصورة"
        )

        await self.game_channel.send(
            embed=embed
        )

        # اللاعبون الوهميون يخمنون
        self.fake_guess()

        # العد التنازلي
        await asyncio.sleep(ROUND_TIME)

        if not self.active_game:

            return

        await self.finish_round()

    # =====================================================
    # تخمين اللاعب الوهمي
    # =====================================================

    def fake_guess(self):

        if not self.fake_players:

            return

        for fake_name in self.fake_players:

            # اختيار دولة عشوائية
            fake_location = random.choice(
                LOCATIONS
            )

            self.current_guesses[
                f"fake:{fake_name}"
            ] = {
                "name": fake_name,
                "guess": fake_location["country"],
                "lat": fake_location["lat"],
                "lon": fake_location["lon"],
                "fake": True,
            }

    # =====================================================
    # استقبال الرسائل
    # =====================================================

    @commands.Cog.listener()
    async def on_message(self, message):

        if message.author.bot:

            return

        if not self.active_game:

            return

        if (
            message.channel.id
            != GAME_CHANNEL_ID
        ):

            return

        # تجاهل أوامر البوت
        if message.content.startswith(
            COMMAND_PREFIX
        ):

            return

        # اللاعب الحقيقي
        if message.author.id not in self.players:

            self.players[message.author.id] = {
                "name": message.author.display_name,
                "score": self.scores.get(
                    message.author.id,
                    0,
                ),
            }

            self.scores.setdefault(
                message.author.id,
                0,
            )

        guess_text = message.content.strip()

        if not guess_text:

            return

        # محاولة إيجاد الدولة
        matched_location = None

        normalized_guess = normalize_text(
            guess_text
        )

        for location in LOCATIONS:

            if normalize_text(
                location["country"]
            ) == normalized_guess:

                matched_location = location

                break

        if matched_location is None:

            # لا نحذف الرسالة ولا نرد على كل كلمة
            return

        # اللاعب يستطيع تعديل تخمينه
        self.current_guesses[
            message.author.id
        ] = {
            "name": message.author.display_name,
            "guess": matched_location["country"],
            "lat": matched_location["lat"],
            "lon": matched_location["lon"],
            "fake": False,
        }

        try:

            await message.add_reaction("📍")

        except Exception:

            pass

    # =====================================================
    # نهاية الجولة
    # =====================================================

    async def finish_round(self):

        if not self.current_location:

            return

        results = []

        true_lat = self.current_location["lat"]
        true_lon = self.current_location["lon"]
        true_country = self.current_location["country"]

        for player_id, guess in self.current_guesses.items():

            distance = calculate_distance(
                guess["lat"],
                guess["lon"],
                true_lat,
                true_lon,
            )

            results.append({
                "id": player_id,
                "name": guess["name"],
                "guess": guess["guess"],
                "lat": guess["lat"],
                "lon": guess["lon"],
                "distance": distance,
                "fake": guess.get(
                    "fake",
                    False,
                ),
            })

        # الأقرب أولاً
        results.sort(
            key=lambda item: item["distance"]
        )

        # إعطاء النقاط
        points_table = [
            10,
            8,
            6,
            4,
            2,
        ]

        for index, result in enumerate(
            results[:5]
        ):

            points = points_table[index]

            player_id = result["id"]

            if result["fake"]:

                self.fake_players[
                    result["name"]
                ]["score"] += points

                self.scores[
                    result["name"]
                ] = self.scores.get(
                    result["name"],
                    0,
                ) + points

            else:

                self.scores[
                    player_id
                ] = self.scores.get(
                    player_id,
                    0,
                ) + points

        # =================================================
        # رسالة نتائج الجولة
        # =================================================

        description = (
            f"🎯 **الدولة الصحيحة: "
            f"{true_country}**\n\n"
        )

        if not results:

            description += (
                "❌ لم يرسل أي لاعب تخميناً."
            )

        else:

            for index, result in enumerate(
                results,
                1,
            ):

                if index > 10:
                    break

                if result["fake"]:

                    total_score = self.scores.get(
                        result["name"],
                        0,
                    )

                else:

                    total_score = self.scores.get(
                        result["id"],
                        0,
                    )

                description += (
                    f"**{index}. "
                    f"{result['name']}**\n"
                    f"↳ تخمين: "
                    f"{result['guess']}\n"
                    f"↳ المسافة: "
                    f"**{result['distance']:,.1f} كم**\n"
                    f"↳ نقاطه: **{total_score}**\n\n"
                )

        embed = discord.Embed(
            title=(
                f"📊 نتائج الجولة "
                f"{self.current_round + 1}"
            ),
            description=description,
            color=discord.Color.green(),
        )

        await self.game_channel.send(
            embed=embed
        )

        # =================================================
        # إرسال الخريطة
        # =================================================

        if results:

            try:

                game_map = create_map(
                    self.current_location,
                    results,
                )

                filename = (
                    f"guess_country_map_"
                    f"{self.current_round + 1}.html"
                )

                game_map.save(filename)

                await self.game_channel.send(
                    "🗺️ **خريطة الجولة:**",
                    file=discord.File(filename),
                )

                import os

                if os.path.exists(filename):

                    os.remove(filename)

            except Exception as error:

                print(
                    f"[GuessCountry] Map error: {error}"
                )

        self.current_round += 1

        # وقت قصير قبل الجولة الجديدة
        await asyncio.sleep(3)

        await self.start_next_round()

    # =====================================================
    # نهاية اللعبة
    # =====================================================

    async def finish_game(self):

        self.active_game = False

        # تحويل النتائج لقائمة
        final_results = []

        # لاعبين حقيقيين
        for user_id, score in self.scores.items():

            if isinstance(user_id, int):

                user = self.bot.get_user(
                    user_id
                )

                name = (
                    user.display_name
                    if user
                    else "لاعب"
                )

                final_results.append({
                    "name": name,
                    "score": score,
                })

        # لاعبين وهميين
        for fake_name, data in self.fake_players.items():

            final_results.append({
                "name": fake_name,
                "score": data["score"],
            })

        final_results.sort(
            key=lambda x: x["score"],
            reverse=True,
        )

        description = (
            "🏁 **انتهت جميع الجولات!**\n\n"
            "🏆 **الترتيب النهائي:**\n\n"
        )

        medals = [
            "🥇",
            "🥈",
            "🥉",
        ]

        for index, player in enumerate(
            final_results,
            1,
        ):

            medal = (
                medals[index - 1]
                if index <= 3
                else f"**{index}.**"
            )

            description += (
                f"{medal} **{player['name']}**"
                f" — **{player['score']} نقطة**\n"
            )

        if final_results:

            winner = final_results[0]

            description += (
                "\n🎉 **الفائز:** "
                f"**{winner['name']}** "
                f"بـ **{winner['score']} نقطة**!"
            )

        else:

            description += (
                "❌ لم يسجل أي لاعب نقاط."
            )

        embed = discord.Embed(
            title="🏆 انتهت لعبة خمن الدولة",
            description=description,
            color=discord.Color.gold(),
        )

        await self.game_channel.send(
            embed=embed
        )

        # إعادة ضبط حالة اللعبة
        self.current_round = 0
        self.current_location = None
        self.current_guesses = {}
        self.selected_locations = []
        self.players = {}
        self.fake_players = {}
        self.scores = {}
        self.owner_id = None
        self.game_channel = None

    # =====================================================
    # أمر إيقاف اللعبة للإدارة
    # =====================================================

    @commands.command(
        name="ايقاف-خمن-الدولة"
    )
    async def stop_game(self, ctx):

        if not self.valid_channel(ctx):

            return

        if not self.active_game:

            await ctx.send(
                "❌ لا توجد لعبة شغالة حالياً."
            )

            return

        has_role = any(
            role.id == ADMIN_ROLE_ID
            for role in ctx.author.roles
        )

        if not has_role:

            return

        self.active_game = False

        await ctx.send(
            "🛑 تم إيقاف لعبة **خمن الدولة**."
        )

        self.current_round = 0
        self.current_location = None
        self.current_guesses = {}
        self.selected_locations = []
        self.players = {}
        self.fake_players = {}
        self.scores = {}
        self.owner_id = None
        self.game_channel = None

    # =====================================================
    # أخطاء الاستخدام
    # =====================================================

    @start_game.error
    async def start_game_error(
        self,
        ctx,
        error,
    ):

        if not self.valid_channel(ctx):

            return

        if isinstance(
            error,
            commands.TooManyArguments,
        ):

            await ctx.send(
                "❌ **خطأ في طريقة الاستخدام**\n\n"
                "الطريقة الصحيحة:\n"
                "`-خمن-الدولة`"
            )


# =========================================================
# Setup
# =========================================================

async def setup(bot):

    await bot.add_cog(
        GuessCountry(bot)
    )
