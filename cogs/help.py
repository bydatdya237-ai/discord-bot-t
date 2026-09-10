import discord
from discord.ext import commands


# =========================================================
# الإعدادات
# =========================================================

# الروم الوحيد المسموح فيه استخدام -اوامر
COMMAND_ROOM_ID = 1547711993568305232

# الرتب المسموح لها باستخدام الأمر
ALLOWED_ROLE_IDS = {
    1544078469657530578,
    1544426415766896690,
    1545851911121666108
}


# =========================================================
# التحقق من الرتبة
# =========================================================

def has_allowed_role(member: discord.Member) -> bool:
    return any(
        role.id in ALLOWED_ROLE_IDS
        for role in member.roles
    )


# =========================================================
# الحصول على روم الأمر تلقائياً
# =========================================================

def get_command_room(command):

    try:
        # نحاول الحصول على المتغيرات الموجودة
        # في نفس ملف الأمر
        command_globals = command.callback.__globals__

        # الطريقة الأساسية التي نستخدمها في أكواد البوت
        room_id = command_globals.get("COMMAND_ROOM_ID")

        if room_id:
            return room_id

        # دعم أسماء أخرى إذا استخدمتها مستقبلاً
        room_id = command_globals.get("ALLOWED_ROOM_ID")

        if room_id:
            return room_id

        room_id = command_globals.get("COMMAND_CHANNEL_ID")

        if room_id:
            return room_id

    except Exception:
        pass

    return None


# =========================================================
# الحصول على وصف الأمر تلقائياً
# =========================================================

def get_command_description(command):

    # discord.py يحفظ help إذا تم تحديده
    if command.help:
        return command.help

    # نحاول أخذ وصف الـcallback
    try:
        callback = command.callback

        if callback.__doc__:
            description = callback.__doc__.strip()

            if description:
                return description

    except Exception:
        pass

    # وصف افتراضي إذا لم يوجد وصف
    return "لا يوجد وصف لهذا الأمر."


# =========================================================
# الحصول على اسم الروم
# =========================================================

def get_channel_display(guild, channel_id):

    if channel_id is None:
        return "🌐 جميع الرومات / غير محدد"

    channel = guild.get_channel(channel_id)

    if channel is None:
        return "❓ الروم غير موجود"

    # mention يظهر اسم الروم للمستخدم
    # وليس الـID
    return channel.mention


# =========================================================
# Cog
# =========================================================

class CommandsListCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    # =====================================================
    # أمر -اوامر
    # =====================================================

    @commands.command(
        name="اوامر",
        help="عرض جميع أوامر البوت ومكان استخدامها."
    )
    async def commands_list(self, ctx):

        # -------------------------------------------------
        # الروم المسموح فقط
        # -------------------------------------------------

        if ctx.channel.id != COMMAND_ROOM_ID:
            return

        # -------------------------------------------------
        # التحقق من الرتبة
        # -------------------------------------------------

        if not isinstance(ctx.author, discord.Member):
            return

        if not has_allowed_role(ctx.author):
            return

        # -------------------------------------------------
        # الحصول على جميع أوامر البوت تلقائياً
        # -------------------------------------------------

        commands_list = []

        for command in self.bot.commands:

            # تجاهل أمر -اوامر نفسه
            if command.name == "اوامر":
                continue

            # تجاهل الأوامر المخفية
            if command.hidden:
                continue

            # =============================================
            # اسم الأمر
            # =============================================

            command_text = f"### `-{command.name}`"

            # =============================================
            # الوصف
            # =============================================

            description = get_command_description(command)

            command_text += f"\n📝 {description}"

            # =============================================
            # الروم الذي يعمل فيه الأمر
            # =============================================

            room_id = get_command_room(command)

            room_display = get_channel_display(
                ctx.guild,
                room_id
            )

            command_text += (
                f"\n📍 يعمل في: {room_display}"
            )

            # =============================================
            # البدائل / Aliases
            # =============================================

            if command.aliases:

                aliases = " ".join(
                    f"`-{alias}`"
                    for alias in command.aliases
                )

                command_text += (
                    f"\n↳ البدائل: {aliases}"
                )

            commands_list.append(command_text)

        # -------------------------------------------------
        # إذا لم توجد أوامر
        # -------------------------------------------------

        if not commands_list:

            await ctx.send(
                "📭 لا توجد أوامر متاحة حالياً.",
                delete_after=10
            )

            return

        # -------------------------------------------------
        # ترتيب الأوامر
        # -------------------------------------------------

        commands_list.sort()

        # -------------------------------------------------
        # تقسيم القائمة الطويلة
        # -------------------------------------------------

        chunks = []
        current_chunk = ""

        for command_text in commands_list:

            if len(current_chunk) + len(command_text) + 2 > 3800:

                chunks.append(current_chunk)
                current_chunk = ""

            current_chunk += command_text + "\n\n"

        if current_chunk:
            chunks.append(current_chunk)

        # -------------------------------------------------
        # إرسال القائمة
        # -------------------------------------------------

        for index, chunk in enumerate(chunks):

            embed = discord.Embed(
                title="📚 أوامر البوت",
                description=chunk,
                color=discord.Color.gold()
            )

            if index == 0:

                embed.set_footer(
                    text=f"عدد الأوامر: {len(commands_list)}"
                )

            await ctx.send(embed=embed)

        # -------------------------------------------------
        # حذف رسالة -اوامر
        # -------------------------------------------------

        try:
            await ctx.message.delete()

        except discord.HTTPException:
            pass


# =========================================================
# Setup
# =========================================================

async def setup(bot):
    await bot.add_cog(CommandsListCog(bot))
