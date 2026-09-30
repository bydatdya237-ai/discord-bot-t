import os
import io
import discord

from discord.ext import commands
from pymongo import MongoClient

from PIL import Image, ImageDraw, ImageOps


# =========================================================
# MongoDB
# =========================================================

MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    raise RuntimeError("MONGO_URI غير موجود في Environment Variables")

mongo = MongoClient(MONGO_URI)
db = mongo["discord_bot_db"]

welcome_settings_collection = db["welcome_settings"]
website_command_collection = db["website_command_settings"]


# =========================================================
# أبعاد صورة الترحيب النهائية
# =========================================================

IMAGE_WIDTH = 1200
IMAGE_HEIGHT = 500


# =========================================================
# معلومات الدائرة في التصميم الأصلي
# الصورة الأصلية: 1920 × 1080
# مركز الدائرة: 1386 × 530
# قطر الدائرة: 502
# =========================================================

ORIGINAL_IMAGE_WIDTH = 1920
ORIGINAL_IMAGE_HEIGHT = 1080

ORIGINAL_CIRCLE_X = 1386
ORIGINAL_CIRCLE_Y = 530
ORIGINAL_CIRCLE_DIAMETER = 502


# =========================================================
# إعدادات الأفاتار
# =========================================================

AVATAR_PADDING = 4


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
    # جلب إعداد الأمر من الموقع
    # =====================================================

    def get_website_command_setting(
        self,
        guild_id,
        command_name
    ):

        guild_id_str = str(guild_id)

        setting = website_command_collection.find_one({
            "$and": [
                {
                    "$or": [
                        {"guild_id": guild_id_str},
                        {"guild_id": guild_id}
                    ]
                },
                {
                    "$or": [
                        {"command_name": command_name},
                        {"name": command_name},
                        {"command": command_name}
                    ]
                }
            ]
        })

        return setting

    # =====================================================
    # التحقق من صلاحية الأمر من الموقع
    # =====================================================

    def website_command_allowed(
        self,
        member,
        channel,
        command_name
    ):

        if member is None:
            return False

        if channel is None:
            return False

        setting = self.get_website_command_setting(
            member.guild.id,
            command_name
        )

        # الأمر غير موجود في الموقع
        if not setting:
            return False

        # الأمر غير مفعّل
        if not setting.get(
            "enabled",
            False
        ):
            return False

        # =================================================
        # الرتب المسموحة
        # =================================================

        role_ids = setting.get(
            "role_ids",
            []
        )

        if not role_ids:
            return False

        allowed_role_ids = {
            str(role_id)
            for role_id in role_ids
        }

        user_role_ids = {
            str(role.id)
            for role in member.roles
        }

        if not allowed_role_ids.intersection(
            user_role_ids
        ):
            return False

        # =================================================
        # الرومات المسموحة
        # =================================================

        channel_ids = setting.get(
            "channel_ids",
            []
        )

        if not channel_ids:
            return False

        allowed_channel_ids = {
            str(channel_id)
            for channel_id in channel_ids
        }

        if str(channel.id) not in allowed_channel_ids:
            return False

        return True

    # =====================================================
    # تجهيز الخلفية إلى 1200 × 500
    #
    # نحافظ على نسبة الصورة.
    # يتم القص من المنتصف فقط، بدون تشويه.
    # =====================================================

    def prepare_background(
        self,
        source_image
    ):

        source_width, source_height = source_image.size

        target_ratio = (
            IMAGE_WIDTH / IMAGE_HEIGHT
        )

        source_ratio = (
            source_width / source_height
        )

        # =================================================
        # الصورة أعرض من المطلوب
        # =================================================

        if source_ratio > target_ratio:

            crop_height = source_height

            crop_width = int(
                source_height * target_ratio
            )

        # =================================================
        # الصورة أطول من المطلوب
        # =================================================

        else:

            crop_width = source_width

            crop_height = int(
                source_width / target_ratio
            )

        # =================================================
        # القص من المنتصف
        # =================================================

        left = int(
            (source_width - crop_width) / 2
        )

        top = int(
            (source_height - crop_height) / 2
        )

        right = left + crop_width
        bottom = top + crop_height

        cropped = source_image.crop(
            (
                left,
                top,
                right,
                bottom
            )
        )

        # =================================================
        # تحويل إلى 1200 × 500
        # =================================================

        final_image = cropped.resize(
            (
                IMAGE_WIDTH,
                IMAGE_HEIGHT
            ),
            Image.Resampling.LANCZOS
        )

        return final_image

    # =====================================================
    # تحميل الخلفية
    # =====================================================

    def get_background(
        self,
        settings
    ):

        bg_binary = settings.get(
            "bg_image_binary"
        )

        # =================================================
        # الخلفية الموجودة في MongoDB
        # =================================================

        if bg_binary:

            try:

                source_image = Image.open(
                    io.BytesIO(bg_binary)
                ).convert("RGB")

                return self.prepare_background(
                    source_image
                )

            except Exception as e:

                print(
                    f"[WelcomeCog] "
                    f"Background DB Error: {e}"
                )

        # =================================================
        # خلفية محلية احتياطية
        # =================================================

        bg_path = "welcome_bg.png"

        if os.path.isfile(bg_path):

            try:

                source_image = Image.open(
                    bg_path
                ).convert("RGB")

                return self.prepare_background(
                    source_image
                )

            except Exception as e:

                print(
                    f"[WelcomeCog] "
                    f"Local Background Error: {e}"
                )

        # =================================================
        # خلفية افتراضية
        # =================================================

        return Image.new(
            "RGB",
            (
                IMAGE_WIDTH,
                IMAGE_HEIGHT
            ),
            (8, 12, 35)
        )

    # =====================================================
    # تحميل Avatar العضو
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

            avatar = Image.open(
                io.BytesIO(data)
            ).convert("RGBA")

            return avatar

        except Exception as e:

            print(
                f"[WelcomeCog] Avatar Error: {e}"
            )

            return None

    # =====================================================
    # إنشاء Avatar دائري
    # =====================================================

    def make_circle_avatar(
        self,
        avatar,
        size
    ):

        size = max(
            1,
            int(size)
        )

        # =================================================
        # قص الأفاتار إلى مربع بدون تشويه
        # =================================================

        avatar = ImageOps.fit(
            avatar,
            (
                size,
                size
            ),
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5)
        )

        # =================================================
        # إنشاء القناع الدائري
        # =================================================

        mask = Image.new(
            "L",
            (
                size,
                size
            ),
            0
        )

        draw = ImageDraw.Draw(
            mask
        )

        draw.ellipse(
            (
                0,
                0,
                size - 1,
                size - 1
            ),
            fill=255
        )

        # =================================================
        # إنشاء الصورة الشفافة
        # =================================================

        result = Image.new(
            "RGBA",
            (
                size,
                size
            ),
            (0, 0, 0, 0)
        )

        result.paste(
            avatar,
            (0, 0),
            mask
        )

        return result

    # =====================================================
    # حساب مكان الدائرة بعد تحويل 1920×1080
    # إلى 1200×500
    # =====================================================

    def get_circle_position(self):

        target_ratio = (
            IMAGE_WIDTH / IMAGE_HEIGHT
        )

        original_ratio = (
            ORIGINAL_IMAGE_WIDTH
            / ORIGINAL_IMAGE_HEIGHT
        )

        # =================================================
        # الصورة الأصلية أعرض من النسبة المطلوبة
        # =================================================

        if original_ratio > target_ratio:

            crop_height = ORIGINAL_IMAGE_HEIGHT

            crop_width = int(
                ORIGINAL_IMAGE_HEIGHT
                * target_ratio
            )

        else:

            crop_width = ORIGINAL_IMAGE_WIDTH

            crop_height = int(
                ORIGINAL_IMAGE_WIDTH
                / target_ratio
            )

        # =================================================
        # مكان القص
        # =================================================

        crop_left = (
            ORIGINAL_IMAGE_WIDTH
            - crop_width
        ) / 2

        crop_top = (
            ORIGINAL_IMAGE_HEIGHT
            - crop_height
        ) / 2

        # =================================================
        # Scale
        # =================================================

        scale_x = (
            IMAGE_WIDTH
            / crop_width
        )

        scale_y = (
            IMAGE_HEIGHT
            / crop_height
        )

        # =================================================
        # مركز الدائرة بعد القص والتحجيم
        # =================================================

        circle_x = (
            ORIGINAL_CIRCLE_X
            - crop_left
        ) * scale_x

        circle_y = (
            ORIGINAL_CIRCLE_Y
            - crop_top
        ) * scale_y

        # =================================================
        # قطر الدائرة بعد التحجيم
        # =================================================

        circle_diameter = (
            ORIGINAL_CIRCLE_DIAMETER
            * scale_x
        )

        return (
            circle_x,
            circle_y,
            circle_diameter
        )

    # =====================================================
    # إنشاء صورة الترحيب
    # =====================================================

    async def generate_welcome_image(
        self,
        member,
        settings
    ):

        # =================================================
        # تحميل الخلفية
        # =================================================

        image = self.get_background(
            settings
        )

        # =================================================
        # تحميل Avatar
        # =================================================

        avatar = await self.download_avatar(
            member
        )

        # =================================================
        # إذا فشل تحميل Avatar
        # =================================================

        if avatar is None:

            print(
                "[WelcomeCog] "
                "لم يتم تحميل Avatar العضو"
            )

            output = io.BytesIO()

            image.save(
                output,
                format="PNG"
            )

            output.seek(0)

            return output

        # =================================================
        # حساب الدائرة
        # =================================================

        (
            circle_x,
            circle_y,
            circle_diameter
        ) = self.get_circle_position()

        # =================================================
        # حجم Avatar
        # =================================================

        avatar_size = int(
            circle_diameter
            - (
                AVATAR_PADDING * 2
            )
        )

        avatar_size = max(
            1,
            avatar_size
        )

        # =================================================
        # إنشاء Avatar دائري
        # =================================================

        avatar_image = self.make_circle_avatar(
            avatar,
            avatar_size
        )

        # =================================================
        # وضع Avatar في منتصف الدائرة
        # =================================================

        avatar_x = int(
            circle_x
            - (
                avatar_size / 2
            )
        )

        avatar_y = int(
            circle_y
            - (
                avatar_size / 2
            )
        )

        # =================================================
        # دمج Avatar
        # =================================================

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

        # =================================================
        # حفظ الصورة النهائية
        # =================================================

        output = io.BytesIO()

        image.save(
            output,
            format="PNG"
        )

        output.seek(0)

        return output

    # =====================================================
    # أمر تغيير خلفية الترحيب
    # =====================================================

    @commands.command(
        name="setwelcomebg"
    )
    async def set_welcome_bg(
        self,
        ctx
    ):

        if ctx.guild is None:
            return

        # =================================================
        # صلاحيات الموقع
        # =================================================

        if not self.website_command_allowed(
            ctx.author,
            ctx.channel,
            "setwelcomebg"
        ):
            return

        # =================================================
        # التأكد من وجود صورة
        # =================================================

        if not ctx.message.attachments:

            await ctx.send(
                "❌ الرجاء إرفاق صورة مع الأمر!"
            )

            return

        attachment = ctx.message.attachments[0]

        # =================================================
        # أنواع الملفات
        # =================================================

        allowed_extensions = (
            ".png",
            ".jpg",
            ".jpeg",
            ".webp"
        )

        if not attachment.filename.lower().endswith(
            allowed_extensions
        ):

            await ctx.send(
                "❌ الملف المرفق ليس صالحاً كصورة!"
            )

            return

        # =================================================
        # الحد الأقصى 10MB
        # =================================================

        MAX_FILE_SIZE = 10 * 1024 * 1024

        if attachment.size > MAX_FILE_SIZE:

            await ctx.send(
                "❌ حجم الصورة كبير جداً! الحد الأقصى 10MB."
            )

            return

        try:

            image_bytes = await attachment.read()

            # =================================================
            # فحص الصورة
            # =================================================

            test_image = Image.open(
                io.BytesIO(image_bytes)
            )

            test_image.verify()

            # =================================================
            # إعادة فتح الصورة
            # =================================================

            source_image = Image.open(
                io.BytesIO(image_bytes)
            ).convert("RGB")

            # =================================================
            # ضبطها إلى 1200 × 500
            # =================================================

            normalized_image = self.prepare_background(
                source_image
            )

            # =================================================
            # حفظ PNG
            # =================================================

            output = io.BytesIO()

            normalized_image.save(
                output,
                format="PNG",
                optimize=True
            )

            normalized_bytes = output.getvalue()

            # =================================================
            # MongoDB
            # =================================================

            welcome_settings_collection.update_one(
                {
                    "guild_id": str(
                        ctx.guild.id
                    )
                },
                {
                    "$set": {
                        "bg_image_binary": normalized_bytes,
                        "bg_width": IMAGE_WIDTH,
                        "bg_height": IMAGE_HEIGHT
                    }
                },
                upsert=True
            )

            await ctx.send(
                "✅ تم حفظ خلفية الترحيب بنجاح!\n"
                "📐 الأبعاد: 1200×500\n"
                "🖼️ تم ضبط الصورة بدون تشويه."
            )

        except Exception as e:

            print(
                f"[WelcomeCog] "
                f"Background Error: {e}"
            )

            await ctx.send(
                "❌ حدث خطأ أثناء معالجة الصورة."
            )

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
        # صورة العضو الصغيرة
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
        # صورة الترحيب
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
    # عند دخول عضو
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
            # إرسال الترحيب
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

        except discord.Forbidden:

            print(
                f"[WelcomeCog] "
                f"لا توجد صلاحية كافية "
                f"في السيرفر {member.guild.id}"
            )

        except discord.HTTPException as e:

            print(
                f"[WelcomeCog] "
                f"Discord API Error: {e}"
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
