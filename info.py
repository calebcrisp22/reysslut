import discord
from discord import app_commands
from discord.ext import commands
import datetime, platform


class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="botinfo", description="View information about the bot")
    async def botinfo(self, interaction: discord.Interaction):
        e = discord.Embed(title=f"ℹ️ {self.bot.user.name}", color=discord.Color.blurple(), timestamp=datetime.datetime.utcnow())
        e.set_thumbnail(url=self.bot.user.display_avatar.url)
        e.add_field(name="Servers", value=str(len(self.bot.guilds)), inline=True)
        e.add_field(name="Members", value=str(sum(g.member_count for g in self.bot.guilds)), inline=True)
        e.add_field(name="Latency", value=f"{round(self.bot.latency*1000)}ms", inline=True)
        e.add_field(name="Python", value=platform.python_version(), inline=True)
        e.add_field(name="discord.py", value=discord.__version__, inline=True)
        e.add_field(name="Platform", value=platform.system(), inline=True)
        e.set_footer(text="Ultimate Bot")
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="help", description="View all available commands")
    async def help(self, interaction: discord.Interaction):
        e = discord.Embed(title="📚 Ultimate Bot — Command List", color=discord.Color.blurple(), timestamp=datetime.datetime.utcnow())

        e.add_field(name="⚔️ Moderation", value=(
            "`/ban` `/unban` `/softban` `/kick` `/timeout` `/untimeout`\n"
            "`/warn` `/warnings` `/delwarn` `/clearwarnings` `/purge`\n"
            "`/lock` `/unlock` `/slowmode` `/nick`\n"
            "`/roleadd` `/roleremove` `/giveroles`\n"
            "`/lockdown` `/unlockdown` `/modlogs`"
        ), inline=False)

        e.add_field(name="🎫 Tickets", value=(
            "`/setuptickets` `/ticketsupport` `/ticketcategory`\n"
            "`/claim` `/ticketlist` `/ticketpurge`"
        ), inline=False)

        e.add_field(name="🛡️ AutoMod", value=(
            "`/automod enable` `/automod disable` `/automod addword`\n"
            "`/automod removeword` `/automod toggleinvites`\n"
            "`/automod togglelinks` `/automod togglespam` `/automod settings`"
        ), inline=False)

        e.add_field(name="📊 Leveling", value=(
            "`/rank` `/leaderboard` `/setlevelmessage`\n"
            "`/setlevelchannel` `/setlevelrole` `/removelevelrole`\n"
            "`/setxp` `/setlevel` `/resetxp`"
        ), inline=False)

        e.add_field(name="📨 Invites", value=(
            "`/invites` `/inviteleaderboard` `/invitepanel` `/setinvitepanel`"
        ), inline=False)

        e.add_field(name="👋 Welcome / Leave", value=(
            "`/setwelchannel` `/setwelcome` `/setleavechannel`\n"
            "`/setleave` `/autorole`"
        ), inline=False)

        e.add_field(name="🎭 Reaction Roles & Suggestions", value=(
            "`/reactionrole` `/reactionroleadd`\n"
            "`/setsuggestchannel` `/suggest`"
        ), inline=False)

        e.add_field(name="🛒 SellAuth", value=(
            "`/sa_products` `/sa_product` `/sa_addproduct`\n"
            "`/sa_editproduct` `/sa_deleteproduct`\n"
            "`/sa_orders` `/sa_order` `/sa_invoices`\n"
            "`/sa_coupons` `/sa_addcoupon` `/sa_deletecoupon`\n"
            "`/sa_blacklist` `/sa_blacklistadd` `/sa_blacklistremove`\n"
            "`/sa_shopinfo` `/sa_revenue` `/sa_topproducts`"
        ), inline=False)

        e.add_field(name="📢 Embeds & Announcements", value=(
            "`/embed` `/testembed` `/announce` `/say` `/poll` `/giveaway`"
        ), inline=False)

        e.add_field(name="🔧 Utility", value=(
            "`/ping` `/uptime` `/serverinfo` `/userinfo`\n"
            "`/avatar` `/banner` `/imagelink`\n"
            "`/steal` `/sync` `/rolelist` `/channelinfo` `/membercount` `/remind`\n"
            "`/afk`"
        ), inline=False)

        e.add_field(name="ℹ️ Info", value="`/help` `/botinfo`", inline=False)

        e.set_footer(text="Ultimate Bot • All commands are slash commands")
        await interaction.response.send_message(embed=e, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Info(bot))
