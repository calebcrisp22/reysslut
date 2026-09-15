import discord
from discord import app_commands
from discord.ext import commands
import json, os, datetime, asyncio

TICKETS_FILE = "data/tickets.json"
CONFIG_FILE = "data/ticket_config.json"


def load_tickets():
    if not os.path.exists(TICKETS_FILE):
        return {}
    with open(TICKETS_FILE) as f:
        return json.load(f)


def save_tickets(d):
    os.makedirs("data", exist_ok=True)
    with open(TICKETS_FILE, "w") as f:
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


# ── Ticket Panel View (the 5 buttons users click to open a ticket) ────────────
class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def _open_ticket(self, interaction: discord.Interaction, category_name: str, emoji: str):
        guild = interaction.guild
        member = interaction.user
        config = load_config()
        gid = str(guild.id)
        tickets = load_tickets()

        safe_name = "".join(c for c in member.name.lower() if c.isalnum() or c == "-").strip("-") or str(member.id)
        existing = discord.utils.get(guild.text_channels, name=f"ticket-{safe_name}")
        if existing:
            return await interaction.response.send_message(
                f"❌ You already have an open ticket: {existing.mention}", ephemeral=True
            )

        cat_name = config.get(gid, {}).get("ticket_category", "Tickets")
        cat = discord.utils.get(guild.categories, name=cat_name)
        if not cat:
            cat = await guild.create_category(cat_name)

        support_role_id = config.get(gid, {}).get("support_role")
        support_role = guild.get_role(int(support_role_id)) if support_role_id else None

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        ch = await guild.create_text_channel(
            f"ticket-{safe_name}",
            category=cat,
            overwrites=overwrites,
            topic=f"Ticket by {member} | Type: {category_name}",
        )

        tickets.setdefault(gid, {})[str(ch.id)] = {
            "user_id": str(member.id),
            "type": category_name,
            "opened": str(datetime.datetime.utcnow()),
            "closed": False,
        }
        save_tickets(tickets)

        e = discord.Embed(
            title=f"{emoji} {category_name} Ticket",
            description=(
                f"Welcome {member.mention}!\n\n"
                f"**Ticket type:** {category_name}\n"
                f"A staff member will be with you shortly.\n\n"
                f"Click 🔒 **Close** to close this ticket when done."
            ),
            color=discord.Color.blurple(),
            timestamp=datetime.datetime.utcnow(),
        )
        e.set_footer(text=f"Ticket ID: {ch.id}")
        await ch.send(
            content=f"{member.mention}" + (f" | {support_role.mention}" if support_role else ""),
            embed=e,
            view=TicketControlView(),
        )
        await interaction.response.send_message(f"✅ Ticket created: {ch.mention}", ephemeral=True)

    @discord.ui.button(label="Speak to Owner", emoji="👑", style=discord.ButtonStyle.danger, custom_id="ticket_owner")
    async def owner(self, interaction, button):
        await self._open_ticket(interaction, "Speak to Owner", "👑")

    @discord.ui.button(label="Support", emoji="🛠️", style=discord.ButtonStyle.primary, custom_id="ticket_support")
    async def support(self, interaction, button):
        await self._open_ticket(interaction, "Support", "🛠️")

    @discord.ui.button(label="Purchase", emoji="💰", style=discord.ButtonStyle.success, custom_id="ticket_purchase")
    async def purchase(self, interaction, button):
        await self._open_ticket(interaction, "Purchase", "💰")

    @discord.ui.button(label="Website Purchased", emoji="🌐", style=discord.ButtonStyle.secondary, custom_id="ticket_website")
    async def website(self, interaction, button):
        await self._open_ticket(interaction, "Website Purchased", "🌐")

    @discord.ui.button(label="Problem with Purchase", emoji="⚠️", style=discord.ButtonStyle.danger, custom_id="ticket_problem")
    async def problem(self, interaction, button):
        await self._open_ticket(interaction, "Problem with Purchase", "⚠️")


# ── Ticket Control View (inside an open ticket) ───────────────────────────────
class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", emoji="🔒", style=discord.ButtonStyle.danger, custom_id="ticket_close")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        e = discord.Embed(title="🔒 Close Ticket", description="Are you sure you want to close this ticket?", color=discord.Color.red())
        await interaction.response.send_message(embed=e, view=TicketCloseConfirmView(), ephemeral=False)

    @discord.ui.button(label="Claim Ticket", emoji="🙋", style=discord.ButtonStyle.primary, custom_id="ticket_claim")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        topic = interaction.channel.topic or ""
        await interaction.channel.edit(topic=f"{topic} | Claimed by {interaction.user}")
        await interaction.response.send_message(f"✅ {interaction.user.mention} claimed this ticket.")
        button.disabled = True
        await interaction.message.edit(view=self)

    @discord.ui.button(label="Add User", emoji="➕", style=discord.ButtonStyle.secondary, custom_id="ticket_add")
    async def add_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Mention the user to add:", ephemeral=True)

        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel

        try:
            msg = await interaction.client.wait_for("message", check=check, timeout=30)
            if msg.mentions:
                user = msg.mentions[0]
                await interaction.channel.set_permissions(user, view_channel=True, send_messages=True)
                await interaction.channel.send(f"✅ Added {user.mention} to this ticket.")
                await msg.delete()
        except asyncio.TimeoutError:
            pass


