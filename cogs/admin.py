import importlib
import sys

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
                ("apps.", "data.", "dev.", "ui.", "utility.")
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
    
    @commands.is_owner()
    @commands.command(name="verify")
    async def verify(self, ctx: commands.Context, member: discord.Member):
        role = ctx.guild.get_role(1108765559849500813)
        await member.add_roles(role)
        await ctx.send(f"{member.mention} is now a {role.mention}")
    
    @commands.is_owner()
    @commands.command(name="unverify")
    async def unverify(self, ctx: commands.Context, member: discord.Member):
        role = ctx.guild.get_role(1108765559849500813)
        await member.remove_roles(role)
        await ctx.send(f"{member.mention} is no longer a {role.mention}")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AdminCog(bot))
