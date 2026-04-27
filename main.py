import discord
from discord.ext import commands
from discord.ui import View, Modal
import io
import datetime
import os

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ========= STORAGE =========
open_tickets = {}
claimed_tickets = {}   # channel_id -> user_id
claim_time = {}        # channel_id -> datetime

LOG_CHANNEL = "ticket-logs"
ADMIN_ROLES = ["Admin", "Supervisor", "Leader"]

# ========= READY =========
@bot.event
async def on_ready():
    print("🔥 BOT ONLINE")

# ========= MODAL =========
class SmartTicketForm(Modal):

    def __init__(self, reason):
        super().__init__(title=f"📋 {reason}")
        self.reason = reason

        self.q1 = discord.ui.TextInput(label="الاسم")
        self.q2 = discord.ui.TextInput(label="تفاصيل الطلب")
        self.q3 = discord.ui.TextInput(label="شرح إضافي", style=discord.TextStyle.paragraph)

        self.add_item(self.q1)
        self.add_item(self.q2)
        self.add_item(self.q3)

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        member = interaction.user

        category = discord.utils.get(guild.categories, name="📁 Tickets")
        if category is None:
            category = await guild.create_category("📁 Tickets")

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        channel = await guild.create_text_channel(
            name=f"ticket-{member.name}",
            category=category,
            overwrites=overwrites
        )

        open_tickets[member.id] = channel.id

        await channel.send(
            f"🎫 **{self.reason}**\n\n"
            f"👤 {self.q1.value}\n"
            f"📌 {self.q2.value}\n"
            f"📝 {self.q3.value}"
        )

        await channel.send(view=ControlView())

        await interaction.response.send_message(
            f"✅ تم فتح التكت: {channel.mention}",
            ephemeral=True
        )

# ========= CONTROL SYSTEM =========
class ControlView(View):
    def __init__(self):
        super().__init__(timeout=None)

    # 👑 CLAIM
@discord.ui.button(label="👑 استلام التكت", style=discord.ButtonStyle.green)
async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):

    channel = interaction.channel

    if channel.id in claimed_tickets:
        await interaction.response.send_message("❌ التكت مستلم بالفعل", ephemeral=True)
        return

    claimed_tickets[channel.id] = interaction.user.id
    claim_time[channel.id] = datetime.datetime.utcnow()

    # 🔐 قفل الكتابة
    for role in interaction.guild.roles:
        if role.name != "@everyone" and role.name not in ADMIN_ROLES:
            await channel.set_permissions(role, send_messages=False)

    await channel.set_permissions(interaction.user, send_messages=True)

    # 🧠 مهم: قفل الزر مباشرة
    button.disabled = True
    await interaction.message.edit(view=self)

    embed = discord.Embed(
        title="👑 تم استلام التكت",
        description=f"👤 {interaction.user.mention}",
        color=0x00ff99
    )

    await interaction.response.send_message("تم الاستلام بنجاح", ephemeral=True)
    await channel.send(embed=embed)

    # 🔒 CLOSE
    @discord.ui.button(label="🔒 إغلاق التكت", style=discord.ButtonStyle.red)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):

        if not any(r.name in ADMIN_ROLES for r in interaction.user.roles):
            await interaction.response.send_message("❌ ليس لديك صلاحية", ephemeral=True)
            return

        channel = interaction.channel
        guild = interaction.guild

        messages = [m async for m in channel.history(limit=200)]
        messages.reverse()

        html = f"""
        <html>
        <body style="background:#1e1e1e;color:white;font-family:Arial">
        <h2>📜 Transcript - {channel.name}</h2>
        <hr>
        """

        for m in messages:
            html += f"<p><b>{m.author}</b>: {m.content}</p>"

        html += "</body></html>"

        file = io.BytesIO(html.encode())

        log = discord.utils.get(guild.text_channels, name=LOG_CHANNEL)
        if log:
            await log.send(file=discord.File(file, "transcript.html"))

        claimed_tickets.pop(channel.id, None)
        claim_time.pop(channel.id, None)

        await interaction.response.send_message("🔒 يتم الإغلاق...", ephemeral=True)
        await channel.delete()

