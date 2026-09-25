import os
import io
import discord

from discord.ext import commands
from pymongo import MongoClient

from PIL import Image, ImageDraw, ImageFont, ImageFilter

import arabic_reshaper
from bidi.algorithm import get_display


# =========================================================
# إعدادات MongoDB
# =========================================================

MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    raise RuntimeError("MONGO_URI غير موجود في Environment Variables")

mongo = MongoClient(MONGO_URI)
db = mongo["discord_bot_db"]

welcome_settings_collection = db["welcome_settings"]


# =========================================================
# إعدادات صورة الترحيب
# =========================================================

IMAGE_WIDTH = 1200
IMAGE_HEIGHT = 500


# ألوان التصميم:
# أزرق داكن + أزرق ملكي + أصفر/ذهبي

BACKGROUND_LEFT = (8, 25, 65)
BACKGROUND_MIDDLE = (12, 55, 120)
BACKGROUND_RIGHT = (15, 95, 165)

WHITE = (255, 255, 255)

YELLOW = (255, 211, 64)
LIGHT_YELLOW = (255, 231, 125)

LIGHT_BLUE = (170, 215, 255)

DARK_BLUE = (5, 18, 45)

SOFT_WHITE = (225, 240, 255)


# =========================================================
# Welcome Cog
# =========================================================

class WelcomeCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    # =====================================================
    # دعم اللغة العربية
    # =====================================================

    def shape_text(self, text):

        if text is None:
            return ""

        text = str(text)

        try:

            reshaped = arabic_reshaper.reshape(text)

            return get_display(
                reshaped
            )

        except Exception:

            return text

    # =====================================================
    # استبدال المتغيرات
    # =====================================================

    def replace_variables(self, text, member):

        if text is None:
            return ""

        text = str(text)

        replacements = {
            "{user}": member.mention,
            "{username}": member.display_name,
            "{server}": member.guild.name,
            "{member_count}": str(member.guild.member_count),
            "{user_id}": str(member.id),
        }

        for key, value in replacements.items():

            text = text.replace(
                key,
                str(value)
            )

        return text

    # =====================================================
    # تحميل الخط
    # =====================================================

    def get_font(self, size, bold=False):

        if bold:

            possible_fonts = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
                "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf",
                "/usr/share/fonts/opentype/noto/NotoSansArabic-Bold.ttf",
            ]

        else:

            possible_fonts = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
                "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
                "/usr/share/fonts/opentype/noto/NotoSansArabic-Regular.ttf",
            ]

        for path in possible_fonts:

            if os.path.exists(path):

                try:

                    return ImageFont.truetype(
                        path,
                        size
                    )

                except Exception:
                    pass

        return ImageFont.load_default()

    # =====================================================
    # الحصول على خط مناسب حسب العرض
    # =====================================================

    def fit_font(
        self,
        draw,
        text,
        max_width,
        start_size,
        bold=False,
        minimum_size=18
    ):

        text = self.shape_text(
            text
        )

        size = start_size

        while size > minimum_size:

            font = self.get_font(
                size,
                bold=bold
            )

            bbox = draw.textbbox(
                (0, 0),
                text,
                font=font
            )

            width = bbox[2] - bbox[0]

            if width <= max_width:
                return font

            size -= 2

        return self.get_font(
            minimum_size,
            bold=bold
        )

    # =====================================================
    # قياس النص
    # =====================================================

    def get_text_size(
        self,
        draw,
        text,
        font
    ):

        shaped_text = self.shape_text(
            text
        )

        bbox = draw.textbbox(
            (0, 0),
            shaped_text,
            font=font
        )

        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]

        return width, height

    # =====================================================
    # رسم نص في المنتصف
    # =====================================================

    def draw_centered_text(
        self,
        draw,
        text,
        font,
        y,
        fill=WHITE
    ):

        text = self.shape_text(
            text
        )

        bbox = draw.textbbox(
            (0, 0),
            text,
            font=font
        )

        text_width = bbox[2] - bbox[0]

        x = (
            IMAGE_WIDTH - text_width
        ) // 2

        draw.text(
            (x, y),
            text,
            font=font,
            fill=fill
        )

    # =====================================================
    # إنشاء خلفية متدرجة
    # =====================================================

    def create_background(self):

        image = Image.new(
            "RGB",
            (
                IMAGE_WIDTH,
                IMAGE_HEIGHT
            )
        )

        pixels = image.load()

        for x in range(IMAGE_WIDTH):

            ratio = x / (
                IMAGE_WIDTH - 1
            )

            if ratio < 0.5:

                local_ratio = ratio / 0.5

                r = int(
                    BACKGROUND_LEFT[0]
                    +
                    (
                        BACKGROUND_MIDDLE[0]
                        -
                        BACKGROUND_LEFT[0]
                    )
                    * local_ratio
                )

                g = int(
                    BACKGROUND_LEFT[1]
                    +
                    (
                        BACKGROUND_MIDDLE[1]
                        -
                        BACKGROUND_LEFT[1]
                    )
                    * local_ratio
                )

                b = int(
                    BACKGROUND_LEFT[2]
                    +
                    (
                        BACKGROUND_MIDDLE[2]
                        -
                        BACKGROUND_LEFT[2]
                    )
                    * local_ratio
                )

            else:

                local_ratio = (
                    ratio - 0.5
                ) / 0.5

                r = int(
                    BACKGROUND_MIDDLE[0]
                    +
                    (
                        BACKGROUND_RIGHT[0]
                        -
                        BACKGROUND_MIDDLE[0]
                    )
                    * local_ratio
                )

                g = int(
                    BACKGROUND_MIDDLE[1]
                    +
                    (
                        BACKGROUND_RIGHT[1]
                        -
                        BACKGROUND_MIDDLE[1]
                    )
                    * local_ratio
                )

                b = int(
                    BACKGROUND_MIDDLE[2]
                    +
                    (
                        BACKGROUND_RIGHT[2]
                        -
                        BACKGROUND_MIDDLE[2]
                    )
                    * local_ratio
                )

            for y in range(IMAGE_HEIGHT):

                pixels[x, y] = (
                    r,
                    g,
                    b
                )

        return image

    # =====================================================
    # تأثيرات الخلفية
    # =====================================================

    def add_background_effects(
        self,
        image
    ):

        overlay = Image.new(
            "RGBA",
            image.size,
            (0, 0, 0, 0)
        )

        draw = ImageDraw.Draw(
            overlay
        )

        # -------------------------------------------------
        # دائرة ذهبية يسار
        # -------------------------------------------------

        draw.ellipse(
            (-180, -180, 300, 300),
            fill=(
                255,
                211,
                64,
                35
            )
        )

        # -------------------------------------------------
        # دائرة زرقاء يمين
        # -------------------------------------------------

        draw.ellipse(
            (
                900,
                160,
                1400,
                660
            ),
            fill=(
                100,
                190,
                255,
                28
            )
        )

        # -------------------------------------------------
        # دائرة صغيرة
        # -------------------------------------------------

        draw.ellipse(
            (
                1030,
                40,
                1130,
                140
            ),
            fill=(
                255,
                211,
                64,
                25
            )
        )

        draw.ellipse(
            (
                60,
                400,
                170,
                510
            ),
            fill=(
                255,
                255,
                255,
                18
            )
        )

        # -------------------------------------------------
        # خطوط زخرفية
        # -------------------------------------------------

        draw.rounded_rectangle(
            (
                20,
                20,
                IMAGE_WIDTH - 20,
                IMAGE_HEIGHT - 20
            ),
            radius=28,
            outline=(
                255,
                211,
                64,
                100
            ),
            width=3
        )

        draw.rounded_rectangle(
            (
                35,
                35,
                IMAGE_WIDTH - 35,
                IMAGE_HEIGHT - 35
            ),
            radius=24,
            outline=(
                255,
                255,
                255,
                30
            ),
            width=2
        )

        overlay = overlay.filter(
            ImageFilter.GaussianBlur(22)
        )

        image = Image.alpha_composite(
            image.convert("RGBA"),
            overlay
        )

        return image.convert("RGB")

    # =====================================================
    # إضافة زخارف واضحة
    # =====================================================

    def add_design_elements(
        self,
        image
    ):

        draw = ImageDraw.Draw(
            image
        )

        # -------------------------------------------------
        # شريط ذهبي علوي
        # -------------------------------------------------

        draw.rounded_rectangle(
            (
                55,
                55,
                190,
                63
            ),
            radius=4,
            fill=YELLOW
        )

        # -------------------------------------------------
        # شريط ذهبي جانبي
        # -------------------------------------------------

        draw.rounded_rectangle(
            (
                350,
                100,
                358,
                400
            ),
            radius=4,
            fill=YELLOW
        )

        # -------------------------------------------------
        # نقاط زخرفية
        # -------------------------------------------------

        for x, y, radius in [
            (1080, 105, 5),
            (1120, 105, 3),
            (1160, 105, 6),
            (1050, 145, 3),
            (1100, 160, 4),
            (1140, 145, 3),
        ]:

            draw.ellipse(
                (
                    x - radius,
                    y - radius,
                    x + radius,
                    y + radius
                ),
                fill=YELLOW
            )

        # -------------------------------------------------
        # خطوط صغيرة
        # -------------------------------------------------

        draw.line(
            (
                900,
                410,
                1100,
                410
            ),
            fill=(
                255,
                211,
                64
            ),
            width=3
        )

        draw.line(
            (
                920,
                420,
                1060,
                420
            ),
            fill=(
                255,
                231,
                125
            ),
            width=2
        )

        return image

    # =====================================================
    # تحميل صورة العضو
    # =====================================================

    async def download_avatar(
        self,
        member
    ):

        try:

            avatar_asset = member.display_avatar.replace(
                size=512,
                format="png"
            )

            avatar_bytes = await avatar_asset.read()

            avatar = Image.open(
                io.BytesIO(
                    avatar_bytes
                )
            ).convert("RGBA")

            return avatar

        except Exception as e:

            print(
                f"[WelcomeCog] Avatar Error: {e}"
            )

            return None

    # =====================================================
    # قص الصورة بشكل دائري
    # =====================================================

    def make_circle_avatar(
        self,
        avatar,
        size=230
    ):

        avatar = avatar.resize(
            (
                size,
                size
            ),
            Image.Resampling.LANCZOS
        )

        # -------------------------------------------------
        # ظل
        # -------------------------------------------------

        shadow_size = size + 34

        shadow = Image.new(
            "RGBA",
            (
                shadow_size,
                shadow_size
            ),
            (
                0,
                0,
                0,
                0
            )
        )

        shadow_draw = ImageDraw.Draw(
            shadow
        )

        shadow_draw.ellipse(
            (
                8,
                12,
                size + 25,
                size + 29
            ),
            fill=(
                0,
                0,
                0,
                100
            )
        )

        shadow = shadow.filter(
            ImageFilter.GaussianBlur(8)
        )

        # -------------------------------------------------
        # القناع الدائري
        # -------------------------------------------------

        mask = Image.new(
            "L",
            (
                size,
                size
            ),
            0
        )

        mask_draw = ImageDraw.Draw(
            mask
        )

        mask_draw.ellipse(
            (
                0,
                0,
                size,
                size
            ),
            fill=255
        )

        # -------------------------------------------------
        # الصورة
        # -------------------------------------------------

        result = Image.new(
            "RGBA",
            (
                size,
                size
            ),
            (
                0,
                0,
                0,
                0
            )
        )

        result.paste(
            avatar,
            (
                0,
                0
            ),
            mask
        )

        # -------------------------------------------------
        # الإطار الذهبي
        # -------------------------------------------------

        border = Image.new(
            "RGBA",
            (
                size + 30,
                size + 30
            ),
            (
                0,
                0,
                0,
                0
            )
        )

        border_draw = ImageDraw.Draw(
            border
        )

        border_draw.ellipse(
            (
                3,
                3,
                size + 27,
                size + 27
            ),
            outline=(
                255,
                211,
                64,
                255
            ),
            width=7
        )

        border_draw.ellipse(
            (
                10,
                10,
                size + 20,
                size + 20
            ),
            outline=(
                255,
                255,
                255,
                130
            ),
            width=2
        )

        border.paste(
            result,
            (
                15,
                15
            ),
            result
        )

        # -------------------------------------------------
        # دمج الظل مع الإطار
        # -------------------------------------------------

        final = Image.new(
            "RGBA",
            border.size,
            (
                0,
                0,
                0,
                0
            )
        )

        final.alpha_composite(
            shadow,
            (
                0,
                0
            )
        )

        final.alpha_composite(
            border,
            (
                0,
                0
            )
        )

        return final

    # =====================================================
    # توليد صورة الترحيب
    # =====================================================

    async def generate_welcome_image(
        self,
        member,
        settings
    ):

        # -------------------------------------------------
        # الخلفية
        # -------------------------------------------------

        image = self.create_background()

        image = self.add_background_effects(
            image
        )

        image = self.add_design_elements(
            image
        )

        draw = ImageDraw.Draw(
            image
        )

        # =================================================
        # صورة العضو
        # =================================================

        avatar = await self.download_avatar(
            member
        )

        if avatar:

            circle_avatar = self.make_circle_avatar(
                avatar,
                230
            )

            avatar_x = 75

            avatar_y = (
                IMAGE_HEIGHT
                -
                circle_avatar.height
            ) // 2

            image.paste(
                circle_avatar,
                (
                    avatar_x,
                    avatar_y
                ),
                circle_avatar
            )

        # =================================================
        # النصوص
        # =================================================

        welcome_text = settings.get(
            "image_welcome_text",
            "WELCOME"
        )

        username_text = settings.get(
            "image_username_text",
            member.display_name
        )

        server_text = settings.get(
            "image_server_text",
            member.guild.name
        )

        members_text = settings.get(
            "image_members_text",
            f"Member #{member.guild.member_count}"
        )

        welcome_text = self.replace_variables(
            welcome_text,
            member
        )

        username_text = self.replace_variables(
            username_text,
            member
        )

        server_text = self.replace_variables(
            server_text,
            member
        )

        members_text = self.replace_variables(
            members_text,
            member
        )

        # =================================================
        # منطقة النص
        # =================================================

        text_area_x = 410

        text_area_width = 690

        # =================================================
        # WELCOME
        # =================================================

        welcome_font = self.fit_font(
            draw,
            welcome_text,
            text_area_width,
            58,
            bold=True,
            minimum_size=30
        )

        welcome_text_shaped = self.shape_text(
            welcome_text
        )

        draw.text(
            (
                text_area_x,
                85
            ),
            welcome_text_shaped,
            font=welcome_font,
            fill=YELLOW
        )

        # =================================================
        # اسم العضو
        # =================================================

        username_font = self.fit_font(
            draw,
            username_text,
            text_area_width,
            44,
            bold=True,
            minimum_size=22
        )

        username_text_shaped = self.shape_text(
            username_text
        )

        draw.text(
            (
                text_area_x,
                165
            ),
            username_text_shaped,
            font=username_font,
            fill=WHITE
        )

        # =================================================
        # خط فاصل
        # =================================================

        draw.rounded_rectangle(
            (
                text_area_x,
                240,
                text_area_x + 580,
                246
            ),
            radius=3,
            fill=YELLOW
        )

        # =================================================
        # اسم السيرفر
        # =================================================

        server_font = self.fit_font(
            draw,
            server_text,
            text_area_width,
            30,
            bold=True,
            minimum_size=18
        )

        server_text_shaped = self.shape_text(
            server_text
        )

        draw.text(
            (
                text_area_x,
                275
            ),
            server_text_shaped,
            font=server_font,
            fill=SOFT_WHITE
        )

        # =================================================
        # عدد الأعضاء
        # =================================================

        members_font = self.fit_font(
            draw,
            members_text,
            text_area_width,
            27,
            bold=False,
            minimum_size=17
        )

        members_text_shaped = self.shape_text(
            members_text
        )

        draw.text(
            (
                text_area_x,
                325
            ),
            members_text_shaped,
            font=members_font,
            fill=LIGHT_YELLOW
        )

        # =================================================
        # لمسة أخيرة
        # =================================================

        draw.text(
            (
                text_area_x,
                390
            ),
            self.shape_text("✦"),
            font=self.get_font(
                25,
                bold=True
            ),
            fill=YELLOW
        )

        # =================================================
        # حفظ الصورة في الذاكرة
        # =================================================

        output = io.BytesIO()

        image.save(
            output,
            format="PNG"
        )

        output.seek(0)

        return output

    # =====================================================
    # لون الـ Embed
    # =====================================================

    def get_color(
        self,
        color_value
    ):

        if not color_value:

            return discord.Color.blue()

        try:

            if isinstance(
                color_value,
                int
            ):

                return discord.Color(
                    color_value
                )

            color_value = str(
                color_value
            ).strip()

            if color_value.startswith("#"):

                color_value = color_value[1:]

            if color_value.lower().startswith("0x"):

                color_value = color_value[2:]

            return discord.Color(
                int(
                    color_value,
                    16
                )
            )

        except Exception:

            return discord.Color.blue()

    # =====================================================
    # Embed الترحيب
    # =====================================================

    def build_welcome_embed(
        self,
        member,
        settings
    ):

        title = settings.get(
            "title",
            "🎉 أهلاً وسهلاً بك!"
        )

        description = settings.get(
            "description",
            "{user}\n\nنورت السيرفر ونتمنى لك وقتًا ممتعًا معنا 💙"
        )

        footer = settings.get(
            "footer",
            "نتمنى لك تجربة ممتعة معنا ✨"
        )

        title = self.replace_variables(
            title,
            member
        )

        description = self.replace_variables(
            description,
            member
        )

        footer = self.replace_variables(
            footer,
            member
        )

        embed = discord.Embed(
            title=title,
            description=description,
            color=self.get_color(
                settings.get(
                    "color",
                    "#1877D2"
                )
            ),
            timestamp=discord.utils.utcnow()
        )

        # =================================================
        # الصورة المصغرة
        # =================================================

        show_avatar = settings.get(
            "show_avatar",
            True
        )

        if show_avatar:

            try:

                embed.set_thumbnail(
                    url=member.display_avatar.url
                )

            except Exception:
                pass

        # =================================================
        # الصورة المولدة
        # =================================================

        if settings.get(
            "generated_image",
            True
        ):

            embed.set_image(
                url="attachment://welcome.png"
            )

        # =================================================
        # Footer
        # =================================================

        if footer:

            try:

                if member.guild.icon:

                    embed.set_footer(
                        text=footer,
                        icon_url=member.guild.icon.url
                    )

                else:

                    embed.set_footer(
                        text=footer
                    )

            except Exception:

                embed.set_footer(
                    text=footer
                )

        return embed

    # =====================================================
    # عند دخول عضو جديد
    # =====================================================

    @commands.Cog.listener()
    async def on_member_join(
        self,
        member
    ):

        try:

            # =================================================
            # جلب إعدادات السيرفر
            # =================================================

            settings = welcome_settings_collection.find_one({
                "guild_id": str(
                    member.guild.id
                )
            })

            if not settings:

                return

            # =================================================
            # التحقق من التفعيل
            # =================================================

            if not settings.get(
                "enabled",
                False
            ):

                return

            # =================================================
            # الروم
            # =================================================

            channel_id = settings.get(
                "channel_id"
            )

            if not channel_id:

                return

            try:

                channel_id = int(
                    channel_id
                )

            except (
                ValueError,
                TypeError
            ):

                return

            channel = member.guild.get_channel(
                channel_id
            )

            if channel is None:

                return

            # =================================================
            # إنشاء الصورة
            # =================================================

            generated_image = settings.get(
                "generated_image",
                True
            )

            image_file = None

            if generated_image:

                image_bytes = await self.generate_welcome_image(
                    member,
                    settings
                )

                image_file = discord.File(
                    image_bytes,
                    filename="welcome.png"
                )

            # =================================================
            # الرسالة العادية
            # =================================================

            message = settings.get(
                "message",
                ""
            )

            message = self.replace_variables(
                message,
                member
            )

            # =================================================
            # Embed
            # =================================================

            embed_enabled = settings.get(
                "embed_enabled",
                True
            )

            embed = None

            if embed_enabled:

                embed = self.build_welcome_embed(
                    member,
                    settings
                )

            # =================================================
            # الإرسال
            # =================================================

            if image_file and embed:

                if message:

                    await channel.send(
                        content=message,
                        embed=embed,
                        file=image_file
                    )

                else:

                    await channel.send(
                        embed=embed,
                        file=image_file
                    )

            elif embed:

                if message:

                    await channel.send(
                        content=message,
                        embed=embed
                    )

                else:

                    await channel.send(
                        embed=embed
                    )

            elif image_file:

                if message:

                    await channel.send(
                        content=message,
                        file=image_file
                    )

                else:

                    await channel.send(
                        file=image_file
                    )

            elif message:

                await channel.send(
                    message
                )

        # =====================================================
        # صلاحيات Discord
        # =====================================================

        except discord.Forbidden:

            print(
                f"[WelcomeCog] لا توجد صلاحية كافية "
                f"في السيرفر {member.guild.id}"
            )

        # =====================================================
        # Discord API
        # =====================================================

        except discord.HTTPException as e:

            print(
                f"[WelcomeCog] Discord API Error: {e}"
            )

        # =====================================================
        # أخطاء أخرى
        # =====================================================

        except Exception as e:

            print(
                f"[WelcomeCog] Error: {e}"
            )


# =========================================================
# Setup
# =========================================================

async def setup(bot):

    await bot.add_cog(
        WelcomeCog(bot)
    )
