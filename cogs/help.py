import discord
from discord.ext import commands

import ast
import os


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
# استخراج قيمة متغير
# =========================================================

def get_global_value(globals_dict, name):

    value = globals_dict.get(name)

    if isinstance(value, int):
        return value

    return None


# =========================================================
# استخراج رقم الروم من أي عقدة
# =========================================================

def extract_room_ids(node, globals_dict):

    rooms = []

    # رقم مباشر
    if isinstance(node, ast.Constant):

        if isinstance(node.value, int):
            rooms.append(node.value)

        return rooms

    # متغير مثل ECONOMY_ROOM_ID
    if isinstance(node, ast.Name):

        value = get_global_value(
            globals_dict,
            node.id
        )

        if value:
            rooms.append(value)

        return rooms

    # قائمة مثل:
    # [123, 456]
    if isinstance(
        node,
        (ast.List, ast.Tuple, ast.Set)
    ):

        for item in node.elts:

            rooms.extend(
                extract_room_ids(
                    item,
                    globals_dict
                )
            )

    return rooms


# =========================================================
# التأكد أن العقدة هي ctx.channel.id
# =========================================================

def is_ctx_channel_id(node):

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
# البحث عن الرومات داخل كود الأمر
# =========================================================

def find_rooms_in_tree(tree, globals_dict):

    rooms = []

    for node in ast.walk(tree):

        # =================================================
        # مقارنة مباشرة
        #
        # ctx.channel.id != ROOM_ID
        # ctx.channel.id == ROOM_ID
        # =================================================

        if isinstance(node, ast.Compare):

            if not is_ctx_channel_id(node.left):
                continue

            for comparator in node.comparators:

                found = extract_room_ids(
                    comparator,
                    globals_dict
                )

                rooms.extend(found)

        # =================================================
        # حالات مثل:
        #
        # ctx.channel.id in [123, 456]
        # =================================================

    # إزالة التكرار
    result = []

    for room_id in rooms:

        if room_id not in result:
            result.append(room_id)

    return result


# =========================================================
# قراءة ملف الكود الحقيقي للأمر
# =========================================================

def get_command_rooms(command):

    try:

        callback = command.callback

        # -------------------------------------------------
        # الحصول على ملف بايثون الذي يحتوي على الأمر
        # -------------------------------------------------

        code = callback.__code__

        filename = code.co_filename

        if not filename:
            return []

        if not os.path.isfile(filename):
            return []

        # -------------------------------------------------
        # قراءة الملف
        # -------------------------------------------------

        with open(
            filename,
            "r",
            encoding="utf-8"
        ) as file:

            source = file.read()

        # -------------------------------------------------
        # تحويل الملف إلى AST
        # -------------------------------------------------

        tree = ast.parse(source)

        # -------------------------------------------------
        # نحتاج فقط دالة الأمر نفسها
        # -------------------------------------------------

        function_name = callback.__name__

        target_function = None

        for node in ast.walk(tree):

            if isinstance(
                node,
                (ast.FunctionDef, ast.AsyncFunctionDef)
            ):

                if node.name == function_name:

                    target_function = node
                    break

        if target_function is None:
            return []

        # -------------------------------------------------
        # فحص كود الدالة
        # -------------------------------------------------

        return find_rooms_in_tree(
            target_function,
            callback.__globals__
        )

    except Exception as error:

        print(
            f"⚠️ تعذر اكتشاف روم الأمر "
            f"{command.name}: {error}"
        )

        return []


# =========================================================
# الحصول على وصف الأمر
# =========================================================

def get_command_description(command):

    if command.help:
        return command.help

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
# عرض الرومات
# =========================================================

def get_rooms_display(guild, room_ids):

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
        # روم -اوامر
        # -------------------------------------------------

        if ctx.channel.id != COMMAND_ROOM_ID:
            return

        # -------------------------------------------------
        # الرتبة
        # -------------------------------------------------

        if not isinstance(
            ctx.author,
            discord.Member
        ):
            return

        if not has_allowed_role(ctx.author):
            return

        # -------------------------------------------------
        # جمع الأوامر
        # -------------------------------------------------

        commands_list = []

        for command in self.bot.commands:

            # تجاهل -اوامر
            if command.name == "اوامر":
                continue

            # تجاهل المخفي
            if command.hidden:
                continue

            # =============================================
            # اسم الأمر
            # =============================================

            command_text = (
                f"### `-{command.name}`"
            )

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
            # اكتشاف الروم
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
        # لا توجد أوامر
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
        # تقسيم القائمة
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
