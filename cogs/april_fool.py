import discord
from discord.ext import commands


class AprilFoolCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command(name="fool")
    async def test_fool(self, ctx: commands.Context, content: str) -> None:
        await ctx.message.delete()
        webhook = await ctx.channel.webhooks()
        if not webhook:
            webhook = await ctx.channel.create_webhook(name="April Fool")
        else:
            webhook = webhook[0]
        await webhook.send(
            content=content,
            username=ctx.author.display_name,
            avatar_url=ctx.author.display_avatar.url,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AprilFoolCog(bot))
