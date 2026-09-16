# Ultimate Bot

A full-featured Discord bot: moderation, a 5-category ticket system, leveling,
invite tracking, welcome/leave messages, reaction roles, suggestions, automod,
AFK, embeds/announcements, utility commands, and a full SellAuth shop
integration — all as slash commands.

## 1. Create the Discord bot

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) → **New Application**.
2. Go to **Bot** → **Reset Token** → copy the token (this is your `BOT_TOKEN`).
3. On the same Bot page, enable **all three Privileged Gateway Intents**:
   - Presence Intent
   - Server Members Intent
   - Message Content Intent
4. Go to **OAuth2 → URL Generator**, tick `bot` and `applications.commands`,
   then under **Bot Permissions** tick `Administrator` (simplest for an
   all-in-one bot) or hand-pick the permissions each cog needs. Open the
   generated URL to invite the bot to your server.

## 2. Get your SellAuth credentials (optional, for `/sa_` commands)

1. Log into SellAuth → **Account → Developers** to get your **API key**.
2. Your **Shop ID** is the numeric ID of your shop (visible in your shop's
   dashboard URL or settings).

## 3. Deploy to Railway.app

1. Push this whole folder to a **GitHub repo** (or use Railway's "Deploy from
   local directory" / CLI).
2. On [Railway](https://railway.app) → **New Project → Deploy from GitHub repo**
   → pick the repo.
3. Once created, go to your service → **Variables** and add:

   | Variable            | Value                                  |
   |---------------------|-----------------------------------------|
   | `BOT_TOKEN`         | your Discord bot token                  |
   | `SELLAUTH_API_KEY`  | your SellAuth API key (optional)        |
   | `SELLAUTH_SHOP_ID`  | your SellAuth numeric shop ID (optional)|

   **Never commit real tokens to GitHub** — `.env` is already git-ignored;
   `.env.example` just shows the variable names.
4. Railway auto-detects Python and uses `requirements.txt`. The `Procfile`
   and `railway.json` tell it to run `python main.py` as a worker (no web
   port needed — this is a background bot process, not a web server).
5. Deploy. Check the **Deployments → Logs** tab — you should see each cog
   load and then `✅ YourBot is online`.

## 4. First steps in Discord

- Run `/setuptickets #channel` to post the ticket panel (Speak to Owner,
  Support, Purchase, Website Purchased, Problem with Purchase buttons).
- Run `/ticketsupport @role` so your staff role can see every ticket.
- Run `/sa_postproduct` to post a SellAuth product card with an image and a
  **Buy Now** button. Clicking it sends the buyer private payment instructions
  in a DM, then shows the buyer “Check your DMs for payment instructions!”.
- Use `/sa_panels` to list active product panels and `/sa_deletepanel` to
  disable one. Panels are saved in `data/sellauth_panels.json` and their
  buttons are restored after a restart.
- Run `/automod enable` then configure banned words / link blocking / anti-spam.
- Run `/setwelchannel`, `/setleavechannel`, `/setlevelchannel` etc. to wire up
  the rest.
- Run `/help` any time to see the full command list grouped by category.

### Product cards and payment DMs

After configuring SellAuth, run `/sa_postproduct` and provide:

| Field | What to enter |
|-------|---------------|
| `product_id` | The ID returned by `/sa_products` |
| `channel` | The Discord channel where the public product card should appear |
| `payment_url` | Your payment or gift-card link |
| `image_url` / `image` | Optional public image URL or image upload |
| `instructions` | Optional custom DM text |

Custom instructions can use `{title}`, `{price}`, and `{payment_url}`. If
left blank, the bot sends generic three-step payment instructions and asks
the buyer to reply with their receipt or payment code. This feature sends
instructions and collects the buyer's reply in their DM; it does not
automatically verify payment or fulfill an order.

### Buyer DM replies

After a buyer clicks **Buy Now** and replies in their DM, the bot sends the
owner identified by `OWNER_ID` a private embed containing the buyer, product,
price, reply/payment code, and any attachments. Pending purchase matches are
stored in `data/sellauth_pending_purchases.json`.

## Notes

- Data (warnings, tickets, levels, invites, config, automod settings,
  reaction roles) is stored in local JSON files under `data/`. Railway's
  filesystem is **ephemeral on redeploy** — for anything you must not lose,
  consider swapping the JSON storage for a small database (e.g. Railway's
  free Postgres or Redis plugin) later. For most small/medium servers the
  JSON approach works fine day-to-day.
- The SellAuth commands hit `https://api.sellauth.com/v1/shops/{shopId}/...`.
  SellAuth's API does evolve — if a command errors, check
  [docs.sellauth.com/api-documentation](https://docs.sellauth.com/api-documentation)
  for the current field names for that endpoint and adjust the payload in
  `cogs/sellauth.py`.
- All commands are slash commands (`/command`) — Discord can take up to an
  hour to show brand new commands globally the very first time, though
  `on_ready` calls a sync every restart so it's usually near-instant.
