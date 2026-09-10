import discord
from discord.ext import commands

import ast
import inspect
import textwrap


# =========================================================
# الإعدادات
# =========================================================

# الروم الوحيد المسموح فيه استخدام -اوامر
COMMAND_ROOM_ID = 1547711993568305232

# الرتب المسموح لها باستخدام -اوامر
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
# فحص هل العقدة تمثل ctx.channel.id
# =========================================================

def is_channel_id_node(node):
    """
    يتأكد أن العقدة هي:

    ctx.channel.id
    """

    if not isinstance(node, ast.Attribute):
        return False

    if node.attr != "id":
        return False

    channel = node.value

    if not isinstance(channel, ast.Attribute):
        return False

    if channel.attr != "channel":
        return False

    ctx = channel.value

    if not isinstance(ctx, ast.Name):
        return False

    return ctx.id == "ctx"


# =========================================================
# استخراج قيمة الروم من AST
# =========================================================

def extract_room_value(node, command_globals):
    """
    يحاول استخراج رقم الروم من:

    123456789

    أو:

    ECONOMY_ROOM_ID

    أو:

    SOME_ROOM_ID
    """

    # -----------------------------------------------------
    # رقم مباشر
    # -----------------------------------------------------

    if isinstance(node, ast.Constant):

        if isinstance(node.value, int):
            return node.value

        return None

    # -----------------------------------------------------
    # متغير
    # -----------------------------------------------------

    if isinstance(node, ast.Name):

        value = command_globals.get(node.id)

        if isinstance(value, int):
            return value

        return None

    # -----------------------------------------------------
    # دعم بعض الحالات البسيطة الأخرى
    # -----------------------------------------------------

    return None


# =========================================================
# استخراج الرومات من شرط ctx.channel.id
# =========================================================

def extract_rooms_from_comparison(node, command_globals):

    rooms = []

    if not isinstance(node, ast.Compare):
        return rooms

    # نحتاج مقارنة يكون الطرف الأيسر فيها:
    #
    # ctx.channel.id
    #
    if not is_channel_id_node(node.left):
        return rooms

    # -----------------------------------------------------
    # مثال:
    #
    # ctx.channel.id != ECONOMY_ROOM_ID
    #
    # ctx.channel.id == 123456789
    # -----------------------------------------------------

    for comparator in node.comparators:

        room_id = extract_room_value(
            comparator,
            command_globals
        )

        if room_id:
            rooms.append(room_id)

    return rooms


# =========================================================
# استخراج الرومات من شرط in / not in
# =========================================================

def extract_rooms_from_iterable(node, command_globals):

    rooms = []

    # -----------------------------------------------------
    # مثال:
    #
    # ctx.channel.id in [123, 456]
    # -----------------------------------------------------

    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):

        for element in node.elts:

            room_id = extract_room_value(
                element,
                command_globals
            )

            if room_id:
                rooms.append(room_id)

    # -----------------------------------------------------
    # مثال:
    #
    # ctx.channel.id in ROOM_IDS
    # -----------------------------------------------------

    elif isinstance(node, ast.Name):

        value = command_globals.get(node.id)

        if isinstance(value, (list, tuple, set)):

            for room_id in value:

                if isinstance(room_id, int):
                    rooms.append(room_id)

    return rooms


# =========================================================
# البحث داخل شرط
# =========================================================

def scan_ast_for_rooms(tree, command_globals):

    rooms = []

    for node in ast.walk(tree):

        # -------------------------------------------------
        # مقارنات:
        #
        # ctx.channel.id != ROOM_ID
        # ctx.channel.id == ROOM_ID
        # -------------------------------------------------

        if isinstance(node, ast.Compare):

            if is_channel_id_node(node.left):

                # حالة in / not in
                for operator, comparator in zip(
                    node.ops,
                    node.comparators
                ):

                    if isinstance(
                        operator,
                        (ast.In, ast.NotIn)
                    ):

                        found = extract_rooms_from_iterable(
                            comparator,
                            command_globals
                        )

                        rooms.extend(found)

                    else:

                        room_id = extract_room_value(
                            comparator,
                            command_globals
                        )

                        if room_id:
                            rooms.append(room_id)

    # إزالة التكرار مع المحافظة على الترتيب
    unique_rooms = []

    for room_id in rooms:

        if room_id not in unique_rooms:
            unique_rooms.append(room_id)

    return unique_rooms


