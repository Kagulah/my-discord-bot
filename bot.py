import os
import sqlite3
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()

# Constants
GUILD_ID = 1371506090382069881
REGISTRATION_CHANNEL_ID = 1377744313840173096
VERIFIED_ROLE_NAME = "🌐 Verified"
TOURNAMENTS = ["Spring Showdown 2025"]  # Rename to your tournaments

# Get Discord Token
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN environment variable not set!")

# SQLite setup
DB_PATH = "registrations.db"
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# Create table if it doesn't exist
c.execute('''
CREATE TABLE IF NOT EXISTS registrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    ign TEXT,
    teammate1 TEXT,
    teammate2 TEXT,
    teammate3 TEXT
)
''')
conn.commit()

# Define Modal for registration input
class RegisterModal(discord.ui.Modal, title="Tournament Registration"):
    def __init__(self):
        super().__init__()
        self.ign = discord.ui.TextInput(label="Your Minecraft IGN", placeholder="Enter your username")
        self.teammate1 = discord.ui.TextInput(label="Teammate 1 (optional)", required=False)
        self.teammate2 = discord.ui.TextInput(label="Teammate 2 (optional)", required=False)
        self.teammate3 = discord.ui.TextInput(label="Teammate 3 (optional)", required=False)

        self.add_item(self.ign)
        self.add_item(self.teammate1)
        self.add_item(self.teammate2)
        self.add_item(self.teammate3)

    async def on_submit(self, interaction: discord.Interaction):
        ign = self.ign.value.strip()
        teammates = [t.value.strip() for t in [self.teammate1, self.teammate2, self.teammate3] if t.value.strip()]

        # Save registration to DB
        c.execute(
            '''
            INSERT INTO registrations (user_id, ign, teammate1, teammate2, teammate3)
            VALUES (?, ?, ?, ?, ?)
            ''',
            (
                interaction.user.id,
                ign,
                teammates[0] if len(teammates) > 0 else None,
                teammates[1] if len(teammates) > 1 else None,
                teammates[2] if len(teammates) > 2 else None,
            )
        )
        conn.commit()

        await interaction.response.send_message(
            f"✅ Registration successful!\nYour IGN: {ign}\n"
            f"Teammates: {', '.join(teammates) if teammates else 'None'}",
            ephemeral=True
        )

# Define the View with the Register button
class RegisterView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # Persistent view, no timeout

    @discord.ui.button(label="Register", style=discord.ButtonStyle.primary, custom_id="register_button")
    async def register_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not TOURNAMENTS:
            await interaction.response.send_message(
                "⚠️ There are currently no active tournaments. Registration is disabled.",
                ephemeral=True
            )
            return

        member = interaction.guild.get_member(interaction.user.id)
        if member is None or VERIFIED_ROLE_NAME not in [role.name for role in member.roles]:
            await interaction.response.send_message(
                "❌ You must verify your profile first!",
                ephemeral=True
            )
            return

        modal = RegisterModal()
        await interaction.response.send_modal(modal)

# Bot setup
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
guild = discord.Object(id=GUILD_ID)

@bot.event
async def on_ready():
    print(f"Bot is ready. Logged in as {bot.user}")

    # Sync slash commands to the guild
    try:
        await bot.tree.sync(guild=guild)
        print("✅ Slash commands synced.")
    except Exception as e:
        print(f"Error syncing commands: {e}")

    # Register persistent view so buttons keep working after restart
    bot.add_view(RegisterView())

    # Post or fetch the persistent registration message in the channel
    channel = bot.get_channel(REGISTRATION_CHANNEL_ID)
    if channel is None:
        print(f"Error: Cannot find channel with ID {REGISTRATION_CHANNEL_ID}")
        return

    # Check for existing registration message
    async for message in channel.history(limit=50):
        if message.author == bot.user and message.components:
            for row in message.components:
                for comp in row.children:
                    if getattr(comp, "custom_id", None) == "register_button":
                        print(f"Found existing registration message: {message.id}")
                        return

    # If no existing message, send a new one
    view = RegisterView()
    msg = await channel.send("📋 Click the button below to register for the tournament!", view=view)
    print(f"Posted new registration message: {msg.id}")

# Slash command to manually post registration message (admin only)
@bot.tree.command(name="post_register_message", description="Post the registration message in this channel", guild=guild)
@app_commands.checks.has_permissions(administrator=True)
async def post_register_message(interaction: discord.Interaction):
    view = RegisterView()
    await interaction.response.send_message(
        "📋 Click the button below to register for the tournament!",
        view=view
    )

# Run the bot
bot.run(TOKEN)
