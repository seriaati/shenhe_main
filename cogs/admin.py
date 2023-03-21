import importlib
import io
import sys
from typing import List
import re

import discord
from discord.ext import commands

from utility.utils import error_embed


def detect_url(message: str) -> List[str]:
    regex = re.compile(
        r"((http|ftp|https):\/\/)?(www\.)?([a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,3})(\/\S*)?"
    )
    url = re.findall(regex, message)
    return [x[0] for x in url]


class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot: commands.Bot = bot
        self.debug: bool = self.bot.debug_toggle

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
            if module.__name__.startswith(("cogs.", "utility.", "apps.", "data.")):
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
        if message.guild.id != self.bot.guild_id:
            return

        urls = detect_url(message.content)
        if message.channel.id and urls:
            await message.delete()
            content = ""
            for url in urls:
                content += f"||{url}||\n"
            await message.channel.send(
                content=f"由 {message.author.mention} 寄出\n" + content
            )

        if message.channel.id == 1061898394446069852 and any(
            not a.is_spoiler() for a in message.attachments
        ):
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

            await message.channel.send(
                content=f"由 <@{message.author.id}> 寄出", files=files
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AdminCog(bot))
