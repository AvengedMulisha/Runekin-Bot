# This example requires the 'message_content' intent.
# permissions 76800

import discord
from discord.ext import commands
import os



intents = discord.Intents.default()
intents.message_content = True

client = commands.Bot('!', intents=intents)



@client.event
async def on_ready():
    await client.load_extension('clean_up_message')
    print(f'We have logged in as {client.user}')




client.run(os.environ['DISCORD_TOKEN'])
