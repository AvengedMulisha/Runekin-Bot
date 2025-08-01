from discord import app_commands
import json
import asyncio

class PointsCog(commands.GroupCog):
    def __init__(self, bot):
        self.bot = bot
        self.data = self.load_data()
        
        # Define sync loop task (this will run periodically)
        self.sync_loop.start()

        # Register slash command to guild (or globally if needed)
        self.bot.tree.add_command(self.addpoints, guild=discord.Object(id=1347682930465706004))
        self.bot.tree.add_command(self.syncwom, guild=discord.Object(id=1347682930465706004))

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
