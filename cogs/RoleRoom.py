import os
import re
import discord
from discord.ext import commands
from pymongo import MongoClient


# =========================================================
# إعدادات MongoDB (متوافقة مع النظام المركزي)
# =========================================================

MONGO_URI = os.getenv("MONGO_URI")

if MONGO_URI:
    mongo_client = MongoClient(MONGO_URI)
    db = mongo_client["discord_bot_db"]
    settings_collection = db["website_command_settings"]
else:
    settings_collection = None


# =========================================================
# الألوان
# =========================================================

COLORS = {
    # =========================
    # أساسية
    # =========================

    "احمر": "#FF0000",
    "أحمر": "#FF0000",

    "اخضر": "#00FF00",
    "أخضر": "#00FF00",

    "ازرق": "#0000FF",
    "أزرق": "#0000FF",

    "اصفر": "#FFFF00",
    "أصفر": "#FFFF00",

    "برتقالي": "#FFA500",
    "بنفسجي": "#800080",
    "وردي": "#FF69B4",

    "اسود": "#000000",
    "أسود": "#000000",

    "ابيض": "#FFFFFF",
    "أبيض": "#FFFFFF",

    # =========================
    # فاتحة
    # =========================

    "احمر فاتح": "#FF6666",
    "أحمر فاتح": "#FF6666",

    "اخضر فاتح": "#66FF66",
    "أخضر فاتح": "#66FF66",

    "ازرق فاتح": "#66CCFF",
    "أزرق فاتح": "#66CCFF",

    "بنفسجي فاتح": "#B76EFF",

    "وردي فاتح": "#FFB6C1",

    "اصفر فاتح": "#FFFF99",
    "أصفر فاتح": "#FFFF99",

    "برتقالي فاتح": "#FFB347",

    "سماوي فاتح": "#87CEFA",

    "تركوازي فاتح": "#7FFFD4",

    # =========================
    # غامقة
    # =========================

    "احمر غامق": "#990000",
    "أحمر غامق": "#990000",

    "اخضر غامق": "#006600",
    "أخضر غامق": "#006600",

    "ازرق غامق": "#000099",
    "أزرق غامق": "#000099",

    "بنفسجي غامق": "#4B0082",

    "وردي غامق": "#C71585",

    "برتقالي غامق": "#CC5500",

    # =========================
    # إضافية
    # =========================

    "سماوي": "#00FFFF",
    "فيروزي": "#40E0D0",
    "تركوازي": "#40E0D0",

    "ذهبي": "#FFD700",
    "فضي": "#C0C0C0",

    "بني": "#8B4513",
    "نيلي": "#4B0082",

    "ليموني": "#CCFF00",
    "نعناعي": "#98FF98",

    "موف": "#C8A2C8",
    "كحلي": "#000080",
    "زيتي": "#808000",

    "مرجاني": "#FF7F50",
    "خوخي": "#FFDAB9",

    "عنابي": "#800000",
    "لافندر": "#E6E6FA",

    "مشمشي": "#FBCEB1",

    "رمادي": "#808080",
    "رمادي فاتح": "#D3D3D3",
    "رمادي غامق": "#404040",
}


# =========================================================
# تحويل النص إلى لون
# =========================================================

def get_color(color_text):

    color_text = color_text.strip()
    color_lower = color_text.lower()

    # =====================================================
    # HEX
    # =====================================================

    if re.fullmatch(r"#?[0-9A-Fa-f]{6}", color_text):

        if not color_text.startswith("#"):
            color_text = "#" + color_text

        try:
            return discord.Color.from_str(color_text)

        except Exception:
            return None

    # =====================================================
    # اسم اللون
    # =====================================================

    if color_lower in COLORS:

        try:
            return discord.Color.from_str(
                COLORS[color_lower]
            )

        except Exception:
            return None

    return None


# =========================================================
# Cog
# =========================================================

