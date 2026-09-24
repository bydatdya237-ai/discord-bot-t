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
                label="؟",
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

            if index in self.revealed:

                child.disabled = True

                nearby_mines = self.get_nearby_mines(
                    index
                )

                if nearby_mines == 0:

                    child.style = (
                        discord.ButtonStyle.success
                    )

                    child.label = "0"

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

                child.label = "؟"

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
            # الخانة مفتوحة
            # =================================================

            if index in self.revealed:

                await interaction.response.send_message(
                    "⚠️ هذه الخانة مفتوحة بالفعل.",
                    ephemeral=True
                )

                return

            # =================================================
            # لغم
            # =================================================

            if index in self.mines:

                self.game_over = True

                self.remove_active_game()

                self.reveal_all_mines()

                new_gold = await self.cog.change_gold(
                    self.guild_id,
                    self.user_id,
                    -LOSS_GOLD
                )

                embed = discord.Embed(
                    title="💥 انفجر اللغم!",
                    description=(
                        "💣 للأسف اخترت لغماً.\n\n"
                        f"💰 الذهب المخصوم: **-{LOSS_GOLD:,}**\n"
                        f"💳 رصيدك الحالي: **{new_gold:,} ذهب**"
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

                embed = discord.Embed(
                    title="🏆 فوز!",
                    description=(
                        "🎉 **مبروك! لقد فتحت جميع الخانات الآمنة.**\n\n"
                        f"💰 الجائزة: **+{WIN_GOLD:,} ذهب**\n"
                        f"💳 رصيدك الحالي: **{new_gold:,} ذهب**"
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

        if document is not None:
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

        # =================================================
        # تحكم الموقع
        # =================================================

        if not await self.has_command_permission(
            ctx.author,
            COMMAND_MINES,
            ctx.channel.id
        ):

            return

        guild_id = ctx.guild.id
        user_id = ctx.author.id

        # =================================================
        # مفتاح اللعبة
        # =================================================

        active_key = (
            guild_id,
            user_id
        )

        # =================================================
        # منع لعبة ثانية
        # =================================================

        if active_key in self.active_games:

            await ctx.send(
                f"{ctx.author.mention}\n"
                "⚠️ لديك لعبة قيد التشغيل بالفعل."
            )

            return

        # =================================================
        # الكول داون
        # =================================================

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

        # =================================================
        # إنشاء بيانات اللاعب
        # =================================================

        await self.get_user_data(
            guild_id,
            user_id
        )

        # =================================================
        # تسجيل بداية اللعبة
        # =================================================

        await self.set_last_game_time(
            guild_id,
            user_id
        )

        # =================================================
        # إنشاء اللعبة
        # =================================================

        view = MinesView(
            self,
            guild_id,
            user_id
        )

        self.active_games[
            active_key
        ] = view

        # =================================================
        # واجهة اللعبة
        # =================================================

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

        embed = discord.Embed(
            title="💰 محفظتي",
            description=(
                f"👤 اللاعب: {ctx.author.mention}\n\n"
                f"💰 رصيدك: **{gold:,} ذهب**"
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

        # =================================================
        # صاحب البوت فقط
        # =================================================

        if not await self.is_bot_owner(
            ctx.author.id
        ):

            await ctx.send(
                "❌ هذا الأمر متاح لصاحب البوت فقط."
            )

            return

        # =================================================
        # الشخص
        # =================================================

        if member is None:

            await ctx.send(
                "❌ الاستخدام الصحيح:\n"
                "`-ضيف @الشخص 1000000`"
            )

            return

        # =================================================
        # المبلغ
        # =================================================

        if amount is None:

            await ctx.send(
                "❌ الاستخدام الصحيح:\n"
                "`-ضيف @الشخص 1000000`"
            )

            return

        # =================================================
        # تنظيف الرقم
        # =================================================

        clean_amount = (
            amount
            .replace(",", "")
            .replace("٬", "")
            .replace("_", "")
            .strip()
        )

        try:

            gold_amount = int(
                clean_amount
            )

        except ValueError:

            await ctx.send(
                "❌ المبلغ يجب أن يكون رقماً صحيحاً."
            )

            return

        # =================================================
        # منع الصفر والسالب
        # =================================================

        if gold_amount <= 0:

            await ctx.send(
                "❌ يجب أن يكون المبلغ أكبر من صفر."
            )

            return

        # =================================================
        # إضافة الذهب
        # =================================================

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

        # =================================================
        # تحكم الموقع
        # =================================================

        if not await self.has_command_permission(
            ctx.author,
            COMMAND_GOLDEN,
            ctx.channel.id
        ):

            return

        guild_id = ctx.guild.id
        user_id = ctx.author.id

        # =================================================
        # الحصول على بيانات اللاعب
        # =================================================

        document = await self.get_user_data(
            guild_id,
            user_id
        )

        # =================================================
        # آخر استخدام
        # =================================================

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

        # =================================================
        # تحديد الجائزة
        # =================================================

        reward = random.randint(
            GOLDEN_MIN,
            GOLDEN_MAX
        )

        # =================================================
        # إضافة الذهب
        # =================================================

        new_gold = await self.change_gold(
            guild_id,
            user_id,
            reward
        )

        # =================================================
        # تسجيل وقت الاستخدام
        # =================================================

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

        # =================================================
        # رسالة المكافأة
        # =================================================

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
