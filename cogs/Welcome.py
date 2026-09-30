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

WHITE = (255, 255, 255)
GOLD = (255, 210, 65)


# =========================================================
# Welcome Cog
# =========================================================

class WelcomeCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    # =====================================================
    # حساب عمر الحساب
    # =====================================================

    def get_account_age(self, member):

        try:

            created_at = member.created_at
            now = discord.utils.utcnow()

            total_days = (
                now - created_at
            ).days

            years = total_days // 365
            remaining_days = total_days % 365

            months = remaining_days // 30
            days = remaining_days % 30

            if years > 0:

                if months > 0:
                    return f"{years} سنة و {months} شهر"

                return f"{years} سنة"

            if months > 0:

                if days > 0:
                    return f"{months} شهر و {days} يوم"

                return f"{months} شهر"

            if days > 0:
                return f"{days} يوم"

            return "أقل من يوم"

        except Exception:

            return "غير معروف"

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
            "{account_age}": self.get_account_age(member),
        }

        for key, value in replacements.items():

            text = text.replace(
                key,
                str(value)
            )

        return text

    # =====================================================
    # تحميل الخلفية من قاعدة البيانات أو الملف المحلي
    # =====================================================

    def get_background(self, settings):

        # أولاً: محاولة جلب الصورة المخزنة في MongoDB كـ Binary
        bg_binary = settings.get("bg_image_binary")

        if bg_binary:
            try:
                bg_image = Image.open(io.BytesIO(bg_binary)).convert("RGB")
                return bg_image.resize((IMAGE_WIDTH, IMAGE_HEIGHT), Image.Resampling.LANCZOS)
            except Exception as e:
                print(f"[WelcomeCog] Error loading background from DB: {e}")

        # ثانياً: محاولة البحث محلياً إن لم توجد في القاعدة
        bg_path = "Welcome.py"
        if os.path.isfile(bg_path):
            try:
                bg_image = Image.open(bg_path).convert("RGB")
                return bg_image.resize((IMAGE_WIDTH, IMAGE_HEIGHT), Image.Resampling.LANCZOS)
            except Exception:
                pass

        # خلفية افتراضية احتياطية
        return Image.new("RGB", (IMAGE_WIDTH, IMAGE_HEIGHT), (8, 12, 35))

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
    # Avatar دائري متناسق مع الدائرة الزرقاء
    # =====================================================

    def make_circle_avatar(
        self,
        avatar,
        size=210
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

        return avatar_result

    # =====================================================
    # إنشاء صورة الترحيب ودمج البروفايل داخل الدائرة بدقة
    # =====================================================

    async def generate_welcome_image(
        self,
        member,
        settings
    ):

        image = self.get_background(settings)

        avatar = await self.download_avatar(
            member
        )

        if avatar:

            avatar_size = 210
            avatar_image = self.make_circle_avatar(
                avatar,
                avatar_size
            )

            # الإحداثيات المضبّطة خصيصاً لمركز الدائرة في صورتك
            avatar_x = 792 - (avatar_size // 2)
            avatar_y = 158 - (avatar_size // 2)

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

        output = io.BytesIO()

        image.save(
            output,
            format="PNG"
        )

        output.seek(0)

        return output

    # =====================================================
    # أمر لتعيين خلفية الترحيب عبر رفع الصورة مباشرة في الشات
    # =====================================================

    @commands.command(name="setwelcomebg")
    @commands.has_permissions(administrator=True)
    async def set_welcome_bg(self, ctx):
        if not ctx.message.attachments:
            await ctx.send("❌ الرجاء إرفاق صورة مع الأمر!")
            return

        attachment = ctx.message.attachments[0]
        if not attachment.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
            await ctx.send("❌ الملف المرفق ليس صالحاً كصورة!")
            return

        try:
            image_bytes = await attachment.read()
            
            welcome_settings_collection.update_one(
                {"guild_id": str(ctx.guild.id)},
                {"$set": {"bg_image_binary": image_bytes}},
                upsert=True
            )

            await ctx.send("✅ تم حفظ خلفية الترحيب الجديدة وتحديث المقاسات بنجاح!")
        except Exception as e:
            await ctx.send(f"❌ حدث خطأ أثناء حفظ الصورة: {e}")

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

        embed.add_field(
            name="👥 أعضاء السيرفر",
            value=f"**{member.guild.member_count:,}** عضو",
            inline=True
        )

        embed.add_field(
            name="📅 عمر الحساب",
            value=f"**{self.get_account_age(member)}**",
            inline=True
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
