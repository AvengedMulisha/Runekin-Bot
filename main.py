import asyncio
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

from keep_alive import keep_alive  # Local import (your own module)

# Load environment variables
load_dotenv()

# Intents and bot setup
intents = discord.Intents.default()
intents.message_content = True

client = commands.Bot(command_prefix='!', intents=intents)

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

async def main():
    keep_alive()  # Start web server to keep bot alive on Replit
    async with client:
        # Load all your cogs here
        await client.load_extension("clean_up_message")  # Your cleanup + approval cog
       # await client.load_extension("points_cog")        # Your new points system cog
        await client.start(os.getenv("DISCORD_TOKEN"))

# Run the bot
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot shut down manually.")
