import discord
from discord import app_commands
from discord.ext import commands
import json, os, datetime

CONFIG_FILE = "data/suggestions_config.json"


def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE) as f:
        return json.load(f)


def save_config(d):
    os.makedirs("data", exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(d, f, indent=2)


class Suggestions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setsuggestchannel", description="Set the channel where /suggest posts suggestions")
    @app_commands.describe(channel="Channel for suggestions")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setsuggestchannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        config = load_config()
        config.setdefault(str(interaction.guild.id), {})["channel"] = str(channel.id)
        save_config(config)
        await interaction.response.send_message(f"✅ Suggestions will be posted in {channel.mention}", ephemeral=True)

    @app_commands.command(name="suggest", description="Submit a suggestion for the server")
    @app_commands.describe(suggestion="Your suggestion")
    async def suggest(self, interaction: discord.Interaction, suggestion: str):
        config = load_config()
        gid = str(interaction.guild.id)
        ch_id = config.get(gid, {}).get("channel")
        channel = interaction.guild.get_channel(int(ch_id)) if ch_id else interaction.channel

        e = discord.Embed(description=suggestion, color=discord.Color.blurple(), timestamp=datetime.datetime.utcnow())
        e.set_author(name=f"Suggestion by {interaction.user}", icon_url=interaction.user.display_avatar.url)
        e.set_footer(text="👍 to upvote • 👎 to downvote")
        msg = await channel.send(embed=e)
        await msg.add_reaction("👍")
        await msg.add_reaction("👎")
        await interaction.response.send_message(f"✅ Suggestion posted in {channel.mention}!", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Suggestions(bot))
