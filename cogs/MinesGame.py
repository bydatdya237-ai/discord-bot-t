import asyncio
import random

import discord
from discord.ext import commands


# =========================================================
# SETTINGS
# =========================================================

GAME_ROOM_ID = 1547418557032308830
GOLD_ROLE_ID = 1545608277159579718

GAME_COOLDOWN = 60
GAME_TIMEOUT = 120

STARTING_GOLD = 1000
WIN_GOLD = 50
LOSS_GOLD = 35


# =========================================================
# MINES GAME VIEW
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
            self.mines.add(random.randint(0, 24))

        for index in range(25):

            button = discord.ui.Button(
                style=discord.ButtonStyle.secondary,
                label="?",
                row=index // 5,
                custom_id=f"mine_{index}"
            )

            button.callback = self.button_callback
            self.add_item(button)

    @staticmethod
    def get_number_style(number):

        if number == 1:
            return discord.ButtonStyle.primary

        if number == 2:
            return discord.ButtonStyle.success

        return discord.ButtonStyle.danger

    def remove_active_game(self):

        self.cog.active_games.pop(
            self.user_id,
            None
        )

    async def on_timeout(self):

        if self.game_over:
            return

        self.game_over = True
        self.remove_active_game()

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

                child.style = discord.ButtonStyle.danger
                child.label = "M"

        if self.message is None:
            return

        embed = discord.Embed(
            title="Mines",
            description=(
                "Time is over.\n\n"
                "The game has ended.\n"
                "No gold was added or removed."
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

    async def button_callback(self, interaction):

        if interaction.user.id != self.user_id:

            await interaction.response.send_message(
                "This is not your game.",
                ephemeral=True
            )

            return

        if self.game_over:

            await interaction.response.send_message(
                "This game has already ended.",
                ephemeral=True
            )

            return

        if self.processing:

            await interaction.response.send_message(
                "Please wait.",
                ephemeral=True
            )

            return

        self.processing = True

        try:

            try:

                custom_id = interaction.data["custom_id"]

                index = int(
                    custom_id.split("_")[1]
                )

            except (ValueError, KeyError, IndexError):

                await interaction.response.send_message(
                    "An error occurred.",
                    ephemeral=True
                )

                return

            if index in self.revealed:

                await interaction.response.send_message(
                    "This cell is already open.",
                    ephemeral=True
                )

                return

            # =================================================
            # HIT MINE
            # =================================================

            if index in self.mines:

                self.game_over = True
                self.remove_active_game()

                for child in self.children:

                    child.disabled = True

                    if child.custom_id is None:
                        continue

                    try:

                        child_index = int(
                            child.custom_id.split("_")[1]
                        )

                    except (ValueError, IndexError):
                        continue

                    if child_index in self.mines:

                        child.style = (
                            discord.ButtonStyle.danger
                        )

                        child.label = "M"

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
                    title="Mines - Game Over",
                    description=(
                        "You hit a mine.\n\n"
                        f"Gold lost: {LOSS_GOLD:,}\n"
                        f"Current gold: {new_gold:,}"
                    ),
                    color=0xE74C3C
                )

                await interaction.response.edit_message(
                    embed=embed,
                    view=self
                )

                return

            # =================================================
            # SAFE CELL
            # =================================================

            self.revealed.add(index)

            row, column = divmod(index, 5)

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

            for child in self.children:

                if child.custom_id == f"mine_{index}":

                    child.disabled = True

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

                    break

            # =================================================
            # WIN
            # =================================================

            if len(self.revealed) >= (
                self.total_cells - self.total_mines
            ):

                self.game_over = True
                self.remove_active_game()

                for child in self.children:

                    child.disabled = True

                    if child.custom_id is None:
                        continue

                    try:

                        child_index = int(
                            child.custom_id.split("_")[1]
                        )

                    except (ValueError, IndexError):
                        continue

                    if child_index in self.mines:

                        child.style = (
                            discord.ButtonStyle.danger
                        )

                        child.label = "M"

                current_gold = self.cog.get_balance(
                    self.user_id
                )

                new_gold = (
                    current_gold + WIN_GOLD
                )

                self.cog.user_balances[
                    self.user_id
                ] = new_gold

                embed = discord.Embed(
                    title="Mines - Victory",
                    description=(
                        "Congratulations!\n\n"
                        f"Gold received: +{WIN_GOLD:,}\n"
                        f"Current gold: {new_gold:,}"
                    ),
                    color=0x2ECC71
                )

                await interaction.response.edit_message(
                    embed=embed,
                    view=self
                )

                return

            await interaction.response.edit_message(
                view=self
            )

        finally:

            self.processing = False


# =========================================================
# MINES GAME COG
# =========================================================

class MinesGame(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        self.user_balances = {}
        self.active_games = {}
        self.last_game_time = {}

    # =====================================================
    # BALANCE
    # =====================================================

    def get_balance(self, user_id):

        if user_id not in self.user_balances:

            self.user_balances[user_id] = STARTING_GOLD

        return self.user_balances[user_id]

    # =====================================================
    # CHANNEL CHECK
    # =====================================================

    def is_game_channel(self, ctx):

        return ctx.channel.id == GAME_ROOM_ID

    # =====================================================
    # MINES COMMAND
    # =====================================================

    @commands.command(name="الغام")
    async def mines_game(self, ctx):

        if not self.is_game_channel(ctx):
            return

        user_id = ctx.author.id

        # Prevent multiple active games
        if user_id in self.active_games:

            await ctx.send(
                f"{ctx.author.mention}\n"
                "You already have an active game."
            )

            return

        # Cooldown
        current_time = asyncio.get_running_loop().time()

        last_time = self.last_game_time.get(
            user_id
        )

        if last_time is not None:

            elapsed = current_time - last_time

            if elapsed < GAME_COOLDOWN:

                remaining = max(
                    1,
                    int(GAME_COOLDOWN - elapsed)
                )

                await ctx.send(
                    f"{ctx.author.mention}\n"
                    f"Please wait {remaining} seconds."
                )

                return

        self.last_game_time[user_id] = current_time

        self.get_balance(user_id)

        view = MinesView(
            self,
            user_id
        )

        self.active_games[user_id] = view

        embed = discord.Embed(
            title="Mines",
            description=(
                "Find the safe cells and avoid the mines.\n\n"
                "The number on a cell tells you how many "
                "mines are around it.\n\n"
                f"WIN: +{WIN_GOLD:,} GOLD\n"
                f"LOSE: -{LOSS_GOLD:,} GOLD\n\n"
                "TIME: 2 MINUTES"
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
    # WALLET COMMAND
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
            title="Gold Wallet",
            description=(
                f"Player: {ctx.author.mention}\n\n"
                f"Gold: {gold:,}"
            ),
            color=0xF1C40F
        )

        await ctx.send(
            embed=embed
        )

    # =====================================================
    # ADD GOLD COMMAND
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

        role = ctx.guild.get_role(
            GOLD_ROLE_ID
        )

        if role is None:

            await ctx.send(
                "The required role was not found."
            )

            return

        # Check role
        if role not in ctx.author.roles:

            await ctx.send(
                "You do not have permission to use this command."
            )

            return

        # Check member
        if member is None:

            await ctx.send(
                "Correct usage:\n"
                "-ضيف @member 1000000"
            )

            return

        # Check amount
        if amount is None:

            await ctx.send(
                "Correct usage:\n"
                "-ضيف @member 1000000"
            )

            return

        # Clean number
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
                "The amount must be a valid number."
            )

            return

        if gold_amount <= 0:

            await ctx.send(
                "The amount must be greater than zero."
            )

            return

        current_gold = self.get_balance(
            member.id
        )

        new_gold = (
            current_gold + gold_amount
        )

        self.user_balances[
            member.id
        ] = new_gold

        embed = discord.Embed(
            title="Gold Added",
            description=(
                f"Player: {member.mention}\n\n"
                f"Added: +{gold_amount:,} GOLD\n"
                f"New balance: {new_gold:,} GOLD"
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