class RoleRoom(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    # =====================================================
    # التحقق من صلاحيات الموقع للأوامر النصية بدون Prefix
    # =====================================================

    def check_permissions(self, message, command_name):
        if not message.guild or not settings_collection:
            return False

        setting = settings_collection.find_one({
            "guild_id": str(message.guild.id),
            "command_name": command_name
        })

        # إذا لم تقم بإعداد الأمر في الموقع، امنعه للحفاظ على الأمان وعدم فتحه للجميع
        if not setting:
            return False

        # إذا كان الإعداد غير مفعل من الموقع
        if not setting.get("enabled", False):
            return False

        allowed_channels = {
            str(c_id) for c_id in setting.get("channel_ids", [])
        }
        allowed_roles = {
            str(r_id) for r_id in setting.get("role_ids", [])
        }

        # فحص الروم إذا كانت محددة في الموقع
        if allowed_channels and str(message.channel.id) not in allowed_channels:
            return False

        # فحص الرتبة إذا كانت محددة في الموقع
        if allowed_roles:
            user_role_ids = {str(role.id) for role in message.author.roles}
            if not (user_role_ids & allowed_roles):
                return False

        return True

    # =====================================================
    # استقبال الرسائل بدون Prefix
    # =====================================================

    @commands.Cog.listener()
    async def on_message(self, message):

        # تجاهل البوتات
        if message.author.bot:
            return

        content = message.content.strip()

        # =================================================
        # أمر الرتبة
        #
        # رتبة + احمد محسن + بنفسجي فاتح
        # =================================================

        if content.startswith("رتبة"):

            # التحقق من صلاحيات الموقع للأمر "رتبة"
            if not self.check_permissions(message, "رتبة"):
                return

            parts = [
                x.strip()
                for x in content.split("+")
            ]

            # يجب أن تكون:
            #
            # رتبة
            # الاسم
            # اللون

            if len(parts) != 3 or parts[0] != "رتبة":

                await message.channel.send(
                    "❌ **طريقة الاستخدام الصحيحة:**\n\n"
                    "`رتبة + اسم الرتبة + اللون`\n\n"
                    "**مثال:**\n"
                    "`رتبة + احمد محسن + بنفسجي فاتح`\n\n"
                    "**أو HEX:**\n"
                    "`رتبة + احمد محسن + #B76EFF`"
                )

                return

            role_name = parts[1].strip()
            color_text = parts[2].strip()

            # =================================================
            # التحقق من اسم الرتبة
            # =================================================

            if not role_name:

                await message.channel.send(
                    "❌ يجب كتابة اسم الرتبة."
                )

                return

            # =================================================
            # التحقق من اللون
            # =================================================

            if not color_text:

                await message.channel.send(
                    "❌ يجب كتابة لون الرتبة."
                )

                return

            color = get_color(color_text)

            if color is None:

                await message.channel.send(
                    "❌ **اللون غير معروف.**\n\n"
                    "يمكنك كتابة اسم لون مثل:\n"
                    "`بنفسجي فاتح`\n"
                    "`أحمر`\n"
                    "`ذهبي`\n"
                    "`سماوي`\n\n"
                    "أو استخدام HEX:\n"
                    "`#B76EFF`"
                )

                return

            # =================================================
            # التأكد أن الرتبة غير موجودة
            # =================================================

            existing_role = discord.utils.find(
                lambda role:
                role.name.lower() == role_name.lower(),
                message.guild.roles
            )

            if existing_role:

                await message.channel.send(
                    f"❌ الرتبة **{existing_role.name}** موجودة بالفعل."
                )

                return

            # =================================================
            # إنشاء الرتبة
            # =================================================

            try:

                role = await message.guild.create_role(
                    name=role_name,
                    color=color,
                    reason=f"إنشاء رتبة بواسطة {message.author}"
                )

                await message.channel.send(
                    "✅ **تم إنشاء الرتبة بنجاح!**\n\n"
                    f"**الاسم:** {role.name}\n"
                    f"**اللون:** {color_text}\n"
                    f"**الرتبة:** {role.mention}"
                )

            except discord.Forbidden:

                await message.channel.send(
                    "❌ البوت لا يملك صلاحية **Manage Roles**."
                )

            except discord.HTTPException:

                await message.channel.send(
                    "❌ حدث خطأ أثناء إنشاء الرتبة."
                )

            return

        # =================================================
        # أمر إنشاء روم
        #
        # سوي+روم + شات الاساطير
        # =================================================

        if content.startswith("سوي+روم"):

            # التحقق من صلاحيات الموقع للأمر "سوي+روم"
            if not self.check_permissions(message, "سوي+روم"):
                return

            # =================================================
            # أخذ كل شيء بعد الأمر
            # =================================================

            channel_name = content[
                len("سوي+روم"):
            ].strip()

            # =================================================
            # إزالة + إذا كانت موجودة
            # =================================================

            if channel_name.startswith("+"):

                channel_name = channel_name[1:].strip()

            # =================================================
            # إذا لم يكتب اسم
            # =================================================

            if not channel_name:

                await message.channel.send(
                    "❌ **اكتب اسم الروم.**\n\n"
                    "**مثال:**\n"
                    "`سوي+روم + شات الاساطير`"
                )

                return

            # =================================================
            # تنظيف المسافات الزائدة فقط
            # =================================================

            channel_name = " ".join(
                channel_name.split()
            )

            # =================================================
            # الحد الأقصى لاسم قناة Discord
            # =================================================

            channel_name = channel_name[:100]

            # =================================================
            # البحث عن روم بنفس الاسم
            # =================================================

            existing_channel = discord.utils.find(
                lambda channel:
                channel.name.lower() == channel_name.lower(),
                message.guild.text_channels
            )

            if existing_channel:

                await message.channel.send(
                    f"❌ الروم {existing_channel.mention} موجود بالفعل."
                )

                return

            # =================================================
            # إنشاء الروم
            # =================================================

            try:

                channel = await message.guild.create_text_channel(
                    name=channel_name,
                    reason=f"إنشاء روم بواسطة {message.author}"
                )

                await message.channel.send(
                    "✅ **تم إنشاء الروم بنجاح!**\n\n"
                    f"**الاسم:** {channel.name}\n"
                    f"**الروم:** {channel.mention}"
                )

            except discord.Forbidden:

                await message.channel.send(
                    "❌ البوت لا يملك صلاحية **Manage Channels**."
                )

            except discord.HTTPException:

                await message.channel.send(
                    "❌ Discord رفض اسم الروم أو حدث خطأ أثناء الإنشاء."
                )

            return


# =========================================================
# Setup
# =========================================================

async def setup(bot):
    await bot.add_cog(RoleRoom(bot))
