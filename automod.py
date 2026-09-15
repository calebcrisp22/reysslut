import discord
from discord import app_commands
from discord.ext import commands
import json, os, re, time, collections

CONFIG_FILE = "data/automod_config.json"


def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE) as f:
        return json.load(f)


def save_config(d):
    os.makedirs("data", exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(d, f, indent=2)


INVITE_RE = re.compile(r"(discord\.gg/|discordapp\.com/invite/|discord\.com/invite/)\S+", re.IGNORECASE)
LINK_RE = re.compile(r"https?://\S+", re.IGNORECASE)


class AutoMod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.spam_tracker = collections.defaultdict(list)  # "gid:uid" -> [timestamps]

    def _gconf(self, gid):
        return load_config().get(str(gid), {})

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        if message.author.guild_permissions.manage_messages:
            return

        conf = self._gconf(message.guild.id)
        if not conf.get("enabled"):
            return

        content = message.content

        # Banned words
        banned_words = conf.get("banned_words", [])
        if banned_words and any(w.lower() in content.lower() for w in banned_words):
            await self._strike(message, "banned word")
            return

        # Discord invite links
        if conf.get("block_invites") and INVITE_RE.search(content):
            await self._strike(message, "Discord invite link")
            return

        # General links
        if conf.get("block_links") and LINK_RE.search(content):
            await self._strike(message, "link")
            return

        # Basic spam protection: N messages within window
        if conf.get("anti_spam"):
            key = f"{message.guild.id}:{message.author.id}"
            now = time.time()
            self.spam_tracker[key] = [t for t in self.spam_tracker[key] if now - t < 6]
            self.spam_tracker[key].append(now)
            if len(self.spam_tracker[key]) >= 6:
                await self._strike(message, "spamming")
                self.spam_tracker[key] = []

    async def _strike(self, message, reason):
        try:
            await message.delete()
        except Exception:
            pass
        try:
            await message.channel.send(f"⚠️ {message.author.mention}, that message was removed ({reason}).", delete_after=6)
        except Exception:
            pass

    automod_group = app_commands.Group(name="automod", description="Configure the automod system")

    @automod_group.command(name="enable", description="Enable automod for this server")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def enable(self, interaction: discord.Interaction):
        config = load_config()
        config.setdefault(str(interaction.guild.id), {})["enabled"] = True
        save_config(config)
        await interaction.response.send_message("✅ AutoMod enabled.", ephemeral=True)

    @automod_group.command(name="disable", description="Disable automod for this server")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def disable(self, interaction: discord.Interaction):
        config = load_config()
        config.setdefault(str(interaction.guild.id), {})["enabled"] = False
        save_config(config)
        await interaction.response.send_message("✅ AutoMod disabled.", ephemeral=True)

    @automod_group.command(name="addword", description="Add a word to the banned words list")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def addword(self, interaction: discord.Interaction, word: str):
        config = load_config()
        g = config.setdefault(str(interaction.guild.id), {})
        g.setdefault("banned_words", [])
        if word.lower() not in [w.lower() for w in g["banned_words"]]:
            g["banned_words"].append(word)
        save_config(config)
        await interaction.response.send_message(f"✅ Added `{word}` to the banned words list.", ephemeral=True)

    @automod_group.command(name="removeword", description="Remove a word from the banned words list")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def removeword(self, interaction: discord.Interaction, word: str):
        config = load_config()
        g = config.setdefault(str(interaction.guild.id), {})
        g["banned_words"] = [w for w in g.get("banned_words", []) if w.lower() != word.lower()]
        save_config(config)
        await interaction.response.send_message(f"✅ Removed `{word}` from the banned words list.", ephemeral=True)

    @automod_group.command(name="toggleinvites", description="Toggle blocking Discord invite links")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def toggleinvites(self, interaction: discord.Interaction):
        config = load_config()
        g = config.setdefault(str(interaction.guild.id), {})
        g["block_invites"] = not g.get("block_invites", False)
        save_config(config)
        await interaction.response.send_message(f"✅ Blocking Discord invites: **{g['block_invites']}**", ephemeral=True)

    @automod_group.command(name="togglelinks", description="Toggle blocking all links")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def togglelinks(self, interaction: discord.Interaction):
        config = load_config()
        g = config.setdefault(str(interaction.guild.id), {})
        g["block_links"] = not g.get("block_links", False)
        save_config(config)
        await interaction.response.send_message(f"✅ Blocking all links: **{g['block_links']}**", ephemeral=True)

    @automod_group.command(name="togglespam", description="Toggle basic anti-spam protection")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def togglespam(self, interaction: discord.Interaction):
        config = load_config()
        g = config.setdefault(str(interaction.guild.id), {})
        g["anti_spam"] = not g.get("anti_spam", False)
        save_config(config)
        await interaction.response.send_message(f"✅ Anti-spam protection: **{g['anti_spam']}**", ephemeral=True)

    @automod_group.command(name="settings", description="View current automod settings")
    async def settings(self, interaction: discord.Interaction):
        conf = self._gconf(interaction.guild.id)
        e = discord.Embed(title="🛡️ AutoMod Settings", color=discord.Color.blurple())
        e.add_field(name="Enabled", value=str(conf.get("enabled", False)), inline=True)
        e.add_field(name="Block Invites", value=str(conf.get("block_invites", False)), inline=True)
        e.add_field(name="Block Links", value=str(conf.get("block_links", False)), inline=True)
        e.add_field(name="Anti-Spam", value=str(conf.get("anti_spam", False)), inline=True)
        e.add_field(name="Banned Words", value=str(len(conf.get("banned_words", []))), inline=True)
        await interaction.response.send_message(embed=e, ephemeral=True)


async def setup(bot):
    await bot.add_cog(AutoMod(bot))
