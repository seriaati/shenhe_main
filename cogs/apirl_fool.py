import discord
from discord.ext import commands


class AprilFoolCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.is_owner()
    @commands.command(name="test-fool")
    async def test_fool(self, ctx: commands.Context, content: str) -> None:
        await ctx.message.delete()
        webhook = (await ctx.guild.webhooks())[0]
        await webhook.send(
            content=content,
            username=ctx.author.display_name,
            avatar_url=ctx.author.display_avatar.url,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AprilFoolCog(bot))
