"""
Products cog

Provides a `/postproduct` slash command that posts a product embed with a
"Buy Now" button. When a user clicks the button, they receive the payment
instructions via DM. Any message the user sends back in that DM (e.g. payment
proof) is forwarded to the bot owner, whose Discord ID is read from the
OWNER_ID environment variable.
"""
import discord
from discord import app_commands
from discord.ext import commands
import datetime
import os


def get_owner_id() -> int:
    """Read OWNER_ID from the environment and convert it to an int."""
    owner_id = os.getenv("OWNER_ID")
    if not owner_id:
        return 0
    try:
        return int(owner_id)
    except (TypeError, ValueError):
        return 0


def is_owner():
    async def predicate(interaction: discord.Interaction) -> bool:
        owner_id = get_owner_id()
        if not owner_id:
            return False
        return interaction.user.id == owner_id
    return app_commands.check(predicate)


class BuyNowView(discord.ui.View):
    """View attached to a product embed with a single 'Buy Now' button."""

    def __init__(self, cog: "Products", product_name: str, product_description: str,
                 price: float, payment_instructions: str, proof_channel_id: int | None = None):
        super().__init__(timeout=None)
        self.cog = cog
        self.product_name = product_name
        self.product_description = product_description
        self.price = price
        self.payment_instructions = payment_instructions
        self.proof_channel_id = proof_channel_id

    @discord.ui.button(label="Buy Now", style=discord.ButtonStyle.success, emoji="💳", custom_id="products:buy_now")
    async def buy_now(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.handle_buy_now(
            interaction,
            self.product_name,
            self.product_description,
            self.price,
            self.payment_instructions,
            self.proof_channel_id,
        )


class Products(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Tracks users who have received payment instructions and are expected
        # to send payment proof back in DMs, along with the selected product.
        self.awaiting_proof: dict[int, dict] = {}

    @property
    def owner_id(self) -> int:
        return get_owner_id()

    def _product_embed(self, product_name: str, product_description: str, price: float,
                        image: discord.Attachment | None = None) -> discord.Embed:
        embed = discord.Embed(
            title=f"🛍️ {product_name}",
            description=product_description,
            color=discord.Color.blurple(),
            timestamp=datetime.datetime.utcnow(),
        )
        embed.add_field(name="Price", value=f"${price:,.2f}", inline=True)
        if image is not None:
            embed.set_image(url=image.url)
        embed.set_footer(text="Click Buy Now to receive payment instructions in your DMs")
        return embed

    def _payment_embed(self, product_name: str, price: float, payment_instructions: str) -> discord.Embed:
        embed = discord.Embed(
            title=f"💰 Purchase: {product_name}",
            description=(
                f"**Price:** ${price:,.2f}\n\n"
                f"{payment_instructions}\n\n"
                "Once payment is complete, reply to this DM with your payment proof "
                "(screenshot, transaction ID, receipt, etc.)."
            ),
            color=discord.Color.gold(),
            timestamp=datetime.datetime.utcnow(),
        )
        embed.set_footer(text="Please keep this DM open while your order is processed")
        return embed

    async def handle_buy_now(self, interaction: discord.Interaction, product_name: str,
                              product_description: str, price: float,
                              payment_instructions: str, proof_channel_id: int | None = None):
        await interaction.response.defer(ephemeral=True)
        try:
            await interaction.user.send(
                embed=self._payment_embed(product_name, price, payment_instructions)
            )
        except discord.Forbidden:
            return await interaction.followup.send(
                "❌ I couldn't DM you. Please enable DMs from server members and click **Buy Now** again.",
                ephemeral=True,
            )
        except discord.HTTPException:
            return await interaction.followup.send(
                "❌ Discord couldn't deliver the payment instructions. Please try again in a moment.",
                ephemeral=True,
            )

        self.awaiting_proof[interaction.user.id] = {
            "product_name": product_name,
            "product_description": product_description,
            "price": price,
            "proof_channel_id": proof_channel_id,
        }
        await interaction.followup.send("✅ Check your DMs for payment instructions!", ephemeral=True)

    @app_commands.command(name="postproduct", description="Post a product with a Buy Now button")
    @app_commands.describe(
        product_name="The name of the product",
        product_description="Description of the product",
        price="The price of the product",
        payment_instructions="Instructions to send to users (payment method, address, account details, etc.)",
        image="An optional image to display on the product post",
        proof_channel="Optional server channel where payment proofs should be posted",
    )
    @is_owner()
    async def postproduct(
        self,
        interaction: discord.Interaction,
        product_name: str,
        product_description: str,
        price: float,
        payment_instructions: str,
        image: discord.Attachment | None = None,
        proof_channel: discord.TextChannel | None = None,
    ):
        if image is not None:
            content_type = image.content_type or ""
            if not content_type.startswith("image/"):
                return await interaction.response.send_message(
                    "❌ The attachment you provided isn't an image. Please attach an image file.",
                    ephemeral=True,
                )

        embed = self._product_embed(product_name, product_description, price, image)
        view = BuyNowView(
            self,
            product_name,
            product_description,
            price,
            payment_instructions,
            proof_channel.id if proof_channel else None,
        )
        await interaction.response.send_message(embed=embed, view=view)

    @postproduct.error
    async def postproduct_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message(
                "❌ Only the bot owner can use this command.", ephemeral=True
            )
        else:
            raise error

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Only handle DMs, ignore the bot's own messages.
        if message.author.bot:
            return
        if not isinstance(message.channel, discord.DMChannel):
            return

        owner_id = self.owner_id
        if not owner_id:
            return

        # Don't forward the owner's own DMs to itself.
        if message.author.id == owner_id:
            return

        # Only forward messages from users who clicked Buy Now and are
        # expected to send payment proof.
        purchase = self.awaiting_proof.get(message.author.id)
        if not purchase:
            return

        owner = self.bot.get_user(owner_id) or await self.bot.fetch_user(owner_id)
        if owner is None:
            return

        submitted_code = message.content.strip() or "(no text content)"
        embed = discord.Embed(
            title="💰 New Payment Submission",
            description="A buyer replied to the payment instructions.",
            color=discord.Color.gold(),
            timestamp=datetime.datetime.utcnow(),
        )
        embed.set_author(
            name=f"{message.author} ({message.author.id})",
            icon_url=message.author.display_avatar.url if message.author.display_avatar else None,
        )
        embed.add_field(
            name="Buyer",
            value=f"{message.author} (`{message.author.id}`)",
            inline=False,
        )
        embed.add_field(
            name="Item",
            value=purchase["product_name"][:1024],
            inline=False,
        )
        embed.add_field(
            name="Price",
            value=f"${purchase['price']:,.2f}",
            inline=False,
        )
        embed.add_field(
            name="Code Submitted",
            value=f"`{submitted_code[:1018]}`",
            inline=False,
        )
        if purchase.get("product_description"):
            embed.add_field(
                name="Product details",
                value=purchase["product_description"][:1024],
                inline=False,
            )

        files = []
        for attachment in message.attachments:
            try:
                files.append(await attachment.to_file())
            except (discord.HTTPException, discord.NotFound):
                continue

        delivered = False
        proof_channel_id = purchase.get("proof_channel_id")
        if proof_channel_id:
            try:
                proof_channel = self.bot.get_channel(int(proof_channel_id))
                if proof_channel is not None:
                    await proof_channel.send(embed=embed, files=files if files else None)
                    delivered = True
            except (ValueError, discord.Forbidden, discord.HTTPException):
                pass

        try:
            await owner.send(embed=embed)
            delivered = True
        except discord.HTTPException:
            pass

        if not delivered:
            try:
                await message.channel.send(
                    "⚠️ I couldn't notify the seller right now. Please try again in a moment."
                )
            except discord.HTTPException:
                pass
            return

        # Consume the purchase context only after the seller was notified.
        self.awaiting_proof.pop(message.author.id, None)

        try:
            await message.channel.send(
                "✅ Got it! Your code has been submitted to our team — we'll confirm shortly."
            )
        except discord.HTTPException:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(Products(bot))
