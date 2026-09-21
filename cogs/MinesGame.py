import asyncio
import random

import discord
from discord.ext import commands


# =========================================================
# الإعدادات
# =========================================================

GAME_ROOM_ID = 1547418557032308830

GOLD_ROLE_ID = 1545608277159579718

GAME_COOLDOWN = 60          # دقيقة بين كل لعبة لكل لاعب
GAME_TIMEOUT = 120          # مدة اللعبة دقيقتان

STARTING_GOLD = 1000

LOSS_GOLD = 35
WIN_GOLD = 50


# =========================================================
# لعبة الألغام
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

        # لمنع ضغطتين في نفس اللحظة
        self.processing = False

        # رسالة اللعبة
        self.message = None

        # =================================================
        # إنشاء الألغام
        # =================================================

        self.mines = set()

        while len(self.mines) < self.total_mines:
            self.mines.add(random.randint(0, 24))

        # =================================================
        # إنشاء أزرار 5x5
        # =================================================

        for i in range(25):

            button = discord.ui.Button(
                style=discord.ButtonStyle.secondary,
                label="❓",
                row=i // 5,
                custom_id=f"mine_{i}"
            )

            button.callback = self.button_callback

            self.add_item(button)

    # =====================================================
    # لون الرقم حسب عدد الألغام
    # =====================================================

    @staticmethod
    def number_style(number):

        if number == 0:
            return discord.ButtonStyle.success

        if number == 1:
            return discord.ButtonStyle.primary

        if number == 2:
            return discord.ButtonStyle.success

        if number == 3:
            return discord.ButtonStyle.danger

        return discord.ButtonStyle.danger

    # =====================================================
    # تنظيف اللعبة
    # =====================================================

    def remove_active_game(self):

        self.cog.active_games.pop(
            self.user_id,
            None
        )

    # =====================================================
    # انتهاء الوقت
    # =====================================================

    async def on_timeout(self):

        if self.game_over:
            return

        self.game_over = True

        self.remove_active_game()

        # تعطيل كل الأزرار
        for child in self.children:

            child.disabled = True

            if child.custom_id:

                try:

                    index = int(
                        child.custom_id.split("_")[1]
                    )

                    # إظهار الألغام
                    if index in self.mines:
                        child.style = discord.ButtonStyle.danger
                        child.label = "💣"

                except (ValueError, IndexError):
                    pass

        if self.message is None:
            return

        embed = discord.Embed(
            title="💣 الألغام",
            description=(
                "━━━━━━━━━━━━━━━━━━\n"
                "⏰ **انتهى الوقت!**\n\n"
                "انتهت مدة اللعبة قبل أن تكشف جميع "
                "الخانات الآمنة.\n\n"
                "🪙 لم يتم خصم أو إضافة أي ذهب.\n"
                "━━━━━━━━━━━━━━━━━━"
            ),
            color=0x95A5A6
        )

        try:

            await self.message.edit(
                embed=embed,
                view=self
            )

        except discord.HTTPException:
            pass

    # =====================================================
    # الضغط على زر
    # =====================================================

    async def button_callback(
        self,
        interaction: discord.Interaction
    ):

        # =================================================
        # التأكد من صاحب اللعبة
        # =================================================

        if interaction.user.id != self.user_id:

            await interaction.response.send_message(
                "❌ هذه ليست لعبتك!",
                ephemeral=True
            )

            return

        # =================================================
        # التأكد من حالة اللعبة
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
            # قراءة رقم الخانة
            # =================================================

            try:

                idx = int(
                    interaction.data["custom_id"].split("_")[1]
                )

            except (ValueError, KeyError, IndexError):

                await interaction.response.send_message(
                    "❌ حدث خطأ في قراءة الخانة.",
                    ephemeral=True
                )

                return

            # =================================================
            # منع فتح الخانة مرتين
            # =================================================

            if idx in self.revealed:

                await interaction.response.send_message(
                    "⚠️ هذه الخانة مفتوحة بالفعل.",
                    ephemeral=True
                )

                return

            # =================================================
            # لغم
            # =================================================

            if idx in self.mines:

                self.game_over = True

                self.remove_active_game()

                # إظهار جميع الألغام
                for child in self.children:

                    child.disabled = True

                    if child.custom_id:

                        try:

                            button_index = int(
                                child.custom_id.split("_")[1]
                            )

                            if button_index in self.mines:

                                child.style = (
                                    discord.ButtonStyle.danger
                                )

                                child.label = "💣"

                        except (ValueError, IndexError):
                            pass

                # خصم الذهب
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
                    title="💥 الألغام",
                    description=(
                        "━━━━━━━━━━━━━━━━━━\n"
                        "💣 **انفجرت في لغم!**\n\n"
                        f"تم خصم **{LOSS_GOLD:,}** 🪙 من رصيدك.\n\n"
                        f"💰 رصيدك الحالي: "
                        f"**{new_gold:,}** ذهب\n"
                        "━━━━━━━━━━━━━━━━━━"
                    ),
                    color=0xE74C3C
                )

                await interaction.response.edit_message(
                    embed=embed,
                    view=self
                )

                return

            # =================================================
            # الخانة آمنة
            # =================================================

            self.revealed.add(idx)

            row, col = divmod(idx, 5)

            nearby_mines = 0

            for r in range(
                max(0, row - 1),
                min(5, row + 2)
            ):

                for c in range(
                    max(0, col - 1),
                    min(5, col + 2)
                ):

                    if r * 5 + c in self.mines:
                        nearby_mines += 1

            # =================================================
            # تحديث الزر
            # =================================================

            for child in self.children:

                if child.custom_id == f"mine_{idx}":

                    child.disabled = True

                    if nearby_mines == 0:

                        child.style = (
                            discord.ButtonStyle.success
                        )

                        child.label = "✓"

                    else:

                        child.style = self.number_style(
                            nearby_mines
                        )

                        child.label = str(
                            nearby_mines
                        )

                    break

            # =================================================
            # فوز
            # =================================================

            if len(self.revealed) >= (
                self.total_cells - self.total_mines
            ):

                self.game_over = True

                self.remove_active_game()

                # تعطيل جميع الأزرار
                for child in self.children:

                    child.disabled = True

                    if child.custom_id:

                        try:

                            button_index = int(
                                child.custom_id.split("_")[1]
                            )

                            if button_index in self.mines:

                                child.style = (
                                    discord.ButtonStyle.danger
                                )

                                child.label = "💣"

                        except (ValueError, IndexError):
                            pass

                # إضافة الذهب
                current_gold = self.cog.get_balance(
                    self.user_id
                )

                new_gold = current_gold + WIN_GOLD

                self.cog.user_balances[
                    self.user_id
                ] = new_gold

                embed = discord.Embed(
                    title="🏆 الألغام",
                    description=(
                        "━━━━━━━━━━━━━━━━━━\n"
                        "🎉 **فــــوز!**\n\n"
                        f"تمت إضافة **{WIN_GOLD:,}** 🪙 "
                        "إلى رصيدك.\n\n"
                        f"💰 رصيدك الحالي: "
                        f"**{new_gold:,}** ذهب\n"
                        "━━━━━━━━━━━━━━━━━━"
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
# Cog
# =========================================================

class MinesGame(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        # أرصدة اللاعبين
        self.user_balances = {}

        # الألعاب الحالية
        self.active_games = {}

        # آخر وقت بدأ فيه اللاعب لعبة
        self.last_game_time = {}

    # =====================================================
    # الحصول على الرصيد
    # =====================================================

    def get_balance(self, user_id):

        if user_id not in self.user_balances:

            self.user_balances[user_id] = STARTING_GOLD

        return self.user_balances[user_id]

    # =====================================================
    # التحقق من روم اللعبة
    # =====================================================

    def is_game_channel(self, ctx):

        return ctx.channel.id == GAME_ROOM_ID

    # =====================================================
    # لعبة الألغام
    # =====================================================

    @commands.command(name="الغام")
    async def mines_game(self, ctx):

        # لا يعمل إلا في الروم المحدد
        if not self.is_game_channel(ctx):
            return

        user_id = ctx.author.id

        # =================================================
        # منع لعبتين في نفس الوقت
        # =================================================

        if user_id in self.active_games:

            await ctx.send(
                f"⚠️ {ctx.author.mention}\n"
                "لديك لعبة ألغام قيد التشغيل بالفعل!"
            )

            return

        # =================================================
        # Cooldown
        # =================================================

        current_time = asyncio.get_running_loop().time()

        last_time = self.last_game_time.get(user_id)

        if last_time is not None:

            elapsed = current_time - last_time

            if elapsed < GAME_COOLDOWN:

                remaining = max(
                    1,
                    int(GAME_COOLDOWN - elapsed)
                )

                await ctx.send(
                    f"⏳ {ctx.author.mention}\n"
                    f"يمكنك اللعب مرة أخرى بعد "
                    f"**{remaining} ثانية**."
                )

                return

        # تسجيل وقت اللعبة
        self.last_game_time[user_id] = current_time

        # إنشاء الرصيد
        self.get_balance(user_id)

        # =================================================
        # إنشاء اللعبة
        # =================================================

        view = MinesView(
            self,
            user_id
        )

        self.active_games[user_id] = view

        embed = discord.Embed(
            title="💣 الألغام",
            description=(
                "━━━━━━━━━━━━━━━━━━\n"
                "🎮 **اختبر حظك وذكاءك!**\n\n"
                "اكشف الخانات الآمنة وتجنب الألغام.\n"
                "الأرقام تخبرك بعدد الألغام الموجودة "
                "حول الخانة.\n\n"
                f"🏆 الفوز: **+{WIN_GOLD:,} 🪙**\n"
                f"💥 الخسارة: **-{LOSS_GOLD:,} 🪙**\n\n"
                "⏱️ مدة اللعبة: **2:00**\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "🍀 **حظًا موفقًا!**"
            ),
            color=0x5865F2
        )

        message = await ctx.send(
            embed=embed,
            view=view
        )

        view.message = message

    # =====================================================
    # الرصيد
    # =====================================================

    @commands.command(name="رصيد")
    async def check_balance(self, ctx):

        if not self.is_game_channel(ctx):
            return

        user_id = ctx.author.id

        gold = self.get_balance(user_id)

        embed = discord.Embed(
            title="💰 رصيدك",
            description=(
                "━━━━━━━━━━━━━━━━━━\n"
                f"👤 اللاعب: {ctx.author.mention}\n\n"
                f"🪙 الذهب:\n"
                f"**{gold:,}**\n"
                "━━━━━━━━━━━━━━━━━━"
            ),
            color=0xF1C40F
        )

        await ctx.send(embed=embed)

    # =====================================================
    # إضافة الذهب
    #
    # الاستخدام:
    #
    # -اضافة @الشخص 1000000
    #
    # =====================================================

    @commands.command(name="اضافة")
    async def add_gold(
        self,
        ctx,
        member: discord.Member = None,
        amount: str = None
    ):

        # لا يعمل إلا في روم اللعبة
        if not self.is_game_channel(ctx):
            return

        # =================================================
        # التحقق من الرتبة
        # =================================================

        if ctx.guild is None:
            return

        role = ctx.guild.get_role(
            GOLD_ROLE_ID
        )

        if role is None:

            await ctx.send(
                "❌ رتبة إضافة الذهب غير موجودة."
            )

            return

        if role not in ctx.author.roles:

            await ctx.send(
                "❌ ليس لديك صلاحية استخدام أمر إضافة الذهب."
            )

            return

        # =================================================
        # التحقق من الشخص
        # =================================================

        if member is None:

            await ctx.send(
                "❌ الاستخدام الصحيح:\n"
                "`-اضافة @الشخص 1000000`"
            )

            return

        # =================================================
        # التحقق من المبلغ
        # =================================================

        if amount is None:

            await ctx.send(
                "❌ اكتب المبلغ بعد الشخص.\n"
                "مثال:\n"
                "`-اضافة @الشخص 1000000`"
            )

            return

        # إزالة الفواصل
        clean_amount = (
            amount
            .replace(",", "")
            .replace("٬", "")
            .strip()
        )

        try:

            gold_amount = int(
                clean_amount
            )

        except ValueError:

            await ctx.send(
                "❌ المبلغ يجب أن يكون رقمًا.\n"
                "مثال:\n"
                "`-اضافة @الشخص 1000000`"
            )

            return

        # منع الصفر والسالب
        if gold_amount <= 0:

            await ctx.send(
                "❌ يجب أن يكون المبلغ أكبر من 0."
            )

            return

        # =================================================
        # إضافة الذهب
        # =================================================

        current_gold = self.get_balance(
            member.id
        )

        new_gold = current_gold + gold_amount

        self.user_balances[
            member.id
        ] = new_gold

        # =================================================
        # رسالة النجاح
        # =================================================

        embed = discord.Embed(
            title="🪙 إضافة ذهب",
            description=(
                "━━━━━━━━━━━━━━━━━━\n"
                f"👤 اللاعب: {member.mention}\n\n"
                f"➕ تمت إضافة:\n"
                f"**{gold_amount:,}** 🪙\n\n"
                f"💰 الرصيد الجديد:\n"
                f"**{new_gold:,}** 🪙\n"
                "━━━━━━━━━━━━━━━━━━"
            ),
            color=0xF1C40F
        )

        await ctx.send(
            embed=embed
        )


# =========================================================
# تحميل الـ Cog
# =========================================================

async def setup(bot):

    await bot.add_cog(
        MinesGame(bot)
    )

الاستخدام الآن:

-الغام

-رصيد

وإضافة الذهب صارت فقط:

-اضافة @الشخص 1000000

وتقدر حتى تكتب:

-اضافة @الشخص 1,000,000

وسيُحسب المبلغ 1,000,000 ذهب.

«ملاحظة مهمة: نظام الذهب في هذا الملف ما زال داخل الذاكرة، لذلك إعادة تشغيل البوت تصفّر الأرصدة. أما مشكلة أمر "-اضافة" نفسها فتم تغيير طريقة استقبال المبلغ والعضو بحيث تطابق الصيغة التي طلبتها.»

ولو قصدك بـ "اللعبة تعلق" أنها أحيانًا تكون الأزرار ما تستجيب رغم أن البوت شغال، فالنسخة فوق عالجت حالات الضغط المتزامن وانتهاء المهلة.
