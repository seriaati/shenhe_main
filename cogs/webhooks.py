import io
import re
from typing import List

import discord
from discord.ext import commands

from dev.model import BotModel, DefaultEmbed


class WebhookCog(commands.Cog):
    def __init__(self, bot):
        self.bot: BotModel = bot

    # auto spoiler
    @commands.Cog.listener("on_message")
    async def auto_spoiler(self, message: discord.Message):
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
                content=message.content,
                files=files,
                username=message.author.display_name,
                avatar_url=message.author.display_avatar.url,
            )

    # use fxtwitter to send tweet
    @commands.Cog.listener("on_message")
    async def use_fxtwitter(self, message: discord.Message):
        if message.author.id == self.bot.user.id:
            return
        if message.guild and message.guild.id != self.bot.guild_id:
            return
        if not isinstance(message.channel, discord.TextChannel):
            return

        # check if message.content contains a URL using regex
        if not re.search(r"(https?://[^\s]+)", message.content):
            return
        if "twitter.com" not in message.content:
            return
        if "fxtwitter.com" in message.content:
            return

        webhooks = await message.channel.webhooks()
        if not webhooks:
            webhook = await message.channel.create_webhook(name="FxTwitter")
        else:
            webhook = webhooks[0]

        await message.delete()
        await webhook.send(
            content=message.content.replace("twitter.com", "fxtwitter.com"),
            username=message.author.display_name,
            avatar_url=message.author.display_avatar.url,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WebhookCog(bot))
