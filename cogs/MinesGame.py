import asyncio
import random

import discord
from discord.ext import commands


# =========================================================
# الاعدادات
# =========================================================

GAME_ROOM_ID = 1547418557032308830
GOLD_ROLE_ID = 1545608277159579718

GAME_COOLDOWN = 30
GAME_TIMEOUT = 120

STARTING_GOLD = 1000
WIN_GOLD = 50
LOSS_GOLD = 35


# =========================================================
# لعبة الالغام
# =========================================================

class MinesView(discord.ui.View):

    def __init__(self, cog, user_id):
        super().__init__(timeout=GAME_TIMEOUT)

        self.cog = cog
        self.user_id = user_id

        self.total_cells = 25
        self.total_mines = 5

        self.game_over = False
        self.revealed = set()
        self.processing = False
        self.message = None

        self.mines = set()

        while len(self.mines) < self.total_mines:
            self.mines.add(
                random.randint(0, 24)
            )

        # انشاء شبكة 5x5
        for index in range(25):

            button = discord.ui.Button(
                style=discord.ButtonStyle.secondary,
                label="؟",
                row=index // 5,
                custom_id=f"mine_{index}"
            )

            button.callback = self.button_callback

            self.add_item(button)

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
    # حذف اللعبة من الالعاب النشطة
    # =====================================================

    def remove_active_game(self):

        self.cog.active_games.pop(
            self.user_id,
            None
        )

    # =====================================================
    # حساب عدد الالغام حول خانة
    # =====================================================

    def get_nearby_mines(self, index):

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
    # الحصول على الخانات المحيطة
    # =====================================================

    def get_neighbors(self, index):

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

    def reveal_safe_area(self, start_index):

        to_check = [start_index]
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

            # اذا كانت الخانة 0
            # نفتح المنطقة الآمنة المتصلة بها
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
    # تحديث شكل الازرار
    # =====================================================

    def update_buttons(self):

        for child in self.children:

            if child.custom_id is None:
                continue

            try:

                index = int(
                    child.custom_id.split("_")[1]
                )

            except (ValueError, IndexError):

                continue

            # خانة تم كشفها
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
    # اظهار الالغام عند الخسارة فقط
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

            except (ValueError, IndexError):

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

        # عند انتهاء الوقت لا نكشف الالغام
        for child in self.children:
            child.disabled = True

        if self.message is None:
            return

        embed = discord.Embed(
            title="💣 لعبة الألغام",
            description=(
                "⏰ انتهى الوقت!\n\n"
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

    async def button_callback(self, interaction):

        # التأكد من صاحب اللعبة
        if interaction.user.id != self.user_id:

            await interaction.response.send_message(
                "❌ هذه اللعبة ليست لك.",
                ephemeral=True
            )

            return

        # اللعبة منتهية
        if self.game_over:

            await interaction.response.send_message(
                "❌ انتهت هذه اللعبة بالفعل.",
                ephemeral=True
            )

            return

        # منع الضغط المتزامن
        if self.processing:

            await interaction.response.send_message(
                "⏳ انتظر لحظة...",
                ephemeral=True
            )

            return

        self.processing = True

        try:

            # =================================================
            # قراءة رقم الخانة
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

            # الخانة مفتوحة مسبقا
            if index in self.revealed:

                await interaction.response.send_message(
                    "⚠️ هذه الخانة مفتوحة بالفعل.",
                    ephemeral=True
                )

                return

            # =================================================
            # اذا كانت لغم
            # =================================================

            if index in self.mines:

                self.game_over = True

                self.remove_active_game()

                # عند الخسارة فقط تظهر الالغام
                self.reveal_all_mines()

                current_gold = self.cog.get_balance(
                    self.user_id
                )

                new_gold = max(
                    0,
                    current_gold - LOSS_GOLD
                )

                self.cog.user_balances[
                    self.user_id
                ] = new_gold

                embed = discord.Embed(
                    title="💥 انفجر اللغم!",
                    description=(
                        "💣 للأسف اخترت لغماً.\n\n"
                        f"💰 الذهب المخصوم: -{LOSS_GOLD:,}\n"
                        f"💳 رصيدك الحالي: {new_gold:,}"
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

            # اذا كانت 0 نفتح المنطقة تلقائيا
            if nearby_mines == 0:

                self.reveal_safe_area(
                    index
                )

            else:

                # اذا كانت 1 او اكثر نفتح الخانة فقط
                self.revealed.add(
                    index
                )

            # تحديث الواجهة
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

                # عند الفوز لا نكشف مواقع الالغام
                for child in self.children:
                    child.disabled = True

                current_gold = self.cog.get_balance(
                    self.user_id
                )

                new_gold = (
                    current_gold
                    + WIN_GOLD
                )

                self.cog.user_balances[
                    self.user_id
                ] = new_gold

                embed = discord.Embed(
                    title="🏆 فوز!",
                    description=(
                        "🎉 مبروك! لقد فتحت جميع الخانات الآمنة.\n\n"
                        f"💰 الجائزة: +{WIN_GOLD:,}\n"
                        f"💳 رصيدك الحالي: {new_gold:,}"
                    ),
                    color=0x2ECC71
                )

                await interaction.response.edit_message(
                    embed=embed,
                    view=self
                )

                return

            # =================================================
            # تحديث اللعبة
            # =================================================

            await interaction.response.edit_message(
                view=self
            )

        finally:

            self.processing = False


# =========================================================
# Mines Game Cog
# =========================================================

class MinesGame(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        self.user_balances = {}

        self.active_games = {}

        self.last_game_time = {}

    # =====================================================
    # جلب الرصيد
    # =====================================================

    def get_balance(self, user_id):

        if user_id not in self.user_balances:

            self.user_balances[
                user_id
            ] = STARTING_GOLD

        return self.user_balances[
            user_id
        ]

    # =====================================================
    # التأكد من الروم
    # =====================================================

    def is_game_channel(self, ctx):

        return (
            ctx.channel.id
            == GAME_ROOM_ID
        )

    # =====================================================
    # امر الغام
    # =====================================================

    @commands.command(name="الغام")
    async def mines_game(self, ctx):

        if not self.is_game_channel(ctx):
            return

        user_id = ctx.author.id

        # منع اكثر من لعبة
        if user_id in self.active_games:

            await ctx.send(
                f"{ctx.author.mention}\n"
                "⚠️ لديك لعبة قيد التشغيل بالفعل."
            )

            return

        # =================================================
        # الكول داون - 30 ثانية
        # =================================================

        current_time = (
            asyncio.get_running_loop().time()
        )

        last_time = self.last_game_time.get(
            user_id
        )

        if last_time is not None:

            elapsed = (
                current_time
                - last_time
            )

            if elapsed < GAME_COOLDOWN:

                remaining = max(
                    1,
                    int(
                        GAME_COOLDOWN
                        - elapsed
                    )
                )

                await ctx.send(
                    f"{ctx.author.mention}\n"
                    f"⏳ انتظر {remaining} ثانية قبل بدء لعبة جديدة."
                )

                return

        self.last_game_time[
            user_id
        ] = current_time

        # انشاء الرصيد
        self.get_balance(
            user_id
        )

        # انشاء اللعبة
        view = MinesView(
            self,
            user_id
        )

        self.active_games[
            user_id
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
                f"🏆 الفوز: +{WIN_GOLD:,} ذهب\n"
                f"💥 الخسارة: -{LOSS_GOLD:,} ذهب\n\n"

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
                user_id,
                None
            )

    # =====================================================
    # امر محفظتي
    # =====================================================

    @commands.command(name="محفظتي")
    async def my_wallet(self, ctx):

        if not self.is_game_channel(ctx):
            return

        user_id = ctx.author.id

        gold = self.get_balance(
            user_id
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
    # امر ضيف
    # =====================================================

    @commands.command(name="ضيف")
    async def add_gold(
        self,
        ctx,
        member: discord.Member = None,
        amount: str = None
    ):

        if not self.is_game_channel(ctx):
            return

        if ctx.guild is None:
            return

        # البحث عن الرتبة
        role = ctx.guild.get_role(
            GOLD_ROLE_ID
        )

        if role is None:

            await ctx.send(
                "❌ لم يتم العثور على الرتبة المطلوبة."
            )

            return

        # التأكد من امتلاك الرتبة
        if role not in ctx.author.roles:

            await ctx.send(
                "❌ ليس لديك صلاحية استخدام هذا الأمر."
            )

            return

        # عدم وجود شخص
        if member is None:

            await ctx.send(
                "❌ الاستخدام الصحيح:\n"
                "`-ضيف @الشخص 1000000`"
            )

            return

        # عدم وجود مبلغ
        if amount is None:

            await ctx.send(
                "❌ الاستخدام الصحيح:\n"
                "`-ضيف @الشخص 1000000`"
            )

            return

        # تنظيف الرقم
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

        # منع المبلغ صفر او السالب
        if gold_amount <= 0:

            await ctx.send(
                "❌ يجب أن يكون المبلغ أكبر من صفر."
            )

            return

        # الرصيد الحالي
        current_gold = self.get_balance(
            member.id
        )

        # الرصيد الجديد
        new_gold = (
            current_gold
            + gold_amount
        )

        self.user_balances[
            member.id
        ] = new_gold

        # رسالة النجاح
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


# =========================================================
# SETUP
# =========================================================

async def setup(bot):

    await bot.add_cog(
        MinesGame(bot)
    )
