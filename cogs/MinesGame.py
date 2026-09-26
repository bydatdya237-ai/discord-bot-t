import os
import asyncio
import random

from datetime import datetime, timezone, timedelta

import discord
from discord.ext import commands

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ReturnDocument


# =========================================================
# MongoDB
# =========================================================

MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    raise RuntimeError(
        "❌ MONGO_URI غير موجود في Environment Variables."
    )


# =========================================================
# إعدادات اللعبة
# =========================================================

GAME_COOLDOWN = 30
GAME_TIMEOUT = 120

STARTING_GOLD = 1000

WIN_GOLD = 50
LOSS_GOLD = 35


# =========================================================
# الحماية
# =========================================================

PROTECTION_PRICE = 35
MAX_PROTECTIONS = 3


# =========================================================
# أمر ذهبي
# =========================================================

GOLDEN_MIN = 100
GOLDEN_MAX = 200
GOLDEN_COOLDOWN = 12 * 60 * 60


# =========================================================
# أسماء الأوامر
# =========================================================

COMMAND_MINES = "الغام"
COMMAND_WALLET = "محفظتي"
COMMAND_ADD = "ضيف"
COMMAND_GOLDEN = "ذهبي"
COMMAND_PROTECTION = "حمايتي"
COMMAND_TOP = "مين-توب"
COMMAND_GIVE_GOLD = "بعطيك-ذهب"
COMMAND_TAKE_GOLD = "هات-مصروف"


# =========================================================
# رسائل عشوائية
# =========================================================

WIN_MESSAGES = [
    "🏆 كفو! نظفت اللوحة بالكامل!",
    "🔥 لعب نظيف! الألغام ما قدرت عليك.",
    "👑 اليوم أنت ملك الألغام!",
    "🎉 فوز مستحق! الحظ كان معك.",
    "😂 الألغام حاولت... بس ما قدرت عليك.",
    "💰 طلعت منها بربح! كفو عليك.",
]

LOSS_MESSAGES = [
    "💀 راحت عليك!",
    "😂 اللغم كان ينتظرك!",
    "💣 اخترت المكان الغلط!",
    "😭 الحظ خانك هالمرة.",
    "🫡 وداعًا لـ 35 ذهب.",
    "💀 اللغم قال لك: مو اليوم.",
]

PROTECTION_MESSAGES = [
    "😂 يا حظك!",
    "🛡️ الحماية أنقذتك في آخر لحظة!",
    "😮 كانت بتروح عليك!",
    "🍀 اليوم الحظ واقف معك.",
    "💀 اللغم حاول... بس فشل.",
    "😂 اللغم انصدم من الحماية!",
]


# =========================================================
# Mines View
# =========================================================

