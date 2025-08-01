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
    print(f"✅ Logged in as {client.user}")

    # Optional: clear guild-specific commands (if any)
    guild = client.get_guild(GUILD_ID)
    if guild:
        await client.tree.clear_commands(guild=discord.Object(id=GUILD_ID))
        await client.tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f"✅ Guild slash commands cleared and re-synced for {guild.name}.")

    # 🔥 Clear all global commands (one-time action)
    await client.tree.clear_commands()        # Remove global commands
    await client.tree.sync()                  # Sync to apply deletion
    print("✅ Global slash commands cleared and re-synced.")

async def main():
    keep_alive()  # Optional: if using a web server to keep the bot alive (e.g., Replit)
    async with client:
        await client.load_extension("clean_up_message")  # Load your combined cog
        await client.start(DISCORD_TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 Bot manually stopped.")
