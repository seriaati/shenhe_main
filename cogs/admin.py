import importlib
import sys
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from utility.utils import error_embed

if TYPE_CHECKING:
    from dev.model import BotModel


class AdminCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot: BotModel = bot
        self.debug: bool = self.bot.debug

    @commands.command(name="mark")
    async def mark(self, ctx: commands.Context) -> None:
        if not ctx.message.reference:
            return
        else:
            await ctx.send(
                "⚠️ 已將此訊息標記為危險訊息,將自動通報至 FBI", reference=ctx.message.reference
            )

    @commands.is_owner()
    @commands.command(name="cleanup")
    async def cleanup(self, ctx: commands.Context, amount: int) -> None:
        assert isinstance(ctx.channel, discord.TextChannel)
        await ctx.channel.purge(limit=amount + 1, check=lambda m: m.author == self.bot.user)

    @commands.is_owner()
    @commands.command(name="reload")
    async def reload(self, ctx: commands.Context):
        modules = list(sys.modules.values())
        for module in modules:
            if module is None:
                continue
            if module.__name__.startswith(("apps.", "data.", "dev.", "ui.", "utility.")):
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
    async def sync(self, ctx: commands.Context) -> None:
        await ctx.send("Syncing...")
        await self.bot.tree.sync()
        await ctx.send("Synced")

    @commands.is_owner()
    @commands.command(name="verify")
    async def verify(self, ctx: commands.Context, member: discord.Member, name: str) -> None:
        assert ctx.guild is not None
        role = discord.utils.get(ctx.guild.roles, name=f"verified {name}")
        if role is None:
            role = await ctx.guild.create_role(name=f"verified {name}")
        await member.add_roles(role)
        await ctx.send(f"{member.mention} is now a {role.mention}")

    @commands.is_owner()
    @commands.command(name="unverify")
    async def unverify(self, ctx: commands.Context, member: discord.Member, name: str) -> None:
        assert ctx.guild is not None
        role = discord.utils.get(ctx.guild.roles, name=f"verified {name}")
        if role is None:
            role = await ctx.guild.create_role(name=f"verified {name}")
        await member.remove_roles(role)
        await ctx.send(f"{member.mention} is no longer a {role.mention}")

        if len(role.members) == 0:
            await role.delete()

    @commands.is_owner()
    @commands.command(name="fake")
    async def fake(self, ctx: commands.Context, user_id: int, message: str) -> None:
        if ctx.guild is None:
            return
        member = ctx.guild.get_member(user_id)
        if member is None:
            await ctx.send("Member not found")
            return
        if not isinstance(ctx.channel, discord.TextChannel):
            return
        webhooks = await ctx.channel.webhooks()
        webhook = webhooks[0] if webhooks else await ctx.channel.create_webhook(name="Fake")
        await webhook.send(
            content=message, username=member.display_name, avatar_url=member.display_avatar.url
        )
        await ctx.message.delete()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AdminCog(bot))
