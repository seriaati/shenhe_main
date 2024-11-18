import asyncio
import io
import re
from typing import TYPE_CHECKING

import discord
from discord.ext import commands
from loguru import logger
from seria.utils import clean_url, extract_media_urls, split_list_to_chunks

if TYPE_CHECKING:
    from dev.model import BotModel

KEMONO_REGEX = r"https:\/\/kemono\.su\/(fanbox|[a-zA-Z]+)\/user\/\d+\/post\/\d+"


class WebhookCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot: BotModel = bot

    @staticmethod
    def _match_kemono(message: discord.Message) -> re.Match[str] | None:
        return re.search(KEMONO_REGEX, message.content)

    async def _download_image(
        self, image_url: str, files: list[discord.File], filename: str
    ) -> None:
        async with self.bot.session.get(image_url) as resp:
            if resp.status != 200:
                logger.error("Failed to download %s, status: %s", image_url, resp.status)
                return

            file_ = discord.File(io.BytesIO(await resp.read()), spoiler=True, filename=filename)
        files.append(file_)

    @commands.Cog.listener("on_message")
    async def auto_spoiler(self, message: discord.Message) -> None:
        """
        Automatically spoiler media urls and uploaded images and videos.
        Only works in 色即是空.
        """
        if message.author.bot and "(Embed Fixer)" not in message.author.name:
            return

        if (
            isinstance(message.channel, discord.TextChannel)
            and message.channel.id == 1061898394446069852  # 色即是空
        ):
            media_urls = extract_media_urls(message.content, clean=False)
            if (
                media_urls
                or any(not a.is_spoiler() for a in message.attachments)
                or self._match_kemono(message)
            ):
                files: list[discord.File] = []

                # auto spoiler media urls
                if media_urls:
                    async with asyncio.TaskGroup() as tg:
                        for url in media_urls:
                            filename = clean_url(url).split("/")[-1]
                            tg.create_task(self._download_image(url, files, filename))
                            message.content = message.content.replace(url, "")

                # auto spoiler attachments
                files.extend(
                    [await attachment.to_file(spoiler=True) for attachment in message.attachments]
                )

                # send the files in chunks of 10
                split_files = split_list_to_chunks(files, 10)
                for split_file in split_files:
                    webhooks = await message.channel.webhooks()
                    webhook = discord.utils.get(webhooks, name="Auto Spoiler")
                    if webhook is None:
                        webhook = await message.channel.create_webhook(name="Auto Spoiler")

                    await webhook.send(
                        content=message.content,
                        username=message.author.display_name.replace(" (Embed Fixer)", ""),
                        avatar_url=message.author.display_avatar.url,
                        files=split_file,
                        suppress_embeds=True,
                    )

                await message.delete()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WebhookCog(bot))
