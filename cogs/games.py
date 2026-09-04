import os
import discord
from discord.ext import commands
from pymongo import MongoClient

class GamesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        mongo_url = os.environ.get('MONGO_URI')
        self.client = MongoClient(mongo_url)
        self.db = self.client['discord_db']
        self.collection = self.db['users']

    @commands.command(name="العاب", help="يعرض لك قائمة الألعاب المتاحة")
    async def games_list(self, ctx):
        embed = discord.Embed(
            title="🎯 قائمة الألعاب",
            description="لعبتنا الحالية المتاحة لكسب النقاط:\n\n🎮 **!حظ** - اختبر حظك واربح نقاط عشوائية!",
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"طلب بواسطة {ctx.author.name}")
        await ctx.send(embed=embed)

    @commands.command(name="حظ", help="العب لعبة الححظ واربح نقاط تُحفظ في سحاب قاعدة البيانات")
    async def luck_game(self, ctx):
        import random
        user_id = str(ctx.author.id)
        earned_points = random.randint(10, 50)
        
        # تحديث النقاط أو إنشاؤها لو العضو جديد مع حفظ اسمه
        user_data = self.collection.find_one({"user_id": user_id})
        if user_data:
            current_points = user_data.get("points", 0) + earned_points
            self.collection.update_one({"user_id": user_id}, {"$set": {"points": current_points, "name": ctx.author.name}})
        else:
            current_points = earned_points
            self.collection.insert_one({"user_id": user_id, "name": ctx.author.name, "points": current_points})

        embed = discord.Embed(
            title="🎲 لعبة الحظ",
            description=f"مبروك يا **{ctx.author.name}** ربحت **{earned_points}** نقطة!\n💰 مجموع نقاطك الحالي: **{current_points}**",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    @commands.command(name="رصيد", help="يعرض رصيدك الحالي من النقاط المخزنة")
    async def balance(self, ctx):
        user_id = str(ctx.author.id)
        user_data = self.collection.find_one({"user_id": user_id})
        points = user_data.get("points", 0) if user_data else 0

        embed = discord.Embed(
            title="💳 رصيد النقاط",
            description=f"يا **{ctx.author.name}**، رصيدك المخزن بالسحاب هو: **{points}** نقطة 🪙",
            color=discord.Color.gold()
        )
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(GamesCog(bot))