# ========= UNCLAIM =========
class UnclaimView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔄 التخلي عن الاستلام", style=discord.ButtonStyle.red)
    async def unclaim(self, interaction: discord.Interaction, button: discord.ui.Button):

        channel = interaction.channel

        if channel.id not in claimed_tickets:
            await interaction.response.send_message("❌ التكت موش مستلم", ephemeral=True)
            return

        if claimed_tickets[channel.id] != interaction.user.id:
            await interaction.response.send_message("❌ الزر خاص بالمستلم فقط", ephemeral=True)
            return

        start = claim_time.get(channel.id)
        now = datetime.datetime.utcnow()

        duration = "غير معروف"
        if start:
            diff = now - start
            duration = f"{int(diff.total_seconds() // 60)} دقيقة"

        claimed_tickets.pop(channel.id, None)
        claim_time.pop(channel.id, None)

        for role in interaction.guild.roles:
            if role.name != "@everyone":
                await channel.set_permissions(role, send_messages=True)

        embed = discord.Embed(
            title="🔄 تم التخلي عن التكت",
            description=(
                f"👤 السابق: {interaction.user.mention}\n"
                f"⏱ وقت التخلي: {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"⏳ مدة الاستلام: {duration}"
            ),
            color=0xffcc00
        )

        await channel.send(embed=embed)
        await interaction.response.send_message("تم التخلي", ephemeral=True)

# ========= PANEL =========
class TicketPanel(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📩 شكوى على مسعف", style=discord.ButtonStyle.primary)
    async def b1(self, interaction, button):
        await interaction.response.send_modal(SmartTicketForm("شكوى على مسعف"))

    @discord.ui.button(label="📩 مسؤولين الدورات", style=discord.ButtonStyle.primary)
    async def b2(self, interaction, button):
        await interaction.response.send_modal(SmartTicketForm("مسؤولين الدورات"))

    @discord.ui.button(label="📩 قيادة الهلال الأحمر", style=discord.ButtonStyle.primary)
    async def b3(self, interaction, button):
        await interaction.response.send_modal(SmartTicketForm("قيادة الهلال الأحمر"))

    @discord.ui.button(label="📩 الشؤون الإدارية", style=discord.ButtonStyle.primary)
    async def b4(self, interaction, button):
        await interaction.response.send_modal(SmartTicketForm("الشؤون الإدارية"))

    @discord.ui.button(label="📩 التوظيف", style=discord.ButtonStyle.primary)
    async def b5(self, interaction, button):
        await interaction.response.send_modal(SmartTicketForm("التوظيف"))

    @discord.ui.button(label="📩 تظلم من ترقية", style=discord.ButtonStyle.primary)
    async def b6(self, interaction, button):
        await interaction.response.send_modal(SmartTicketForm("تظلم من ترقية"))

    @discord.ui.button(label="📩 استقالة", style=discord.ButtonStyle.primary)
    async def b7(self, interaction, button):
        await interaction.response.send_modal(SmartTicketForm("استقالة"))

    @discord.ui.button(label="📩 إعادة خدمة", style=discord.ButtonStyle.primary)
    async def b8(self, interaction, button):
        await interaction.response.send_modal(SmartTicketForm("إعادة خدمة"))




# ========= PANEL COMMAND =========
@bot.command()
async def panel(ctx):

    embed = discord.Embed(
        title="🚑 قطاع الهلال الأحمر",
        description=(
            "👋 مرحبا بكم في نظام التذاكر الرسمي\n\n"
            "📌 اختر نوع التكت ثم املأ الاستمارة\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ احترام القوانين داخل التكتات إجباري"
        ),
        color=0xff2d2d
    )

    embed.set_image(url="https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExY2ZjZ2Z3c3loYWZqY2Zzamg3YWVlZWRtNjVqazcxOHNkYTYweGhrNiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/sWOIurMRIehaw/giphy.gif")
    embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1426529602423230524/1498424312594567390/Square_City.png?ex=69f11be3&is=69efca63&hm=38c77779136a05ae8d6655abe8e9b435da1496819fdab4e52ce22c93409d575b")
    embed.set_footer(text="🚑 الهلال الأحمر | Ticket System", icon_url="https://cdn.discordapp.com/attachments/1426529602423230524/1498424312594567390/Square_City.png?ex=69f11be3&is=69efca63&hm=38c77779136a05ae8d6655abe8e9b435da1496819fdab4e52ce22c93409d575b")

    await ctx.send(embed=embed, view=TicketPanel())

import os
bot.run(os.getenv("TOKEN"))

