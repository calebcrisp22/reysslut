import discord
from discord import app_commands
from discord.ext import commands
import json, os

CONFIG_FILE = "data/reaction_roles.json"


def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE) as f:
        return json.load(f)


def save_config(d):
    os.makedirs("data", exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(d, f, indent=2)


class ReactionRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="reactionrole", description="Create a reaction-role message: react to get a role")
    @app_commands.describe(channel="Channel to post in", role="Role to give", emoji="Emoji to react with", title="Message title", description="Message description")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def reactionrole(self, interaction: discord.Interaction, channel: discord.TextChannel, role: discord.Role, emoji: str, title: str = "Role Selection", description: str = "React below to get a role!"):
        if role >= interaction.guild.me.top_role:
            return await interaction.response.send_message("❌ I can't assign a role higher than or equal to my own top role.", ephemeral=True)

        e = discord.Embed(title=title, description=f"{description}\n\nReact with {emoji} to get {role.mention}", color=discord.Color.blurple())
        msg = await channel.send(embed=e)
        try:
            await msg.add_reaction(emoji)
        except discord.HTTPException:
            return await interaction.response.send_message("❌ That doesn't look like a valid emoji.", ephemeral=True)

        config = load_config()
        gid = str(interaction.guild.id)
        config.setdefault(gid, {})[str(msg.id)] = {"channel_id": str(channel.id), "emoji": str(emoji), "role_id": str(role.id)}
        save_config(config)
        await interaction.response.send_message(f"✅ Reaction role posted in {channel.mention}", ephemeral=True)

    @app_commands.command(name="reactionroleadd", description="Add another emoji→role pair to an existing reaction-role message")
    @app_commands.describe(message_id="Message ID of the reaction-role panel", role="Role to give", emoji="Emoji to react with")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def reactionroleadd(self, interaction: discord.Interaction, message_id: str, role: discord.Role, emoji: str):
        config = load_config()
        gid = str(interaction.guild.id)
        entry = config.get(gid, {}).get(message_id)
        if not entry:
            return await interaction.response.send_message("❌ Reaction-role message not found. Use /reactionrole to create one first.", ephemeral=True)

        # Store as a list going forward, supporting multiple emoji->role pairs per message
        pairs = entry.get("pairs", [{"emoji": entry["emoji"], "role_id": entry["role_id"]}])
        pairs.append({"emoji": str(emoji), "role_id": str(role.id)})
        entry["pairs"] = pairs
        save_config(config)

        try:
            channel = interaction.guild.get_channel(int(entry["channel_id"]))
            msg = await channel.fetch_message(int(message_id))
            await msg.add_reaction(emoji)
        except Exception:
            pass

        await interaction.response.send_message(f"✅ Added {emoji} → {role.mention} to that panel.", ephemeral=True)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.member is None or payload.member.bot:
            return
        config = load_config()
        entry = config.get(str(payload.guild_id), {}).get(str(payload.message_id))
        if not entry:
            return
        role_id = self._match_role(entry, payload.emoji)
        if not role_id:
            return
        guild = self.bot.get_guild(payload.guild_id)
        role = guild.get_role(int(role_id))
        if role:
            try:
                await payload.member.add_roles(role, reason="Reaction role")
            except Exception:
                pass

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        config = load_config()
        entry = config.get(str(payload.guild_id), {}).get(str(payload.message_id))
        if not entry:
            return
        role_id = self._match_role(entry, payload.emoji)
        if not role_id:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        member = guild.get_member(payload.user_id)
        role = guild.get_role(int(role_id))
        if member and role:
            try:
                await member.remove_roles(role, reason="Reaction role removed")
            except Exception:
                pass

    def _match_role(self, entry, emoji):
        pairs = entry.get("pairs", [{"emoji": entry["emoji"], "role_id": entry["role_id"]}])
        for p in pairs:
            if p["emoji"] == str(emoji):
                return p["role_id"]
        return None


async def setup(bot):
    await bot.add_cog(ReactionRoles(bot))
