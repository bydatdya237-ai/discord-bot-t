import os
import io
import discord

from discord.ext import commands
from pymongo import MongoClient

from PIL import Image, ImageDraw, ImageFont, ImageFilter


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

BG_1 = (8, 12, 35)
BG_2 = (24, 35, 85)
BG_3 = (67, 30, 125)

WHITE = (255, 255, 255)
GOLD = (255, 210, 65)
LIGHT_GOLD = (255, 235, 145)
BLUE = (90, 190, 255)
PURPLE = (180, 100, 255)


# =========================================================
# Welcome Cog
# =========================================================

class WelcomeCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

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
            fonts = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
                "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
            ]

        else:
            fonts = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
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

        return ImageFont.load_default()

    # =====================================================
    # الخلفية المتدرجة
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
                    BG_1[0]
                    +
                    (BG_2[0] - BG_1[0])
                    * ratio2
                )

                g = int(
                    BG_1[1]
                    +
                    (BG_2[1] - BG_1[1])
                    * ratio2
                )

                b = int(
                    BG_1[2]
                    +
                    (BG_2[2] - BG_1[2])
                    * ratio2
                )

            else:

                ratio2 = (
                    ratio - 0.5
                ) * 2

                r = int(
                    BG_2[0]
                    +
                    (BG_3[0] - BG_2[0])
                    * ratio2
                )

                g = int(
                    BG_2[1]
                    +
                    (BG_3[1] - BG_2[1])
                    * ratio2
                )

                b = int(
                    BG_2[2]
                    +
                    (BG_3[2] - BG_2[2])
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
    # مؤثرات الخلفية
    # =====================================================

    def add_background_effects(self, image):

        overlay = Image.new(
            "RGBA",
            image.size,
            (0, 0, 0, 0)
        )

        draw = ImageDraw.Draw(
            overlay
        )

        draw.ellipse(
            (-180, -180, 420, 420),
            fill=(90, 170, 255, 55)
        )

        draw.ellipse(
            (850, -150, 1400, 400),
            fill=(190, 80, 255, 60)
        )

        draw.ellipse(
            (850, 280, 1400, 830),
            fill=(50, 170, 255, 45)
        )

        draw.ellipse(
            (-250, 300, 350, 900),
            fill=(180, 80, 255, 35)
        )

        circles = [
            (70, 80, 10),
            (160, 390, 7),
            (275, 65, 6),
            (1010, 80, 9),
            (1110, 150, 6),
            (1080, 410, 10),
            (950, 350, 5),
            (1160, 330, 7),
            (760, 60, 5),
            (680, 430, 7),
        ]

        for x, y, radius in circles:

            draw.ellipse(
                (
                    x - radius,
                    y - radius,
                    x + radius,
                    y + radius
                ),
                fill=(255, 220, 90, 180)
            )

        draw.line(
            (0, 95, 300, 0),
            fill=(100, 190, 255, 70),
            width=3
        )

        draw.line(
            (900, 500, 1200, 390),
            fill=(210, 110, 255, 80),
            width=3
        )

        draw.line(
            (980, 0, 1200, 90),
            fill=(255, 215, 80, 70),
            width=2
        )

        overlay = overlay.filter(
            ImageFilter.GaussianBlur(28)
        )

        image = Image.alpha_composite(
            image.convert("RGBA"),
            overlay
        )

        return image.convert("RGB")

    # =====================================================
    # زخارف التصميم
    # =====================================================

    def add_design(self, image):

        draw = ImageDraw.Draw(
            image
        )

        draw.rounded_rectangle(
            (
                18,
                18,
                IMAGE_WIDTH - 18,
                IMAGE_HEIGHT - 18
            ),
            radius=30,
            outline=(
                255,
                220,
                100
            ),
            width=3
        )

        draw.rounded_rectangle(
            (
                28,
                28,
                IMAGE_WIDTH - 28,
                IMAGE_HEIGHT - 28
            ),
            radius=24,
            outline=(
                100,
                190,
                255
            ),
            width=1
        )

        draw.line(
            (65, 55, 250, 55),
            fill=GOLD,
            width=3
        )

        draw.line(
            (950, 55, 1135, 55),
            fill=GOLD,
            width=3
        )

        draw.line(
            (65, 445, 250, 445),
            fill=BLUE,
            width=3
        )

        draw.line(
            (950, 445, 1135, 445),
            fill=BLUE,
            width=3
        )

        corner = 45

        draw.line(
            (35, 35, 35 + corner, 35),
            fill=GOLD,
            width=4
        )

        draw.line(
            (35, 35, 35, 35 + corner),
            fill=GOLD,
            width=4
        )

        draw.line(
            (1165, 35, 1165 - corner, 35),
            fill=GOLD,
            width=4
        )

        draw.line(
            (1165, 35, 1165, 35 + corner),
            fill=GOLD,
            width=4
        )

        draw.line(
            (35, 465, 35 + corner, 465),
            fill=GOLD,
            width=4
        )

        draw.line(
            (35, 465, 35, 465 - corner),
            fill=GOLD,
            width=4
        )

        draw.line(
            (1165, 465, 1165 - corner, 465),
            fill=GOLD,
            width=4
        )

        draw.line(
            (1165, 465, 1165, 465 - corner),
            fill=GOLD,
            width=4
        )

        return image

    # =====================================================
    # تحميل Avatar
    # =====================================================

    async def download_avatar(self, member):

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
    # Avatar دائري مع توهج
    # =====================================================

    def make_circle_avatar(
        self,
        avatar,
        size=250
    ):

        avatar = avatar.resize(
            (
                size,
                size
            ),
            Image.Resampling.LANCZOS
        )

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
                size - 1,
                size - 1
            ),
            fill=255
        )

        avatar_result = Image.new(
            "RGBA",
            (
                size,
                size
            ),
            (0, 0, 0, 0)
        )

        avatar_result.paste(
            avatar,
            (0, 0),
            mask
        )

        padding = 38

        final_size = size + (
            padding * 2
        )

        final = Image.new(
            "RGBA",
            (
                final_size,
                final_size
            ),
            (0, 0, 0, 0)
        )

        glow = Image.new(
            "RGBA",
            (
                final_size,
                final_size
            ),
            (0, 0, 0, 0)
        )

        glow_draw = ImageDraw.Draw(
            glow
        )

        glow_draw.ellipse(
            (
                8,
                8,
                final_size - 8,
                final_size - 8
            ),
            outline=(
                255,
                210,
                65,
                180
            ),
            width=18
        )

        glow = glow.filter(
            ImageFilter.GaussianBlur(15)
        )

        final = Image.alpha_composite(
            final,
            glow
        )

        final_draw = ImageDraw.Draw(
            final
        )

        final_draw.ellipse(
            (
                14,
                20,
                final_size - 6,
                final_size + 2
            ),
            fill=(
                0,
                0,
                0,
                120
            )
        )

        final_draw.ellipse(
            (
                8,
                8,
                final_size - 8,
                final_size - 8
            ),
            outline=GOLD,
            width=8
        )

        final_draw.ellipse(
            (
                17,
                17,
                final_size - 17,
                final_size - 17
            ),
            outline=(
                120,
                205,
                255,
                230
            ),
            width=3
        )

        final.paste(
            avatar_result,
            (
                padding,
                padding
            ),
            avatar_result
        )

        return final

    # =====================================================
    # رسم WELCOME
    # =====================================================

    def draw_welcome_text(
        self,
        image,
        text="WELCOME"
    ):

        draw = ImageDraw.Draw(
            image
        )

        font = self.get_font(
            62,
            bold=True
        )

        bbox = draw.textbbox(
            (0, 0),
            text,
            font=font
        )

        text_width = (
            bbox[2] - bbox[0]
        )

        text_height = (
            bbox[3] - bbox[1]
        )

        x = (
            IMAGE_WIDTH
            -
            text_width
        ) // 2

        y = 350

        draw.text(
            (
                x + 4,
                y + 6
            ),
            text,
            font=font,
            fill=(
                0,
                0,
                0,
                170
            )
        )

        glow = Image.new(
            "RGBA",
            image.size,
            (0, 0, 0, 0)
        )

        glow_draw = ImageDraw.Draw(
            glow
        )

        glow_draw.text(
            (
                x,
                y
            ),
            text,
            font=font,
            fill=(
                255,
                210,
                65,
                170
            )
        )

        glow = glow.filter(
            ImageFilter.GaussianBlur(10)
        )

        image = Image.alpha_composite(
            image.convert("RGBA"),
            glow
        ).convert("RGB")

        draw = ImageDraw.Draw(
            image
        )

        draw.text(
            (
                x,
                y
            ),
            text,
            font=font,
            fill=WHITE
        )

        line_width = min(
            text_width + 30,
            430
        )

        line_x1 = (
            IMAGE_WIDTH - line_width
        ) // 2

        line_x2 = (
            IMAGE_WIDTH + line_width
        ) // 2

        draw.rounded_rectangle(
            (
                line_x1,
                y + text_height + 20,
                line_x2,
                y + text_height + 25
            ),
            radius=3,
            fill=GOLD
        )

        return image

    # =====================================================
    # إنشاء صورة الترحيب
    # =====================================================

    async def generate_welcome_image(
        self,
        member,
        settings
    ):

        image = self.create_background()

        image = self.add_background_effects(
            image
        )

        image = self.add_design(
            image
        )

        avatar = await self.download_avatar(
            member
        )

        if avatar:

            avatar_image = self.make_circle_avatar(
                avatar,
                250
            )

            avatar_x = (
                IMAGE_WIDTH
                -
                avatar_image.width
            ) // 2

            avatar_y = 55

            image = image.convert(
                "RGBA"
            )

            image.alpha_composite(
                avatar_image,
                (
                    avatar_x,
                    avatar_y
                )
            )

            image = image.convert(
                "RGB"
            )

        welcome_text = "WELCOME"

        image = self.draw_welcome_text(
            image,
            welcome_text
        )

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

        if settings.get(
            "generated_image",
            True
        ):

            embed.set_image(
                url="attachment://welcome.png"
            )

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

            settings = welcome_settings_collection.find_one({
                "guild_id": str(
                    member.guild.id
                )
            })

            if not settings:
                return

            if not settings.get(
                "enabled",
                False
            ):
                return

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

            message = settings.get(
                "message",
                ""
            )

            message = self.replace_variables(
                message,
                member
            )

            embed = None

            if settings.get(
                "embed_enabled",
                True
            ):

                embed = self.build_welcome_embed(
                    member,
                    settings
                )

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

        except discord.Forbidden:

            print(
                f"[WelcomeCog] لا توجد صلاحية كافية "
                f"في السيرفر {member.guild.id}"
            )

        except discord.HTTPException as e:

            print(
                f"[WelcomeCog] Discord API Error: {e}"
            )

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
