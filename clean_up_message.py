import discord
import itertools
import datetime
from discord.ext import commands, tasks

# ========== CONFIG ==========
utc = datetime.timezone.utc
cleanup_time = datetime.time(hour=0, minute=0, tzinfo=utc)

CHANNELS_TO_DELETE_FROM = [
    1383717273704857670,  # planned-events
    1385130581599457413   # event-polls-and-payments
]

SUBMISSION_CHANNEL_ID = 1395474287531397283
APPROVAL_CHANNEL_ID = 1398377286436257872
APPROVED_POSTS_CHANNEL_ID = 1395474287531397283

# ========== CLEANUP COG ==========

class CleanupCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cleanup_task.start()

    def cog_unload(self):
        self.cleanup_task.cancel()

    @tasks.loop(time=cleanup_time)
    async def cleanup_task(self):
        print('🧹 Cleaning up old messages...')
        await self.delete_old_messages()

    async def delete_old_messages(self):
        now = discord.utils.utcnow()
        cutoff = now - datetime.timedelta(days=7)

        for channel_id in CHANNELS_TO_DELETE_FROM:
            channel = self.bot.get_channel(channel_id)
            if not isinstance(channel, discord.TextChannel):
                continue

            to_delete = []
            async for message in channel.history(before=cutoff):
                if not message.pinned:
                    to_delete.append(message)

            await self.bulk_delete(channel, to_delete, now)

    async def bulk_delete(self, channel, messages, now):
        if len(messages) > 100:
            for chunked in chunk(messages, 100):
                await self.bulk_delete(channel, chunked, now)
            return

        bulk = []
        old_cutoff = now - datetime.timedelta(days=14)
        for m in messages:
            if m.created_at < old_cutoff:
                await m.delete()
            else:
                bulk.append(m)

        await channel.delete_messages(bulk)

def chunk(items, size):
    iterator = iter(items)
    return [list(itertools.islice(iterator, size)) for _ in range((len(items) + size - 1) // size)]

# ========== APPROVAL VIEW ==========

class ApprovalView(discord.ui.View):
    def __init__(self, message_content, author):
        super().__init__(timeout=None)  # Buttons will expire after 5 minutes
        self.message_content = message_content
        self.author = author

    @discord.ui.button(label="✅ Approve", style=discord.ButtonStyle.green)
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        approved_channel = interaction.client.get_channel(APPROVED_POSTS_CHANNEL_ID)
        if approved_channel:
            await approved_channel.send(
                f"**Submitted by {self.author.mention}:**\n{self.message_content}"
            )
        await interaction.message.delete()  # ✅ Delete the approval message with buttons
        await interaction.response.send_message("✅ Approved and posted.", ephemeral=True)
        self.stop()

    @discord.ui.button(label="❌ Reject", style=discord.ButtonStyle.red)
    async def reject_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()  # ❌ Delete the approval message with buttons
        await interaction.response.send_message("❌ Rejected.", ephemeral=True)
        self.stop()


# ========== APPROVAL COG ==========

class ApprovalCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        if message.channel.id == SUBMISSION_CHANNEL_ID:
            approval_channel = self.bot.get_channel(APPROVAL_CHANNEL_ID)
            if approval_channel:
                embed = discord.Embed(
                    title="New Submission",
                    description=message.content,
                    color=discord.Color.blue()
                )
                embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)

                view = ApprovalView(message.content, message.author)
                await approval_channel.send(embed=embed, view=view)

            await message.delete()

# ========== EXTENSION ENTRY POINT ==========

async def setup(bot):
    await bot.add_cog(CleanupCog(bot))
    await bot.add_cog(ApprovalCog(bot))
    print("✅ clean_up_message extension loaded.")
