import asyncio
import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from keep_alive import keep_alive  # Optional: only if you're using Replit-style hosting

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# Guild ID for slash command syncing
GUILD_ID = 1347682930465706004  # Replace with your server ID

# Set up bot intents and instance
intents = discord.Intents.default()
intents.message_content = True

client = commands.Bot(command_prefix='!', intents=intents)
client.tree.copy_global_to(guild=discord.Object(id=GUILD_ID))  # Force slash commands to your test server

@client.event
async def on_ready():
    guild = discord.Object(id=GUILD_ID)

    # Clear any previously registered commands in the guild (old leftovers)
    client.tree.clear_commands(guild=guild)

    # Resync with only the new ones
    await client.tree.sync(guild=guild)

    print(f"✅ Logged in as {client.user}")
    print("✅ Slash commands cleared and re-synced for guild")


async def main():
    keep_alive()  # Optional: if using a web server to keep bot alive
    async with client:
        await client.load_extension("clean_up_message")  # Load your combined cog
        await client.start(DISCORD_TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 Bot manually stopped.")
