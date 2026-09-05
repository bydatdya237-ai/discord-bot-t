import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Modal, Select, View

class CreateRoleModal(Modal, title="مصنع الرتب الخارق"):
    role_name = discord.ui.TextInput(
        label="اسم الرتبة الجديدة",
        placeholder="مثال: VIP, Developer, Legend...",
        max_length=50
    )
    role_color = discord.ui.TextInput(
        label="لون الرتبة (اكتب: red, blue, gold, green)",
        placeholder="gold",
        max_length=20,
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        name = self.role_name.value.strip()
        color_input = self.role_color.value.strip().lower()

        # خريطة ألوان ذكية
        color_map = {
            "red": discord.Color.red(),
            "blue": discord.Color.blue(),
            "green": discord.Color.green(),
            "gold": discord.Color.gold(),
            "orange": discord.Color.orange(),
            "purple": discord.Color.purple(),
            "dark": discord.Color.dark_embed()
        }
        
        role_color = color_map.get(color_input, discord.Color.default())

        try:
            # إنشاء الرتبة في السيرفر
            new_role = await guild.create_role(name=name, color=role_color, reason=f"Created by {interaction.user}")
            
            embed = discord.Embed(
                title="✨ تم خلق رتبة جديدة بنجاح!",
                description=f"تم إطلاق الرتبة **{new_role.mention}** وإضافتها لسيرفرك.",
                color=role_color
            )
            embed.add_field(name="معرف الرتبة (ID):", value=f"`{new_role.id}`", inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(f"❌ فشل إنشاء الرتبة: تأكد أن رتبة البوت أعلى من الرتبة المراد إنشاؤها ولديه صلاحية (Manage Roles).", ephemeral=True)


class RolesControlCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # 1. أمر إنشاء الرتب
    @app_commands.command(name="رتبة", description="إنشاء رتبة جديدة وتلوينها بضغطة زر")
    async def create_role_command(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message("❌ عذراً، لا تمتلك صلاحية إدارة الرتب (Manage Roles)!", ephemeral=True)
            return
        
        await interaction.response.send_modal(CreateRoleModal())

    # 2. أمر التحكم بصلاحيات الرومات (إظهار أو إخفاء روم معين عن رتبة)
    @app_commands.command(name="صلاحية_روم", description="التحكم الكامل: إعطاء أو منع رتبة من رؤية أو الكتابة في هذا الروم")
    @app_commands.describe(
        role="الرتبة المستهدفة",
        action="اختر هل تريد إعطاء الصلاحية أو منعها",
        target_type="هل تريد التحكم في (رؤية الروم) أو (الكتابة فيه)?"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="🟢 السماح (Allow)", value="allow"),
        app_commands.Choice(name="🔴 منع (Deny)", value="deny")
    ], target_type=[
        app_commands.Choice(name="👁️ رؤية الروم (Read Messages)", value="read"),
        app_commands.Choice(name="✍️ الكتابة في الروم (Send Messages)", value="write")
    ])
    async def manage_room_permission(
        self, 
        interaction: discord.Interaction, 
        role: discord.Role, 
        action: str, 
        target_type: str
    ):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("❌ عذراً، لا تمتلك صلاحية إدارة القنوات!", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        
        # استخراج الصلاحيات الحالية للرتبة في هذا الروم أو إنشاء إعداد جديد
        overwrite = channel.overwrites_for(role)
        
        is_allow = (action == "allow")
        
        if target_type == "read":
            overwrite.read_messages = is_allow
            desc_text = "رؤية ودخول الروم"
        else:
            overwrite.send_messages = is_allow
            desc_text = "الكتابة وإرسال الرسائل في الروم"

        try:
            # تطبيق التعديلات الجذرية على الروم الحالي
            await channel.set_permissions(role, overwrite=overwrite)
            
            status_word = "السماح بـ" if is_allow else "منع"
            embed = discord.Embed(
                title="🛡️ تم تحديث صلاحيات الروم بنجاح",
                description=f"تم **{status_word} ({desc_text})** للرتبة {role.mention} في هذا الروم ({channel.mention}).",
                color=discord.Color.green() if is_allow else discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(f"❌ حدث خطأ أثناء تعديل الصلاحيات: تأكد من تسلسل رتبة البوت.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(RolesControlCog(bot))
