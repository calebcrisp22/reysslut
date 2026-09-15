import discord
from discord import app_commands
from discord.ext import commands
import datetime, time, re

START_TIME = time.time()


class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Check the bot's latency")
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        color = discord.Color.green() if latency < 100 else discord.Color.yellow() if latency < 200 else discord.Color.red()
        e = discord.Embed(title="🏓 Pong!", description=f"**Latency:** {latency}ms", color=color)
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="uptime", description="Check how long the bot has been online")
    async def uptime(self, interaction: discord.Interaction):
        elapsed = int(time.time() - START_TIME)
        h, rem = divmod(elapsed, 3600)
        m, s = divmod(rem, 60)
        await interaction.response.send_message(f"⏱️ Uptime: **{h}h {m}m {s}s**")

    @app_commands.command(name="serverinfo", description="View information about this server")
    async def serverinfo(self, interaction: discord.Interaction):
        g = interaction.guild
        e = discord.Embed(title=g.name, color=discord.Color.blurple(), timestamp=datetime.datetime.utcnow())
        if g.icon:
            e.set_thumbnail(url=g.icon.url)
        e.add_field(name="Owner", value=str(g.owner), inline=True)
        e.add_field(name="Members", value=str(g.member_count), inline=True)
        e.add_field(name="Channels", value=str(len(g.channels)), inline=True)
        e.add_field(name="Roles", value=str(len(g.roles)), inline=True)
        e.add_field(name="Boosts", value=str(g.premium_subscription_count), inline=True)
        e.add_field(name="Created", value=g.created_at.strftime("%Y-%m-%d"), inline=True)
        e.add_field(name="Server ID", value=str(g.id), inline=False)
        e.set_footer(text=f"ID: {g.id}")
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="userinfo", description="View information about a user")
    @app_commands.describe(member="Member to inspect")
    async def userinfo(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        roles = [r.mention for r in reversed(member.roles) if r.name != "@everyone"]
        e = discord.Embed(title=str(member), color=member.color, timestamp=datetime.datetime.utcnow())
        e.set_thumbnail(url=member.display_avatar.url)
        e.add_field(name="ID", value=str(member.id), inline=True)
        e.add_field(name="Nickname", value=member.nick or "None", inline=True)
        e.add_field(name="Status", value=str(member.status).title(), inline=True)
        e.add_field(name="Joined Server", value=member.joined_at.strftime("%Y-%m-%d") if member.joined_at else "?", inline=True)
        e.add_field(name="Account Created", value=member.created_at.strftime("%Y-%m-%d"), inline=True)
        e.add_field(name="Bot", value="✅" if member.bot else "❌", inline=True)
        e.add_field(name=f"Roles ({len(roles)})", value=" ".join(roles[:10]) or "None", inline=False)
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="avatar", description="Get a user's avatar")
    @app_commands.describe(member="Member (default: yourself)")
    async def avatar(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        e = discord.Embed(title=f"{member.display_name}'s Avatar", color=discord.Color.blurple())
        e.set_image(url=member.display_avatar.url)
        e.add_field(name="Direct Link", value=f"[Click here]({member.display_avatar.url})")
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="banner", description="Get a user's banner")
    @app_commands.describe(member="Member (default: yourself)")
    async def banner(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        user = await self.bot.fetch_user(member.id)
        if not user.banner:
            return await interaction.response.send_message(f"❌ {member.display_name} has no banner.", ephemeral=True)
        e = discord.Embed(title=f"{member.display_name}'s Banner", color=discord.Color.blurple())
        e.set_image(url=user.banner.url)
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="imagelink", description="Get the direct link of an image from a message")
    @app_commands.describe(message_id="ID of the message containing the image")
    async def imagelink(self, interaction: discord.Interaction, message_id: str):
        try:
            msg = await interaction.channel.fetch_message(int(message_id))
            if msg.attachments:
                links = "\n".join(a.url for a in msg.attachments)
                await interaction.response.send_message(f"🖼️ Direct link(s):\n{links}")
            elif msg.embeds and msg.embeds[0].image:
                await interaction.response.send_message(f"🖼️ {msg.embeds[0].image.url}")
            else:
                await interaction.response.send_message("❌ No image found in that message.", ephemeral=True)
        except discord.NotFound:
            await interaction.response.send_message("❌ Message not found.", ephemeral=True)

    @app_commands.command(name="steal", description="Add a custom emoji from another server to this one")
    @app_commands.describe(emoji="Custom emoji or direct image URL to add")
    @app_commands.checks.has_permissions(manage_emojis=True)
    async def steal(self, interaction: discord.Interaction, emoji: str):
        import aiohttp
        await interaction.response.defer(ephemeral=True)

        match = re.match(r"<a?:(\w+):(\d+)>", emoji)
        if match:
            name = match.group(1)
            eid = match.group(2)
            ext = "gif" if emoji.startswith("<a") else "png"
            url = f"https://cdn.discordapp.com/emojis/{eid}.{ext}"
        elif emoji.startswith("http"):
            url = emoji
            name = "added_emoji"
        else:
            return await interaction.followup.send("❌ Please provide a custom emoji or image URL.", ephemeral=True)

        async with aiohttp.ClientSession() as s:
            async with s.get(url) as r:
                if r.status != 200:
                    return await interaction.followup.send("❌ Could not fetch image.", ephemeral=True)
                img_bytes = await r.read()

        try:
            new_emoji = await interaction.guild.create_custom_emoji(name=name, image=img_bytes)
            await interaction.followup.send(f"✅ Emoji added: {new_emoji}", ephemeral=False)
        except discord.HTTPException as e:
            await interaction.followup.send(f"❌ Failed: {e}", ephemeral=True)

    @app_commands.command(name="sync", description="Sync slash commands (owner only)")
    async def sync(self, interaction: discord.Interaction):
        if interaction.user.id != interaction.guild.owner_id:
            return await interaction.response.send_message("❌ Owner only.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        synced = await self.bot.tree.sync()
        await interaction.followup.send(f"✅ Synced **{len(synced)}** commands.", ephemeral=True)

    @app_commands.command(name="rolelist", description="List all roles in this server")
    async def rolelist(self, interaction: discord.Interaction):
        roles = [r.mention for r in reversed(interaction.guild.roles) if r.name != "@everyone"]
        chunks = [roles[i:i + 20] for i in range(0, len(roles), 20)]
        e = discord.Embed(title=f"📋 Server Roles ({len(roles)})", description=" ".join(chunks[0]) if chunks else "None", color=discord.Color.blurple())
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="channelinfo", description="Get info about a channel")
    @app_commands.describe(channel="Channel to inspect")
    async def channelinfo(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        ch = channel or interaction.channel
        e = discord.Embed(title=f"#{ch.name}", color=discord.Color.blurple())
        e.add_field(name="ID", value=str(ch.id), inline=True)
        e.add_field(name="Category", value=ch.category.name if ch.category else "None", inline=True)
        e.add_field(name="NSFW", value="✅" if ch.is_nsfw() else "❌", inline=True)
        e.add_field(name="Slowmode", value=f"{ch.slowmode_delay}s", inline=True)
        e.add_field(name="Created", value=ch.created_at.strftime("%Y-%m-%d"), inline=True)
        e.add_field(name="Topic", value=ch.topic or "None", inline=False)
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="membercount", description="Show the server member count")
    async def membercount(self, interaction: discord.Interaction):
        g = interaction.guild
        humans = sum(1 for m in g.members if not m.bot)
        bots = sum(1 for m in g.members if m.bot)
        e = discord.Embed(title="👥 Member Count", color=discord.Color.blurple())
        e.add_field(name="Total", value=str(g.member_count), inline=True)
        e.add_field(name="Humans", value=str(humans), inline=True)
        e.add_field(name="Bots", value=str(bots), inline=True)
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="remind", description="Get a DM reminder after a set time")
    @app_commands.describe(minutes="Minutes from now", text="What to remind you about")
    async def remind(self, interaction: discord.Interaction, minutes: app_commands.Range[int, 1, 10080], text: str):
        import asyncio
        await interaction.response.send_message(f"⏰ Okay, I'll remind you about **{text}** in **{minutes}** minute(s).", ephemeral=True)

        async def _wait_and_remind():
            await asyncio.sleep(minutes * 60)
            try:
                await interaction.user.send(f"⏰ Reminder: {text}")
            except Exception:
                pass

        self.bot.loop.create_task(_wait_and_remind())


async def setup(bot):
    await bot.add_cog(Utility(bot))
