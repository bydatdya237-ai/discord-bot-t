import os

import discord
from discord.ext import commands
from discord import ui
from motor.motor_asyncio import AsyncIOMotorClient


# =========================================================
# أسماء الإعدادات في الموقع
# =========================================================

COMMAND_NAME = "طلب"
LOG_COMMAND_NAME = "طلب-سجل"


# =========================================================
# Cog
# =========================================================

class OrdersCog(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        # =================================================
        # MongoDB
        # =================================================

        mongo_uri = os.environ.get("MONGO_URI")

        if mongo_uri:

            self.db_client = AsyncIOMotorClient(
                mongo_uri
            )

            self.db = self.db_client.discord_bot_db

            self.website_command_settings = (
                self.db.website_command_settings
            )

        else:

            self.db_client = None
            self.db = None
            self.website_command_settings = None

    # =====================================================
    # دعم guild_id كـ String أو Integer
    # =====================================================

    def guild_id_variants(
        self,
        guild_id
    ):

        variants = [
            str(guild_id)
        ]

        try:

            variants.append(
                int(guild_id)
            )

        except Exception:
            pass

        return variants

    # =====================================================
    # جلب إعدادات أمر من الموقع
    # =====================================================

    async def get_command_setting(
        self,
        guild_id,
        command_name
    ):

        if self.website_command_settings is None:
            return None

        guild_ids = self.guild_id_variants(
            guild_id
        )

        # -------------------------------------------------
        # البيانات الجديدة
        # -------------------------------------------------

        setting = await self.website_command_settings.find_one(
            {
                "guild_id": {
                    "$in": guild_ids
                },
                "command_name": str(command_name)
            }
        )

        if setting:
            return setting

        # -------------------------------------------------
        # دعم البيانات القديمة
        # -------------------------------------------------

        setting = await self.website_command_settings.find_one(
            {
                "guild_id": {
                    "$in": guild_ids
                },
                "name": str(command_name)
            }
        )

        return setting

    # =====================================================
    # التحقق من صلاحية استخدام أمر طلب
    # =====================================================

    async def has_order_permission(
        self,
        guild_id,
        member,
        channel_id=None
    ):

        if member is None:
            return False

        setting = await self.get_command_setting(
            guild_id,
            COMMAND_NAME
        )

        if not setting:
            return False

        # -------------------------------------------------
        # التفعيل
        # -------------------------------------------------

        if not setting.get(
            "enabled",
            False
        ):
            return False

        # -------------------------------------------------
        # الرتب
        # -------------------------------------------------

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

        # -------------------------------------------------
        # الروم
        # -------------------------------------------------

        if channel_id is not None:

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

            if str(channel_id) not in allowed_channel_ids:
                return False

        return True

    # =====================================================
    # جلب روم سجل الطلبات
    # =====================================================

    async def get_log_channel(
        self,
        guild
    ):

        setting = await self.get_command_setting(
            guild.id,
            LOG_COMMAND_NAME
        )

        if not setting:
            return None

        if not setting.get(
            "enabled",
            False
        ):
            return None

        channel_ids = setting.get(
            "channel_ids",
            []
        )

        if not channel_ids:
            return None

        # =================================================
        # نأخذ أول روم من الموقع
        # =================================================

        try:

            channel_id = int(
                str(channel_ids[0]).strip()
            )

        except (
            ValueError,
            TypeError
        ):

            return None

        # =================================================
        # جلب الروم
        # =================================================

        channel = self.bot.get_channel(
            channel_id
        )

        if channel is None:

            try:

                channel = await self.bot.fetch_channel(
                    channel_id
                )

            except (
                discord.NotFound,
                discord.Forbidden,
                discord.HTTPException
            ):

                return None

        # =================================================
        # التأكد من نفس السيرفر
        # =================================================

        channel_guild = getattr(
            channel,
            "guild",
            None
        )

        if channel_guild is not None:

            if channel_guild.id != guild.id:
                return None

        return channel

    # =====================================================
    # إنشاء Embed الطلب
    # =====================================================

    def create_order_embed(
        self,
        order_type,
        target_user,
        reason,
        requester
    ):

        embed = discord.Embed(
            title="📋 طلب جديد",
            color=discord.Color.gold()
        )

        embed.add_field(
            name="نوع الطلب",
            value=order_type,
            inline=False
        )

        embed.add_field(
            name="العضو المطلوب له الطلب",
            value=target_user.mention,
            inline=True
        )

        embed.add_field(
            name="ايدي العضو",
            value=str(target_user.id),
            inline=True
        )

        embed.add_field(
            name="السبب",
            value=reason,
            inline=False
        )

        embed.add_field(
            name="مقدم الطلب",
            value=requester.mention,
            inline=False
        )

        embed.add_field(
            name="حالة الطلب",
            value="⏳ قيد المراجعة",
            inline=False
        )

        embed.set_footer(
            text=f"ID مقدم الطلب: {requester.id}"
        )

        return embed


# =========================================================
# قائمة اختيار نوع الطلب
# =========================================================

class OrderSelect(
    ui.Select
):

    def __init__(
        self,
        cog,
        target_user
    ):

        self.cog = cog
        self.target_user = target_user

        options = [

            discord.SelectOption(
                label="رفع طلب عملة",
                description="رفع طلب خاص بالعملة",
                emoji="💰",
                value="رفع طلب عملة"
            ),

            discord.SelectOption(
                label="رفع طلب رتبة",
                description="رفع طلب خاص بالرتبة",
                emoji="👑",
                value="رفع طلب رتبة"
            ),

            discord.SelectOption(
                label="رفع طلب بنك",
                description="رفع طلب خاص بالبنك",
                emoji="🏦",
                value="رفع طلب بنك"
            ),

        ]

        super().__init__(
            placeholder="اختر نوع الطلب...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        # =================================================
        # السيرفر
        # =================================================

        if interaction.guild is None:

            await interaction.response.send_message(
                "❌ تعذر تحديد السيرفر.",
                ephemeral=True
            )

            return

        # =================================================
        # إعادة التحقق من الموقع
        # =================================================

        allowed = await self.cog.has_order_permission(
            interaction.guild.id,
            interaction.user,
            interaction.channel.id
        )

        if not allowed:

            await interaction.response.send_message(
                "❌ ليس لديك صلاحية استخدام نظام الطلبات.",
                ephemeral=True
            )

            return

        # =================================================
        # فتح Modal
        # =================================================

        await interaction.response.send_modal(
            OrderModal(
                self.cog,
                self.values[0],
                self.target_user
            )
        )


# =========================================================
# View اختيار نوع الطلب
# =========================================================

class OrderSelectView(
    ui.View
):

    def __init__(
        self,
        cog,
        target_user
    ):

        super().__init__(
            timeout=300
        )

        self.cog = cog

        self.add_item(
            OrderSelect(
                cog,
                target_user
            )
        )


# =========================================================
# Modal كتابة السبب
# =========================================================

class OrderModal(
    ui.Modal,
    title="تقديم طلب جديد"
):

    def __init__(
        self,
        cog,
        order_type,
        target_user
    ):

        super().__init__()

        self.cog = cog
        self.order_type = order_type
        self.target_user = target_user

        self.reason_input = ui.TextInput(
            label="السبب / التفاصيل",
            style=discord.TextStyle.paragraph,
            placeholder="اكتب تفاصيل أو سبب طلبك هنا...",
            required=True,
            max_length=1000
        )

        self.add_item(
            self.reason_input
        )

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        # =================================================
        # السيرفر
        # =================================================

        if interaction.guild is None:

            await interaction.response.send_message(
                "❌ تعذر تحديد السيرفر.",
                ephemeral=True
            )

            return

        # =================================================
        # إعادة التحقق من الصلاحية
        # =================================================

        allowed = await self.cog.has_order_permission(
            interaction.guild.id,
            interaction.user,
            interaction.channel.id
        )

        if not allowed:

            await interaction.response.send_message(
                "❌ لم تعد تملك صلاحية استخدام نظام الطلبات.",
                ephemeral=True
            )

            return

        # =================================================
        # جلب روم السجل
        # =================================================

        log_channel = await self.cog.get_log_channel(
            interaction.guild
        )

        if not log_channel:

            await interaction.response.send_message(
                "❌ لم يتم تحديد روم سجل الطلبات من الموقع.",
                ephemeral=True
            )

            return

        # =================================================
        # إنشاء الطلب
        # =================================================

        embed = self.cog.create_order_embed(
            self.order_type,
            self.target_user,
            self.reason_input.value,
            interaction.user
        )

        # =================================================
        # إرسال الطلب
        # =================================================

        try:

            await log_channel.send(
                embed=embed,
                view=OrderActionView(
                    self.cog
                )
            )

        except discord.Forbidden:

            await interaction.response.send_message(
                "❌ البوت لا يملك صلاحية إرسال الرسائل في روم سجل الطلبات.",
                ephemeral=True
            )

            return

        except discord.HTTPException:

            await interaction.response.send_message(
                "❌ حدث خطأ أثناء إرسال الطلب.",
                ephemeral=True
            )

            return

        # =================================================
        # نجاح
        # =================================================

        await interaction.response.send_message(
            f"✅ تم إرسال الطلب بنجاح للعضو "
            f"{self.target_user.mention}",
            ephemeral=True
        )


# =========================================================
# أزرار التحكم بالطلب
# =========================================================

class OrderActionView(
    ui.View
):

    def __init__(
        self,
        cog
    ):

        super().__init__(
            timeout=None
        )

        self.cog = cog

    # =====================================================
    # التحقق من صلاحية التحكم
    # =====================================================

    async def check_control_permission(
        self,
        interaction
    ):

        if interaction.guild is None:
            return False

        return await self.cog.has_order_permission(
            interaction.guild.id,
            interaction.user,
            None
        )

    # =====================================================
    # تم التسليم
    # =====================================================

    @ui.button(
        label="تم التسليم",
        style=discord.ButtonStyle.green,
        emoji="✅"
    )
    async def accept_order(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        allowed = await self.check_control_permission(
            interaction
        )

        if not allowed:

            await interaction.response.send_message(
                "❌ ليس لديك صلاحية للتحكم بالطلبات!",
                ephemeral=True
            )

            return

        # =================================================
        # التأكد من وجود Embed
        # =================================================

        if not interaction.message.embeds:

            await interaction.response.send_message(
                "❌ تعذر قراءة بيانات الطلب.",
                ephemeral=True
            )

            return

        embed = interaction.message.embeds[0]

        embed.color = discord.Color.green()

        # =================================================
        # تحديث الحالة
        # =================================================

        for i, field in enumerate(
            embed.fields
        ):

            if field.name == "حالة الطلب":

                embed.set_field_at(
                    i,
                    name="حالة الطلب",
                    value=(
                        "✅ تم التسليم\n"
                        f"بواسطة: {interaction.user.mention}"
                    ),
                    inline=False
                )

                break

        # =================================================
        # تعديل الرسالة
        # =================================================

        try:

            await interaction.message.edit(
                embed=embed,
                view=None
            )

        except discord.HTTPException:

            await interaction.response.send_message(
                "❌ حدث خطأ أثناء تحديث الطلب.",
                ephemeral=True
            )

            return

        await interaction.response.send_message(
            f"✅ تم قبول الطلب بواسطة "
            f"{interaction.user.mention}",
            ephemeral=True
        )

    # =====================================================
    # لم يتم التسليم
    # =====================================================

    @ui.button(
        label="لم يتم التسليم",
        style=discord.ButtonStyle.red,
        emoji="❌"
    )
    async def reject_order(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        allowed = await self.check_control_permission(
            interaction
        )

        if not allowed:

            await interaction.response.send_message(
                "❌ ليس لديك صلاحية للتحكم بالطلبات!",
                ephemeral=True
            )

            return

        # =================================================
        # التأكد من وجود Embed
        # =================================================

        if not interaction.message.embeds:

            await interaction.response.send_message(
                "❌ تعذر قراءة بيانات الطلب.",
                ephemeral=True
            )

            return

        embed = interaction.message.embeds[0]

        embed.color = discord.Color.red()

        # =================================================
        # تحديث الحالة
        # =================================================

        for i, field in enumerate(
            embed.fields
        ):

            if field.name == "حالة الطلب":

                embed.set_field_at(
                    i,
                    name="حالة الطلب",
                    value=(
                        "❌ لم يتم التسليم\n"
                        f"بواسطة: {interaction.user.mention}"
                    ),
                    inline=False
                )

                break

        # =================================================
        # تعديل الرسالة
        # =================================================

        try:

            await interaction.message.edit(
                embed=embed,
                view=None
            )

        except discord.HTTPException:

            await interaction.response.send_message(
                "❌ حدث خطأ أثناء تحديث الطلب.",
                ephemeral=True
            )

            return

        await interaction.response.send_message(
            f"❌ تم رفض الطلب بواسطة "
            f"{interaction.user.mention}",
            ephemeral=True
        )


# =========================================================
# أمر -طلب
# =========================================================

class OrdersCog(
    OrdersCog
):

    @commands.command(
        name="طلب"
    )
    async def order_cmd(
        self,
        ctx,
        member: discord.Member = None
    ):

        # =================================================
        # يجب أن يكون داخل سيرفر
        # =================================================

        if ctx.guild is None:
            return

        # =================================================
        # التحقق من الموقع
        # =================================================

        allowed = await self.has_order_permission(
            ctx.guild.id,
            ctx.author,
            ctx.channel.id
        )

        # =================================================
        # الأمر غير متاح
        # =================================================

        if not allowed:

            setting = await self.get_command_setting(
                ctx.guild.id,
                COMMAND_NAME
            )

            if not setting:
                return

            if not setting.get(
                "enabled",
                False
            ):
                return

            channel_ids = setting.get(
                "channel_ids",
                []
            )

            allowed_channels = {
                str(channel_id)
                for channel_id in channel_ids
            }

            # الأمر في روم غير مسموح
            if str(ctx.channel.id) not in allowed_channels:
                return

            # الرتبة غير مسموحة
            return

        # =================================================
        # لم يتم تحديد عضو
        # =================================================

        if member is None:

            await ctx.send(
                "❌ **خطأ في الاستخدام**\n"
                "يجب تحديد العضو المطلوب بالمنشن.\n\n"
                "📝 **مثال:**\n"
                "`-طلب @الشخص`",
                delete_after=10
            )

            try:

                await ctx.message.delete()

            except discord.HTTPException:
                pass

            return

        # =================================================
        # منع البوتات
        # =================================================

        if member.bot:

            await ctx.send(
                "❌ لا يمكن تقديم طلبات للبوتات.",
                delete_after=10
            )

            try:

                await ctx.message.delete()

            except discord.HTTPException:
                pass

            return

        # =================================================
        # رسالة اختيار نوع الطلب
        # =================================================

        embed = discord.Embed(
            title="📄 رفع طلب",
            description=(
                f"**العضو:** {member.mention}\n\n"
                "اختر نوع الطلب من القائمة بالأسفل."
            ),
            color=discord.Color.gold()
        )

        await ctx.send(
            embed=embed,
            view=OrderSelectView(
                self,
                member
            )
        )

        # =================================================
        # حذف أمر -طلب
        # =================================================

        try:

            await ctx.message.delete()

        except discord.HTTPException:
            pass

    # =====================================================
    # معالجة أخطاء الأمر
    # =====================================================

    @order_cmd.error
    async def order_cmd_error(
        self,
        ctx,
        error
    ):

        if ctx.guild is None:
            return

        # -------------------------------------------------
        # جلب الإعدادات
        # -------------------------------------------------

        setting = await self.get_command_setting(
            ctx.guild.id,
            COMMAND_NAME
        )

        if not setting:
            return

        if not setting.get(
            "enabled",
            False
        ):
            return

        # -------------------------------------------------
        # التأكد من الروم
        # -------------------------------------------------

        channel_ids = setting.get(
            "channel_ids",
            []
        )

        allowed_channels = {
            str(channel_id)
            for channel_id in channel_ids
        }

        if str(ctx.channel.id) not in allowed_channels:
            return

        # -------------------------------------------------
        # الأخطاء المتوقعة
        # -------------------------------------------------

        if isinstance(
            error,
            commands.MemberNotFound
        ):

            await ctx.send(
                "❌ لم أتمكن من العثور على هذا العضو.",
                delete_after=10
            )

            return

        if isinstance(
            error,
            commands.BadArgument
        ):

            await ctx.send(
                "❌ العضو غير صحيح.\n"
                "استخدم: `-طلب @الشخص`",
                delete_after=10
            )

            return

        # -------------------------------------------------
        # أخطاء غير متوقعة
        # -------------------------------------------------

        print(
            f"[Orders] Error: {repr(error)}"
        )


# =========================================================
# Setup
# =========================================================

async def setup(bot):

    await bot.add_cog(
        OrdersCog(bot)
    )