class TicketCloseConfirmView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="Yes, Close", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        tickets = load_tickets()
        gid = str(interaction.guild.id)
        cid = str(interaction.channel.id)
        if gid in tickets and cid in tickets[gid]:
            tickets[gid][cid]["closed"] = True
            save_tickets(tickets)
        await interaction.response.send_message("🔒 Closing ticket in 5 seconds...")
        await asyncio.sleep(5)
        await interaction.channel.delete(reason="Ticket closed")

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Cancelled.", ephemeral=True)
        self.stop()


class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.add_view(TicketPanelView())
        bot.add_view(TicketControlView())

    # ── /setuptickets — asks which channel, then posts the 5-option panel ─────
    @app_commands.command(name="setuptickets", description="Set up the ticket panel in a channel")
    @app_commands.describe(channel="Channel to post the ticket panel in")
    @app_commands.checks.has_permissions(administrator=True)
    async def setuptickets(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await interaction.response.defer(ephemeral=True)
        e = discord.Embed(
            title="🎫 Support Tickets",
            description=(
                "Need help? Open a ticket below and our team will assist you.\n\n"
                "👑 **Speak to Owner** — Direct message to the owner\n"
                "🛠️ **Support** — General help & questions\n"
                "💰 **Purchase** — Want to buy something?\n"
                "🌐 **Website Purchased** — Bought from our website\n"
                "⚠️ **Problem with Purchase** — Issue with an order\n\n"
                "*Select a category below to open your ticket.*"
            ),
            color=discord.Color.blurple(),
        )
        e.set_footer(text="One ticket per user • Staff will respond shortly")
        await channel.send(embed=e, view=TicketPanelView())
        await interaction.followup.send(f"✅ Ticket panel sent to {channel.mention}!", ephemeral=True)

    @app_commands.command(name="ticketsupport", description="Set the support role for tickets")
    @app_commands.describe(role="Role that can see all tickets")
    @app_commands.checks.has_permissions(administrator=True)
    async def ticketsupport(self, interaction: discord.Interaction, role: discord.Role):
        config = load_config()
        config.setdefault(str(interaction.guild.id), {})["support_role"] = str(role.id)
        save_config(config)
        await interaction.response.send_message(f"✅ Support role set to {role.mention}", ephemeral=True)

    @app_commands.command(name="ticketcategory", description="Set the category name for ticket channels")
    @app_commands.describe(name="Category name")
    @app_commands.checks.has_permissions(administrator=True)
    async def ticketcategory(self, interaction: discord.Interaction, name: str):
        config = load_config()
        config.setdefault(str(interaction.guild.id), {})["ticket_category"] = name
        save_config(config)
        await interaction.response.send_message(f"✅ Ticket category set to **{name}**", ephemeral=True)

    @app_commands.command(name="claim", description="Claim the current ticket")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def claim(self, interaction: discord.Interaction):
        topic = interaction.channel.topic or ""
        await interaction.channel.edit(topic=f"{topic} | Claimed by {interaction.user}")
        await interaction.response.send_message(f"✅ {interaction.user.mention} has claimed this ticket.")

    @app_commands.command(name="ticketlist", description="List all open tickets")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def ticketlist(self, interaction: discord.Interaction):
        tickets = load_tickets()
        gid = str(interaction.guild.id)
        open_tickets = {cid: t for cid, t in tickets.get(gid, {}).items() if not t.get("closed")}
        if not open_tickets:
            return await interaction.response.send_message("✅ No open tickets.", ephemeral=True)
        lines = []
        for cid, t in open_tickets.items():
            ch = interaction.guild.get_channel(int(cid))
            ch_str = ch.mention if ch else f"#{cid}"
            uid = t.get("user_id", "?")
            user = interaction.guild.get_member(int(uid))
            lines.append(f"{ch_str} — **{t.get('type','?')}** | {user.mention if user else uid}")
        e = discord.Embed(title=f"🎫 Open Tickets ({len(open_tickets)})", description="\n".join(lines), color=discord.Color.blurple())
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="ticketpurge", description="Delete ALL ticket channels (Owner only)")
    @app_commands.checks.has_permissions(administrator=True)
    async def ticketpurge(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        deleted = 0
        for ch in interaction.guild.text_channels:
            if ch.name.startswith("ticket-"):
                try:
                    await ch.delete(reason="Ticket purge")
                    deleted += 1
                except Exception:
                    pass
        tickets = load_tickets()
        tickets.pop(str(interaction.guild.id), None)
        save_tickets(tickets)
        await interaction.followup.send(f"🗑️ Purged **{deleted}** ticket channels.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Tickets(bot))