class MinesView(discord.ui.View):

    def __init__(
        self,
        cog,
        guild_id,
        user_id
    ):

        super().__init__(
            timeout=GAME_TIMEOUT
        )

        self.cog = cog

        self.guild_id = guild_id
        self.user_id = user_id

        self.total_cells = 25
        self.total_mines = 5

        self.game_over = False
        self.revealed = set()

        # الألغام التي تم تفجيرها بالحماية
        # لا تعتبر خانات آمنة
        self.protected_mines = set()

        self.processing = False

        self.message = None

        self.mines = set()

        # =================================================
        # إنشاء الألغام
        # =================================================

        while len(self.mines) < self.total_mines:

            self.mines.add(
                random.randint(
                    0,
                    24
                )
            )

        # =================================================
        # إنشاء شبكة 5 × 5
        # =================================================

        for index in range(25):

            button = discord.ui.Button(
                style=discord.ButtonStyle.secondary,
                label="▪️",
                row=index // 5,
                custom_id=f"mine_{index}"
            )

            button.callback = self.button_callback

            self.add_item(
                button
            )

    # =====================================================
    # لون الرقم
    # =====================================================

    @staticmethod
    def get_number_style(number):

        if number == 1:
            return discord.ButtonStyle.primary

        if number == 2:
            return discord.ButtonStyle.success

        return discord.ButtonStyle.danger

    # =====================================================
    # حذف اللعبة من الألعاب النشطة
    # =====================================================

    def remove_active_game(self):

        active_key = (
            self.guild_id,
            self.user_id
        )

        self.cog.active_games.pop(
            active_key,
            None
        )

    # =====================================================
    # حساب الألغام حول الخانة
    # =====================================================

    def get_nearby_mines(
        self,
        index
    ):

        row, column = divmod(
            index,
            5
        )

        nearby_mines = 0

        for current_row in range(
            max(0, row - 1),
            min(5, row + 2)
        ):

            for current_column in range(
                max(0, column - 1),
                min(5, column + 2)
            ):

                nearby_index = (
                    current_row * 5
                    + current_column
                )

                if nearby_index in self.mines:

                    nearby_mines += 1

        return nearby_mines

    # =====================================================
    # الخانات المحيطة
    # =====================================================

    def get_neighbors(
        self,
        index
    ):

        row, column = divmod(
            index,
            5
        )

        neighbors = []

        for current_row in range(
            max(0, row - 1),
            min(5, row + 2)
        ):

            for current_column in range(
                max(0, column - 1),
                min(5, column + 2)
            ):

                nearby_index = (
                    current_row * 5
                    + current_column
                )

                if nearby_index != index:

                    neighbors.append(
                        nearby_index
                    )

        return neighbors

    # =====================================================
    # الكشف التلقائي
    # =====================================================

    def reveal_safe_area(
        self,
        start_index
    ):

        to_check = [
            start_index
        ]

        revealed_now = set()

        while to_check:

            current_index = to_check.pop()

            if current_index in revealed_now:
                continue

            if current_index in self.mines:
                continue

            if current_index in self.revealed:
                continue

            revealed_now.add(
                current_index
            )

            nearby_mines = self.get_nearby_mines(
                current_index
            )

            self.revealed.add(
                current_index
            )

            if nearby_mines == 0:

                for neighbor in self.get_neighbors(
                    current_index
                ):

                    if neighbor in self.mines:
                        continue

                    if neighbor in self.revealed:
                        continue

                    to_check.append(
                        neighbor
                    )

        return revealed_now

    # =====================================================
    # تحديث الأزرار
    # =====================================================

    def update_buttons(self):

        for child in self.children:

            if child.custom_id is None:
                continue

            try:

                index = int(
                    child.custom_id.split("_")[1]
                )

            except (
                ValueError,
                IndexError
            ):

                continue

            # =================================================
            # لغم تم إنقاذه بالحماية
            # =================================================

            if index in self.protected_mines:

                child.disabled = True

                child.style = (
                    discord.ButtonStyle.success
                )

                child.label = "🛡️"

                continue

            # =================================================
            # خانة آمنة مفتوحة
            # =================================================

            if index in self.revealed:

                child.disabled = True

                nearby_mines = self.get_nearby_mines(
                    index
                )

                if nearby_mines == 0:

                    child.style = (
                        discord.ButtonStyle.success
                    )

                    # مربع أخضر بدل 0
                    child.label = "🟩"

                else:

                    child.style = (
                        self.get_number_style(
                            nearby_mines
                        )
                    )

                    child.label = str(
                        nearby_mines
                    )

            else:

                child.disabled = False

                child.style = (
                    discord.ButtonStyle.secondary
                )

                child.label = "▪️"

    # =====================================================
    # إظهار الألغام عند الخسارة
    # =====================================================

    def reveal_all_mines(self):

        for child in self.children:

            child.disabled = True

            if child.custom_id is None:
                continue

            try:

                index = int(
                    child.custom_id.split("_")[1]
                )

            except (
                ValueError,
                IndexError
            ):

                continue

            if index in self.protected_mines:

                child.style = (
                    discord.ButtonStyle.success
                )

                child.label = "🛡️"

                continue

            if index in self.mines:

                child.style = (
                    discord.ButtonStyle.danger
                )

                child.label = "💣"

    # =====================================================
    # انتهاء الوقت
    # =====================================================

    async def on_timeout(self):

        if self.game_over:
            return

        self.game_over = True

        self.remove_active_game()

        for child in self.children:
            child.disabled = True

        if self.message is None:
            return

        embed = discord.Embed(
            title="💣 لعبة الألغام",
            description=(
                "⏰ **انتهى الوقت!**\n\n"
                "انتهت اللعبة بسبب انتهاء الوقت.\n"
                "لم يتم إضافة أو خصم أي ذهب."
            ),
            color=0x808080
        )

        try:

            await self.message.edit(
                embed=embed,
                view=self
            )

        except discord.HTTPException:

            pass

    # =====================================================
    # الضغط على الخانة
    # =====================================================

    async def button_callback(
        self,
        interaction
    ):

        # =================================================
        # صاحب اللعبة فقط
        # =================================================

        if interaction.user.id != self.user_id:

            await interaction.response.send_message(
                "❌ هذه اللعبة ليست لك.",
                ephemeral=True
            )

            return

        # =================================================
        # اللعبة منتهية
        # =================================================

        if self.game_over:

            await interaction.response.send_message(
                "❌ انتهت هذه اللعبة بالفعل.",
                ephemeral=True
            )

            return

        # =================================================
        # منع الضغط المتزامن
        # =================================================

        if self.processing:

            await interaction.response.send_message(
                "⏳ انتظر لحظة...",
                ephemeral=True
            )

            return

        self.processing = True

        try:

            # =================================================
            # قراءة الخانة
            # =================================================

            try:

                custom_id = interaction.data[
                    "custom_id"
                ]

                index = int(
                    custom_id.split("_")[1]
                )

            except (
                ValueError,
                KeyError,
                IndexError
            ):

                await interaction.response.send_message(
                    "❌ حدث خطأ أثناء فتح الخانة.",
                    ephemeral=True
                )

                return

            # =================================================
            # الخانة الآمنة المفتوحة
            # =================================================

            if index in self.revealed:

                await interaction.response.send_message(
                    "⚠️ هذه الخانة مفتوحة بالفعل.",
                    ephemeral=True
                )

                return

            # =================================================
            # لغم تم إنقاذه مسبقًا
            # =================================================

            if index in self.protected_mines:

                await interaction.response.send_message(
                    "🛡️ هذا اللغم تم إيقافه بالحماية.",
                    ephemeral=True
                )

                return

            # =================================================
            # لغم
            # =================================================

            if index in self.mines:

                # =============================================
                # فحص الحماية واستهلاكها ذريًا
                # =============================================

                protection_used = (
                    await self.cog.use_protection(
                        self.guild_id,
                        self.user_id
                    )
                )

                if protection_used:

                    # مهم:
                    # لا نضيف اللغم إلى self.revealed
                    # حتى لا يتم احتسابه كخانة آمنة.

                    self.protected_mines.add(
                        index
                    )

                    self.update_buttons()

                    protection_message = random.choice(
                        PROTECTION_MESSAGES
                    )

                    remaining_protection = (
                        await self.cog.get_protection(
                            self.guild_id,
                            self.user_id
                        )
                    )

                    embed = discord.Embed(
                        title="🛡️ نجوت!",
                        description=(
                            f"{protection_message}\n\n"
                            "💣 ضغطت على لغم، لكن الحماية أنقذتك.\n"
                            "🛡️ تم استهلاك حماية واحدة.\n\n"
                            f"🛡️ الحماية المتبقية: "
                            f"**{remaining_protection}/{MAX_PROTECTIONS}**\n\n"
                            "🎮 أكمل اللعبة!"
                        ),
                        color=0x2ECC71
                    )

                    await interaction.response.edit_message(
                        embed=embed,
                        view=self
                    )

                    return

                # =============================================
                # بدون حماية
                # =============================================

                self.game_over = True

                self.remove_active_game()

                self.reveal_all_mines()

                new_gold = await self.cog.change_gold(
                    self.guild_id,
                    self.user_id,
                    -LOSS_GOLD
                )

                loss_message = random.choice(
                    LOSS_MESSAGES
                )

                embed = discord.Embed(
                    title="💥 انفجر اللغم!",
                    description=(
                        f"{loss_message}\n\n"
                        f"💰 الذهب المخصوم: "
                        f"**-{LOSS_GOLD:,}**\n"
                        f"💳 رصيدك الحالي: "
                        f"**{new_gold:,} ذهب**"
                    ),
                    color=0xE74C3C
                )

                await interaction.response.edit_message(
                    embed=embed,
                    view=self
                )

                return

            # =================================================
            # خانة آمنة
            # =================================================

            nearby_mines = self.get_nearby_mines(
                index
            )

            if nearby_mines == 0:

                self.reveal_safe_area(
                    index
                )

            else:

                self.revealed.add(
                    index
                )

            # =================================================
            # تحديث الأزرار
            # =================================================

            self.update_buttons()

            # =================================================
            # التحقق من الفوز
            # =================================================

            safe_cells = (
                self.total_cells
                - self.total_mines
            )

            if len(self.revealed) >= safe_cells:

                self.game_over = True

                self.remove_active_game()

                for child in self.children:
                    child.disabled = True

                new_gold = await self.cog.change_gold(
                    self.guild_id,
                    self.user_id,
                    WIN_GOLD
                )

                win_message = random.choice(
                    WIN_MESSAGES
                )

                embed = discord.Embed(
                    title="🏆 فوز!",
                    description=(
                        f"{win_message}\n\n"
                        f"💰 الجائزة: "
                        f"**+{WIN_GOLD:,} ذهب**\n"
                        f"💳 رصيدك الحالي: "
                        f"**{new_gold:,} ذهب**"
                    ),
                    color=0x2ECC71
                )

                await interaction.response.edit_message(
                    embed=embed,
                    view=self
                )

                return

            # =================================================
            # استمرار اللعبة
            # =================================================

            await interaction.response.edit_message(
                view=self
            )

        except discord.HTTPException:

            pass

        except Exception as error:

            print(
                f"[MinesGame] Button Error: {error}"
            )

            try:

                if not interaction.response.is_done():

                    await interaction.response.send_message(
                        "❌ حدث خطأ غير متوقع.",
                        ephemeral=True
                    )

            except Exception:

                pass

        finally:

            self.processing = False


