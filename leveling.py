import discord
from discord import app_commands
from discord.ext import commands
import json, os, datetime, random

LEVELS_FILE = "data/levels.json"
CONFIG_FILE = "data/level_config.json"


def load_levels():
    if not os.path.exists(LEVELS_FILE):
        return {}
    with open(LEVELS_FILE) as f:
        return json.load(f)


def save_levels(d):
    os.makedirs("data", exist_ok=True)
    with open(LEVELS_FILE, "w") as f:
        json.dump(d, f, indent=2)


def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE) as f:
        return json.load(f)


def save_config(d):
    os.makedirs("data", exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(d, f, indent=2)


def xp_for_level(level):
    return 5 * (level ** 2) + 50 * level + 100


class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cooldowns = {}

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        uid = str(message.author.id)
        gid = str(message.guild.id)
        now = datetime.datetime.utcnow().timestamp()

        if self.cooldowns.get(f"{gid}:{uid}", 0) + 60 > now:
            return
        self.cooldowns[f"{gid}:{uid}"] = now

        levels = load_levels()
        levels.setdefault(gid, {}).setdefault(uid, {"xp": 0, "level": 0})
        user_data = levels[gid][uid]
        user_data["xp"] += random.randint(15, 25)

        while user_data["xp"] >= xp_for_level(user_data["level"] + 1):
            user_data["xp"] -= xp_for_level(user_data["level"] + 1)
            user_data["level"] += 1
            save_levels(levels)
            await self._on_level_up(message, gid, uid, user_data["level"])
            return

        save_levels(levels)

    async def _on_level_up(self, message, gid, uid, new_level):
        config = load_config()
        g_config = config.get(gid, {})
        level_channel_id = g_config.get("level_channel")
        ch = message.guild.get_channel(int(level_channel_id)) if level_channel_id else message.channel
        custom_msg = g_config.get("level_message", "🎉 {user} reached **Level {level}**!")
        text = custom_msg.replace("{user}", message.author.mention).replace("{level}", str(new_level))
        if ch:
            await ch.send(text)

        level_roles = g_config.get("level_roles", {})
        role_id = level_roles.get(str(new_level))
        if role_id:
            role = message.guild.get_role(int(role_id))
            if role:
                try:
                    await message.author.add_roles(role, reason=f"Reached level {new_level}")
                except Exception:
                    pass

    @app_commands.command(name="rank", description="Check your or someone else's level")
    @app_commands.describe(member="Member to check (leave blank for yourself)")
    async def rank(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        uid, gid = str(member.id), str(interaction.guild.id)
        data = load_levels().get(gid, {}).get(uid, {"xp": 0, "level": 0})
        lv, xp = data["level"], data["xp"]
        needed = xp_for_level(lv + 1)
        e = discord.Embed(color=discord.Color.blurple(), timestamp=datetime.datetime.utcnow())
        e.set_author(name=member.display_name, icon_url=member.display_avatar.url)
        e.add_field(name="Level", value=str(lv), inline=True)
        e.add_field(name="XP", value=f"{xp} / {needed}", inline=True)
        e.set_footer(text="Leveling System")
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="leaderboard", description="View the server XP leaderboard")
    async def leaderboard(self, interaction: discord.Interaction):
        gid = str(interaction.guild.id)
        users = load_levels().get(gid, {})
        sorted_users = sorted(users.items(), key=lambda x: (x[1]["level"], x[1]["xp"]), reverse=True)
        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, (uid, d) in enumerate(sorted_users[:10]):
            member = interaction.guild.get_member(int(uid))
            name = member.display_name if member else f"User {uid}"
            medal = medals[i] if i < 3 else f"**#{i+1}**"
            lines.append(f"{medal} {name} — Level {d['level']} ({d['xp']} XP)")
        e = discord.Embed(title="🏆 Leaderboard", description="\n".join(lines) or "No data yet.", color=discord.Color.gold())
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="setlevelmessage", description="Customize the level-up message")
    @app_commands.describe(message="Use {user} and {level} as placeholders")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setlevelmessage(self, interaction: discord.Interaction, message: str):
        config = load_config()
        config.setdefault(str(interaction.guild.id), {})["level_message"] = message
        save_config(config)
        await interaction.response.send_message(f"✅ Level-up message set to:\n`{message}`", ephemeral=True)

    @app_commands.command(name="setlevelchannel", description="Set the channel for level-up messages")
    @app_commands.describe(channel="Channel for level-up announcements")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setlevelchannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        config = load_config()
        config.setdefault(str(interaction.guild.id), {})["level_channel"] = str(channel.id)
        save_config(config)
        await interaction.response.send_message(f"✅ Level-up messages will be sent to {channel.mention}", ephemeral=True)

    @app_commands.command(name="setlevelrole", description="Set a role reward for reaching a certain level")
    @app_commands.describe(level="Level required", role="Role to assign")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setlevelrole(self, interaction: discord.Interaction, level: int, role: discord.Role):
        config = load_config()
        config.setdefault(str(interaction.guild.id), {}).setdefault("level_roles", {})[str(level)] = str(role.id)
        save_config(config)
        await interaction.response.send_message(f"✅ {role.mention} will be awarded at level **{level}**", ephemeral=True)

    @app_commands.command(name="removelevelrole", description="Remove a level role reward")
    @app_commands.describe(level="Level to remove reward from")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def removelevelrole(self, interaction: discord.Interaction, level: int):
        config = load_config()
        config.get(str(interaction.guild.id), {}).get("level_roles", {}).pop(str(level), None)
        save_config(config)
        await interaction.response.send_message(f"✅ Level role for level **{level}** removed.", ephemeral=True)

    @app_commands.command(name="setxp", description="Manually set a user's XP")
    @app_commands.describe(member="Member", xp="XP amount to set")
    @app_commands.checks.has_permissions(administrator=True)
    async def setxp(self, interaction: discord.Interaction, member: discord.Member, xp: int):
        gid, uid = str(interaction.guild.id), str(member.id)
        levels = load_levels()
        levels.setdefault(gid, {}).setdefault(uid, {"xp": 0, "level": 0})
        levels[gid][uid]["xp"] = xp
        save_levels(levels)
        await interaction.response.send_message(f"✅ Set {member.mention}'s XP to **{xp}**", ephemeral=True)

    @app_commands.command(name="setlevel", description="Manually set a user's level")
    @app_commands.describe(member="Member", level="Level to set")
    @app_commands.checks.has_permissions(administrator=True)
    async def setlevel(self, interaction: discord.Interaction, member: discord.Member, level: int):
        gid, uid = str(interaction.guild.id), str(member.id)
        levels = load_levels()
        levels.setdefault(gid, {}).setdefault(uid, {"xp": 0, "level": 0})
        levels[gid][uid]["level"] = level
        save_levels(levels)
        await interaction.response.send_message(f"✅ Set {member.mention}'s level to **{level}**", ephemeral=True)

    @app_commands.command(name="resetxp", description="Reset a user's XP and level to zero")
    @app_commands.describe(member="Member to reset")
    @app_commands.checks.has_permissions(administrator=True)
    async def resetxp(self, interaction: discord.Interaction, member: discord.Member):
        gid, uid = str(interaction.guild.id), str(member.id)
        levels = load_levels()
        levels.get(gid, {}).pop(uid, None)
        save_levels(levels)
        await interaction.response.send_message(f"✅ Reset {member.mention}'s level and XP.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Leveling(bot))
