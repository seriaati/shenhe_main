import importlib
import io
import sys
from typing import List

import discord
from discord.ext import commands

from dev.model import BotModel
from utility.utils import error_embed


class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot: BotModel = bot
        self.debug: bool = self.bot.debug

    @commands.command(name="mark")
    async def mark(self, ctx: commands.Context):
        if not ctx.message.reference:
            return
        else:
            await ctx.send(
                "⚠️ 已將此訊息標記為危險訊息，將自動通報至 FBI", reference=ctx.message.reference
            )

    @commands.is_owner()
    @commands.command(name="cleanup")
    async def cleanup(self, ctx: commands.Context, amount: int):
        assert isinstance(ctx.channel, discord.TextChannel)
        await ctx.channel.purge(
            limit=amount + 1, check=lambda m: m.author == self.bot.user
        )

    @commands.is_owner()
    @commands.command(name="reload")
    async def reload(self, ctx: commands.Context):
        modules = list(sys.modules.values())
        for module in modules:
            if module is None:
                continue
            if module.__name__.startswith(
                ("apps.", "cogs.", "data.", "dev.", "ui.", "utility.")
            ):
                try:
                    importlib.reload(module)
                except Exception as e:
                    return await ctx.send(
                        embed=error_embed(module.__name__, f"```{e}```"),
                        ephemeral=True,
                    )
        await ctx.send("Reloaded")

    @commands.is_owner()
    @commands.command(name="sync")
    async def sync(self, ctx: commands.Context):
        await ctx.send("Syncing...")
        await self.bot.tree.sync()
        await ctx.send("Synced")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.id == self.bot.user.id:
            return
        if message.guild and message.guild.id != self.bot.guild_id:
            return

        if message.channel.id == 1061898394446069852 and any(
            not a.is_spoiler() for a in message.attachments
        ):
            assert isinstance(message.channel, discord.TextChannel)

            files: List[discord.File] = []
            await message.delete()

            for attachment in message.attachments:
                if not attachment.is_spoiler():
                    async with self.bot.session.get(attachment.proxy_url) as resp:
                        bytes_obj = io.BytesIO(await resp.read())
                        file_ = discord.File(
                            bytes_obj, filename=attachment.filename, spoiler=True
                        )
                        files.append(file_)
                else:
                    files.append(await attachment.to_file())

            webhooks = await message.channel.webhooks()
            if not webhooks:
                webhook = await message.channel.create_webhook(name="Auto-Spoiler")
            else:
                webhook = webhooks[0]

            await webhook.send(
                files=files,
                username=message.author.display_name,
                avatar_url=message.author.display_avatar.url,
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AdminCog(bot))
