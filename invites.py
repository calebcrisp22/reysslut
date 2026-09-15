import discord
from discord import app_commands
from discord.ext import commands
import json, os, datetime

INVITES_FILE = "data/invites.json"
CONFIG_FILE = "data/invite_config.json"


def load_invites():
    if not os.path.exists(INVITES_FILE):
        return {}
    with open(INVITES_FILE) as f:
        return json.load(f)


def save_invites(d):
    os.makedirs("data", exist_ok=True)
    with open(INVITES_FILE, "w") as f:
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


class Invites(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.invite_cache = {}

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            try:
                invites = await guild.invites()
                self.invite_cache[guild.id] = {inv.code: inv.uses for inv in invites}
            except Exception:
                pass

    @commands.Cog.listener()
    async def on_invite_create(self, invite):
        self.invite_cache.setdefault(invite.guild.id, {})[invite.code] = invite.uses

    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild = member.guild
        try:
            new_invites = await guild.invites()
        except Exception:
            return
        old_cache = self.invite_cache.get(guild.id, {})
        inviter_id = None
        used_code = None

        for inv in new_invites:
            if old_cache.get(inv.code, 0) < inv.uses:
                inviter_id = str(inv.inviter.id) if inv.inviter else None
                used_code = inv.code
                break

        self.invite_cache[guild.id] = {inv.code: inv.uses for inv in new_invites}

        if inviter_id:
            data = load_invites()
            gid = str(guild.id)
            data.setdefault(gid, {}).setdefault(inviter_id, {"total": 0, "left": 0, "codes": []})
            data[gid][inviter_id]["total"] += 1
            if used_code not in data[gid][inviter_id]["codes"]:
                data[gid][inviter_id]["codes"].append(used_code)
            save_invites(data)

        config = load_config()
        gid = str(guild.id)
        welch_id = config.get(gid, {}).get("welcome_channel")
        if welch_id:
            ch = guild.get_channel(int(welch_id))
            if ch:
                inviter_text = f"Invited by <@{inviter_id}>" if inviter_id else "Used a vanity/unknown invite"
                e = discord.Embed(
                    title="👋 New Member!",
                    description=f"Welcome {member.mention} to **{guild.name}**!\n{inviter_text}",
                    color=discord.Color.green(),
                    timestamp=datetime.datetime.utcnow(),
                )
                e.set_thumbnail(url=member.display_avatar.url)
                e.set_footer(text=f"Member #{guild.member_count}")
                await ch.send(embed=e)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        gid = str(member.guild.id)
        data = load_invites()
        data.setdefault(gid, {}).setdefault("__leaves__", 0)
        data[gid]["__leaves__"] = data[gid].get("__leaves__", 0) + 1
        save_invites(data)

    @app_commands.command(name="invites", description="Check your invite stats")
    @app_commands.describe(member="Member to check (default: yourself)")
    async def invites(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        uid, gid = str(member.id), str(interaction.guild.id)
        stats = load_invites().get(gid, {}).get(uid, {"total": 0, "left": 0})
        e = discord.Embed(
            title=f"📨 Invites for {member.display_name}",
            description=f"**Total Invites:** {stats.get('total',0)}\n**Codes Used:** {len(stats.get('codes',[]))}",
            color=discord.Color.blurple(),
        )
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="inviteleaderboard", description="View the invite leaderboard")
    async def inviteleaderboard(self, interaction: discord.Interaction):
        gid = str(interaction.guild.id)
        data = load_invites()
        users = {uid: d for uid, d in data.get(gid, {}).items() if uid != "__leaves__" and isinstance(d, dict)}
        sorted_users = sorted(users.items(), key=lambda x: x[1].get("total", 0), reverse=True)
        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, (uid, d) in enumerate(sorted_users[:10]):
            m = interaction.guild.get_member(int(uid))
            name = m.display_name if m else f"User {uid}"
            medal = medals[i] if i < 3 else f"**#{i+1}**"
            lines.append(f"{medal} {name} — **{d.get('total',0)}** invites")
        e = discord.Embed(title="📨 Invite Leaderboard", description="\n".join(lines) or "No data.", color=discord.Color.gold())
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="invitepanel", description="Post the invite tracking panel")
    @app_commands.describe(channel="Channel to post in")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def invitepanel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        gid = str(interaction.guild.id)
        data = load_invites()
        users = {uid: d for uid, d in data.get(gid, {}).items() if uid != "__leaves__" and isinstance(d, dict)}
        sorted_users = sorted(users.items(), key=lambda x: x[1].get("total", 0), reverse=True)
        lines = [f"**#{i+1}** <@{uid}> — {d.get('total',0)} invites" for i, (uid, d) in enumerate(sorted_users[:15])]
        e = discord.Embed(
            title="📊 Invite Tracking Panel",
            description="\n".join(lines) or "No invites tracked yet.",
            color=discord.Color.blurple(),
            timestamp=datetime.datetime.utcnow(),
        )
        e.set_footer(text="Updates on new joins")
        await channel.send(embed=e)
        await interaction.response.send_message(f"✅ Invite panel posted in {channel.mention}", ephemeral=True)

    @app_commands.command(name="setinvitepanel", description="Customize the invite panel title")
    @app_commands.describe(title="Panel title")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setinvitepanel(self, interaction: discord.Interaction, title: str):
        config = load_config()
        config.setdefault(str(interaction.guild.id), {})["panel_title"] = title
        save_config(config)
        await interaction.response.send_message(f"✅ Invite panel title set to **{title}**", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Invites(bot))
