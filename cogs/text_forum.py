import discord
from discord.ext import commands

from utility.utils import contains_url

CHANNEL_ID = 1061899087525458031


class TextForum(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener("on_message")
    async def auto_create_forum(self, message: discord.Message) -> None:
        if message.channel.id != CHANNEL_ID:
            return
        if not contains_url(message.content):
            return

        keywords = ("youtube",)
        if not any((keyword in message.content.lower() for keyword in keywords)):
            return

        await message.create_thread(
            name="影片討論", auto_archive_duration=1440, reason="auto thread create"
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TextForum(bot))
