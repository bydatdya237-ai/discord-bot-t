import os
from datetime import datetime, timezone

import discord
from discord.ext import commands
from pymongo import MongoClient


# =========================================================
# إعدادات MongoDB
# =========================================================

MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    raise RuntimeError(
        "❌ MONGO_URI غير موجود في Environment Variables"
    )

mongo_client = MongoClient(MONGO_URI)

db = mongo_client["discord_bot_db"]

commands_collection = db["website_commands"]


# =========================================================
# حفظ أوامر البوت
# =========================================================

def save_bot_commands(bot):

    commands_data = []

    for command in bot.commands:

        # تجاهل الأوامر المخفية
        if command.hidden:
            continue

        # تجاهل الأوامر الفرعية
        if command.parent is not None:
            continue

        commands_data.append({
            "name": command.name,
            "description": (
                command.help
                or command.description
                or "لا يوجد وصف لهذا الأمر."
            ),
            "aliases": list(command.aliases),
        })

    commands_data.sort(
        key=lambda x: x["name"].lower()
    )

    # حذف النسخة القديمة
    commands_collection.delete_many({})

    # حفظ النسخة الجديدة
    if commands_data:
        commands_collection.insert_many(
            commands_data
        )

    # حفظ وقت آخر تحديث
    db["website_settings"].update_one(
        {"_id": "commands"},
        {
            "$set": {
                "updated_at": datetime.now(
                    timezone.utc
                ),
                "commands_count": len(commands_data)
            }
        },
        upsert=True
    )

    print(
        "🌐 تم تحديث أوامر الموقع"
    )

    print(
        f"📋 عدد الأوامر المحفوظة: "
        f"{len(commands_data)}"
    )


# =========================================================
# Cog
# =========================================================

class WebsiteCommands(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        print(
            "🌐 WebsiteCommands تم تحميله"
        )


    @commands.Cog.listener()
    async def on_ready(self):

        # ننتظر قليلاً حتى تكون جميع الـ Cogs
        # قد تم تحميلها بالكامل
        await self.bot.wait_until_ready()

        save_bot_commands(
            self.bot
        )


# =========================================================
# تحميل الـ Cog
# =========================================================

async def setup(bot):

    await bot.add_cog(
        WebsiteCommands(bot)
    )

    print(
        "✅ WebsiteCommands جاهز"
    )
