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
    raise RuntimeError(
        "MONGO_URI غير موجود في Environment Variables"
    )


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
# مكان دائرة الأفاتار في التصميم
# =========================================================

FINAL_CIRCLE_CENTER_X = 798
FINAL_CIRCLE_CENTER_Y = 250
FINAL_CIRCLE_DIAMETER = 294


# =========================================================
# إعدادات الأفاتار
# =========================================================

# المسافة بين الأفاتار وحافة الدائرة
AVATAR_PADDING = 12

# تحريك الأفاتار لليمين قليلًا
AVATAR_OFFSET_X = 10

# بدون تحريك عمودي
AVATAR_OFFSET_Y = 0


# =========================================================
# Welcome Cog
# =========================================================

class WelcomeCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    # =====================================================
    # استبدال المتغيرات
    # =====================================================

    def replace_variables(
        self,
        text,
        member
    ):

        if text is None:
            return ""

        text = str(text)

        replacements = {
            "{user}": member.mention,
            "{username}": member.display_name,
            "{server}": member.guild.name,
            "{member_count}": str(
                member.guild.member_count
            ),
            "{user_id}": str(
                member.id
            ),
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

        guild_id_str = str(
            guild_id
        )

        setting = website_command_collection.find_one({
            "$and": [
                {
                    "$or": [
                        {
                            "guild_id": guild_id_str
                        },
                        {
                            "guild_id": guild_id
                        }
                    ]
                },
                {
                    "$or": [
                        {
                            "command_name": command_name
                        },
                        {
                            "name": command_name
                        },
                        {
                            "command": command_name
                        }
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

        # =================================================
        # الأمر غير موجود في الموقع
        # =================================================

        if not setting:
            return False

        # =================================================
        # الأمر غير مفعّل
        # =================================================

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
    # يتم القص من المنتصف بدون تشويه.
    # =====================================================

    def prepare_background(
        self,
        source_image
    ):

        source_width, source_height = (
            source_image.size
        )

        target_ratio = (
            IMAGE_WIDTH / IMAGE_HEIGHT
        )

        source_ratio = (
            source_width / source_height
        )

        # =================================================
        # الصورة أعرض من النسبة المطلوبة
        # =================================================

        if source_ratio > target_ratio:

            crop_height = source_height

            crop_width = int(
                source_height * target_ratio
            )

        # =================================================
        # الصورة أطول من النسبة المطلوبة
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

                # =================================================
                # إذا كانت محفوظة أصلًا 1200×500
                # نستخدمها مباشرة
                # =================================================

                if source_image.size == (
                    IMAGE_WIDTH,
                    IMAGE_HEIGHT
                ):

                    return source_image

                # =================================================
                # إذا كانت قديمة أو بحجم مختلف
                # نضبطها مرة واحدة
                # =================================================

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

        if os.path.isfile(
            bg_path
        ):

            try:

                source_image = Image.open(
                    bg_path
                ).convert("RGB")

                if source_image.size == (
                    IMAGE_WIDTH,
                    IMAGE_HEIGHT
                ):

                    return source_image

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

            avatar_asset = (
                member.display_avatar.replace(
                    size=512,
                    format="png"
                )
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
        # حجم الأفاتار
        # =================================================

        avatar_size = int(
            FINAL_CIRCLE_DIAMETER
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
        # مكان Avatar
        #
        # تم تحريكه 10 بكسل لليمين
        # =================================================

        avatar_x = int(
            FINAL_CIRCLE_CENTER_X
            - (
                avatar_size / 2
            )
            + AVATAR_OFFSET_X
        )

        avatar_y = int(
            FINAL_CIRCLE_CENTER_Y
            - (
                avatar_size / 2
            )
            + AVATAR_OFFSET_Y
        )

        # =================================================
        # دمج Avatar مع الخلفية
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
        # حفظ الصورة
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

        attachment = (
            ctx.message.attachments[0]
        )

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

        MAX_FILE_SIZE = (
            10 * 1024 * 1024
        )

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
            # ضبط الصورة إلى 1200×500
            # =================================================

            normalized_image = (
                self.prepare_background(
                    source_image
                )
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

            normalized_bytes = (
                output.getvalue()
            )

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
                        "bg_image_binary":
                            normalized_bytes,

                        "bg_width":
                            IMAGE_WIDTH,

                        "bg_height":
                            IMAGE_HEIGHT
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
    # معاينة الترحيب
    #
    # يستخدم حساب الشخص الذي نفذ الأمر كعضو تجريبي.
    # نفس الخلفية + نفس الأفاتار + نفس الرسالة.
    # =====================================================

    @commands.command(
        name="previewwelcome"
    )
    async def preview_welcome(
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
            "previewwelcome"
        ):
            return

        try:

            settings = (
                welcome_settings_collection.find_one({
                    "guild_id": str(
                        ctx.guild.id
                    )
                })
            )

            # =================================================
            # لا توجد إعدادات
            # =================================================

            if not settings:

                await ctx.send(
                    "❌ لا توجد إعدادات ترحيب لهذا السيرفر."
                )

                return

            # =================================================
            # إنشاء صورة المعاينة
            #
            # نستخدم الشخص الذي نفذ الأمر
            # =================================================

            image_bytes = (
                await self.generate_welcome_image(
                    ctx.author,
                    settings
                )
            )

            image_file = discord.File(
                image_bytes,
                filename="welcome_preview.png"
            )

            # =================================================
            # تجهيز رسالة الترحيب
            # =================================================

            message = settings.get(
                "message",
                ""
            )

            message = self.replace_variables(
                message,
                ctx.author
            )

            # =================================================
            # رسالة المعاينة
            # =================================================

            preview_text = (
                "👀 **معاينة الترحيب**\n\n"
            )

            if message:

                preview_text += message

            await ctx.send(
                content=preview_text,
                file=image_file
            )

        except discord.Forbidden:

            print(
                f"[WelcomeCog] "
                f"لا توجد صلاحية للمعاينة "
                f"في السيرفر {ctx.guild.id}"
            )

        except discord.HTTPException as e:

            print(
                f"[WelcomeCog] "
                f"Preview Discord API Error: {e}"
            )

        except Exception as e:

            print(
                f"[WelcomeCog] "
                f"Preview Error: {e}"
            )

            await ctx.send(
                "❌ حدث خطأ أثناء إنشاء المعاينة."
            )

    # =====================================================
    # عند دخول عضو
    #
    # يتم إرسال الترحيب كرسالة عادية + صورة Attachment
    # بدون Embed.
    # =====================================================

    @commands.Cog.listener()
    async def on_member_join(
        self,
        member
    ):

        try:

            settings = (
                welcome_settings_collection.find_one({
                    "guild_id": str(
                        member.guild.id
                    )
                })
            )

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

                image_bytes = (
                    await self.generate_welcome_image(
                        member,
                        settings
                    )
                )

                image_file = discord.File(
                    image_bytes,
                    filename="welcome.png"
                )

            # =================================================
            # الرسالة النصية
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
            # إرسال الترحيب
            #
            # بدون Embed
            # فقط النص + الصورة
            # =================================================

            if image_file:

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
                    content=message
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

async def setup(
    bot
):

    await bot.add_cog(
        WelcomeCog(bot)
    )
