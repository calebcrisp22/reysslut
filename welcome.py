import discord
from discord import app_commands
from discord.ext import commands
import json, os, datetime

CONFIG_FILE = "data/welcome_config.json"


def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE) as f:
        return json.load(f)


def save_config(d):
    os.makedirs("data", exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(d, f, indent=2)


class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        config = load_config()
        gid = str(member.guild.id)
        g_config = config.get(gid, {})

        ch_id = g_config.get("welcome_channel")
        if ch_id:
            ch = member.guild.get_channel(int(ch_id))
            if ch:
                msg = g_config.get("welcome_message", "Welcome {user} to **{server}**! You are member #{count}.")
                msg = msg.replace("{user}", member.mention).replace("{server}", member.guild.name).replace("{count}", str(member.guild.member_count))
                color = int(g_config.get("welcome_color", "0x57F287").replace("0x", ""), 16)
                e = discord.Embed(description=msg, color=color, timestamp=datetime.datetime.utcnow())
                e.set_author(name=member.display_name, icon_url=member.display_avatar.url)
                e.set_footer(text=f"ID: {member.id}")
                await ch.send(embed=e)

        auto_role_id = g_config.get("auto_role")
        if auto_role_id:
            role = member.guild.get_role(int(auto_role_id))
            if role:
                try:
                    await member.add_roles(role, reason="Auto-role on join")
                except Exception:
                    pass

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        config = load_config()
        gid = str(member.guild.id)
        g_config = config.get(gid, {})

        ch_id = g_config.get("leave_channel")
        if ch_id:
            ch = member.guild.get_channel(int(ch_id))
            if ch:
                msg = g_config.get("leave_message", "**{user}** has left the server. We now have {count} members.")
                msg = msg.replace("{user}", str(member)).replace("{server}", member.guild.name).replace("{count}", str(member.guild.member_count))
                color = int(g_config.get("leave_color", "0xED4245").replace("0x", ""), 16)
                e = discord.Embed(description=msg, color=color, timestamp=datetime.datetime.utcnow())
                e.set_author(name=str(member), icon_url=member.display_avatar.url)
                await ch.send(embed=e)

    @app_commands.command(name="setwelchannel", description="Set the welcome message channel")
    @app_commands.describe(channel="Channel for welcome messages")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setwelchannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        config = load_config()
        config.setdefault(str(interaction.guild.id), {})["welcome_channel"] = str(channel.id)
        save_config(config)
        await interaction.response.send_message(f"✅ Welcome channel set to {channel.mention}", ephemeral=True)

    @app_commands.command(name="setwelcome", description="Customize the welcome embed message")
    @app_commands.describe(message="Use {user}, {server}, {count} as placeholders")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setwelcome(self, interaction: discord.Interaction, message: str):
        config = load_config()
        config.setdefault(str(interaction.guild.id), {})["welcome_message"] = message
        save_config(config)
        await interaction.response.send_message("✅ Welcome message updated.", ephemeral=True)

    @app_commands.command(name="setleavechannel", description="Set the leave message channel")
    @app_commands.describe(channel="Channel for leave messages")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setleavechannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        config = load_config()
        config.setdefault(str(interaction.guild.id), {})["leave_channel"] = str(channel.id)
        save_config(config)
        await interaction.response.send_message(f"✅ Leave channel set to {channel.mention}", ephemeral=True)

    @app_commands.command(name="setleave", description="Customize the leave embed message")
    @app_commands.describe(message="Use {user}, {server}, {count} as placeholders")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setleave(self, interaction: discord.Interaction, message: str):
        config = load_config()
        config.setdefault(str(interaction.guild.id), {})["leave_message"] = message
        save_config(config)
        await interaction.response.send_message("✅ Leave message updated.", ephemeral=True)

    @app_commands.command(name="autorole", description="Set a role to be given to new members automatically")
    @app_commands.describe(role="Role to assign on join (leave blank to disable)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def autorole(self, interaction: discord.Interaction, role: discord.Role = None):
        config = load_config()
        gid = str(interaction.guild.id)
        if role:
            config.setdefault(gid, {})["auto_role"] = str(role.id)
            msg = f"✅ Auto-role set to {role.mention}"
        else:
            config.get(gid, {}).pop("auto_role", None)
            msg = "✅ Auto-role disabled."
        save_config(config)
        await interaction.response.send_message(msg, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Welcome(bot))
