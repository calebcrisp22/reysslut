"""
ULTIMATE BOT — main entry point
Ready for Railway.app deployment. All secrets are pulled from environment
variables (set these in Railway → Variables), never hardcoded.
"""
import discord
from discord.ext import commands
import logging
import os
import asyncio

# ══════════════════════════════════════════════════════════════
#  CONFIGURATION — pulled from environment variables (Railway → Variables)
#  Required:  BOT_TOKEN
#  Optional:  SELLAUTH_API_KEY, SELLAUTH_SHOP_ID  (needed for /sa_ commands)
#             COMMAND_PREFIX (defaults to "!")
# ══════════════════════════════════════════════════════════════
BOT_TOKEN         = os.getenv("BOT_TOKEN")
SELLAUTH_API_KEY  = os.getenv("SELLAUTH_API_KEY", "")
SELLAUTH_SHOP_ID  = os.getenv("SELLAUTH_SHOP_ID", "")
OWNER_ID          = os.getenv("OWNER_ID", "1173668793382354999")
COMMAND_PREFIX    = os.getenv("COMMAND_PREFIX", "!")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("main")

intents = discord.Intents.all()   # full intents for ultimate bot
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents, help_command=None)

# Attach SellAuth credentials to the bot object so cogs can read them
bot.SELLAUTH_API_KEY = SELLAUTH_API_KEY
bot.SELLAUTH_SHOP_ID = SELLAUTH_SHOP_ID
bot.OWNER_ID = OWNER_ID

# All cogs that make up the ultimate bot
COGS = [
    "moderation",
    "tickets",
    "leveling",
    "invites",
    "utility",
    "sellauth",
    "welcome",
    "embeds",
    "info",
    "automod",
    "afk",
    "reactionroles",
    "suggestions",
    "cogs.products",
]


@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        log.info(f"Synced {len(synced)} slash commands")
    except Exception as e:
        log.warning(f"Slash command sync failed: {e}")

    activity = discord.Activity(type=discord.ActivityType.watching, name="the server 👁")
    await bot.change_presence(status=discord.Status.online, activity=activity)
    print(f"✅  {bot.user} is online | {len(bot.guilds)} guild(s) | Commands synced")


async def main():
    if not BOT_TOKEN:
        raise SystemExit(
            "❌ BOT_TOKEN is not set. On Railway, go to your project → Variables "
            "and add BOT_TOKEN with your Discord bot token."
        )

    async with bot:
        for cog in COGS:
            try:
                await bot.load_extension(cog)
                print(f"  ✔  Loaded {cog}")
            except Exception as e:
                print(f"  ✘  Failed to load {cog}: {e}")
        await bot.start(BOT_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
