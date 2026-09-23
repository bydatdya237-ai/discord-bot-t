import os
import asyncio
import traceback
from datetime import datetime, timezone

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

    print("🌐 [WEBSITE] بدء قراءة أوامر البوت...")

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

    # ترتيب الأوامر
    commands_data.sort(
        key=lambda x: x["name"].lower()
    )

    print(
        f"📋 [WEBSITE] تم العثور على "
        f"{len(commands_data)} أمر"
    )

    # حذف القائمة القديمة
    commands_collection.delete_many({})

    # إضافة القائمة الجديدة
    if commands_data:

        commands_collection.insert_many(
            commands_data
        )

    # حفظ معلومات التحديث
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
        "✅ [WEBSITE] تم حفظ أوامر البوت في MongoDB"
    )

    print(
        f"📦 [WEBSITE] العدد المحفوظ: "
        f"{len(commands_data)}"
    )


# =========================================================
# Cog
# =========================================================

class WebsiteCommands(commands.Cog):

    def __init__(self, bot):

        self.bot = bot
        self.updated = False

        print(
            "🌐 [WEBSITE] WebsiteCommands تم تحميله"
        )


    @commands.Cog.listener()
    async def on_ready(self):

        # منع تكرار الحفظ إذا Discord أعاد
        # اتصال البوت بدون إعادة تشغيل البرنامج
        if self.updated:
            return

        self.updated = True

        print(
            "🌐 [WEBSITE] البوت أصبح جاهزًا"
        )

        # نعطي جميع الـ Cogs وقتًا إضافيًا
        await asyncio.sleep(5)

        try:

            save_bot_commands(
                self.bot
            )

        except Exception as error:

            print(
                "❌ [WEBSITE] حدث خطأ أثناء حفظ الأوامر"
            )

            print(
                f"❌ نوع الخطأ: "
                f"{type(error).__name__}"
            )

            print(
                f"❌ الخطأ: {error}"
            )

            traceback.print_exc()


# =========================================================
# تحميل الـ Cog
# =========================================================

async def setup(bot):

    await bot.add_cog(
        WebsiteCommands(bot)
    )

    print(
        "✅ [WEBSITE] WebsiteCommands جاهز"
    )
