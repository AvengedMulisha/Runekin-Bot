import asyncio
import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from keep_alive import keep_alive  # Optional: only if you're using Replit-style hosting

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# Set up bot intents and instance
intents = discord.Intents.default()
intents.message_content = True

client = commands.Bot(command_prefix='!', intents=intents)

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")
    # This block can be removed if you no longer want to manage slash commands
    print("Slash command management removed.")  # Inform that we're no longer managing slash commands

async def main():
    keep_alive()  # Optional: if using a web server to keep the bot alive (e.g., Replit)
    async with client:
        await client.load_extension("clean_up_message")  # Load your cog (assuming you have one)
        await client.start(DISCORD_TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 Bot manually stopped.")
