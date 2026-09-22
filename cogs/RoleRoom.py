import re
import discord
from discord.ext import commands


# =========================================================
# الإعدادات
# =========================================================

ALLOWED_ROLE_ID = 1545608277159579718
COMMAND_ROOM_ID = 1545601155952812044


# =========================================================
# الألوان
# =========================================================

COLORS = {
    # ألوان أساسية
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

    # ألوان فاتحة
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

    # ألوان غامقة
    "احمر غامق": "#990000",
    "أحمر غامق": "#990000",

    "اخضر غامق": "#006600",
    "أخضر غامق": "#006600",

    "ازرق غامق": "#000099",
    "أزرق غامق": "#000099",

    "بنفسجي غامق": "#4B0082",
    "وردي غامق": "#C71585",
    "برتقالي غامق": "#CC5500",

    # ألوان إضافية
    "سماوي": "#00FFFF",
    "فيروزي": "#40E0D0",
    "ذهبي": "#FFD700",
    "فضي": "#C0C0C0",
    "بني": "#8B4513",
    "نيلي": "#4B0082",
    "ليموني": "#CCFF00",
    "نعناعي": "#98FF98",
    "موف": "#C8A2C8",
    "كحلي": "#000080",
    "زيتي": "#808000",

    # ألوان مشهورة إضافية
    "مرجاني": "#FF7F50",
    "خوخي": "#FFDAB9",
    "عنابي": "#800000",
    "تركوازي": "#40E0D0",
    "لافندر": "#E6E6FA",
    "مشمشي": "#FBCEB1",
    "رمادي": "#808080",
    "رمادي فاتح": "#D3D3D3",
    "رمادي غامق": "#404040",
}


# =========================================================
# الحصول على اللون
# =========================================================

def get_color(color_text):

    color_text = color_text.strip()
    color_lower = color_text.lower()

    # دعم HEX
    if re.fullmatch(r"#?[0-9A-Fa-f]{6}", color_text):

        if not color_text.startswith("#"):
            color_text = "#" + color_text

        try:
            return discord.Color.from_str(color_text)
        except Exception:
            return None

    # اسم اللون
    if color_lower in COLORS:
        try:
            return discord.Color.from_str(COLORS[color_lower])
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
    # التحقق من الصلاحية
    # =====================================================

    def is_allowed(self, message):

        # الروم الصحيح فقط
        if message.channel.id != COMMAND_ROOM_ID:
            return False

        # الرتبة المطلوبة
        if not any(
            role.id == ALLOWED_ROLE_ID
            for role in message.author.roles
        ):
            return False

        return True

    # =====================================================
    # معالجة الرسائل بدون Prefix
    # =====================================================

    @commands.Cog.listener()
    async def on_message(self, message):

        # تجاهل البوتات
        if message.author.bot:
            return

        # الروم الخاطئ = تجاهل كامل
        if message.channel.id != COMMAND_ROOM_ID:
            return

        # الرتبة غير موجودة = تجاهل كامل
        if not any(
            role.id == ALLOWED_ROLE_ID
            for role in message.author.roles
        ):
            return

        content = message.content.strip()

        # =================================================
        # أمر إنشاء رتبة
        # =================================================

        if content.startswith("رتبة"):

            parts = [
                x.strip()
                for x in content.split("+")
            ]

            # الشكل:
            # رتبة + اسم + لون

            if len(parts) != 3 or parts[0] != "رتبة":

                await message.channel.send(
                    "❌ **طريقة الاستخدام الصحيحة:**\n\n"
                    "`رتبة + اسم الرتبة + اللون`\n\n"
                    "**مثال:**\n"
                    "`رتبة + احمد محسن + بنفسجي فاتح`\n\n"
                    "ويمكنك أيضًا استخدام HEX:\n"
                    "`رتبة + احمد محسن + #B76EFF`"
                )

                return

            role_name = parts[1]
            color_text = parts[2]

            # اسم فارغ
            if not role_name:

                await message.channel.send(
                    "❌ يجب كتابة اسم الرتبة."
                )

                return

            # لون فارغ
            if not color_text:

                await message.channel.send(
                    "❌ يجب كتابة لون الرتبة."
                )

                return

            # الحصول على اللون
            color = get_color(color_text)

            if color is None:

                await message.channel.send(
                    "❌ اللون غير معروف.\n\n"
                    "اكتب اسم اللون، مثل:\n"
                    "`بنفسجي فاتح`\n"
                    "`أحمر`\n"
                    "`أزرق سماوي`\n\n"
                    "أو استخدم HEX مثل:\n"
                    "`#B76EFF`"
                )

                return

            # التأكد من عدم وجود الرتبة
            existing_role = discord.utils.find(
                lambda r: r.name.lower() == role_name.lower(),
                message.guild.roles
            )

            if existing_role:

                await message.channel.send(
                    f"❌ الرتبة **{existing_role.name}** موجودة بالفعل."
                )

                return

            try:

                # إنشاء الرتبة
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
        # =================================================

        if content.startswith("سوي+روم"):

            parts = [
                x.strip()
                for x in content.split("+")
            ]

            # الشكل:
            # سوي+روم + اسم الروم

            if len(parts) != 2 or parts[0] != "سوي":

                await message.channel.send(
                    "❌ **طريقة الاستخدام الصحيحة:**\n\n"
                    "`سوي+روم + اسم الروم`\n\n"
                    "**مثال:**\n"
                    "`سوي+روم + شات الاساطير`"
                )

                return

            channel_name = parts[1]

            if not channel_name:

                await message.channel.send(
                    "❌ يجب كتابة اسم الروم."
                )

                return

            # تنظيف الاسم
            channel_name = channel_name.strip()

            # تحويل المسافات إلى -
            # حتى يكون اسم الروم مقبولًا في Discord
            channel_name = re.sub(
                r"\s+",
                "-",
                channel_name
            )

            # إزالة الرموز غير المناسبة
            channel_name = re.sub(
                r"[^a-zA-Z0-9\u0600-\u06FF\-_]",
                "",
                channel_name
            )

            if not channel_name:

                await message.channel.send(
                    "❌ اسم الروم غير صالح."
                )

                return

            # Discord يسمح حتى 100 حرف
            channel_name = channel_name[:100]

            # التأكد أن الروم غير موجود
            existing_channel = discord.utils.find(
                lambda c: c.name.lower() == channel_name.lower(),
                message.guild.text_channels
            )

            if existing_channel:

                await message.channel.send(
                    f"❌ الروم {existing_channel.mention} موجود بالفعل."
                )

                return

            try:

                channel = await message.guild.create_text_channel(
                    name=channel_name,
                    reason=f"إنشاء روم بواسطة {message.author}"
                )

                await message.channel.send(
                    "✅ **تم إنشاء الروم بنجاح!**\n\n"
                    f"{channel.mention}"
                )

            except discord.Forbidden:

                await message.channel.send(
                    "❌ البوت لا يملك صلاحية **Manage Channels**."
                )

            except discord.HTTPException:

                await message.channel.send(
                    "❌ حدث خطأ أثناء إنشاء الروم."
                )

            return


# =========================================================
# Setup
# =========================================================

async def setup(bot):
    await bot.add_cog(RoleRoom(bot))
