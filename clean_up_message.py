import discord
import itertools
import datetime
from discord.ext import commands, tasks

utc = datetime.timezone.utc

# If no tzinfo is given then UTC is assumed.
time = datetime.time(hour=1, minute=9, tzinfo=utc)

CHANNELS_TO_DELETE_FROM = [
    #planned-events
    1383717273704857670,
    #event-polls-and-payments
    1385130581599457413

]

async def setup(bot):
    await bot.add_cog(MyCog(bot, CHANNELS_TO_DELETE_FROM))
    print('added daily clean up task')

async def delete_message(channel, messages_to_delete, now):
    # more than 100
    if len(messages_to_delete) > 100:
        for messages in chunk(messages_to_delete, 100):
            await delete_message(channel, messages)

        return

    # over 14 days old
    bulk= []
    fourteen_days_ago = now - datetime.timedelta(days=14)

    for message in messages_to_delete:
        if message.created_at <  fourteen_days_ago:
            await message.delete()
        else:
            bulk.append(message)

    await channel.delete_messages(bulk)


async def delete_messages(channel):
    if isinstance(channel, discord.TextChannel):
        now = discord.utils.utcnow()
        delta = datetime.timedelta(days=7)
        jeff = now - delta
        messages_to_delete = []
        async for message in channel.history(before=jeff):
            if message.pinned:
                # print(message.content)
                continue
            if message.created_at < jeff:
                messages_to_delete.append(message)
        # await delete_message(channel, messages_to_delete, now)
        for message in messages_to_delete:
            print(message.content)

async def delete_old_messages_from_channels(client, channels):
    for channel in channels:
        discord_channel = client.get_channel(channel)

        print(discord_channel.name)

        await delete_messages(discord_channel)

class MyCog(commands.Cog):
    def __init__(self, bot, channels):
        self.bot = bot
        self.channels = channels
        self.my_task.start()

    def cog_unload(self):
        self.my_task.cancel()

    @tasks.loop(time=time)
    async def my_task(self):
        print('cleaning up messages')
        await delete_old_messages_from_channels(self.bot, self.channels)



def chunk(items, chunk_size):
    iterator = iter(items)

    return [list(itertools.islice(iterator, chunk_size)) for _ in  range((len(items) + chunk_size - 1) // chunk_size)]