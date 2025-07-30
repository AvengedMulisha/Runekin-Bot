import discord
import itertools
import datetime
import os
import json
import requests
import asyncio
from discord.ext import commands, tasks
from discord import app_commands

# ========== CONFIG ==========
utc = datetime.timezone.utc
cleanup_time = datetime.time(hour=0, minute=0, tzinfo=utc)

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
    "Leader": 1000,
    "Co-Leader": 999,
    "Admin": 950,
    "Mentor": 900,
    "Teacher": 850,
    "Zamorakian": 504,
    "Zarosaian": 503,
    "Saradominist": 502,
    "Guthixian": 501,
    "Armadylean": 500,
    "Mind": 2, "Water": 5, "Earth": 10, "Fire": 20, "Cosmic": 30, "Chaos": 50,
    "Astral": 75, "Nature": 100, "Law": 125, "Death": 150, "Blood": 200,
    "Soul": 250, "Wrath": 300
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
        await interaction.response.send_message("✅ Approved and posted.", ephemeral=True)
        self.stop()

    @discord.ui.button(label="❌ Reject", style=discord.ButtonStyle.red)
    async def reject_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()
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

# ========== POINTS COG ==========
class PointsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Register slash commands
        self.bot.tree.add_command(self.linkrsn)
        self.bot.tree.add_command(self.myrsn)
        self.bot.tree.add_command(self.setrsnfor)
        self.data = self.load_data()
        self.sync_loop.start()

    def cog_unload(self):
        self.sync_loop.cancel()

    def load_data(self):
        if os.path.exists(POINTS_FILE):
            with open(POINTS_FILE, "r") as f:
                return json.load(f)
        return {}

    def save_data(self):
        with open(POINTS_FILE, "w") as f:
            json.dump(self.data, f, indent=2)

    def get_rank(self, points):
        last_rank = "Unranked"
        for rank, threshold in sorted(RANK_THRESHOLDS.items(), key=lambda x: x[1]):
            if points >= threshold:
                last_rank = rank
            else:
                break
        return last_rank

    def sync_from_wise_old_man(self):
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

    @app_commands.command(name="linkrsn", description="Link your RuneScape name and update your server nickname")
    @app_commands.describe(rsn="Your in-game RuneScape name")
    async def linkrsn(self, interaction: discord.Interaction, rsn: str):
        print(f"🔗 Linking RSN for {interaction.user} to {rsn}")
        if not os.path.exists("linked_rsn.json"):
            links = {}
        else:
            with open("linked_rsn.json", "r") as f:
                links = json.load(f)

        links[str(interaction.user.id)] = rsn

        with open("linked_rsn.json", "w") as f:
            json.dump(links, f, indent=2)

        try:
            if isinstance(interaction.channel, discord.TextChannel):
                await interaction.user.edit(nick=rsn)
        except discord.Forbidden:
            await interaction.response.send_message("✅ RSN linked, but I don't have permission to change your nickname.", ephemeral=True)
            return

        await interaction.response.send_message(f"✅ RSN linked to **{rsn}** and nickname updated.", ephemeral=True)

    @app_commands.command(name="myrsn", description="Check the RSN linked to your account")
    async def myrsn(self, interaction: discord.Interaction):
        if not os.path.exists("linked_rsn.json"):
            await interaction.response.send_message("⚠️ No RSN links found.", ephemeral=True)
            return

        with open("linked_rsn.json", "r") as f:
            links = json.load(f)

        rsn = links.get(str(interaction.user.id))
        if rsn:
            await interaction.response.send_message(f"🔗 Your linked RSN is: **{rsn}**", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ You have not linked an RSN yet.", ephemeral=True)

    @app_commands.command(name="setrsnfor", description="Admin command to set or change another user's RSN")
    @app_commands.describe(member="The user to link", rsn="The RuneScape name to assign")
    async def setrsnfor(self, interaction: discord.Interaction, member: discord.Member, rsn: str):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You do not have permission to do that.", ephemeral=True)
            return

        if not os.path.exists("linked_rsn.json"):
            links = {}
        else:
            with open("linked_rsn.json", "r") as f:
                links = json.load(f)

        links[str(member.id)] = rsn

        with open("linked_rsn.json", "w") as f:
            json.dump(links, f, indent=2)

        try:
            await member.edit(nick=rsn)
        except discord.Forbidden:
            await interaction.response.send_message(f"✅ Set RSN for {member.mention} to **{rsn}**, but couldn't update nickname.", ephemeral=True)
            return

        await interaction.response.send_message(f"✅ Set RSN for {member.mention} to **{rsn}** and updated their nickname.", ephemeral=True)

    @app_commands.command(name="mypoints", description="Check your rank and points.")
    async def mypoints(self, interaction: discord.Interaction):
                # Try linked RSN first
        linked_rsn = None
        if os.path.exists("linked_rsn.json"):
            with open("linked_rsn.json", "r") as f:
                links = json.load(f)
                linked_rsn = links.get(str(interaction.user.id))

        rsn = linked_rsn if linked_rsn else interaction.user.display_name
        player = self.data.get(rsn)

        if not player:
            await interaction.response.send_message("❌ You don't have any points recorded.", ephemeral=True)
            return

        points = player["points"]
        rank = self.get_rank(points)
        await interaction.response.send_message(f"🧾 **{rsn}**: {points} points — Rank: **{rank}**", ephemeral=True)

    @app_commands.command(name="addpoints", description="Add points to a player (admin only)")
    @app_commands.describe(player="Enter the RSN of the player", amount="Points to add")
    async def addpoints(self, interaction: discord.Interaction, player: str, amount: int):
        if interaction.channel.id != ADDPOINTS_CHANNEL_ID:
            await interaction.response.send_message(
                "❌ This command can only be used in the designated points channel.",
                ephemeral=True
            )
            return

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return

        self.data.setdefault(player, {"points": 0, "approved": True, "rank": "Mind"})
        self.data[player]["points"] += amount
        self.data[player]["rank"] = self.get_rank(self.data[player]["points"])
        self.save_data()

        await interaction.response.send_message(f"✅ Added {amount} points to **{player}**. New total: {self.data[player]['points']}.")

    @app_commands.command(name="leaderboard", description="Show the top players by points.")
    async def leaderboard(self, interaction: discord.Interaction):
        sorted_players = sorted(self.data.items(), key=lambda x: x[1]["points"], reverse=True)
        top_10 = sorted_players[:10]

        if not top_10:
            await interaction.response.send_message("No leaderboard data yet.")
            return

        lines = [f"🏅 **{name}** — {info['points']} pts ({info['rank']})" for name, info in top_10]
        leaderboard_text = "\n".join(lines)
        await interaction.response.send_message(f"📊 **Top Players**:\n{leaderboard_text}")

    @app_commands.command(name="syncpoints", description="Sync members from Wise Old Man group.")
    async def syncpoints(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You don't have permission to sync points.", ephemeral=True)
            return

        self.sync_from_wise_old_man()
        await interaction.response.send_message("🔄 Sync complete!", ephemeral=True)

    @commands.Cog.listener()
    async def on_ready(self):
        try:
            synced = await self.bot.tree.sync()
            print(f"🔃 Synced {len(synced)} slash commands.")
        except Exception as e:
            print(f"❌ Error syncing slash commands: {e}")

# ========== EXTENSION ENTRY POINT ==========
async def setup(bot):
    await bot.add_cog(CleanupCog(bot))
    await bot.add_cog(ApprovalCog(bot))
    await bot.add_cog(PointsCog(bot))
    print("✅ clean_up_message extension loaded.")
