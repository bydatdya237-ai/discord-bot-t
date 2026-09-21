import asyncio
import random

import discord
from discord.ext import commands


# =========================================================
# الإعدادات
# =========================================================

GAME_ROOM_ID = 1547418557032308830

GOLD_ROLE_ID = 1545608277159579718

GAME_COOLDOWN = 60

GAME_TIMEOUT = 120

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

        self.rows = 5
        self.cols = 5
        self.total_mines = 5

        self.game_over = False
        self.revealed = set()

        # إنشاء الألغام
        self.mines = set()

        while len(self.mines) < self.total_mines:
            self.mines.add(random.randint(0, 24))

        # إنشاء شبكة 5x5
        for i in range(25):

            button = discord.ui.Button(
                style=discord.ButtonStyle.secondary,
                label="\u200b",
                row=i // 5,
                custom_id=f"mine_{i}"
            )

            button.callback = self.button_callback

            self.add_item(button)

    # =====================================================
    # انتهاء وقت اللعبة
    # =====================================================

    async def on_timeout(self):

        if self.game_over:
            return

        self.game_over = True

        self.cog.active_games.pop(self.user_id, None)

        # تعطيل الأزرار
        for child in self.children:

            child.disabled = True

            if child.custom_id:

                try:
                    index = int(child.custom_id.split("_")[1])

                    if index in self.mines:
                        child.style = discord.ButtonStyle.danger
                        child.label = "💣"

                except (ValueError, IndexError):
                    pass

        # تعديل رسالة اللعبة إن كانت موجودة
        if hasattr(self, "message") and self.message:

            embed = discord.Embed(
                title="الألغام | ⏰",
                description=(
                    "انتهى وقت اللعبة!\n\n"
                    "⏱️ مدة اللعبة كانت **دقيقتين**.\n"
                    "لم يتم خصم أو إضافة ذهب."
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

    async def button_callback(self, interaction: discord.Interaction):

        # التأكد أن اللاعب هو صاحب اللعبة
        if interaction.user.id != self.user_id:

            await interaction.response.send_message(
                "❌ هذه ليست لعبتك!",
                ephemeral=True
            )

            return

        # التأكد أن اللعبة لم تنته
        if self.game_over:

            await interaction.response.send_message(
                "❌ انتهت اللعبة بالفعل!",
                ephemeral=True
            )

            return

        # الحصول على رقم الخانة
        try:
            idx = int(interaction.data["custom_id"].split("_")[1])
        except (ValueError, KeyError, IndexError):

            await interaction.response.send_message(
                "❌ حدث خطأ في اللعبة.",
                ephemeral=True
            )

            return

        # منع الضغط على خانة مفتوحة
        if idx in self.revealed:

            await interaction.response.send_message(
                "⚠️ هذه الخانة مفتوحة بالفعل.",
                ephemeral=True
            )

            return

        # =================================================
        # إذا كانت الخانة لغم
        # =================================================

        if idx in self.mines:

            self.game_over = True

            self.cog.active_games.pop(self.user_id, None)

            # تعطيل جميع الأزرار وكشف الألغام
            for child in self.children:

                child.disabled = True

                if child.custom_id:

                    try:
                        button_index = int(
                            child.custom_id.split("_")[1]
                        )

                        if button_index in self.mines:
                            child.style = discord.ButtonStyle.danger
                            child.label = "💣"

                    except (ValueError, IndexError):
                        pass

            # خصم الذهب
            current_gold = self.cog.get_balance(self.user_id)

            new_gold = max(
                0,
                current_gold - LOSS_GOLD
            )

            self.cog.user_balances[self.user_id] = new_gold

            embed = discord.Embed(
                title="الألغام | 💣",
                description=(
                    "لقد خسرت 😕\n\n"
                    f"تم خصم **{LOSS_GOLD}** ذهب من رصيدك.\n\n"
                    f"🪙 ذهبك الحالي: **{new_gold}**"
                ),
                color=0xE74C3C
            )

            await interaction.response.edit_message(
                embed=embed,
                view=self
            )

            return

        # =================================================
        # الخانة ليست لغم
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

        # تحديث الزر
        for child in self.children:

            if child.custom_id == f"mine_{idx}":

                child.style = discord.ButtonStyle.success

                child.label = (
                    str(nearby_mines)
                    if nearby_mines > 0
                    else " "
                )

                child.disabled = True

                break

        # =================================================
        # فوز اللاعب
        # =================================================

        if len(self.revealed) >= (
            25 - self.total_mines
        ):

            self.game_over = True

            self.cog.active_games.pop(
                self.user_id,
                None
            )

            # تعطيل كل الأزرار وكشف الألغام
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
                title="الألغام | 🎉",
                description=(
                    "مبروك! لقد فزت 🎉\n\n"
                    f"تمت إضافة **{WIN_GOLD}** ذهب إلى رصيدك.\n\n"
                    f"🪙 ذهبك الحالي: **{new_gold}**"
                ),
                color=0x2ECC71
            )

            await interaction.response.edit_message(
                embed=embed,
                view=self
            )

            return

        # تحديث اللعبة
        await interaction.response.edit_message(
            view=self
        )


# =========================================================
# Cog
# =========================================================

class MinesGame(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        # أرصدة الذهب
        self.user_balances = {}

        # الألعاب الحالية
        self.active_games = {}

        # وقت آخر لعبة لكل لاعب
        self.last_game_time = {}

    # =====================================================
    # الحصول على الرصيد
    # =====================================================

    def get_balance(self, user_id):

        if user_id not in self.user_balances:

            self.user_balances[user_id] = STARTING_GOLD

        return self.user_balances[user_id]

    # =====================================================
    # التحقق من الروم
    # =====================================================

    def is_game_channel(self, ctx):

        return ctx.channel.id == GAME_ROOM_ID

    # =====================================================
    # أمر الألغام
    # =====================================================

    @commands.command(name="الغام")
    async def mines_game(self, ctx):

        # تجاهل الأمر خارج الروم
        if not self.is_game_channel(ctx):
            return

        user_id = ctx.author.id

        # منع تشغيل أكثر من لعبة بنفس الوقت
        if user_id in self.active_games:

            await ctx.send(
                f"⚠️ {ctx.author.mention} "
                "لديك لعبة قيد التشغيل بالفعل!"
            )

            return

        # =================================================
        # Cooldown دقيقة
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
                    f"يمكنك لعب الألغام مرة أخرى بعد "
                    f"**{remaining} ثانية**."
                )

                return

        # تسجيل وقت بداية اللعبة
        self.last_game_time[user_id] = current_time

        # إنشاء الرصيد إذا لم يكن موجود
        self.get_balance(user_id)

        # إنشاء اللعبة
        view = MinesView(
            self,
            user_id
        )

        self.active_games[user_id] = view

        embed = discord.Embed(
            title="الألغام | 🎮",
            description=(
                "حاول تجنب الألغام من خلال تحليل "
                "الأرقام واتجاهات الأزرار.\n\n"
                f"🏆 الفوز: **+{WIN_GOLD} ذهب**\n"
                f"💣 الخسارة: **-{LOSS_GOLD} ذهب**\n\n"
                "⏱️ الوقت: **2:00**\n\n"
                "🍀 حظًا موفقًا!"
            ),
            color=0x3498DB
        )

        message = await ctx.send(
            embed=embed,
            view=view
        )

        # حفظ الرسالة حتى يتم تعديلها عند انتهاء الوقت
        view.message = message

    # =====================================================
    # أمر الرصيد
    # =====================================================

    @commands.command(name="رصيد")
    async def check_balance(self, ctx):

        # تجاهل الأمر خارج الروم
        if not self.is_game_channel(ctx):
            return

        user_id = ctx.author.id

        gold = self.get_balance(user_id)

        embed = discord.Embed(
            title="البنك | 💰",
            description=(
                f"مرحباً {ctx.author.mention}\n\n"
                "🪙 رصيدك الحالي من الذهب:\n"
                f"**{gold}**"
            ),
            color=0xF1C40F
        )

        await ctx.send(embed=embed)

    # =====================================================
    # أمر إضافة الذهب
    #
    # الاستخدام:
    # -اضافة ذهب @الشخص 500
    #
    # =====================================================

    @commands.command(
        name="اضافة",
        aliases=["اضافة-ذهب"]
    )
    async def add_gold(self, ctx, *args):

        # تجاهل الأمر خارج الروم
        if not self.is_game_channel(ctx):
            return

        # =================================================
        # التحقق من الرتبة
        # =================================================

        if ctx.guild is None:
            return

        role = ctx.guild.get_role(GOLD_ROLE_ID)

        if role is None:

            await ctx.send(
                "❌ لم يتم العثور على رتبة إضافة الذهب."
            )

            return

        if role not in ctx.author.roles:

            await ctx.send(
                "❌ ليس لديك صلاحية استخدام هذا الأمر."
            )

            return

        # =================================================
        # التحقق من الصيغة
        # =================================================

        if len(args) < 2:

            await ctx.send(
                "❌ الاستخدام الصحيح:\n"
                "`-اضافة ذهب @الشخص 500`"
            )

            return

        # أول كلمة يجب أن تكون ذهب
        if args[0] != "ذهب":

            await ctx.send(
                "❌ الاستخدام الصحيح:\n"
                "`-اضافة ذهب @الشخص 500`"
            )

            return

        # =================================================
        # الحصول على العضو
        # =================================================

        if not ctx.message.mentions:

            await ctx.send(
                "❌ يجب تحديد الشخص الذي تريد "
                "إضافة الذهب له."
            )

            return

        member = ctx.message.mentions[0]

        # =================================================
        # الحصول على المبلغ
        # =================================================

        try:

            amount = int(args[1])

        except ValueError:

            await ctx.send(
                "❌ مبلغ الذهب يجب أن يكون رقمًا صحيحًا."
            )

            return

        # منع الصفر والسالب
        if amount <= 0:

            await ctx.send(
                "❌ يجب أن يكون مقدار الذهب أكبر من 0."
            )

            return

        # =================================================
        # إضافة الذهب
        # =================================================

        current_gold = self.get_balance(member.id)

        new_gold = current_gold + amount

        self.user_balances[member.id] = new_gold

        # =================================================
        # رسالة النجاح
        # =================================================

        embed = discord.Embed(
            title="إضافة ذهب | 🪙",
            description=(
                f"تمت إضافة **{amount}** ذهب إلى "
                f"{member.mention} بنجاح.\n\n"
                f"💰 الرصيد الجديد: **{new_gold}** ذهب"
            ),
            color=0xF1C40F
        )

        await ctx.send(embed=embed)


# =========================================================
# تحميل الـ Cog
# =========================================================

async def setup(bot):

    await bot.add_cog(
        MinesGame(bot)
    )
