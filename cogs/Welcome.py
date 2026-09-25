import os
import io
import discord

from discord.ext import commands
from pymongo import MongoClient

from PIL import Image, ImageDraw, ImageFont, ImageFilter


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

BACKGROUND_LEFT = (45, 18, 80)
BACKGROUND_RIGHT = (150, 70, 220)

WHITE = (255, 255, 255)
LIGHT_PURPLE = (220, 190, 255)
DARK = (25, 15, 40)


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
            text = text.replace(key, value)

        return text

    # =====================================================
    # تحميل الخط
    # =====================================================

    def get_font(self, size, bold=False):

        possible_fonts = []

        if bold:
            possible_fonts = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
            ]

        else:
            possible_fonts = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
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

        bbox = draw.textbbox(
            (0, 0),
            text,
            font=font
        )

        text_width = bbox[2] - bbox[0]

        x = (IMAGE_WIDTH - text_width) // 2

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
            (IMAGE_WIDTH, IMAGE_HEIGHT)
        )

        pixels = image.load()

        for x in range(IMAGE_WIDTH):

            ratio = x / IMAGE_WIDTH

            r = int(
                BACKGROUND_LEFT[0]
                +
                (BACKGROUND_RIGHT[0] - BACKGROUND_LEFT[0])
                * ratio
            )

            g = int(
                BACKGROUND_LEFT[1]
                +
                (BACKGROUND_RIGHT[1] - BACKGROUND_LEFT[1])
                * ratio
            )

            b = int(
                BACKGROUND_LEFT[2]
                +
                (BACKGROUND_RIGHT[2] - BACKGROUND_LEFT[2])
                * ratio
            )

            for y in range(IMAGE_HEIGHT):

                pixels[x, y] = (
                    r,
                    g,
                    b
                )

        return image

    # =====================================================
    # إضافة دوائر ضوئية للخلفية
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

        # دائرة كبيرة يسار
        draw.ellipse(
            (-150, -150, 350, 350),
            fill=(210, 150, 255, 35)
        )

        # دائرة كبيرة يمين
        draw.ellipse(
            (900, 200, 1400, 700),
            fill=(190, 120, 255, 30)
        )

        # دوائر صغيرة
        draw.ellipse(
            (80, 390, 180, 490),
            fill=(255, 255, 255, 20)
        )

        draw.ellipse(
            (1020, 50, 1100, 130),
            fill=(255, 255, 255, 18)
        )

        overlay = overlay.filter(
            ImageFilter.GaussianBlur(25)
        )

        image = Image.alpha_composite(
            image.convert("RGBA"),
            overlay
        )

        return image.convert("RGB")

    # =====================================================
    # تحميل صورة العضو
    # =====================================================

    async def download_avatar(self, member):

        try:

            avatar_asset = member.display_avatar.replace(
                size=512,
                format="png"
            )

            avatar_bytes = await avatar_asset.read()

            return Image.open(
                io.BytesIO(avatar_bytes)
            ).convert("RGBA")

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
        size=250
    ):

        avatar = avatar.resize(
            (size, size),
            Image.Resampling.LANCZOS
        )

        mask = Image.new(
            "L",
            (size, size),
            0
        )

        mask_draw = ImageDraw.Draw(
            mask
        )

        mask_draw.ellipse(
            (0, 0, size, size),
            fill=255
        )

        result = Image.new(
            "RGBA",
            (size, size),
            (0, 0, 0, 0)
        )

        result.paste(
            avatar,
            (0, 0),
            mask
        )

        # إطار
        border = Image.new(
            "RGBA",
            (size + 16, size + 16),
            (0, 0, 0, 0)
        )

        border_draw = ImageDraw.Draw(
            border
        )

        border_draw.ellipse(
            (2, 2, size + 13, size + 13),
            outline=(255, 255, 255, 230),
            width=8
        )

        border.paste(
            result,
            (8, 8),
            result
        )

        return border

    # =====================================================
    # توليد صورة الترحيب
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

        draw = ImageDraw.Draw(
            image
        )

        # =================================================
        # الخطوط
        # =================================================

        welcome_font = self.get_font(
            58,
            bold=True
        )

        username_font = self.get_font(
            42,
            bold=True
        )

        normal_font = self.get_font(
            28,
            bold=False
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

            avatar_x = 80
            avatar_y = (
                IMAGE_HEIGHT - circle_avatar.height
            ) // 2

            image.paste(
                circle_avatar,
                (avatar_x, avatar_y),
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
        # مكان النص
        # =================================================

        text_area_x = 390

        # WELCOME
        draw.text(
            (text_area_x, 95),
            welcome_text,
            font=welcome_font,
            fill=WHITE
        )

        # اسم العضو
        draw.text(
            (text_area_x, 175),
            username_text,
            font=username_font,
            fill=LIGHT_PURPLE
        )

        # خط فاصل
        draw.rounded_rectangle(
            (
                text_area_x,
                245,
                text_area_x + 500,
                250
            ),
            radius=3,
            fill=(255, 255, 255, 80)
        )

        # اسم السيرفر
        draw.text(
            (text_area_x, 280),
            server_text,
            font=normal_font,
            fill=WHITE
        )

        # عدد الأعضاء
        draw.text(
            (text_area_x, 325),
            members_text,
            font=normal_font,
            fill=LIGHT_PURPLE
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

    def get_color(self, color_value):

        if not color_value:
            return discord.Color.purple()

        try:

            if isinstance(color_value, int):
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
                int(color_value, 16)
            )

        except Exception:

            return discord.Color.purple()

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
            "{user}\n\nنورت السيرفر ونتمنى لك وقتًا ممتعًا معنا 💜"
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
                    "#B66CFF"
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
    async def on_member_join(self, member):

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

            except (ValueError, TypeError):

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
