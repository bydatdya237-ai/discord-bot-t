import os
import asyncio
import traceback
from datetime import datetime, timezone

from discord.ext import commands
from pymongo import MongoClient


# =========================================================
# MongoDB
# =========================================================

MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    raise RuntimeError(
        "❌ MONGO_URI غير موجود في Environment Variables"
    )

mongo_client = MongoClient(MONGO_URI)

db = mongo_client["discord_bot_db"]

commands_collection = db["website_commands"]
settings_collection = db["website_command_settings"]
guilds_collection = db["website_guilds"]


# =========================================================
# حفظ الأوامر
# =========================================================

def save_bot_commands(bot):

    print("🌐 [WEBSITE] بدء تحديث قائمة الأوامر...")

    commands_data = []

    for command in bot.commands:

        if command.hidden:
            continue

        if command.parent is not None:
            continue

        # -------------------------------------------------
        # إزالة أي Prefix من اسم الأمر
        # -------------------------------------------------

        clean_name = str(command.name)

        for prefix in ("-", ".", "/"):
            if clean_name.startswith(prefix):
                clean_name = clean_name[1:]

        # -------------------------------------------------
        # البيانات
        # -------------------------------------------------

        commands_data.append({
            "name": clean_name,
            "real_name": command.name,
            "description": (
                command.help
                or command.description
                or "لا يوجد وصف لهذا الأمر."
            ),
            "aliases": [
                str(alias)
                for alias in command.aliases
            ],
        })

    commands_data.sort(
        key=lambda x: x["name"].lower()
    )

    print(
        f"📋 [WEBSITE] تم العثور على "
        f"{len(commands_data)} أمر"
    )

    # -----------------------------------------------------
    # استبدال قائمة الأوامر
    # -----------------------------------------------------

    commands_collection.delete_many({})

    if commands_data:
        commands_collection.insert_many(
            commands_data
        )

    # -----------------------------------------------------
    # الإعدادات العامة
    # -----------------------------------------------------

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
        "✅ [WEBSITE] تم حفظ الأوامر في MongoDB"
    )


# =========================================================
# حفظ السيرفرات والرومات والرتب
# =========================================================

def save_guild_data(bot):

    print("🌐 [WEBSITE] بدء تحديث بيانات السيرفرات...")

    for guild in bot.guilds:

        # -------------------------------------------------
        # الرومات
        # -------------------------------------------------

        channels = []

        for channel in guild.channels:

            # نستبعد بعض الأنواع غير المناسبة للأوامر
            if hasattr(channel, "name"):

                channels.append({
                    "id": str(channel.id),
                    "name": channel.name,
                    "type": str(channel.type),
                })

        # -------------------------------------------------
        # الرتب
        # -------------------------------------------------

        roles = []

        for role in guild.roles:

            # تجاهل @everyone
            if role.is_default():
                continue

            roles.append({
                "id": str(role.id),
                "name": role.name,
                "position": role.position,
            })

        # -------------------------------------------------
        # حفظ البيانات
        # -------------------------------------------------

        guilds_collection.update_one(
            {
                "guild_id": str(guild.id)
            },
            {
                "$set": {
                    "guild_id": str(guild.id),
                    "guild_name": guild.name,
                    "owner_id": str(guild.owner_id),
                    "channels": channels,
                    "roles": roles,
                    "updated_at": datetime.now(
                        timezone.utc
                    ),
                }
            },
            upsert=True
        )

        print(
            f"✅ [WEBSITE] تم تحديث: "
            f"{guild.name}"
        )

    print(
        "🌐 [WEBSITE] تم تحديث بيانات السيرفرات"
    )


# =========================================================
# التحقق من صلاحية الأمر
# =========================================================

def check_command_permission(ctx):

    # -----------------------------------------------------
    # الخاص
    # -----------------------------------------------------

    if ctx.guild is None:
        return True

    # -----------------------------------------------------
    # اسم الأمر
    # -----------------------------------------------------

    if not ctx.command:
        return True

    command_name = str(ctx.command.name)

    # -----------------------------------------------------
    # إزالة Prefix احتياطيًا
    # -----------------------------------------------------

    for prefix in ("-", ".", "/"):
        if command_name.startswith(prefix):
            command_name = command_name[1:]

    # -----------------------------------------------------
    # البحث عن إعدادات السيرفر + الأمر
    # -----------------------------------------------------

    setting = settings_collection.find_one({
        "guild_id": str(ctx.guild.id),
        "command_name": command_name,
    })

    # -----------------------------------------------------
    # إذا ما فيه إعدادات من الموقع
    # نخلي الأمر يعمل مثل قبل
    # -----------------------------------------------------

    if not setting:
        return True

    # -----------------------------------------------------
    # التحكم غير مفعل
    # -----------------------------------------------------

    if not setting.get("enabled", False):
        return True

    # -----------------------------------------------------
    # الرومات
    # -----------------------------------------------------

    allowed_channels = setting.get(
        "channel_ids",
        []
    )

    # إذا تم تحديد رومات
    if allowed_channels:

        if str(ctx.channel.id) not in [
            str(x)
            for x in allowed_channels
        ]:
            return False

    # -----------------------------------------------------
    # الرتب
    # -----------------------------------------------------

    allowed_roles = setting.get(
        "role_ids",
        []
    )

    # إذا تم تحديد رتب
    if allowed_roles:

        user_roles = {
            str(role.id)
            for role in ctx.author.roles
        }

        if not user_roles.intersection(
            {
                str(x)
                for x in allowed_roles
            }
        ):

            return False

    # -----------------------------------------------------
    # السماح
    # -----------------------------------------------------

    return True


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

    # =====================================================
    # Global Check
    # =====================================================

    @commands.Cog.listener()
    async def on_command(self, ctx):

        # هذا فقط للتسجيل
        pass

    # =====================================================
    # تحديث البيانات عند الجاهزية
    # =====================================================

    @commands.Cog.listener()
    async def on_ready(self):

        if self.updated:
            return

        self.updated = True

        print(
            "🌐 [WEBSITE] البوت أصبح جاهزًا"
        )

        await asyncio.sleep(5)

        try:

            save_bot_commands(
                self.bot
            )

            save_guild_data(
                self.bot
            )

        except Exception as error:

            print(
                "❌ [WEBSITE] حدث خطأ أثناء التحديث"
            )

            print(
                f"❌ النوع: "
                f"{type(error).__name__}"
            )

            print(
                f"❌ الخطأ: {error}"
            )

            traceback.print_exc()

    # =====================================================
    # تحديث السيرفرات
    # =====================================================

    @commands.Cog.listener()
    async def on_guild_join(self, guild):

        try:
            save_guild_data(self.bot)

        except Exception as error:

            print(
                f"❌ خطأ تحديث السيرفر: {error}"
            )

    # =====================================================
    # Global Check
    # =====================================================

    async def cog_check(self, ctx):

        try:

            return check_command_permission(
                ctx
            )

        except Exception as error:

            print(
                "❌ [WEBSITE] خطأ في فحص صلاحيات الأمر"
            )

            print(
                f"❌ {type(error).__name__}: {error}"
            )

            # في حالة الخطأ نخلي الأمر يعمل
            # حتى لا تتعطل الأوامر القديمة

            return True


# =========================================================
# Setup
# =========================================================

async def setup(bot):

    await bot.add_cog(
        WebsiteCommands(bot)
    )

    print(
        "✅ [WEBSITE] WebsiteCommands جاهز"
    )