# =========================================================
# Protection View
# =========================================================

class ProtectionView(discord.ui.View):

    def __init__(
        self,
        cog,
        guild_id,
        user_id
    ):

        super().__init__(
            timeout=120
        )

        self.cog = cog
        self.guild_id = guild_id
        self.user_id = user_id

        self.buy_button = discord.ui.Button(
            style=discord.ButtonStyle.success,
            label="🛡️ شراء حماية",
            custom_id="buy_mines_protection"
        )

        self.buy_button.callback = self.buy_protection

        self.add_item(
            self.buy_button
        )

    # =====================================================
    # شراء الحماية
    # =====================================================

    async def buy_protection(
        self,
        interaction
    ):

        if interaction.user.id != self.user_id:

            await interaction.response.send_message(
                "❌ هذه النافذة ليست لك.",
                ephemeral=True
            )

            return

        # =================================================
        # تحكم الموقع
        # =================================================

        if not await self.cog.has_command_permission(
            interaction.user,
            COMMAND_PROTECTION,
            interaction.channel.id
        ):

            await interaction.response.send_message(
                "❌ هذا الأمر غير متاح لك.",
                ephemeral=True
            )

            return

        try:

            # =================================================
            # محاولة الشراء
            # =================================================

            result = await self.cog.buy_protection(
                self.guild_id,
                self.user_id
            )

            status = result.get(
                "status"
            )

            # =================================================
            # الحد الأقصى
            # =================================================

            if status == "max":

                self.buy_button.disabled = True

                await interaction.response.send_message(
                    f"🛡️ لديك الحد الأقصى من الحماية بالفعل: "
                    f"**{MAX_PROTECTIONS}/{MAX_PROTECTIONS}**.",
                    ephemeral=True
                )

                return

            # =================================================
            # الذهب غير كافٍ
            # =================================================

            if status == "insufficient":

                current_gold = await self.cog.get_balance(
                    self.guild_id,
                    self.user_id
                )

                await interaction.response.send_message(
                    f"❌ تحتاج إلى **{PROTECTION_PRICE:,} ذهب** "
                    f"لشراء الحماية.\n"
                    f"💳 رصيدك الحالي: **{current_gold:,} ذهب**",
                    ephemeral=True
                )

                return

            # =================================================
            # نجاح الشراء
            # =================================================

            if status == "success":

                remaining = result.get(
                    "protection",
                    0
                )

                new_gold = result.get(
                    "gold",
                    0
                )

                if remaining >= MAX_PROTECTIONS:

                    self.buy_button.disabled = True

                embed = discord.Embed(
                    title="🛡️ تم شراء الحماية",
                    description=(
                        "✅ تمت عملية الشراء بنجاح!\n\n"
                        f"🛡️ الحماية: "
                        f"**{remaining}/{MAX_PROTECTIONS}**\n"
                        f"💰 السعر: "
                        f"**-{PROTECTION_PRICE:,} ذهب**\n"
                        f"💳 رصيدك الحالي: "
                        f"**{new_gold:,} ذهب**"
                    ),
                    color=0x2ECC71
                )

                await interaction.response.edit_message(
                    embed=embed,
                    view=self
                )

                return

            # =================================================
            # خطأ غير معروف
            # =================================================

            await interaction.response.send_message(
                "❌ حدث خطأ أثناء شراء الحماية.",
                ephemeral=True
            )

        except Exception as error:

            print(
                f"[MinesGame] Protection Purchase Error: {error}"
            )

            try:

                if not interaction.response.is_done():

                    await interaction.response.send_message(
                        "❌ حدث خطأ أثناء شراء الحماية.",
                        ephemeral=True
                    )

            except Exception:

                pass


