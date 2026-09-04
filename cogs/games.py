import os
import random
import discord
from discord.ext import commands
from discord import app_commands
from pymongo import MongoClient

class GamesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        mongo_url = os.environ.get('MONGO_URI')
        self.client = MongoClient(mongo_url)
        self.db = self.client['discord_db']
        self.collection = self.db['users']

    @app_commands.command(name="العاب", description="يعرض لك قائمة الألعاب المتاحة")
    async def games_list(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎯 قائمة الألعاب",
            description="لعبتنا الحالية المتاحة لكسب النقاط:\n\n🎮 **/حظ** - اختبر حظك واربح نقاط عشوائية!",
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"طلب بواسطة {interaction.user.name}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="حظ", description="العب لعبة الحظ واربح نقاط تُحفظ في سحاب قاعدة البيانات")
    async def luck_game(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        earned_points = random.randint(10, 50)
        
        # تحديث النقاط أو إنشاؤها لو العضو جديد مع حفظ اسمه
        user_data = self.collection.find_one({"user_id": user_id})
        if user_data:
            current_points = user_data.get("points", 0) + earned_points
            self.collection.update_one({"user_id": user_id}, {"$set": {"points": current_points, "name": interaction.user.name}})
        else:
            current_points = earned_points
            self.collection.insert_one({"user_id": user_id, "name": interaction.user.name, "points": current_points})

        embed = discord.Embed(
            title="🎲 لعبة الحظ",
            description=f"مبروك يا **{interaction.user.name}** ربحت **{earned_points}** نقطة!\n💰 مجموع نقاطك الحالي: **{current_points}**",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="رصيد", description="يعرض رصيدك الحالي من النقاط المخزنة")
    async def balance(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        user_data = self.collection.find_one({"user_id": user_id})
        points = user_data.get("points", 0) if user_data else 0

        embed = discord.Embed(
            title="💳 رصيد النقاط",
            description=f"يا **{interaction.user.name}**، رصيدك المخزن بالسحاب هو: **{points}** نقطة 🪙",
            color=discord.Color.gold()
        )
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(GamesCog(bot))