# =========================================================
# الحصول على روم الأمر من الكود نفسه
# =========================================================

def get_command_rooms(command):

    rooms = []

    try:

        callback = command.callback

        # -------------------------------------------------
        # متغيرات الملف الذي يحتوي على الأمر
        # -------------------------------------------------

        command_globals = callback.__globals__

        # -------------------------------------------------
        # قراءة كود الدالة الحقيقي
        # -------------------------------------------------

        source = inspect.getsource(callback)

        source = textwrap.dedent(source)

        # -------------------------------------------------
        # تحويل الكود إلى AST
        # -------------------------------------------------

        tree = ast.parse(source)

        # -------------------------------------------------
        # البحث عن شروط الرومات
        # -------------------------------------------------

        rooms = scan_ast_for_rooms(
            tree,
            command_globals
        )

    except Exception:
        pass

    return rooms


# =========================================================
# الحصول على وصف الأمر
# =========================================================

def get_command_description(command):

    # إذا كان للأمر Help محدد
    if command.help:
        return command.help

    # محاولة قراءة وصف الدالة
    try:

        callback = command.callback

        if callback.__doc__:

            description = callback.__doc__.strip()

            if description:
                return description

    except Exception:
        pass

    return "لا يوجد وصف لهذا الأمر."


# =========================================================
# الحصول على اسم الروم
# =========================================================

def get_channel_display(guild, channel_id):

    if channel_id is None:
        return "🌐 جميع الرومات / غير محدد"

    channel = guild.get_channel(channel_id)

    if channel is None:
        return f"❓ روم غير موجود (`{channel_id}`)"

    return channel.mention


# =========================================================
# عرض أكثر من روم
# =========================================================

def get_rooms_display(guild, room_ids):

    # لا يوجد روم مكتشف
    if not room_ids:
        return "🌐 جميع الرومات / غير محدد"

    displays = []

    for room_id in room_ids:

        display = get_channel_display(
            guild,
            room_id
        )

        if display not in displays:
            displays.append(display)

    return "، ".join(displays)


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
        # التأكد أن -اوامر مستخدم في الروم المحدد
        # -------------------------------------------------

        if ctx.channel.id != COMMAND_ROOM_ID:
            return

        # -------------------------------------------------
        # التأكد من الرتبة
        # -------------------------------------------------

        if not isinstance(ctx.author, discord.Member):
            return

        if not has_allowed_role(ctx.author):
            return

        # -------------------------------------------------
        # جمع الأوامر
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

            description = get_command_description(
                command
            )

            command_text += (
                f"\n📝 {description}"
            )

            # =============================================
            # الرومات التي يعمل فيها الأمر
            # =============================================

            room_ids = get_command_rooms(
                command
            )

            room_display = get_rooms_display(
                ctx.guild,
                room_ids
            )

            command_text += (
                f"\n📍 يعمل في: {room_display}"
            )

            # =============================================
            # البدائل
            # =============================================

            if command.aliases:

                aliases = " ".join(
                    f"`-{alias}`"
                    for alias in command.aliases
                )

                command_text += (
                    f"\n↳ البدائل: {aliases}"
                )

            commands_list.append(
                command_text
            )

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

        commands_list.sort(
            key=lambda x: x.lower()
        )

        # -------------------------------------------------
        # تقسيم القائمة إذا كانت طويلة
        # -------------------------------------------------

        chunks = []
        current_chunk = ""

        for command_text in commands_list:

            if (
                len(current_chunk)
                + len(command_text)
                + 2
                > 3800
            ):

                chunks.append(
                    current_chunk
                )

                current_chunk = ""

            current_chunk += (
                command_text
                + "\n\n"
            )

        if current_chunk:
            chunks.append(
                current_chunk
            )

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

            await ctx.send(
                embed=embed
            )

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

    await bot.add_cog(
        CommandsListCog(bot)
    )