# =========================================================
# Mines Game Cog
# =========================================================

class MinesGame(commands.Cog):

    def __init__(
        self,
        bot
    ):

        self.bot = bot

        # =================================================
        # MongoDB
        # =================================================

        self.mongo_client = AsyncIOMotorClient(
            MONGO_URI
        )

        self.db = self.mongo_client[
            "discord_bot_db"
        ]

        self.game_data = self.db[
            "mines_game_data"
        ]

        self.website_command_settings = self.db[
            "website_command_settings"
        ]

        # =================================================
        # الألعاب النشطة
        # =================================================

        self.active_games = {}

        # =================================================
        # صاحب البوت
        # =================================================

        self.bot_owner_id = None
        self.owner_lock = asyncio.Lock()

    # =====================================================
    # Guild ID variants
    # =====================================================

    def guild_id_variants(
        self,
        guild_id
    ):

        variants = [
            str(guild_id)
        ]

        try:

            variants.append(
                int(guild_id)
            )

        except (
            TypeError,
            ValueError
        ):

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

        guild_ids = self.guild_id_variants(
            guild_id
        )

        # =================================================
        # النظام الجديد
        # =================================================

        setting = await self.website_command_settings.find_one(
            {
                "guild_id": {
                    "$in": guild_ids
                },
                "command_name": str(
                    command_name
                )
            }
        )

        if setting is not None:
            return setting

        # =================================================
        # دعم النظام القديم
        # =================================================

        setting = await self.website_command_settings.find_one(
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
    # صلاحية الأمر من الموقع
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

        setting = await self.get_command_setting(
            member.guild.id,
            command_name
        )

        # =================================================
        # لا يوجد إعداد للموقع
        # =================================================

        if setting is None:

            return True

        # =================================================
        # الأمر معطل
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

        if channel_ids:

            if channel_id is None:
                return False

            allowed_channel_ids = {
                str(cid)
                for cid in channel_ids
            }

            if str(channel_id) not in allowed_channel_ids:

                return False

        return True

    # =====================================================
    # الحصول على صاحب البوت
    # =====================================================

    async def get_bot_owner_id(self):

        if self.bot_owner_id is not None:
            return self.bot_owner_id

        async with self.owner_lock:

            if self.bot_owner_id is not None:
                return self.bot_owner_id

            try:

                application = (
                    await self.bot.application_info()
                )

                if application.owner:

                    self.bot_owner_id = (
                        application.owner.id
                    )

            except Exception as error:

                print(
                    f"[MinesGame] Owner Error: {error}"
                )

                return None

        return self.bot_owner_id

    # =====================================================
    # هل هو صاحب البوت؟
    # =====================================================

    async def is_bot_owner(
        self,
        user_id
    ):

        owner_id = await self.get_bot_owner_id()

        if owner_id is None:
            return False

        return int(user_id) == int(
            owner_id
        )

    # =====================================================
    # بيانات اللاعب
    # =====================================================

    async def get_user_data(
        self,
        guild_id,
        user_id
    ):

        guild_ids = self.guild_id_variants(
            guild_id
        )

        document = await self.game_data.find_one(
            {
                "guild_id": {
                    "$in": guild_ids
                },
                "user_id": str(
                    user_id
                )
            }
        )

        # =================================================
        # لاعب موجود
        # =================================================

        if document is not None:

            # =================================================
            # إصلاح البيانات القديمة
            # =================================================

            if "protection" not in document:

                await self.game_data.update_one(
                    {
                        "_id": document["_id"]
                    },
                    {
                        "$set": {
                            "protection": 0
                        }
                    }
                )

                document["protection"] = 0

            return document

        # =================================================
        # إنشاء اللاعب
        # =================================================

        document = {
            "guild_id": str(
                guild_id
            ),
            "user_id": str(
                user_id
            ),
            "gold": STARTING_GOLD,
            "protection": 0,
            "last_game_at": None,
            "last_golden_at": None,
            "created_at": datetime.now(
                timezone.utc
            )
        }

        try:

            await self.game_data.insert_one(
                document
            )

        except Exception:

            document = await self.game_data.find_one(
                {
                    "guild_id": {
                        "$in": guild_ids
                    },
                    "user_id": str(
                        user_id
                    )
                }
            )

            if document is not None:

                if "protection" not in document:

                    await self.game_data.update_one(
                        {
                            "_id": document["_id"]
                        },
                        {
                            "$set": {
                                "protection": 0
                            }
                        }
                    )

                    document["protection"] = 0

                return document

        return document

    # =====================================================
    # الحصول على الرصيد
    # =====================================================

    async def get_balance(
        self,
        guild_id,
        user_id
    ):

        document = await self.get_user_data(
            guild_id,
            user_id
        )

        return int(
            document.get(
                "gold",
                STARTING_GOLD
            )
        )

    # =====================================================
    # تغيير الذهب
    # =====================================================

    async def change_gold(
        self,
        guild_id,
        user_id,
        amount
    ):

        await self.get_user_data(
            guild_id,
            user_id
        )

        guild_ids = self.guild_id_variants(
            guild_id
        )

        # =================================================
        # خصم
        # =================================================

        if amount < 0:

            document = await self.game_data.find_one_and_update(
                {
                    "guild_id": {
                        "$in": guild_ids
                    },
                    "user_id": str(
                        user_id
                    ),
                    "gold": {
                        "$gte": abs(
                            amount
                        )
                    }
                },
                {
                    "$inc": {
                        "gold": amount
                    }
                },
                return_document=ReturnDocument.AFTER
            )

            if document is None:

                await self.game_data.update_one(
                    {
                        "guild_id": {
                            "$in": guild_ids
                        },
                        "user_id": str(
                            user_id
                        )
                    },
                    {
                        "$set": {
                            "gold": 0
                        }
                    }
                )

                return 0

            return int(
                document.get(
                    "gold",
                    0
                )
            )

        # =================================================
        # إضافة
        # =================================================

        document = await self.game_data.find_one_and_update(
            {
                "guild_id": {
                    "$in": guild_ids
                },
                "user_id": str(
                    user_id
                )
            },
            {
                "$inc": {
                    "gold": amount
                }
            },
            return_document=ReturnDocument.AFTER
        )

        if document is None:
            return 0

        return int(
            document.get(
                "gold",
                0
            )
        )

    # =====================================================
    # الحصول على الحماية
    # =====================================================

    async def get_protection(
        self,
        guild_id,
        user_id
    ):

        document = await self.get_user_data(
            guild_id,
            user_id
        )

        return min(
            MAX_PROTECTIONS,
            int(
                document.get(
                    "protection",
                    0
                )
            )
        )

    # =====================================================
    # شراء الحماية
    # =====================================================

    async def buy_protection(
        self,
        guild_id,
        user_id
    ):

        # =================================================
        # مهم جدًا:
        # هذا يصلح بيانات اللاعبين القديمة
        # ويضمن وجود protection قبل عملية الشراء
        # =================================================

        await self.get_user_data(
            guild_id,
            user_id
        )

        guild_ids = self.guild_id_variants(
            guild_id
        )

        # =================================================
        # محاولة الشراء بشكل ذري
        # =================================================

        document = await self.game_data.find_one_and_update(
            {
                "guild_id": {
                    "$in": guild_ids
                },
                "user_id": str(
                    user_id
                ),
                "gold": {
                    "$gte": PROTECTION_PRICE
                },
                "protection": {
                    "$lt": MAX_PROTECTIONS
                }
            },
            {
                "$inc": {
                    "gold": -PROTECTION_PRICE,
                    "protection": 1
                }
            },
            return_document=ReturnDocument.AFTER
        )

        # =================================================
        # تم الشراء
        # =================================================

        if document is not None:

            return {
                "status": "success",
                "gold": int(
                    document.get(
                        "gold",
                        0
                    )
                ),
                "protection": int(
                    document.get(
                        "protection",
                        0
                    )
                )
            }

        # =================================================
        # معرفة سبب فشل الشراء
        # =================================================

        current = await self.game_data.find_one(
            {
                "guild_id": {
                    "$in": guild_ids
                },
                "user_id": str(
                    user_id
                )
            }
        )

        if current is None:

            return {
                "status": "error"
            }

        # =================================================
        # حماية قديمة بدون الحقل
        # =================================================

        if "protection" not in current:

            await self.game_data.update_one(
                {
                    "_id": current["_id"]
                },
                {
                    "$set": {
                        "protection": 0
                    }
                }
            )

            current["protection"] = 0

        current_protection = int(
            current.get(
                "protection",
                0
            )
        )

        current_gold = int(
            current.get(
                "gold",
                0
            )
        )

        if current_protection >= MAX_PROTECTIONS:

            return {
                "status": "max"
            }

        if current_gold < PROTECTION_PRICE:

            return {
                "status": "insufficient"
            }

        return {
            "status": "error"
        }

    # =====================================================
    # استخدام حماية واحدة
    # =====================================================

    async def use_protection(
        self,
        guild_id,
        user_id
    ):

        await self.get_user_data(
            guild_id,
            user_id
        )

        guild_ids = self.guild_id_variants(
            guild_id
        )

        document = await self.game_data.find_one_and_update(
            {
                "guild_id": {
                    "$in": guild_ids
                },
                "user_id": str(
                    user_id
                ),
                "protection": {
                    "$gt": 0
                }
            },
            {
                "$inc": {
                    "protection": -1
                }
            },
            return_document=ReturnDocument.AFTER
        )

        return document is not None

    # =====================================================
    # تسجيل وقت آخر لعبة
    # =====================================================

    async def set_last_game_time(
        self,
        guild_id,
        user_id
    ):

        guild_ids = self.guild_id_variants(
            guild_id
        )

        await self.game_data.update_one(
            {
                "guild_id": {
                    "$in": guild_ids
                },
                "user_id": str(
                    user_id
                )
            },
            {
                "$set": {
                    "last_game_at": datetime.now(
                        timezone.utc
                    )
                }
            }
        )

    # =====================================================
    # حساب وقت انتظار اللعبة
    # =====================================================

    async def get_game_cooldown_remaining(
        self,
        guild_id,
        user_id
    ):

        document = await self.get_user_data(
            guild_id,
            user_id
        )

        last_game_at = document.get(
            "last_game_at"
        )

        if not last_game_at:
            return 0

        if last_game_at.tzinfo is None:

            last_game_at = last_game_at.replace(
                tzinfo=timezone.utc
            )

        elapsed = (
            datetime.now(
                timezone.utc
            )
            - last_game_at
        ).total_seconds()

        remaining = (
            GAME_COOLDOWN
            - elapsed
        )

        if remaining <= 0:
            return 0

        return max(
            1,
            int(remaining)
        )

    # =====================================================
    # تحويل مبلغ الإدخال
    # =====================================================

    def parse_gold_amount(
        self,
        amount
    ):

        if amount is None:
            return None

        clean_amount = (
            str(amount)
            .replace(",", "")
            .replace("٬", "")
            .replace("_", "")
            .strip()
        )

        if not clean_amount:
            return None

        try:

            return int(
                clean_amount
            )

        except ValueError:

            return None

    # =====================================================
    # أمر الغام
    # =====================================================

    @commands.command(
        name=COMMAND_MINES
    )
    async def mines_game(
        self,
        ctx
    ):

        if ctx.guild is None:
            return

        if not await self.has_command_permission(
            ctx.author,
            COMMAND_MINES,
            ctx.channel.id
        ):

            return

        guild_id = ctx.guild.id
        user_id = ctx.author.id

        active_key = (
            guild_id,
            user_id
        )

        if active_key in self.active_games:

            await ctx.send(
                f"{ctx.author.mention}\n"
                "⚠️ لديك لعبة قيد التشغيل بالفعل."
            )

            return

        remaining = await self.get_game_cooldown_remaining(
            guild_id,
            user_id
        )

        if remaining > 0:

            await ctx.send(
                f"{ctx.author.mention}\n"
                f"⏳ انتظر **{remaining} ثانية** قبل بدء لعبة جديدة."
            )

            return

        await self.get_user_data(
            guild_id,
            user_id
        )

        await self.set_last_game_time(
            guild_id,
            user_id
        )

        view = MinesView(
            self,
            guild_id,
            user_id
        )

        self.active_games[
            active_key
        ] = view

        embed = discord.Embed(
            title="💣 لعبة الألغام",
            description=(
                "🎯 **الهدف**\n"
                "افتح الخانات الآمنة وتجنب الألغام.\n\n"

                "🔢 **الأرقام**\n"
                "الرقم الموجود في الخانة يخبرك بعدد "
                "الألغام الموجودة حولها.\n\n"

                "✨ **الكشف التلقائي**\n"
                "إذا فتحت خانة رقمها 0، سيتم فتح المنطقة "
                "الآمنة المتصلة بها تلقائياً.\n\n"

                "🛡️ **الحماية**\n"
                f"يمكنك شراء الحماية من أمر **{COMMAND_PROTECTION}** "
                f"بسعر **{PROTECTION_PRICE:,} ذهب**، "
                f"وبحد أقصى **{MAX_PROTECTIONS}**.\n\n"

                "💰 **المكافآت**\n"
                f"🏆 الفوز: **+{WIN_GOLD:,} ذهب**\n"
                f"💥 الخسارة: **-{LOSS_GOLD:,} ذهب**\n\n"

                "⏱️ **الوقت:** دقيقتان\n"
                "💣 **عدد الألغام:** 5\n"
                "⬜ **حجم اللوحة:** 5 × 5"
            ),
            color=0x5865F2
        )

        try:

            message = await ctx.send(
                embed=embed,
                view=view
            )

            view.message = message

        except discord.HTTPException:

            self.active_games.pop(
                active_key,
                None
            )

    # =====================================================
    # أمر محفظتي
    # =====================================================

    @commands.command(
        name=COMMAND_WALLET
    )
    async def my_wallet(
        self,
        ctx
    ):

        if ctx.guild is None:
            return

        if not await self.has_command_permission(
            ctx.author,
            COMMAND_WALLET,
            ctx.channel.id
        ):

            return

        gold = await self.get_balance(
            ctx.guild.id,
            ctx.author.id
        )

        protection = await self.get_protection(
            ctx.guild.id,
            ctx.author.id
        )

        embed = discord.Embed(
            title="💰 محفظتي",
            description=(
                f"👤 اللاعب: {ctx.author.mention}\n\n"
                f"💰 رصيدك: **{gold:,} ذهب**\n"
                f"🛡️ الحماية: **{protection}/{MAX_PROTECTIONS}**"
            ),
            color=0xF1C40F
        )

        await ctx.send(
            embed=embed
        )

    # =====================================================
    # أمر ضيف
    # =====================================================

    @commands.command(
        name=COMMAND_ADD
    )
    async def add_gold(
        self,
        ctx,
        member: discord.Member = None,
        amount: str = None
    ):

        if ctx.guild is None:
            return

        if not await self.has_command_permission(
            ctx.author,
            COMMAND_ADD,
            ctx.channel.id
        ):

            return

        if not await self.is_bot_owner(
            ctx.author.id
        ):

            await ctx.send(
                "❌ هذا الأمر متاح لصاحب البوت فقط."
            )

            return

        if member is None:

            await ctx.send(
                "❌ الاستخدام الصحيح:\n"
                "`-ضيف @الشخص 1000000`"
            )

            return

        if amount is None:

            await ctx.send(
                "❌ الاستخدام الصحيح:\n"
                "`-ضيف @الشخص 1000000`"
            )

            return

        gold_amount = self.parse_gold_amount(
            amount
        )

        if gold_amount is None:

            await ctx.send(
                "❌ المبلغ يجب أن يكون رقماً صحيحاً."
            )

            return

        if gold_amount <= 0:

            await ctx.send(
                "❌ يجب أن يكون المبلغ أكبر من صفر."
            )

            return

        new_gold = await self.change_gold(
            ctx.guild.id,
            member.id,
            gold_amount
        )

        embed = discord.Embed(
            title="💰 تمت إضافة الذهب",
            description=(
                f"👤 اللاعب: {member.mention}\n\n"
                f"➕ المبلغ المضاف: **{gold_amount:,} ذهب**\n"
                f"💳 الرصيد الجديد: **{new_gold:,} ذهب**"
            ),
            color=0xF1C40F
        )

        await ctx.send(
            embed=embed
        )

    # =====================================================
    # أمر حمايتي
    # =====================================================

    @commands.command(
        name=COMMAND_PROTECTION
    )
    async def my_protection(
        self,
        ctx
    ):

        if ctx.guild is None:
            return

        if not await self.has_command_permission(
            ctx.author,
            COMMAND_PROTECTION,
            ctx.channel.id
        ):

            return

        gold = await self.get_balance(
            ctx.guild.id,
            ctx.author.id
        )

        protection = await self.get_protection(
            ctx.guild.id,
            ctx.author.id
        )

        embed = discord.Embed(
            title="🛡️ الحماية",
            description=(
                "احمِ نفسك من لغم واحد عند استخدام اللعبة.\n\n"
                f"🛡️ الحماية الحالية: **{protection}/{MAX_PROTECTIONS}**\n"
                f"💰 سعر الحماية الواحدة: **{PROTECTION_PRICE:,} ذهب**\n"
                f"💳 رصيدك الحالي: **{gold:,} ذهب**\n\n"
                "عند الضغط على لغم، سيتم استهلاك حماية واحدة "
                "بدلاً من خسارة الذهب."
            ),
            color=0x3498DB
        )

        view = ProtectionView(
            self,
            ctx.guild.id,
            ctx.author.id
        )

        if protection >= MAX_PROTECTIONS:

            view.buy_button.disabled = True

        await ctx.send(
            embed=embed,
            view=view
        )

    # =====================================================
    # أمر مين-توب
    # =====================================================

    @commands.command(
        name=COMMAND_TOP
    )
    async def mines_top(
        self,
        ctx
    ):

        if ctx.guild is None:
            return

        if not await self.has_command_permission(
            ctx.author,
            COMMAND_TOP,
            ctx.channel.id
        ):

            return

        guild_ids = self.guild_id_variants(
            ctx.guild.id
        )

        cursor = self.game_data.find(
            {
                "guild_id": {
                    "$in": guild_ids
                }
            }
        ).sort(
            "gold",
            -1
        ).limit(10)

        players = await cursor.to_list(
            length=10
        )

        if not players:

            await ctx.send(
                "❌ لا يوجد لاعبين لديهم رصيد حتى الآن."
            )

            return

        lines = []

        medals = [
            "🥇",
            "🥈",
            "🥉"
        ]

        used_users = set()

        for player in players:

            user_id = player.get(
                "user_id"
            )

            if user_id in used_users:
                continue

            used_users.add(
                user_id
            )

            index = len(lines) + 1

            try:

                member = ctx.guild.get_member(
                    int(user_id)
                )

            except (
                TypeError,
                ValueError
            ):

                member = None

            if member is not None:

                name = member.mention

            else:

                name = f"<@{user_id}>"

            gold = int(
                player.get(
                    "gold",
                    0
                )
            )

            if index <= 3:

                position = medals[index - 1]

            else:

                position = f"**{index}.**"

            lines.append(
                f"{position} {name} — **{gold:,} ذهب**"
            )

            if len(lines) >= 10:
                break

        embed = discord.Embed(
            title="🏆 مين-توب",
            description=(
                "💰 **أغنى اللاعبين في السيرفر**\n\n"
                + "\n".join(lines)
            ),
            color=0xF1C40F
        )

        await ctx.send(
            embed=embed
        )

    # =====================================================
    # أمر بعطيك-ذهب
    # =====================================================

    @commands.command(
        name=COMMAND_GIVE_GOLD
    )
    async def give_gold(
        self,
        ctx,
        member: discord.Member = None,
        amount: str = None
    ):

        if ctx.guild is None:
            return

        if not await self.has_command_permission(
            ctx.author,
            COMMAND_GIVE_GOLD,
            ctx.channel.id
        ):

            return

        if member is None:

            await ctx.send(
                "❌ الاستخدام الصحيح:\n"
                "`بعطيك-ذهب @الشخص 1000`"
            )

            return

        if member.id == ctx.author.id:

            await ctx.send(
                "❌ ما تقدر تحول الذهب لنفسك."
            )

            return

        if amount is None:

            await ctx.send(
                "❌ الاستخدام الصحيح:\n"
                "`بعطيك-ذهب @الشخص 1000`\n"
                "أو\n"
                "`بعطيك-ذهب @الشخص كامل`"
            )

            return

        if str(amount).strip().lower() == "كامل":

            gold_amount = await self.get_balance(
                ctx.guild.id,
                ctx.author.id
            )

        else:

            gold_amount = self.parse_gold_amount(
                amount
            )

        if gold_amount is None:

            await ctx.send(
                "❌ المبلغ يجب أن يكون رقماً صحيحاً أو `كامل`."
            )

            return

        if gold_amount <= 0:

            await ctx.send(
                "❌ يجب أن يكون المبلغ أكبر من صفر."
            )

            return

        sender_document = await self.game_data.find_one_and_update(
            {
                "guild_id": {
                    "$in": self.guild_id_variants(
                        ctx.guild.id
                    )
                },
                "user_id": str(
                    ctx.author.id
                ),
                "gold": {
                    "$gte": gold_amount
                }
            },
            {
                "$inc": {
                    "gold": -gold_amount
                }
            },
            return_document=ReturnDocument.AFTER
        )

        if sender_document is None:

            sender_balance = await self.get_balance(
                ctx.guild.id,
                ctx.author.id
            )

            await ctx.send(
                f"❌ رصيدك غير كافٍ.\n"
                f"💳 رصيدك الحالي: **{sender_balance:,} ذهب**"
            )

            return

        new_sender_gold = int(
            sender_document.get(
                "gold",
                0
            )
        )

        new_member_gold = await self.change_gold(
            ctx.guild.id,
            member.id,
            gold_amount
        )

        embed = discord.Embed(
            title="💰 تم تحويل الذهب",
            description=(
                f"👤 المرسل: {ctx.author.mention}\n"
                f"👤 المستلم: {member.mention}\n\n"
                f"💰 المبلغ: **{gold_amount:,} ذهب**\n"
                f"💳 رصيدك الحالي: **{new_sender_gold:,} ذهب**\n"
                f"💳 رصيد المستلم: **{new_member_gold:,} ذهب**"
            ),
            color=0x2ECC71
        )

        await ctx.send(
            embed=embed
        )

    # =====================================================
    # أمر هات-مصروف
    # =====================================================

    @commands.command(
        name=COMMAND_TAKE_GOLD
    )
    async def take_gold(
        self,
        ctx,
        member: discord.Member = None,
        amount: str = None
    ):

        if ctx.guild is None:
            return

        if not await self.has_command_permission(
            ctx.author,
            COMMAND_TAKE_GOLD,
            ctx.channel.id
        ):

            return

        if member is None:

            await ctx.send(
                "❌ الاستخدام الصحيح:\n"
                "`هات-مصروف @الشخص 1000`"
            )

            return

        if member.id == ctx.author.id:

            await ctx.send(
                "❌ ما تقدر تسحب الذهب من نفسك."
            )

            return

        if amount is None:

            await ctx.send(
                "❌ الاستخدام الصحيح:\n"
                "`هات-مصروف @الشخص 1000`\n"
                "أو\n"
                "`هات-مصروف @الشخص كامل`"
            )

            return

        if str(amount).strip().lower() == "كامل":

            gold_amount = await self.get_balance(
                ctx.guild.id,
                member.id
            )

        else:

            gold_amount = self.parse_gold_amount(
                amount
            )

        if gold_amount is None:

            await ctx.send(
                "❌ المبلغ يجب أن يكون رقماً صحيحاً أو `كامل`."
            )

            return

        if gold_amount <= 0:

            await ctx.send(
                "❌ يجب أن يكون المبلغ أكبر من صفر."
            )

            return

        target_document = await self.game_data.find_one_and_update(
            {
                "guild_id": {
                    "$in": self.guild_id_variants(
                        ctx.guild.id
                    )
                },
                "user_id": str(
                    member.id
                ),
                "gold": {
                    "$gte": gold_amount
                }
            },
            {
                "$inc": {
                    "gold": -gold_amount
                }
            },
            return_document=ReturnDocument.AFTER
        )

        if target_document is None:

            target_balance = await self.get_balance(
                ctx.guild.id,
                member.id
            )

            await ctx.send(
                f"❌ رصيد {member.mention} غير كافٍ.\n"
                f"💳 رصيده الحالي: **{target_balance:,} ذهب**"
            )

            return

        new_target_gold = int(
            target_document.get(
                "gold",
                0
            )
        )

        new_sender_gold = await self.change_gold(
            ctx.guild.id,
            ctx.author.id,
            gold_amount
        )

        embed = discord.Embed(
            title="💸 تم سحب المصروف",
            description=(
                f"👤 الشخص: {member.mention}\n"
                f"👤 المستلم: {ctx.author.mention}\n\n"
                f"💰 المبلغ المسحوب: **{gold_amount:,} ذهب**\n"
                f"💳 رصيد الشخص: **{new_target_gold:,} ذهب**\n"
                f"💳 رصيدك الحالي: **{new_sender_gold:,} ذهب**"
            ),
            color=0xE67E22
        )

        await ctx.send(
            embed=embed
        )

    # =====================================================
    # أمر ذهبي
    # =====================================================

    @commands.command(
        name=COMMAND_GOLDEN
    )
    async def golden_gold(
        self,
        ctx
    ):

        if ctx.guild is None:
            return

        if not await self.has_command_permission(
            ctx.author,
            COMMAND_GOLDEN,
            ctx.channel.id
        ):

            return

        guild_id = ctx.guild.id
        user_id = ctx.author.id

        document = await self.get_user_data(
            guild_id,
            user_id
        )

        last_golden_at = document.get(
            "last_golden_at"
        )

        if last_golden_at:

            if last_golden_at.tzinfo is None:

                last_golden_at = last_golden_at.replace(
                    tzinfo=timezone.utc
                )

            elapsed = (
                datetime.now(
                    timezone.utc
                )
                - last_golden_at
            ).total_seconds()

            remaining = (
                GOLDEN_COOLDOWN
                - elapsed
            )

            if remaining > 0:

                hours = int(
                    remaining // 3600
                )

                minutes = int(
                    (remaining % 3600) // 60
                )

                seconds = int(
                    remaining % 60
                )

                if hours > 0:

                    if minutes > 0:

                        time_text = (
                            f"**{hours} ساعة و {minutes} دقيقة**"
                        )

                    else:

                        time_text = (
                            f"**{hours} ساعة**"
                        )

                elif minutes > 0:

                    time_text = (
                        f"**{minutes} دقيقة و {seconds} ثانية**"
                    )

                else:

                    time_text = (
                        f"**{seconds} ثانية**"
                    )

                await ctx.send(
                    f"{ctx.author.mention}\n"
                    f"⏳ تقدر تستخدم الأمر الذهبي مرة ثانية بعد {time_text}."
                )

                return

        reward = random.randint(
            GOLDEN_MIN,
            GOLDEN_MAX
        )

        new_gold = await self.change_gold(
            guild_id,
            user_id,
            reward
        )

        await self.game_data.update_one(
            {
                "guild_id": {
                    "$in": self.guild_id_variants(
                        guild_id
                    )
                },
                "user_id": str(
                    user_id
                )
            },
            {
                "$set": {
                    "last_golden_at": datetime.now(
                        timezone.utc
                    )
                }
            }
        )

        embed = discord.Embed(
            title="✨ المكافأة الذهبية",
            description=(
                f"🎉 {ctx.author.mention} حصلت على مكافأة ذهبية!\n\n"
                f"💰 الذهب الذي حصلت عليه: **+{reward:,} ذهب**\n"
                f"💳 رصيدك الحالي: **{new_gold:,} ذهب**\n\n"
                "⏰ يمكنك استخدام المكافأة الذهبية مرة أخرى بعد **12 ساعة**."
            ),
            color=0xFFD700
        )

        await ctx.send(
            embed=embed
        )


# =========================================================
# Setup
# =========================================================

async def setup(bot):

    await bot.add_cog(
        MinesGame(bot)
    )
