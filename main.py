# main.py

import discord
from discord.ext import commands
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()  # Loads .env file
TOKEN = os.getenv("DISCORD_TOKEN")  # Securely get token

intents = discord.Intents.default()
intents.message_content = True

client = commands.Bot(command_prefix='!', intents=intents)

@client.event
async def on_ready():
    print(f'✅ Logged in as {client.user} (ID: {client.user.id})')

async def main():
    async with client:
        await client.load_extension("clean_up_message")  # Load your cog once here
        await client.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
