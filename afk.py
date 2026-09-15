import discord
from discord import app_commands
from discord.ext import commands
import datetime


class AFK(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.afk_users = {}  # "gid:uid" -> {"reason": str, "since": datetime}

    @app_commands.command(name="afk", description="Set yourself as AFK")
    @app_commands.describe(reason="Reason you're AFK (optional)")
    async def afk(self, interaction: discord.Interaction, reason: str = "AFK"):
        key = f"{interaction.guild.id}:{interaction.user.id}"
        self.afk_users[key] = {"reason": reason, "since": datetime.datetime.utcnow()}
        await interaction.response.send_message(f"💤 {interaction.user.mention} is now AFK: {reason}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        # Welcome back if the author was AFK
        key = f"{message.guild.id}:{message.author.id}"
        if key in self.afk_users:
            del self.afk_users[key]
            try:
                await message.channel.send(f"👋 Welcome back {message.author.mention}, I removed your AFK status.", delete_after=8)
            except Exception:
                pass

        # Notify if someone pings an AFK user
        for member in message.mentions:
            mkey = f"{message.guild.id}:{member.id}"
            if mkey in self.afk_users:
                info = self.afk_users[mkey]
                try:
                    await message.channel.send(f"💤 {member.display_name} is AFK: {info['reason']}", delete_after=8)
                except Exception:
                    pass


async def setup(bot):
    await bot.add_cog(AFK(bot))
