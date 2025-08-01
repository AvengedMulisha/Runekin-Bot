import asyncio
import os
import discord
from discord.ext import commands, tasks
from discord import app_commands
from dotenv import load_dotenv
import json
import requests
import datetime  # Ensure datetime is imported here
import itertools

# ========== CONFIG ==========
utc = datetime.timezone.utc
cleanup_time = datetime.time(hour=0, minute=0, tzinfo=utc)

# Channel IDs (adjust as needed)
CHANNELS_TO_DELETE_FROM = [
    1383717273704857670,  # planned-events
    1385130581599457413,  # event-polls-and-payments
    1347682931111493734,  # welcome
]

SUBMISSION_CHANNEL_ID = 1395474287531397283
APPROVAL_CHANNEL_ID = 1398377286436257872
APPROVED_POSTS_CHANNEL_ID = 1395474287531397283

NEW_PLAYERS_CHANNEL_ID = 1347682931111493734
REMOVED_PLAYERS_CHANNEL_ID = 1383716927113003078
ADDPOINTS_CHANNEL_ID = 1384493244464894042  # Only allow /addpoints here

POINTS_FILE = "points.json"
WOM_GROUP_ID = 12559

RANK_THRESHOLDS = {
    "Air": 0,
    "Mind": 2,
    "Water": 5,
    "Earth": 10,
    "Fire": 20,
    "Cosmic": 30,
    "Chaos": 50,
    "Astral": 75,
    "Nature": 100,
    "Law": 125,
    "Death": 150,
    "Blood": 200,
    "Soul": 250,
    "Wrath": 300,
    "Armadylean": 500,
    "Guthixian": 501,
    "Saradominist": 502,
    "Zarosaian": 503,
    "Zamorakian": 504,
    "Teacher": 850,
    "Mentor": 900,
    "Admin": 950,
    "Co-Leader": 999,
    "Leader": 1000
}

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
        super().__init__(timeout=None)
        self.message_content = message_content
        self.author = author

    @discord.ui.button(label="✅ Approve", style=discord.ButtonStyle.green)
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        approved_channel = interaction.client.get_channel(APPROVED_POSTS_CHANNEL_ID)
        if approved_channel:
            await approved_channel.send(f"**Submitted by {self.author.mention}:**\n{self.message_content}")
        await interaction.message.delete()
        await interaction.followup.send("✅ Approved and posted.", ephemeral=True)
        self.stop()

    @discord.ui.button(label="❌ Reject", style=discord.ButtonStyle.red)
    async def reject_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()
        await interaction.followup.send("❌ Rejected.", ephemeral=True)
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


# ========== POINTS COG ==========
class PointsCog(commands.GroupCog):
    def __init__(self, bot):
        self.bot = bot
        self.data = self.load_data()

        # Define sync loop task (this will run periodically)
        self.sync_loop.start()

    def load_data(self):
        """Load existing player data from a file."""
        if os.path.exists(POINTS_FILE):
            with open(POINTS_FILE, "r") as f:
                return json.load(f)
        return {}

    def save_data(self):
        """Save updated player data to a file."""
        with open(POINTS_FILE, "w") as f:
            json.dump(self.data, f, indent=2)

    def get_rank(self, points):
        """Get the rank for a player based on their points."""
        last_rank = "Air"
        for rank, threshold in sorted(RANK_THRESHOLDS.items(), key=lambda x: x[1]):
            if points >= threshold:
                last_rank = rank
            else:
                break
        return last_rank

    @app_commands.command(name="addpoints", description="Add points to a player.")
    @app_commands.checks.has_permissions(administrator=True)
    async def addpoints(self, interaction: discord.Interaction, rsn: str, points: int):
        """Command to add points to a player."""
        print(f"Command /addpoints triggered by {interaction.user} for RSN: {rsn} with points: {points}")

        # Ensure the command is only usable in a specific channel
        if interaction.channel.id != ADDPOINTS_CHANNEL_ID:
            await interaction.response.send_message("❌ This command can only be used in the designated channel.", ephemeral=True)
            return

        # Initialize player if not in the data
        if rsn not in self.data:
            self.data[rsn] = {"points": 0, "approved": False, "rank": "Mind"}

        # Update points and rank
        self.data[rsn]["points"] += points
        self.data[rsn]["rank"] = self.get_rank(self.data[rsn]["points"])
        self.save_data()

        # Respond to user
        await interaction.response.send_message(
            f"✅ Added **{points}** points to **{rsn}**.\n"
            f"Total: **{self.data[rsn]['points']}** ({self.data[rsn]['rank']})",
            ephemeral=True
        )

    @app_commands.command(name="syncwom", description="Force sync from Wise Old Man.")
    @app_commands.checks.has_permissions(administrator=True)
    async def syncwom(self, interaction: discord.Interaction):
        """Command to manually sync from Wise Old Man."""
        await interaction.response.send_message("🔄 Syncing from Wise Old Man...", ephemeral=True)
        try:
            await asyncio.to_thread(self.sync_from_wise_old_man)
            await interaction.followup.send("✅ Manual sync complete.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Sync failed: {e}", ephemeral=True)

    def sync_from_wise_old_man(self):
        """Sync player data from Wise Old Man API."""
        try:
            print("🔄 Syncing from Wise Old Man...")
            response = requests.get(f"https://api.wiseoldman.net/v2/groups/{WOM_GROUP_ID}")
            response.raise_for_status()
            data = response.json()

            if "memberships" not in data:
                print("⚠️ No memberships found in WOM response.")
                return

            existing_members = set(self.data.keys())
            current_members = set()
            added = []
            removed = []

            for membership in data["memberships"]:
                rsn = membership["player"]["displayName"]
                current_members.add(rsn)

                if rsn not in self.data:
                    self.data[rsn] = {
                        "points": 0,
                        "approved": False,
                        "rank": "Mind"
                    }
                    added.append(rsn)

            removed = list(existing_members - current_members)
            for old_member in removed:
                del self.data[old_member]

            self.save_data()

            if added or removed:
                print(f"✅ Sync complete. Total members: {len(current_members)}")
                if added:
                    print(f"➕ Added: {', '.join(added)}")
                if removed:
                    print(f"➖ Removed: {', '.join(removed)}")
            else:
                print("✅ Sync complete. No changes detected.")

            added_channel = self.bot.get_channel(NEW_PLAYERS_CHANNEL_ID)
            if added and added_channel:
                message = "**➕ New Players Added:**\n" + "\n".join(f"- {name}" for name in added)
                asyncio.create_task(added_channel.send(message))

            removed_channel = self.bot.get_channel(REMOVED_PLAYERS_CHANNEL_ID)
            if removed and removed_channel:
                message = "**➖ Players Removed:**\n" + "\n".join(f"- {name}" for name in removed)
                asyncio.create_task(removed_channel.send(message))

        except Exception as e:
            print(f"❌ Error during Wise Old Man sync: {e}")

    @tasks.loop(time=[datetime.time(minute=0, tzinfo=datetime.timezone.utc)])
    async def sync_loop(self):
        print("🕒 Running scheduled WOM sync...")
        self.sync_from_wise_old_man()


# ========== EXTENSION ENTRY POINT ==========
async def setup(bot):
    await bot.add_cog(CleanupCog(bot))
    await bot.add_cog(ApprovalCog(bot))
    await bot.add_cog(PointsCog(bot))  # Ensure the PointsCog is added properly
    print("✅ clean_up_message extension loaded.")
