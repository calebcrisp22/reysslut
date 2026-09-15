"""
SellAuth API cog
Docs: https://docs.sellauth.com/api-documentation
All requests go to: https://api.sellauth.com/v1/shops/{SHOP_ID}/...

Reads SELLAUTH_API_KEY / SELLAUTH_SHOP_ID from the bot object, which main.py
sets from the SELLAUTH_API_KEY / SELLAUTH_SHOP_ID environment variables.
"""
import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import datetime
import json
import os
import secrets


def is_owner():
    async def predicate(interaction: discord.Interaction) -> bool:
        owner_id = getattr(interaction.client, 'OWNER_ID', '')
        if not owner_id:
            return False
        return str(interaction.user.id) == str(owner_id)
    return app_commands.check(predicate)


def sa_embed(title, description="", color=discord.Color.green()):
    e = discord.Embed(title=title, description=description, color=color, timestamp=datetime.datetime.utcnow())
    e.set_footer(text="SellAuth Integration")
    return e


class PurchaseView(discord.ui.View):
    """Persistent Buy Now button attached to a product panel."""

    def __init__(self, cog, panel_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.panel_id = panel_id
        button = discord.ui.Button(
            label="Buy Now",
            emoji="💰",
            style=discord.ButtonStyle.success,
            custom_id=f"sellauth:buy:{panel_id}",
        )
        button.callback = self.buy
        self.add_item(button)

    async def buy(self, interaction: discord.Interaction):
        await self.cog.handle_purchase(interaction, self.panel_id)


class SellAuth(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.panel_file = os.path.join("data", "sellauth_panels.json")
        self.panels = self._load_panels()

        # Re-register buttons after a restart so existing product panels keep working.
        for panel_id in self.panels:
            bot.add_view(PurchaseView(self, panel_id))

    def _load_panels(self):
        try:
            with open(self.panel_file, "r", encoding="utf-8") as f:
                panels = json.load(f)
            return panels if isinstance(panels, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}

    def _save_panels(self):
        os.makedirs(os.path.dirname(self.panel_file), exist_ok=True)
        with open(self.panel_file, "w", encoding="utf-8") as f:
            json.dump(self.panels, f, indent=2)

    async def _get_product(self, product_id):
        if not self._configured():
            return None, "❌ SellAuth isn't configured. Set SELLAUTH_API_KEY / SELLAUTH_SHOP_ID."
        async with aiohttp.ClientSession() as s:
            r = await s.get(f"{self.base}/products/{product_id}", headers=self.headers)
            try:
                product = await r.json()
            except (aiohttp.ContentTypeError, ValueError):
                product = {"error": await r.text()}
        if r.status != 200:
            return None, f"❌ API Error: {product}"
        return product, None

    @staticmethod
    def _product_name(product):
        return str(product.get("name", product.get("title", "Product")))

    @staticmethod
    def _product_price(product):
        return str(product.get("price", "?"))

    def _sale_embed(self, product, image_url=""):
        name = self._product_name(product)
        price = self._product_price(product)
        description = str(product.get("description", "")).strip()
        body = f"**{name}**\n\n**Price**\n${price}"
        if description:
            body += f"\n\n{description[:2500]}"
        body += "\n\nClick **Buy Now** to get payment instructions in your DMs."
        embed = discord.Embed(
            title=f"🛒 {name}",
            description=body,
            color=discord.Color.gold(),
            timestamp=datetime.datetime.utcnow(),
        )
        if image_url:
            embed.set_image(url=image_url)
        embed.set_footer(text="Secure purchase instructions are sent privately")
        return embed

    def _payment_embed(self, panel, product):
        name = self._product_name(product)
        price = self._product_price(product)
        payment_url = panel["payment_url"]
        instructions = panel.get("instructions", "").strip()
        if instructions:
            # These replacements are optional; ordinary braces in custom text remain untouched.
            instructions = (
                instructions
                .replace("{title}", name)
                .replace("{price}", price)
                .replace("{payment_url}", payment_url)
            )
        else:
            instructions = (
                f"**How to pay:**\n"
                f"1️⃣ Complete payment here: {payment_url}\n"
                "2️⃣ Once payment is complete, reply to this DM with your receipt or payment code and nothing else.\n"
                "3️⃣ We'll confirm and process your order once we receive it."
            )

        embed = discord.Embed(
            title=f"💰 Purchase: {name}",
            description=f"**Price:** ${price}\n\n{instructions}",
            color=discord.Color.gold(),
            timestamp=datetime.datetime.utcnow(),
        )
        if panel.get("image_url"):
            embed.set_image(url=panel["image_url"])
        embed.set_footer(text="Please keep this DM open while your order is processed")
        return embed

    async def handle_purchase(self, interaction, panel_id):
        panel = self.panels.get(panel_id)
        if not panel:
            return await interaction.response.send_message(
                "❌ This product panel is no longer active.", ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)
        product, error = await self._get_product(panel["product_id"])
        if error:
            # Keep a snapshot in the panel so a temporary SellAuth outage does not
            # prevent the seller from sending instructions.
            product = panel.get("product", {})

        try:
            await interaction.user.send(embed=self._payment_embed(panel, product))
        except discord.Forbidden:
            return await interaction.followup.send(
                "❌ I couldn't DM you. Enable DMs from server members and click **Buy Now** again.",
                ephemeral=True,
            )
        except discord.HTTPException:
            return await interaction.followup.send(
                "❌ Discord couldn't deliver the payment instructions. Please try again in a moment.",
                ephemeral=True,
            )

        await interaction.followup.send(
            "✅ Check your DMs for payment instructions!", ephemeral=True
        )

    # ── /sa_postproduct ──────────────────────────────────────
    @app_commands.command(
        name="sa_postproduct",
        description="Post a product card with a Buy Now button",
    )
    @app_commands.describe(
        product_id="Product ID from /sa_products",
        channel="Channel where the product card should be posted",
        payment_url="Payment or gift-card link shown in the buyer's DM",
        image_url="Optional product image URL",
        instructions="Optional DM instructions. Use {title}, {price}, and {payment_url}.",
        image="Optional image upload for the product card",
    )
    @is_owner()
    async def sa_postproduct(
        self,
        interaction: discord.Interaction,
        product_id: str,
        channel: discord.TextChannel,
        payment_url: str,
        image_url: str = "",
        instructions: str = "",
        image: discord.Attachment = None,
    ):
        await interaction.response.defer(ephemeral=True)
        product, error = await self._get_product(product_id)
        if error:
            return await interaction.followup.send(error, ephemeral=True)

        if image:
            image_url = image.url
        panel_id = secrets.token_hex(10)
        panel = {
            "panel_id": panel_id,
            "product_id": product_id,
            "payment_url": payment_url,
            "image_url": image_url,
            "instructions": instructions,
            "channel_id": str(channel.id),
            "product": {
                "name": self._product_name(product),
                "price": self._product_price(product),
                "description": str(product.get("description", "")),
            },
        }
        self.panels[panel_id] = panel
        try:
            self._save_panels()
            message = await channel.send(
                embed=self._sale_embed(product, image_url),
                view=PurchaseView(self, panel_id),
            )
        except (discord.Forbidden, discord.HTTPException, OSError) as exc:
            self.panels.pop(panel_id, None)
            try:
                self._save_panels()
            except OSError:
                pass
            return await interaction.followup.send(
                f"❌ I couldn't post the product panel: {exc}", ephemeral=True
            )

        await interaction.followup.send(
            f"✅ Product panel posted in {channel.mention}.\n"
            f"Panel ID: `{panel_id}` | Message ID: `{message.id}`",
            ephemeral=True,
        )

    # ── /sa_panels ───────────────────────────────────────────
    @app_commands.command(name="sa_panels", description="List active Buy Now product panels")
    @is_owner()
    async def sa_panels(self, interaction: discord.Interaction):
        if not self.panels:
            return await interaction.response.send_message(
                "No active product panels.", ephemeral=True
            )
        lines = [
            f"`{panel_id}` — {panel.get('product', {}).get('name', panel.get('product_id', '?'))}"
            f" — <#{panel.get('channel_id', '0')}>"
            for panel_id, panel in list(self.panels.items())[:25]
        ]
        await interaction.response.send_message(
            embed=sa_embed("🛒 Active Product Panels", "\n".join(lines)),
            ephemeral=True,
        )

    # ── /sa_deletepanel ─────────────────────────────────────
    @app_commands.command(name="sa_deletepanel", description="Disable a Buy Now product panel")
    @app_commands.describe(panel_id="Panel ID shown by /sa_panels")
    @is_owner()
    async def sa_deletepanel(self, interaction: discord.Interaction, panel_id: str):
        if panel_id not in self.panels:
            return await interaction.response.send_message(
                "❌ Panel not found.", ephemeral=True
            )
        self.panels.pop(panel_id)
        self._save_panels()
        await interaction.response.send_message(
            "✅ Panel disabled. Its existing button will no longer send payment instructions.",
            ephemeral=True,
        )

    @property
    def base(self):
        shop_id = getattr(self.bot, "SELLAUTH_SHOP_ID", "")
        return f"https://api.sellauth.com/v1/shops/{shop_id}"

    @property
    def headers(self):
        api_key = getattr(self.bot, "SELLAUTH_API_KEY", "")
        return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    def _configured(self):
        return bool(getattr(self.bot, "SELLAUTH_API_KEY", "")) and bool(getattr(self.bot, "SELLAUTH_SHOP_ID", ""))

    # ── /sa_products ──────────────────────────────────────────
    @app_commands.command(name="sa_products", description="List all products in your SellAuth shop")
    @is_owner()
    async def sa_products(self, interaction: discord.Interaction):
        if not self._configured():
            return await interaction.response.send_message("❌ SellAuth isn't configured. Set SELLAUTH_API_KEY / SELLAUTH_SHOP_ID.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        async with aiohttp.ClientSession() as s:
            r = await s.get(f"{self.base}/products", headers=self.headers)
            data = await r.json()
        if r.status != 200:
            return await interaction.followup.send(f"❌ API Error: {data}", ephemeral=True)
        products = data.get("data", data) if isinstance(data, dict) else data
        if not products:
            return await interaction.followup.send("No products found.", ephemeral=True)
        lines = [f"**{p.get('name', p.get('title','?'))}** — ID: `{p.get('id','?')}` | ${p.get('price','?')}" for p in products[:20]]
        e = sa_embed(f"🛒 Products ({len(products)})", "\n".join(lines))
        await interaction.followup.send(embed=e, ephemeral=True)

    # ── /sa_product ───────────────────────────────────────────
    @app_commands.command(name="sa_product", description="View details of a specific product")
    @app_commands.describe(product_id="Product ID from /sa_products")
    @is_owner()
    async def sa_product(self, interaction: discord.Interaction, product_id: str):
        await interaction.response.defer(ephemeral=True)
        async with aiohttp.ClientSession() as s:
            r = await s.get(f"{self.base}/products/{product_id}", headers=self.headers)
            p = await r.json()
        if r.status != 200:
            return await interaction.followup.send(f"❌ API Error: {p}", ephemeral=True)
        e = sa_embed(f"🛒 {p.get('name', p.get('title','Product'))}")
        e.add_field(name="ID", value=str(p.get("id", "?")), inline=True)
        e.add_field(name="Price", value=f"${p.get('price','?')}", inline=True)
        e.add_field(name="Stock", value=str(p.get("stock", "∞")), inline=True)
        e.add_field(name="Visible", value="✅" if p.get("visible") else "❌", inline=True)
        e.add_field(name="Description", value=str(p.get("description", "—"))[:500], inline=False)
        await interaction.followup.send(embed=e, ephemeral=True)

    # ── /sa_addproduct ────────────────────────────────────────
    @app_commands.command(name="sa_addproduct", description="Create a new product in your SellAuth shop")
    @app_commands.describe(title="Product name", price="Price (e.g. 9.99)", description="Product description", stock="Stock quantity (-1 for unlimited)")
    @is_owner()
    async def sa_addproduct(self, interaction: discord.Interaction, title: str, price: float, description: str = "", stock: int = -1):
        await interaction.response.defer(ephemeral=True)
        payload = {"name": title, "price": price, "description": description}
        if stock != -1:
            payload["stock"] = stock
        async with aiohttp.ClientSession() as s:
            r = await s.post(f"{self.base}/products", headers=self.headers, json=payload)
            data = await r.json()
        if r.status not in (200, 201):
            return await interaction.followup.send(f"❌ Failed: {data}", ephemeral=True)
        pid = data.get("id", "?")
        await interaction.followup.send(embed=sa_embed("✅ Product Created", f"**{title}** created!\nID: `{pid}` | Price: **${price}**"), ephemeral=True)

    # ── /sa_editproduct ───────────────────────────────────────
    @app_commands.command(name="sa_editproduct", description="Edit an existing product")
    @app_commands.describe(product_id="Product ID to edit", title="New title (leave blank to keep)", price="New price (leave 0 to keep)", description="New description")
    @is_owner()
    async def sa_editproduct(self, interaction: discord.Interaction, product_id: str, title: str = "", price: float = 0, description: str = ""):
        await interaction.response.defer(ephemeral=True)
        payload = {}
        if title:
            payload["name"] = title
        if price:
            payload["price"] = price
        if description:
            payload["description"] = description
        if not payload:
            return await interaction.followup.send("❌ Provide at least one field to edit.", ephemeral=True)
        async with aiohttp.ClientSession() as s:
            r = await s.put(f"{self.base}/products/{product_id}", headers=self.headers, json=payload)
            data = await r.json()
        if r.status != 200:
            return await interaction.followup.send(f"❌ Failed: {data}", ephemeral=True)
        await interaction.followup.send(embed=sa_embed("✅ Product Updated", f"Product `{product_id}` has been updated."), ephemeral=True)

    # ── /sa_deleteproduct ─────────────────────────────────────
    @app_commands.command(name="sa_deleteproduct", description="Delete a product from your shop")
    @app_commands.describe(product_id="Product ID to delete")
    @is_owner()
    async def sa_deleteproduct(self, interaction: discord.Interaction, product_id: str):
        await interaction.response.defer(ephemeral=True)
        async with aiohttp.ClientSession() as s:
            r = await s.delete(f"{self.base}/products/{product_id}", headers=self.headers)
        if r.status in (200, 204):
            await interaction.followup.send(embed=sa_embed("🗑️ Product Deleted", f"Product `{product_id}` deleted."), ephemeral=True)
        else:
            data = await r.json()
            await interaction.followup.send(f"❌ Failed: {data}", ephemeral=True)

    # ── /sa_orders ────────────────────────────────────────────
    @app_commands.command(name="sa_orders", description="List recent orders from your shop")
    @is_owner()
    async def sa_orders(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        async with aiohttp.ClientSession() as s:
            r = await s.get(f"{self.base}/orders", headers=self.headers)
            data = await r.json()
        if r.status != 200:
            return await interaction.followup.send(f"❌ API Error: {data}", ephemeral=True)
        orders = data.get("data", data) if isinstance(data, dict) else data
        if not orders:
            return await interaction.followup.send("No orders found.", ephemeral=True)
        lines = [f"**#{o.get('id','?')}** — {o.get('product_title','?')} | ${o.get('total','?')} | {o.get('status','?')}" for o in orders[:15]]
        e = sa_embed(f"📦 Recent Orders ({len(orders)})", "\n".join(lines))
        await interaction.followup.send(embed=e, ephemeral=True)

    # ── /sa_order ─────────────────────────────────────────────
    @app_commands.command(name="sa_order", description="View a specific order")
    @app_commands.describe(order_id="Order ID")
    @is_owner()
    async def sa_order(self, interaction: discord.Interaction, order_id: str):
        await interaction.response.defer(ephemeral=True)
        async with aiohttp.ClientSession() as s:
            r = await s.get(f"{self.base}/orders/{order_id}", headers=self.headers)
            o = await r.json()
        if r.status != 200:
            return await interaction.followup.send("❌ Not found.", ephemeral=True)
        e = sa_embed(f"📦 Order #{order_id}")
        e.add_field(name="Product", value=o.get("product_title", "?"), inline=True)
        e.add_field(name="Total", value=f"${o.get('total','?')}", inline=True)
        e.add_field(name="Status", value=o.get("status", "?"), inline=True)
        e.add_field(name="Email", value=o.get("email", "?"), inline=True)
        e.add_field(name="Date", value=str(o.get("created_at", "?"))[:10], inline=True)
        await interaction.followup.send(embed=e, ephemeral=True)

    # ── /sa_invoices ──────────────────────────────────────────
    @app_commands.command(name="sa_invoices", description="List recent invoices for your shop")
    @is_owner()
    async def sa_invoices(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        async with aiohttp.ClientSession() as s:
            r = await s.get(f"{self.base}/invoices", headers=self.headers)
            data = await r.json()
        if r.status != 200:
            return await interaction.followup.send(f"❌ API Error: {data}", ephemeral=True)
        invoices = data.get("data", data) if isinstance(data, dict) else data
        if not invoices:
            return await interaction.followup.send("No invoices found.", ephemeral=True)
        lines = [f"**#{i.get('id','?')}** — ${i.get('total', i.get('amount','?'))} | {i.get('status','?')}" for i in invoices[:15]]
        await interaction.followup.send(embed=sa_embed(f"🧾 Invoices ({len(invoices)})", "\n".join(lines)), ephemeral=True)

    # ── /sa_coupons ───────────────────────────────────────────
    @app_commands.command(name="sa_coupons", description="List all coupons")
    @is_owner()
    async def sa_coupons(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        async with aiohttp.ClientSession() as s:
            r = await s.get(f"{self.base}/coupons", headers=self.headers)
            data = await r.json()
        if r.status != 200:
            return await interaction.followup.send(f"❌ {data}", ephemeral=True)
        coupons = data.get("data", data) if isinstance(data, dict) else data
        if not coupons:
            return await interaction.followup.send("No coupons found.", ephemeral=True)
        lines = [f"`{c.get('code','?')}` — {c.get('discount','?')}% off | Uses: {c.get('uses',0)}" for c in coupons[:20]]
        await interaction.followup.send(embed=sa_embed(f"🏷️ Coupons ({len(coupons)})", "\n".join(lines)), ephemeral=True)

    # ── /sa_addcoupon ─────────────────────────────────────────
    @app_commands.command(name="sa_addcoupon", description="Create a discount coupon")
    @app_commands.describe(code="Coupon code", discount="Discount percentage (1-100)", max_uses="Max uses (0 = unlimited)")
    @is_owner()
    async def sa_addcoupon(self, interaction: discord.Interaction, code: str, discount: int, max_uses: int = None):
        await interaction.response.defer(ephemeral=True)
        payload = {"code": code, "discount": discount}
        if max_uses:
            payload["max_uses"] = max_uses
        async with aiohttp.ClientSession() as s:
            r = await s.post(f"{self.base}/coupons", headers=self.headers, json=payload)
            data = await r.json()
        if r.status not in (200, 201):
            return await interaction.followup.send(f"❌ {data}", ephemeral=True)
        await interaction.followup.send(embed=sa_embed("✅ Coupon Created", f"Code: `{code}` | {discount}% off"), ephemeral=True)

    # ── /sa_deletecoupon ──────────────────────────────────────
    @app_commands.command(name="sa_deletecoupon", description="Delete a coupon")
    @app_commands.describe(coupon_id="Coupon ID")
    @is_owner()
    async def sa_deletecoupon(self, interaction: discord.Interaction, coupon_id: str):
        await interaction.response.defer(ephemeral=True)
        async with aiohttp.ClientSession() as s:
            r = await s.delete(f"{self.base}/coupons/{coupon_id}", headers=self.headers)
        if r.status in (200, 204):
            await interaction.followup.send(embed=sa_embed("🗑️ Coupon Deleted", f"Coupon `{coupon_id}` deleted."), ephemeral=True)
        else:
            await interaction.followup.send("❌ Failed to delete coupon.", ephemeral=True)

    # ── /sa_blacklist ─────────────────────────────────────────
    @app_commands.command(name="sa_blacklist", description="List blacklist entries on your shop")
    @is_owner()
    async def sa_blacklist(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        async with aiohttp.ClientSession() as s:
            r = await s.get(f"{self.base}/blacklist", headers=self.headers)
            data = await r.json()
        if r.status != 200:
            return await interaction.followup.send(f"❌ {data}", ephemeral=True)
        entries = data.get("data", data) if isinstance(data, dict) else data
        if not entries:
            return await interaction.followup.send("No blacklist entries.", ephemeral=True)
        lines = [f"**#{b.get('id','?')}** — {b.get('type','?')}: `{b.get('value','?')}`" for b in entries[:20]]
        await interaction.followup.send(embed=sa_embed(f"🚫 Blacklist ({len(entries)})", "\n".join(lines)), ephemeral=True)

    # ── /sa_blacklistadd ──────────────────────────────────────
    @app_commands.command(name="sa_blacklistadd", description="Add an entry (email/ip/etc) to the SellAuth blacklist")
    @app_commands.describe(type="Blacklist type, e.g. email, ip, discord_id", value="The value to blacklist")
    @is_owner()
    async def sa_blacklistadd(self, interaction: discord.Interaction, type: str, value: str):
        await interaction.response.defer(ephemeral=True)
        payload = {"type": type, "match_type": "exact", "value": value}
        async with aiohttp.ClientSession() as s:
            r = await s.post(f"{self.base}/blacklist", headers=self.headers, json=payload)
            data = await r.json()
        if r.status not in (200, 201):
            return await interaction.followup.send(f"❌ {data}", ephemeral=True)
        await interaction.followup.send(embed=sa_embed("✅ Blacklist Entry Added", f"`{type}`: `{value}`"), ephemeral=True)

    # ── /sa_blacklistremove ───────────────────────────────────
    @app_commands.command(name="sa_blacklistremove", description="Remove a blacklist entry by its ID")
    @app_commands.describe(blacklist_id="Blacklist entry ID from /sa_blacklist")
    @is_owner()
    async def sa_blacklistremove(self, interaction: discord.Interaction, blacklist_id: str):
        await interaction.response.defer(ephemeral=True)
        async with aiohttp.ClientSession() as s:
            r = await s.delete(f"{self.base}/blacklist/{blacklist_id}", headers=self.headers)
        if r.status in (200, 204):
            await interaction.followup.send(embed=sa_embed("🗑️ Blacklist Entry Removed", f"Entry `{blacklist_id}` removed."), ephemeral=True)
        else:
            await interaction.followup.send("❌ Failed to remove entry.", ephemeral=True)

    # ── /sa_shopinfo ──────────────────────────────────────────
    @app_commands.command(name="sa_shopinfo", description="View your SellAuth shop details")
    @is_owner()
    async def sa_shopinfo(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        async with aiohttp.ClientSession() as s:
            r = await s.get(f"{self.base}", headers=self.headers)
            data = await r.json()
        if r.status != 200:
            return await interaction.followup.send(f"❌ {data}", ephemeral=True)
        e = sa_embed("🏪 Shop Info")
        for k, v in data.items():
            if isinstance(v, (str, int, float, bool)) and len(str(v)) < 100:
                e.add_field(name=k.replace("_", " ").title(), value=str(v), inline=True)
        await interaction.followup.send(embed=e, ephemeral=True)

    # ── /sa_revenue ───────────────────────────────────────────
    @app_commands.command(name="sa_revenue", description="Check shop revenue/stats")
    @is_owner()
    async def sa_revenue(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        async with aiohttp.ClientSession() as s:
            r = await s.get(f"{self.base}/analytics", headers=self.headers)
            data = await r.json()
        if r.status != 200:
            return await interaction.followup.send(f"❌ {data}", ephemeral=True)
        e = sa_embed("📈 Shop Revenue & Stats")
        for k, v in data.items():
            if isinstance(v, (str, int, float)):
                e.add_field(name=k.replace("_", " ").title(), value=str(v), inline=True)
        await interaction.followup.send(embed=e, ephemeral=True)

    # ── /sa_topproducts ───────────────────────────────────────
    @app_commands.command(name="sa_topproducts", description="View your top 5 products by revenue")
    @is_owner()
    async def sa_topproducts(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        async with aiohttp.ClientSession() as s:
            r = await s.get(f"{self.base}/analytics/top-products", headers=self.headers)
            data = await r.json()
        if r.status != 200:
            return await interaction.followup.send(f"❌ {data}", ephemeral=True)
        items = data if isinstance(data, list) else data.get("data", [])
        if not items:
            return await interaction.followup.send("No product revenue data yet.", ephemeral=True)
        lines = [f"**{p.get('product_name','?')}** — ${p.get('total_revenue_usd',0)} ({p.get('total_orders',0)} orders)" for p in items]
        await interaction.followup.send(embed=sa_embed("🏆 Top Products", "\n".join(lines)), ephemeral=True)

    async def cog_app_command_error(self, interaction, error):
        if isinstance(error, (app_commands.MissingPermissions, app_commands.CheckFailure)):
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return
        if not interaction.response.is_done():
            await interaction.response.send_message(f"❌ SellAuth error: {error}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(SellAuth(bot))
