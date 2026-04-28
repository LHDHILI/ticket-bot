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
claimed_tickets = {}
claim_time = {}

LOG_CHANNEL = "ticket-logs"
ADMIN_ROLES = ["〢◈ King"]

# ========= READY =========
@bot.event
async def on_ready():
    print("🔥 BOT ONLINE")

    # تثبيت الأزرار بعد restart
    bot.add_view(ControlView())
    bot.add_view(TicketPanel())
    bot.add_view(UnclaimView())

# ========= MODAL =========
class SmartTicketForm(Modal):

    def __init__(self, reason):
        super().__init__(title=f"📋 {reason}")
        self.reason = reason

        # 🔥 أسئلة ذكية حسب نوع التكت

        if reason == "شكوى على مسعف":
            self.q1 = discord.ui.TextInput(label="👤 اسمك داخل المقاطعة")
            self.q2 = discord.ui.TextInput(label="📛 اسم المسعف او كوده الميداني")
            self.q3 = discord.ui.TextInput(label="📛 سبب الشكوى")
            self.q4 = discord.ui.TextInput(label="  رابط التصوير")
               


        elif reason ==  "طلب استقالة":
            self.q1 = discord.ui.TextInput(label="👤 اسمك داخل المقاطعة")
            self.q2 = discord.ui.TextInput(label="📅 سبب الاستقالة")
            self.q3 = discord.ui.TextInput( label="📝 الرتبة الحالية")
               
          

        elif reason == "تظلم من ترقية":
            self.q1 = discord.ui.TextInput(label="👤 اسمك داخل المقاطعة")
            self.q2 = discord.ui.TextInput(label="📊 سبب التظلم")
            self.q3 = discord.ui.TextInput(
                label="📝 شرح مفصل",
                style=discord.TextStyle.paragraph
            )

        elif reason == "مسؤولين التوظيف":
            self.q1 = discord.ui.TextInput(label="👤 اسمك داخل المقاطعة")
            self.q2 = discord.ui.TextInput(label="🎓 سبب التواصل")
            self.q3 = discord.ui.TextInput(
                label="📝 لماذا تريد الانضمام؟",
                style=discord.TextStyle.paragraph
            )

        elif reason == "قيادة الهلال الأحمر":
            self.q1 = discord.ui.TextInput(label="👤 اسمك داخل المقاطعة")
            self.q2 = discord.ui.TextInput(label="📌 سبب التواصل مع القيادة")
            self.q3 = discord.ui.TextInput(label="📝 التفاصيل")
               
          
        else:
            # fallback
            self.q1 = discord.ui.TextInput(label="👤 اسمك داخل المقاطعة")
            self.q2 = discord.ui.TextInput(label="📌 تفاصيل الطلب")
            self.q3 = discord.ui.TextInput(
                label="📝 شرح إضافي",
                style=discord.TextStyle.paragraph
            )

        self.add_item(self.q1)
        self.add_item(self.q2)
        self.add_item(self.q3)
        self.add_item(self.q4)

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

        embed = discord.Embed(
            title=f"🎫 {self.reason}",
            description="يرجى انتظار الرد من الإدارة 🚑",
            color=0x2b2d31
        )

        embed.add_field(name="👤 الاسم", value=self.q1.value, inline=False)
        embed.add_field(name="📌 التفاصيل", value=self.q2.value, inline=False)
        embed.add_field(name="📝 الشرح", value=self.q3.value, inline=False)

        await channel.send(
            content=f"السلام عليكم {member.mention}",
            embed=embed
        )

        await channel.send(view=ControlView())

        await interaction.response.send_message(
            f"✅ تم فتح التكت: {channel.mention}",
            ephemeral=True
        )

