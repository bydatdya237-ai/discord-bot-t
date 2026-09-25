import os
import io
import discord

from discord.ext import commands
from pymongo import MongoClient

from PIL import Image, ImageDraw, ImageFont, ImageFilter

import arabic_reshaper
from bidi.algorithm import get_display


# =========================================================
# MongoDB
# =========================================================

MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    raise RuntimeError("MONGO_URI غير موجود في Environment Variables")

mongo = MongoClient(MONGO_URI)
db = mongo["discord_bot_db"]

welcome_settings_collection = db["welcome_settings"]


# =========================================================
# إعدادات الصورة
# =========================================================

IMAGE_WIDTH = 1200
IMAGE_HEIGHT = 500

BLUE_1 = (5, 22, 55)
BLUE_2 = (8, 55, 115)
BLUE_3 = (15, 100, 175)

WHITE = (255, 255, 255)
YELLOW = (255, 210, 55)
LIGHT_YELLOW = (255, 230, 125)
LIGHT_BLUE = (190, 225, 255)


# =========================================================
# Welcome Cog
# =========================================================

class WelcomeCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    # =====================================================
    # معالجة النص العربي
    # =====================================================

    def shape_text(self, text):

        if text is None:
            return ""

        text = str(text)

        if not text:
            return ""

        try:
            # ترتيب الحروف العربية وربطها
            reshaped = arabic_reshaper.reshape(text)

            # تحويل اتجاه العربي إلى RTL
            return get_display(
                reshaped,
                base_dir="R"
            )

        except Exception as e:

            print(
                f"[WelcomeCog] Text shaping error: {e}"
            )

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

        # DejaVu Sans هو أهم fallback لأنه موجود
        # غالباً في Railway/Linux ويدعم العربية.

        if bold:

            fonts = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
                "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf",
                "/usr/share/fonts/opentype/noto/NotoSansArabic-Bold.ttf",
                "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
            ]

        else:

            fonts = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
                "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
                "/usr/share/fonts/opentype/noto/NotoSansArabic-Regular.ttf",
                "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
            ]

        for font_path in fonts:

            if not os.path.isfile(font_path):
                continue

            try:

                return ImageFont.truetype(
                    font_path,
                    size
                )

            except Exception:
                continue

        print(
            "[WelcomeCog] لم يتم العثور على خط مناسب، سيتم استخدام الخط الافتراضي"
        )

        return ImageFont.load_default()

    # =====================================================
    # اختيار حجم الخط المناسب
    # =====================================================

    def fit_font(
        self,
        draw,
        text,
        max_width,
        start_size,
        minimum_size=16,
        bold=False
    ):

        shaped = self.shape_text(
            text
        )

        for size in range(
            start_size,
            minimum_size - 1,
            -2
        ):

            font = self.get_font(
                size,
                bold=bold
            )

            bbox = draw.textbbox(
                (0, 0),
                shaped,
                font=font
            )

            width = bbox[2] - bbox[0]

            if width <= max_width:

                return font

        return self.get_font(
            minimum_size,
            bold=bold
        )

    # =====================================================
    # قياس النص
    # =====================================================

    def text_width(
        self,
        draw,
        text,
        font
    ):

        shaped = self.shape_text(
            text
        )

        bbox = draw.textbbox(
            (0, 0),
            shaped,
            font=font
        )

        return bbox[2] - bbox[0]

    # =====================================================
    # رسم نص داخل منطقة
    # =====================================================

    def draw_centered_in_area(
        self,
        draw,
        text,
        font,
        area_left,
        area_right,
        y,
        fill
    ):

        if not text:
            return

        shaped = self.shape_text(
            text
        )

        bbox = draw.textbbox(
            (0, 0),
            shaped,
            font=font
        )

        width = bbox[2] - bbox[0]

        area_width = (
            area_right - area_left
        )

        x = (
            area_left
            +
            (area_width - width) / 2
            -
            bbox[0]
        )

        draw.text(
            (
                int(x),
                y
            ),
            shaped,
            font=font,
            fill=fill
        )

    # =====================================================
    # الخلفية
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

                ratio2 = ratio * 2

                r = int(
                    BLUE_1[0]
                    +
                    (
                        BLUE_2[0]
                        -
                        BLUE_1[0]
                    )
                    * ratio2
                )

                g = int(
                    BLUE_1[1]
                    +
                    (
                        BLUE_2[1]
                        -
                        BLUE_1[1]
                    )
                    * ratio2
                )

                b = int(
                    BLUE_1[2]
                    +
                    (
                        BLUE_2[2]
                        -
                        BLUE_1[2]
                    )
                    * ratio2
                )

            else:

                ratio2 = (
                    ratio - 0.5
                ) * 2

                r = int(
                    BLUE_2[0]
                    +
                    (
                        BLUE_3[0]
                        -
                        BLUE_2[0]
                    )
                    * ratio2
                )

                g = int(
                    BLUE_2[1]
                    +
                    (
                        BLUE_3[1]
                        -
                        BLUE_2[1]
                    )
                    * ratio2
                )

                b = int(
                    BLUE_2[2]
                    +
                    (
                        BLUE_3[2]
                        -
                        BLUE_2[2]
                    )
                    * ratio2
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
            (
                0,
                0,
                0,
                0
            )
        )

        draw = ImageDraw.Draw(
            overlay
        )

        # دائرة ذهبية
        draw.ellipse(
            (
                -170,
                -170,
                300,
                300
            ),
            fill=(
                255,
                210,
                55,
                35
            )
        )

        # دائرة زرقاء
        draw.ellipse(
            (
                900,
                150,
                1400,
                650
            ),
            fill=(
                100,
                200,
                255,
                30
            )
        )

        # نقاط
        draw.ellipse(
            (
                1030,
                55,
                1110,
                135
            ),
            fill=(
                255,
                210,
                55,
                22
            )
        )

        overlay = overlay.filter(
            ImageFilter.GaussianBlur(25)
        )

        return Image.alpha_composite(
            image.convert("RGBA"),
            overlay
        ).convert("RGB")

    # =====================================================
    # زخارف التصميم
    # =====================================================

    def add_design(
        self,
        image
    ):

        draw = ImageDraw.Draw(
            image
        )

        # إطار خارجي
        draw.rounded_rectangle(
            (
                20,
                20,
                IMAGE_WIDTH - 20,
                IMAGE_HEIGHT - 20
            ),
            radius=28,
            outline=YELLOW,
            width=3
        )

        # خط ذهبي تحت العنوان
        draw.rounded_rectangle(
            (
                395,
                235,
                1030,
                241
            ),
            radius=3,
            fill=YELLOW
        )

        # خطوط زخرفية يمين
        draw.line(
            (
                1050,
                390,
                1130,
                390
            ),
            fill=YELLOW,
            width=3
        )

        draw.line(
            (
                1070,
                400,
                1150,
                400
            ),
            fill=LIGHT_YELLOW,
            width=2
        )

        return image

    # =====================================================
    # تحميل Avatar
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

            data = await avatar_asset.read()

            return Image.open(
                io.BytesIO(data)
            ).convert("RGBA")

        except Exception as e:

            print(
                f"[WelcomeCog] Avatar Error: {e}"
            )

            return None

    # =====================================================
    # Avatar دائري
    # =====================================================

    def make_circle_avatar(
        self,
        avatar,
        size=225
    ):

        avatar = avatar.resize(
            (
                size,
                size
            ),
            Image.Resampling.LANCZOS
        )

        # -------------------------------------------------
        # القناع
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
        # الحجم النهائي
        # -------------------------------------------------

        final_size = size + 30

        final = Image.new(
            "RGBA",
            (
                final_size,
                final_size
            ),
            (
                0,
                0,
                0,
                0
            )
        )

        final_draw = ImageDraw.Draw(
            final
        )

        # ظل
        final_draw.ellipse(
            (
                5,
                8,
                size + 25,
                size + 28
            ),
            fill=(
                0,
                0,
                0,
                100
            )
        )

        # إطار ذهبي
        final_draw.ellipse(
            (
                2,
                2,
                size + 28,
                size + 28
            ),
            outline=YELLOW,
            width=7
        )

        # إطار أبيض داخلي
        final_draw.ellipse(
            (
                9,
                9,
                size + 21,
                size + 21
            ),
            outline=(
                255,
                255,
                255,
                150
            ),
            width=2
        )

        final.paste(
            result,
            (
                15,
                15
            ),
            result
        )

        return final

    # =====================================================
    # إنشاء صورة الترحيب
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

        image = self.add_design(
            image
        )

        draw = ImageDraw.Draw(
            image
        )

        # -------------------------------------------------
        # Avatar
        # -------------------------------------------------

        avatar = await self.download_avatar(
            member
        )

        if avatar:

            avatar_image = self.make_circle_avatar(
                avatar,
                225
            )

            avatar_x = 75

            avatar_y = (
                IMAGE_HEIGHT
                -
                avatar_image.height
            ) // 2

            image.paste(
                avatar_image,
                (
                    avatar_x,
                    avatar_y
                ),
                avatar_image
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

        # -------------------------------------------------
        # المتغيرات
        # -------------------------------------------------

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

        TEXT_LEFT = 390
        TEXT_RIGHT = 1120

        # =================================================
        # WELCOME
        # =================================================

        welcome_font = self.fit_font(
            draw,
            welcome_text,
            680,
            58,
            minimum_size=30,
            bold=True
        )

        self.draw_centered_in_area(
            draw,
            welcome_text,
            welcome_font,
            TEXT_LEFT,
            TEXT_RIGHT,
            70,
            YELLOW
        )

        # =================================================
        # اسم العضو
        # =================================================

        username_font = self.fit_font(
            draw,
            username_text,
            680,
            44,
            minimum_size=20,
            bold=True
        )

        self.draw_centered_in_area(
            draw,
            username_text,
            username_font,
            TEXT_LEFT,
            TEXT_RIGHT,
            150,
            WHITE
        )

        # =================================================
        # خط فاصل
        # =================================================

        draw.rounded_rectangle(
            (
                460,
                235,
                1050,
                241
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
            680,
            31,
            minimum_size=17,
            bold=True
        )

        self.draw_centered_in_area(
            draw,
            server_text,
            server_font,
            TEXT_LEFT,
            TEXT_RIGHT,
            270,
            LIGHT_BLUE
        )

        # =================================================
        # عدد الأعضاء
        # =================================================

        members_font = self.fit_font(
            draw,
            members_text,
            680,
            28,
            minimum_size=16,
            bold=False
        )

        self.draw_centered_in_area(
            draw,
            members_text,
            members_font,
            TEXT_LEFT,
            TEXT_RIGHT,
            325,
            LIGHT_YELLOW
        )

        # =================================================
        # حفظ
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
        # Avatar
        # =================================================

        if settings.get(
            "show_avatar",
            True
        ):

            try:

                embed.set_thumbnail(
                    url=member.display_avatar.url
                )

            except Exception:
                pass

        # =================================================
        # الصورة
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
    # Member Join
    # =====================================================

    @commands.Cog.listener()
    async def on_member_join(
        self,
        member
    ):

        try:

            # -------------------------------------------------
            # الإعدادات
            # -------------------------------------------------

            settings = welcome_settings_collection.find_one({
                "guild_id": str(
                    member.guild.id
                )
            })

            if not settings:
                return

            # -------------------------------------------------
            # التفعيل
            # -------------------------------------------------

            if not settings.get(
                "enabled",
                False
            ):
                return

            # -------------------------------------------------
            # الروم
            # -------------------------------------------------

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
            # الصورة
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
            # الرسالة
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

            embed = None

            if settings.get(
                "embed_enabled",
                True
            ):

                embed = self.build_welcome_embed(
                    member,
                    settings
                )

            # =================================================
            # إرسال
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
        # Discord Permissions
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
