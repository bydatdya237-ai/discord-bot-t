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
    # أساسية
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

    # فاتحة
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

    # غامقة
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
}


# =========================================================
# تحويل اللون
# =========================================================

def get_color(color_text: str):
    color_text = color_text.strip()

    # إذا كتب HEX
    if re.fullmatch(r"#?[0-9A-Fa-f]{6}", color_text):
        if not color_text.startswith("#"):
            color_text = "#" + color_text

        return discord.Color.from_str(color_text)

    # إذا كتب اسم لون معروف
    color_key = color_text.lower()

    if color_key in COLORS:
        return discord.Color.from_str(COLORS[color_key])

    # محاولات بسيطة للألوان العربية
    normalized = color_text.replace("ال", "", 1)

    if normalized in COLORS:
        return discord.Color.from_str(COLORS[normalized])

    return None


# =========================================================
# البوت
# =========================================================

class RoleRoom(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    # =====================================================
    # التحقق
    # =====================================================

    def allowed(self, ctx):

        # روم خاطئ = تجاهل كامل
        if ctx.channel.id != COMMAND_ROOM_ID:
            return False

        # رتبة غير مسموحة = تجاهل كامل
        if not any(role.id == ALLOWED_ROLE_ID for role in ctx.author.roles):
            return False

        return True

    # =====================================================
    # إنشاء رتبة
    #
    # مثال:
    # -رتبة + احمد محسن + بنفسجي فاتح
    #
    # أو:
    # -رتبة + احمد محسن + #B76EFF
    # =====================================================

    @commands.command(name="رتبة")
    async def create_role(self, ctx, *, text: str = None):

        if not self.allowed(ctx):
            return

        if not text:
            return

        parts = [x.strip() for x in text.split("+")]

        if len(parts) < 2:
            await ctx.send(
                "❌ الاستخدام الصحيح:\n"
                "`-رتبة + اسم الرتبة + اللون`"
            )
            return

        role_name = parts[0]
        color_text = parts[1]

        if not role_name:
            return

        if not color_text:
            return

        # الحصول على اللون
        color = get_color(color_text)

        if color is None:
            await ctx.send(
                "❌ ما قدرت أتعرف على اللون.\n\n"
                "اكتب اسم اللون أو استخدم HEX، مثل:\n"
                "`-رتبة + الاسطورة + بنفسجي فاتح`\n"
                "`-رتبة + الاسطورة + #B76EFF`"
            )
            return

        # التأكد أن اسم الرتبة غير موجود
        for role in ctx.guild.roles:
            if role.name.lower() == role_name.lower():
                await ctx.send(
                    f"❌ رتبة **{role.name}** موجودة بالفعل."
                )
                return

        try:

            # إنشاء الرتبة
            role = await ctx.guild.create_role(
                name=role_name,
                color=color,
                reason=f"إنشاء رتبة بواسطة {ctx.author}"
            )

            await ctx.send(
                f"✅ تم إنشاء الرتبة بنجاح!\n\n"
                f"**الرتبة:** {role.mention}\n"
                f"**اللون:** `{color_text}`"
            )

        except discord.Forbidden:
            await ctx.send(
                "❌ البوت ما عنده صلاحية **Manage Roles**."
            )

        except discord.HTTPException:
            await ctx.send(
                "❌ حدث خطأ أثناء إنشاء الرتبة."
            )

    # =====================================================
    # إنشاء روم
    #
    # مثال:
    # -سوي+روم
    #
    # أو:
    # -سوي+روم + الشات الجديد
    # =====================================================

    @commands.command(name="سوي+روم")
    async def create_channel(self, ctx, *, channel_name: str = None):

        if not self.allowed(ctx):
            return

        # إذا ما كتب اسم
        if not channel_name:
            await ctx.send(
                "❌ اكتب اسم الروم.\n"
                "مثال:\n"
                "`-سوي+روم + الشات الجديد`"
            )
            return

        # تنظيف الاسم
        channel_name = channel_name.strip()

        # تحويل المسافات إلى -
        channel_name = re.sub(r"\s+", "-", channel_name)

        # إزالة الرموز الغريبة
        channel_name = re.sub(
            r"[^a-zA-Z0-9\u0600-\u06FF\-_]",
            "",
            channel_name
        )

        # منع الاسم الفارغ
        if not channel_name:
            return

        # حد Discord
        channel_name = channel_name[:100]

        # التأكد أن الروم غير موجود
        for channel in ctx.guild.text_channels:
            if channel.name.lower() == channel_name.lower():
                await ctx.send(
                    f"❌ الروم **#{channel.name}** موجود بالفعل."
                )
                return

        try:

            channel = await ctx.guild.create_text_channel(
                channel_name,
                reason=f"إنشاء روم بواسطة {ctx.author}"
            )

            await ctx.send(
                f"✅ تم إنشاء الروم بنجاح!\n"
                f"{channel.mention}"
            )

        except discord.Forbidden:
            await ctx.send(
                "❌ البوت ما عنده صلاحية **Manage Channels**."
            )

        except discord.HTTPException:
            await ctx.send(
                "❌ حدث خطأ أثناء إنشاء الروم."
            )


# =========================================================
# Setup
# =========================================================

async def setup(bot):
    await bot.add_cog(RoleRoom(bot))