# ========= CONTROL =========
class ControlView(View):
    def __init__(self):
        super().__init__(timeout=None)

    # 👑 CLAIM
    @discord.ui.button(label="👑 استلام", style=discord.ButtonStyle.green)
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):

        # ❌ منع صاحب التكت من الاستلام
        if interaction.user.id in open_tickets and open_tickets[interaction.user.id] == interaction.channel.id:
            await interaction.response.send_message("❌ لا يمكنك استلام تكتك", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel

        if channel.id in claimed_tickets:
            await interaction.followup.send("❌ التكت مستلم بالفعل", ephemeral=True)
            return

        claimed_tickets[channel.id] = interaction.user.id
        claim_time[channel.id] = datetime.datetime.utcnow()

        # 🔒 قفل الكتابة لغير الإدارة
        for role in interaction.guild.roles:
            if role.name != "@everyone" and role.name not in ADMIN_ROLES:
                await channel.set_permissions(role, send_messages=False)

        # السماح للمستلم فقط
        await channel.set_permissions(interaction.user, send_messages=True)

        # تعطيل زر الاستلام
        button.disabled = True
        await interaction.message.edit(view=self)

        await channel.send(f"👑 تم الاستلام بواسطة {interaction.user.mention}")
        await interaction.followup.send("تم الاستلام", ephemeral=True)

        # 🔄 زر التخلي
        await channel.send(view=UnclaimView())

    # 🔒 CLOSE (Lock فقط)
    @discord.ui.button(label="🔒 اغلاق التكت", style=discord.ButtonStyle.gray)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ ليس لديك صلاحية", ephemeral=True)
            return

        channel = interaction.channel
        guild = interaction.guild

        # 📜 Transcript (اختياري خليته كما هو)
        messages = [m async for m in channel.history(limit=200)]
        messages.reverse()

        html = "<html><body style='background:#1e1e1e;color:white;'>"
        for m in messages:
            html += f"<p><b>{m.author}</b>: {m.content}</p>"
        html += "</body></html>"

        file = io.BytesIO(html.encode())

        log = discord.utils.get(guild.text_channels, name=LOG_CHANNEL)
        if log:
            await log.send(file=discord.File(file, "transcript.html"))

        # 🔒 قفل التكت (موش حذف)
        await channel.set_permissions(guild.default_role, send_messages=False)

        await interaction.response.send_message("🔒 تم إغلاق التكت", ephemeral=True)
        await channel.send("🔒 تم إغلاق التكت، لا يمكن الكتابة الآن")

        # 🗑️ زر الحذف يظهر بعد الإغلاق
        await channel.send(view=DeleteView())
        class DeleteView(View):
          def __init__(self):
            super().__init__(timeout=None)

    @discord.ui.button(label="🗑️ حذف التكت", style=discord.ButtonStyle.red)
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):

        channel = interaction.channel

        # ✅ فقط الأدمن أو المستلم
        if not interaction.user.guild_permissions.administrator and claimed_tickets.get(channel.id) != interaction.user.id:
            await interaction.response.send_message("❌ ليس لديك صلاحية", ephemeral=True)
            return

        await interaction.response.send_message("🗑️ يتم حذف التكت...", ephemeral=True)
        await channel.delete()
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

    @discord.ui.button(label="📩 مسؤولين التوظيف", style=discord.ButtonStyle.primary)
    async def b5(self, interaction, button):
        await interaction.response.send_modal(SmartTicketForm("مسؤولين التوظيف"))

    @discord.ui.button(label="📩 تظلم من ترقية", style=discord.ButtonStyle.primary)
    async def b6(self, interaction, button):
        await interaction.response.send_modal(SmartTicketForm("تظلم من ترقية"))

    @discord.ui.button(label="📩 طلب استقالة", style=discord.ButtonStyle.primary)
    async def b7(self, interaction, button):
        await interaction.response.send_modal(SmartTicketForm("طلب استقالة"))

    @discord.ui.button(label="📩 إعادة خدمة", style=discord.ButtonStyle.primary)
    async def b8(self, interaction, button):
        await interaction.response.send_modal(SmartTicketForm("إعادة خدمة"))

# ========= COMMAND =========
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
