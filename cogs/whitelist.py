import os
import discord
from discord.ext import commands
from discord import app_commands
from pymongo import MongoClient

class WhitelistCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        mongo_url = os.environ.get('MONGO_URI')
        self.client = MongoClient(mongo_url)
        self.db = self.client['discord_db']
        self.whitelist_collection = self.db['whitelist_admins']

    def _has_permission(self, interaction: discord.Interaction):
        # 1. صاحب السيرفر
        if interaction.user.id == interaction.guild.owner_id:
            return True
            
        # 2. المشرفون المضافون في قاعدة البيانات
        db_admin = self.whitelist_collection.find_one({"user_id": str(interaction.user.id)})
        if db_admin:
            return True
            
        return False

    @app_commands.command(name="تحديد", description="إضافة عضو لقائمة المشرفين (خاص بصاحب السيرفر)")
    @app_commands.describe(member="العضو المراد إضافته للمشرفين")
    async def add_whitelist(self, interaction: discord.Interaction, member: discord.Member):
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message("❌ عذراً، هذا الأمر مخصص لصاحب السيرفر فقط!", ephemeral=True)
            return

        user_id = str(member.id)
        existing = self.whitelist_collection.find_one({"user_id": user_id})
        
        if existing:
            await interaction.response.send_message(f"⚠️ العضو **{member.name}** مضاف مسبقاً!", ephemeral=True)
        else:
            self.whitelist_collection.insert_one({"user_id": user_id, "name": member.name})
            await interaction.response.send_message(f"✅ تم بنجاح إضافة **{member.name}** لقائمة المشرفين!")

    @app_commands.command(name="ازالة", description="إزالة عضو من قائمة المشرفين (خاص بصاحب السيرفر)")
    @app_commands.describe(member="العضو المراد إزالته من المشرفين")
    async def remove_whitelist(self, interaction: discord.Interaction, member: discord.Member):
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message("❌ عذراً، هذا الأمر مخصص لصاحب السيرفر فقط!", ephemeral=True)
            return

        user_id = str(member.id)
        result = self.whitelist_collection.delete_one({"user_id": user_id})
        
        if result.deleted_count > 0:
            await interaction.response.send_message(f"🗑️ تم إزالة **{member.name}** بنجاح.")
        else:
            await interaction.response.send_message(f"⚠️ العضو غير موجود أساساً في القائمة.", ephemeral=True)

    @app_commands.command(name="كشف", description="عرض قائمة المشرفين المعتمدين")
    async def show_whitelist(self, interaction: discord.Interaction):
        if not self._has_permission(interaction):
            await interaction.response.send_message("❌ عذراً، ليس لديك صلاحية!", ephemeral=True)
            return

        admins = list(self.whitelist_collection.find({}))
        
        embed = discord.Embed(
            title="🛡️ قائمة المشرفين المعتمدين",
            color=discord.Color.blue()
        )
        
        if admins:
            admins_list = "\n".join([f"• <@{admin['user_id']}>" for admin in admins])
            embed.add_field(name="📂 المشرفون بالسحاب:", value=admins_list, inline=False)
        else:
            embed.add_field(name="📂 المشرفون بالسحاب:", value="لا يوجد مشرفون إضافيون.", inline=False)

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(WhitelistCog(bot))
