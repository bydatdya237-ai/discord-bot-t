import os
import discord
from discord.ext import commands
from pymongo import MongoClient


# =========================================================
# إعدادات MongoDB
# =========================================================

MONGO_URI = os.getenv("MONGO_URI")

mongo = MongoClient(MONGO_URI)
db = mongo["discord_bot_db"]

welcome_settings_collection = db["welcome_settings"]


# =========================================================
# Welcome Cog
# =========================================================

class WelcomeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # =====================================================
    # عند دخول عضو جديد
    # =====================================================

    @commands.Cog.listener()
    async def on_member_join(self, member):

        try:
            settings = welcome_settings_collection.find_one({
                "guild_id": str(member.guild.id)
            })

            # لا توجد إعدادات للسيرفر
            if not settings:
                return

            # الترحيب غير مفعّل
            if not settings.get("enabled", False):
                return

            channel_id = settings.get("channel_id")
            message = settings.get("message", "")

            # لا يوجد روم
            if not channel_id:
                return

            # لا توجد رسالة
            if not message:
                return

            # محاولة تحويل ID الروم
            try:
                channel_id = int(channel_id)
            except (ValueError, TypeError):
                return

            # الحصول على الروم
            channel = member.guild.get_channel(channel_id)

            if channel is None:
                return

            # =================================================
            # المتغيرات المتاحة في رسالة الترحيب
            # =================================================

            message = str(message)

            message = message.replace(
                "{user}",
                member.mention
            )

            message = message.replace(
                "{username}",
                member.display_name
            )

            message = message.replace(
                "{server}",
                member.guild.name
            )

            message = message.replace(
                "{member_count}",
                str(member.guild.member_count)
            )

            # =================================================
            # إرسال رسالة الترحيب
            # =================================================

            await channel.send(message)

        except discord.Forbidden:
            # البوت لا يملك صلاحية الإرسال
            pass

        except discord.HTTPException:
            # خطأ من Discord API
            pass

        except Exception as e:
            print(f"[WelcomeCog] Error: {e}")


# =========================================================
# Setup
# =========================================================

async def setup(bot):
    await bot.add_cog(WelcomeCog(bot))
