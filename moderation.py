import discord
from discord import app_commands
from discord.ext import commands
from datetime import timedelta
import json, os, datetime

WARNS_FILE = "data/warns.json"


def load_warns():
    if not os.path.exists(WARNS_FILE):
        return {}
    with open(WARNS_FILE) as f:
        return json.load(f)


def save_warns(data):
    os.makedirs("data", exist_ok=True)
    with open(WARNS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def mod_embed(title, description, color=discord.Color.red()):
    e = discord.Embed(title=title, description=description, color=color, timestamp=datetime.datetime.utcnow())
    e.set_footer(text="Moderation System")
    return e


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── /ban ─────────────────────────────────────────────────
    @app_commands.command(name="ban", description="Ban a member from the server")
    @app_commands.describe(member="Member to ban", reason="Reason for ban", delete_days="Days of messages to delete (0-7)")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided", delete_days: int = 0):
        if member.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
            return await interaction.response.send_message("❌ You can't ban someone with an equal or higher role.", ephemeral=True)
        try:
            await member.send(embed=mod_embed("🔨 You Were Banned", f"**Server:** {interaction.guild.name}\n**Reason:** {reason}"))
        except Exception:
            pass
        seconds = max(0, min(delete_days, 7)) * 86400
        await member.ban(reason=f"{reason} | By {interaction.user}", delete_message_seconds=seconds)
        await interaction.response.send_message(embed=mod_embed("🔨 Member Banned", f"**User:** {member.mention}\n**Reason:** {reason}\n**Moderator:** {interaction.user.mention}", discord.Color.red()))

    # ── /unban ────────────────────────────────────────────────
    @app_commands.command(name="unban", description="Unban a user by their ID")
    @app_commands.describe(user_id="The user's Discord ID", reason="Reason for unban")
    @app_commands.checks.has_permissions(ban_members=True)
    async def unban(self, interaction: discord.Interaction, user_id: str, reason: str = "No reason provided"):
        try:
            user = await self.bot.fetch_user(int(user_id))
            await interaction.guild.unban(user, reason=reason)
            await interaction.response.send_message(embed=mod_embed("✅ Member Unbanned", f"**User:** {user}\n**Reason:** {reason}", discord.Color.green()))
        except (discord.NotFound, ValueError):
            await interaction.response.send_message("❌ User not found or not banned.", ephemeral=True)

    # ── /softban ──────────────────────────────────────────────
    @app_commands.command(name="softban", description="Ban then immediately unban a member (wipes their messages)")
    @app_commands.describe(member="Member to softban", reason="Reason", delete_days="Days of messages to delete (0-7)")
    @app_commands.checks.has_permissions(ban_members=True)
    async def softban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided", delete_days: int = 1):
        if member.top_role >= interaction.user.top_role:
            return await interaction.response.send_message("❌ You can't softban someone with an equal or higher role.", ephemeral=True)
        seconds = max(0, min(delete_days, 7)) * 86400
        await member.ban(reason=f"Softban: {reason} | By {interaction.user}", delete_message_seconds=seconds)
        await interaction.guild.unban(member, reason="Softban auto-unban")
        await interaction.response.send_message(embed=mod_embed("🔨 Member Softbanned", f"**User:** {member.mention}\n**Reason:** {reason}\n**Moderator:** {interaction.user.mention}", discord.Color.orange()))

    # ── /kick ─────────────────────────────────────────────────
    @app_commands.command(name="kick", description="Kick a member from the server")
    @app_commands.describe(member="Member to kick", reason="Reason for kick")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        if member.top_role >= interaction.user.top_role:
            return await interaction.response.send_message("❌ You can't kick someone with an equal or higher role.", ephemeral=True)
        try:
            await member.send(embed=mod_embed("👢 You Were Kicked", f"**Server:** {interaction.guild.name}\n**Reason:** {reason}"))
        except Exception:
            pass
        await member.kick(reason=f"{reason} | By {interaction.user}")
        await interaction.response.send_message(embed=mod_embed("👢 Member Kicked", f"**User:** {member.mention}\n**Reason:** {reason}\n**Moderator:** {interaction.user.mention}", discord.Color.orange()))

    # ── /timeout ──────────────────────────────────────────────
    @app_commands.command(name="timeout", description="Timeout (mute) a member")
    @app_commands.describe(member="Member to timeout", minutes="Duration in minutes", reason="Reason")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def timeout(self, interaction: discord.Interaction, member: discord.Member, minutes: int, reason: str = "No reason provided"):
        if member.top_role >= interaction.user.top_role:
            return await interaction.response.send_message("❌ You can't timeout someone with an equal or higher role.", ephemeral=True)
        until = discord.utils.utcnow() + timedelta(minutes=minutes)
        await member.timeout(until, reason=reason)
        await interaction.response.send_message(embed=mod_embed("⏱️ Member Timed Out", f"**User:** {member.mention}\n**Duration:** {minutes} minutes\n**Reason:** {reason}\n**Moderator:** {interaction.user.mention}", discord.Color.yellow()))

    # ── /untimeout ────────────────────────────────────────────
    @app_commands.command(name="untimeout", description="Remove a timeout from a member")
    @app_commands.describe(member="Member to untimeout")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def untimeout(self, interaction: discord.Interaction, member: discord.Member):
        await member.timeout(None)
        await interaction.response.send_message(embed=mod_embed("✅ Timeout Removed", f"**User:** {member.mention}\n**Moderator:** {interaction.user.mention}", discord.Color.green()))

    # ── /warn ─────────────────────────────────────────────────
    @app_commands.command(name="warn", description="Warn a member")
    @app_commands.describe(member="Member to warn", reason="Reason for warning")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        warns = load_warns()
        uid = str(member.id)
        gid = str(interaction.guild.id)
        warns.setdefault(gid, {}).setdefault(uid, [])
        entry = {"reason": reason, "mod": str(interaction.user), "time": str(datetime.datetime.utcnow())}
        warns[gid][uid].append(entry)
        save_warns(warns)
        count = len(warns[gid][uid])
        try:
            await member.send(embed=mod_embed("⚠️ You Were Warned", f"**Server:** {interaction.guild.name}\n**Reason:** {reason}\n**Total Warnings:** {count}"))
        except Exception:
            pass
        await interaction.response.send_message(embed=mod_embed("⚠️ Member Warned", f"**User:** {member.mention}\n**Reason:** {reason}\n**Total Warnings:** {count}\n**Moderator:** {interaction.user.mention}", discord.Color.yellow()))

    # ── /warnings ─────────────────────────────────────────────
    @app_commands.command(name="warnings", description="View warnings for a member")
    @app_commands.describe(member="Member to check")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def warnings(self, interaction: discord.Interaction, member: discord.Member):
        warns = load_warns()
        uid = str(member.id)
        gid = str(interaction.guild.id)
        user_warns = warns.get(gid, {}).get(uid, [])
        if not user_warns:
            return await interaction.response.send_message(f"✅ {member.mention} has no warnings.", ephemeral=True)
        desc = "\n".join([f"**{i+1}.** {w['reason']} — *{w['mod']}* at {w['time'][:10]}" for i, w in enumerate(user_warns)])
        e = discord.Embed(title=f"⚠️ Warnings for {member}", description=desc, color=discord.Color.yellow())
        await interaction.response.send_message(embed=e)

    # ── /delwarn ──────────────────────────────────────────────
    @app_commands.command(name="delwarn", description="Delete a single warning by its number")
    @app_commands.describe(member="Member", index="Warning number shown in /warnings (starts at 1)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def delwarn(self, interaction: discord.Interaction, member: discord.Member, index: int):
        warns = load_warns()
        gid, uid = str(interaction.guild.id), str(member.id)
        user_warns = warns.get(gid, {}).get(uid, [])
        if index < 1 or index > len(user_warns):
            return await interaction.response.send_message("❌ Invalid warning number.", ephemeral=True)
        removed = user_warns.pop(index - 1)
        save_warns(warns)
        await interaction.response.send_message(embed=mod_embed("✅ Warning Removed", f"Removed warning: *{removed['reason']}*", discord.Color.green()))

    # ── /clearwarnings ────────────────────────────────────────
    @app_commands.command(name="clearwarnings", description="Clear all warnings for a member")
    @app_commands.describe(member="Member to clear warnings for")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def clearwarnings(self, interaction: discord.Interaction, member: discord.Member):
        warns = load_warns()
        warns.get(str(interaction.guild.id), {}).pop(str(member.id), None)
        save_warns(warns)
        await interaction.response.send_message(embed=mod_embed("✅ Warnings Cleared", f"All warnings for {member.mention} have been cleared.", discord.Color.green()))

    # ── /purge ────────────────────────────────────────────────
    @app_commands.command(name="purge", description="Delete a number of messages")
    @app_commands.describe(amount="Number of messages to delete (1-100)", member="Only delete messages from this member")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def purge(self, interaction: discord.Interaction, amount: app_commands.Range[int, 1, 100], member: discord.Member = None):
        await interaction.response.defer(ephemeral=True)
        if member:
            def check(m):
                return m.author == member
            deleted = await interaction.channel.purge(limit=amount, check=check)
        else:
            deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"🗑️ Deleted **{len(deleted)}** messages.", ephemeral=True)

    # ── /lock ─────────────────────────────────────────────────
    @app_commands.command(name="lock", description="Lock a channel so members can't send messages")
    @app_commands.describe(channel="Channel to lock (defaults to current)", reason="Reason")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def lock(self, interaction: discord.Interaction, channel: discord.TextChannel = None, reason: str = "No reason provided"):
        ch = channel or interaction.channel
        await ch.set_permissions(interaction.guild.default_role, send_messages=False)
        await interaction.response.send_message(embed=mod_embed("🔒 Channel Locked", f"{ch.mention} has been locked.\n**Reason:** {reason}", discord.Color.red()))

    # ── /unlock ───────────────────────────────────────────────
    @app_commands.command(name="unlock", description="Unlock a channel")
    @app_commands.describe(channel="Channel to unlock (defaults to current)")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def unlock(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        ch = channel or interaction.channel
        await ch.set_permissions(interaction.guild.default_role, send_messages=None)
        await interaction.response.send_message(embed=mod_embed("🔓 Channel Unlocked", f"{ch.mention} has been unlocked.", discord.Color.green()))

    # ── /slowmode ─────────────────────────────────────────────
    @app_commands.command(name="slowmode", description="Set slowmode for a channel")
    @app_commands.describe(seconds="Slowmode delay in seconds (0 to disable)", channel="Channel to set slowmode on")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def slowmode(self, interaction: discord.Interaction, seconds: app_commands.Range[int, 0, 21600], channel: discord.TextChannel = None):
        ch = channel or interaction.channel
        await ch.edit(slowmode_delay=seconds)
        msg = f"Slowmode set to **{seconds}s** in {ch.mention}" if seconds > 0 else f"Slowmode **disabled** in {ch.mention}"
        await interaction.response.send_message(embed=mod_embed("⏱️ Slowmode Updated", msg, discord.Color.blurple()))

    # ── /nick ─────────────────────────────────────────────────
    @app_commands.command(name="nick", description="Change a member's nickname")
    @app_commands.describe(member="Member to rename", nickname="New nickname (leave blank to reset)")
    @app_commands.checks.has_permissions(manage_nicknames=True)
    async def nick(self, interaction: discord.Interaction, member: discord.Member, nickname: str = None):
        old = member.display_name
        await member.edit(nick=nickname)
        await interaction.response.send_message(embed=mod_embed("✏️ Nickname Changed", f"**{old}** → **{nickname or member.name}**", discord.Color.blurple()))

    # ── /roleadd, /roleremove ────────────────────────────────
    @app_commands.command(name="roleadd", description="Add a role to a member")
    @app_commands.describe(member="Member", role="Role to add")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def roleadd(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role):
        await member.add_roles(role)
        await interaction.response.send_message(embed=mod_embed("✅ Role Added", f"Added {role.mention} to {member.mention}", discord.Color.green()))

    @app_commands.command(name="roleremove", description="Remove a role from a member")
    @app_commands.describe(member="Member", role="Role to remove")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def roleremove(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role):
        await member.remove_roles(role)
        await interaction.response.send_message(embed=mod_embed("✅ Role Removed", f"Removed {role.mention} from {member.mention}", discord.Color.green()))

    # ── /giveroles (online members) ────────────────────────────
    @app_commands.command(name="giveroles", description="Give the Active Member role to all online members")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def giveroles(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        role = discord.utils.get(guild.roles, name="Active Member")
        if not role:
            role = await guild.create_role(name="Active Member", reason="/giveroles")
        ONLINE = {discord.Status.online, discord.Status.idle, discord.Status.dnd}
        targets = [m for m in guild.members if m.status in ONLINE and not m.bot and role not in m.roles]
        for m in targets:
            try:
                await m.add_roles(role)
            except Exception:
                pass
        await interaction.followup.send(f"✅ Gave **{role.name}** to **{len(targets)}** online members.", ephemeral=True)

    # ── /lockdown, /unlockdown ────────────────────────────────
    @app_commands.command(name="lockdown", description="Lock ALL channels in the server")
    @app_commands.checks.has_permissions(administrator=True)
    async def lockdown(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        locked = 0
        for ch in interaction.guild.text_channels:
            try:
                await ch.set_permissions(interaction.guild.default_role, send_messages=False)
                locked += 1
            except Exception:
                pass
        await interaction.followup.send(f"🔒 Server lockdown activated — **{locked}** channels locked.", ephemeral=True)

    @app_commands.command(name="unlockdown", description="Unlock ALL channels in the server")
    @app_commands.checks.has_permissions(administrator=True)
    async def unlockdown(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        unlocked = 0
        for ch in interaction.guild.text_channels:
            try:
                await ch.set_permissions(interaction.guild.default_role, send_messages=None)
                unlocked += 1
            except Exception:
                pass
        await interaction.followup.send(f"🔓 Lockdown lifted — **{unlocked}** channels unlocked.", ephemeral=True)

    # ── /modlogs ──────────────────────────────────────────────
    @app_commands.command(name="modlogs", description="View a member's full moderation history (warnings)")
    @app_commands.describe(member="Member to inspect")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def modlogs(self, interaction: discord.Interaction, member: discord.Member):
        warns = load_warns().get(str(interaction.guild.id), {}).get(str(member.id), [])
        e = discord.Embed(title=f"📁 Mod Logs for {member}", color=discord.Color.blurple())
        e.add_field(name="Total Warnings", value=str(len(warns)), inline=True)
        if warns:
            last = warns[-1]
            e.add_field(name="Most Recent", value=f"{last['reason']} — *{last['mod']}*", inline=True)
        await interaction.response.send_message(embed=e)

    async def cog_app_command_error(self, interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        else:
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ Error: {error}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Moderation(bot))
