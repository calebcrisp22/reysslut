import discord
from discord import app_commands
from discord.ext import commands
import datetime


class Embeds(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="embed", description="Create and send a custom embed")
    @app_commands.describe(
        title="Embed title",
        description="Embed description (supports \\n for newlines)",
        color="Hex color code (e.g. #FF0000)",
        channel="Channel to send to (default: current)",
        footer="Footer text",
        image_url="Image URL to attach",
        thumbnail_url="Thumbnail URL",
        author="Author name displayed at the top",
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def embed(
        self,
        interaction: discord.Interaction,
        title: str = "",
        description: str = "",
        color: str = "#5865F2",
        channel: discord.TextChannel = None,
        footer: str = "",
        image_url: str = "",
        thumbnail_url: str = "",
        author: str = "",
    ):
        ch = channel or interaction.channel
        try:
            color_int = int(color.strip("#"), 16)
        except ValueError:
            color_int = 0x5865F2

        e = discord.Embed(timestamp=datetime.datetime.utcnow())
        e.color = color_int
        if title:
            e.title = title
        if description:
            e.description = description.replace("\\n", "\n")
        if footer:
            e.set_footer(text=footer)
        if image_url:
            e.set_image(url=image_url)
        if thumbnail_url:
            e.set_thumbnail(url=thumbnail_url)
        if author:
            e.set_author(name=author)

        await ch.send(embed=e)
        await interaction.response.send_message(f"✅ Embed sent to {ch.mention}", ephemeral=True)

    @app_commands.command(name="testembed", description="Test if embeds work in this channel")
    async def testembed(self, interaction: discord.Interaction):
        e = discord.Embed(
            title="✅ Embeds Work!",
            description="This channel supports Discord embeds.",
            color=discord.Color.green(),
            timestamp=datetime.datetime.utcnow(),
        )
        e.set_footer(text="Embed test")
        await interaction.response.send_message(embed=e, ephemeral=True)

    @app_commands.command(name="announce", description="Send an announcement embed to a channel")
    @app_commands.describe(channel="Channel to announce in", title="Announcement title", message="Announcement content", ping="Role to ping (optional)")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def announce(self, interaction: discord.Interaction, channel: discord.TextChannel, title: str, message: str, ping: discord.Role = None):
        e = discord.Embed(title=f"📢 {title}", description=message.replace("\\n", "\n"), color=discord.Color.blurple(), timestamp=datetime.datetime.utcnow())
        e.set_footer(text=f"Announced by {interaction.user}", icon_url=interaction.user.display_avatar.url)
        content = ping.mention if ping else None
        await channel.send(content=content, embed=e)
        await interaction.response.send_message(f"✅ Announced in {channel.mention}", ephemeral=True)

    @app_commands.command(name="say", description="Make the bot say something in a channel")
    @app_commands.describe(message="Message to send", channel="Channel to send to")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def say(self, interaction: discord.Interaction, message: str, channel: discord.TextChannel = None):
        ch = channel or interaction.channel
        await ch.send(message)
        await interaction.response.send_message("✅ Sent!", ephemeral=True)

    @app_commands.command(name="poll", description="Create a quick yes/no poll")
    @app_commands.describe(question="Poll question")
    async def poll(self, interaction: discord.Interaction, question: str):
        e = discord.Embed(title="📊 Poll", description=question, color=discord.Color.blurple(), timestamp=datetime.datetime.utcnow())
        e.set_footer(text=f"Poll by {interaction.user}")
        await interaction.response.send_message(embed=e)
        msg = await interaction.original_response()
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")

    @app_commands.command(name="giveaway", description="Start a quick giveaway (react to enter)")
    @app_commands.describe(prize="What you're giving away", channel="Channel to post in")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def giveaway(self, interaction: discord.Interaction, prize: str, channel: discord.TextChannel = None):
        ch = channel or interaction.channel
        e = discord.Embed(
            title="🎉 GIVEAWAY 🎉",
            description=f"**Prize:** {prize}\n\nReact with 🎉 to enter!\nHosted by {interaction.user.mention}",
            color=discord.Color.gold(),
            timestamp=datetime.datetime.utcnow(),
        )
        msg = await ch.send(embed=e)
        await msg.add_reaction("🎉")
        await interaction.response.send_message(f"✅ Giveaway started in {ch.mention}!", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Embeds(bot))
