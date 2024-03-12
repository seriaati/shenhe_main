import asyncio
import contextlib
import io
import re
from typing import List

import discord
from discord.ext import commands
from seria.utils import extract_media_urls, split_list_to_chunks

from dev.model import BotModel

KEMONO_REGEX = r"https:\/\/kemono\.su\/(fanbox|[a-zA-Z]+)\/user\/\d+\/post\/\d+"


class WebhookCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot: BotModel = bot

    def _match_kemono(self, message: discord.Message) -> re.Match[str] | None:
        return re.search(KEMONO_REGEX, message.content)

    async def _download_image_task(
        self, image_url: str, files: list[discord.File]
    ) -> None:
        async with self.bot.session.get(image_url) as resp:
            if resp.status != 200:
                return
            file_ = discord.File(io.BytesIO(await resp.read()), spoiler=True)
        files.append(file_)

    async def _fetch_kemono_images(self, kemono_url: str) -> list[discord.File]:
        api_url = "https://kemono.su/api/v1/"
        request_url = kemono_url.replace("https://kemono.su/", api_url)
        async with self.bot.session.get(request_url) as resp:
            data = await resp.json()

        attachments: list[dict[str, str]] = data.get("attachments", [])
        files: list[discord.File] = []
        tasks: list[asyncio.Task] = []
        for attachment in attachments:
            url = (
                f"https://c4.kemono.su/data/{attachment['path']}?f={attachment['name']}"
            )
            tasks.append(asyncio.create_task(self._download_image_task(url, files)))

        await asyncio.gather(*tasks, return_exceptions=True)
        return files

    # auto add reactions
    @commands.Cog.listener("on_message")
    async def auto_add_reactions(self, message: discord.Message) -> None:
        """
        Automatically add reactions to messages with medias.
        Only works in 美圖展版 and 色即是空.
        """
        if (
            message.guild is None
            or message.guild.id != self.bot.guild_id
            or message.channel.id not in {1061881404167815249, 1061898394446069852}
        ):
            return

        # check for attachments
        content = message.content
        if message.attachments or extract_media_urls(content):
            await self.add_reactions_to_message(message)

    @staticmethod
    async def add_reactions_to_message(message: discord.Message) -> None:
        with contextlib.suppress(discord.HTTPException):
            await message.add_reaction("👍")
            await message.add_reaction("🤔")
            await message.add_reaction("<a:ganyuLick:1154951202073739364>")
            await message.add_reaction("<:hasuhasu:1067657689846534275>")
            await message.add_reaction("<:poinkoHmm:1175282036286705674>")

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
            and message.guild is not None
            and message.guild.id == self.bot.guild_id
            and message.channel.id == 1061898394446069852  # 色即是空
        ):
            media_urls = extract_media_urls(message.content, clean=False)
            if media_urls or any(
                not attachment.is_spoiler() for attachment in message.attachments
            ):
                await message.delete()

                files: List[discord.File] = []
                tasks: List[asyncio.Task] = []

                # auto spoiler media urls
                for url in media_urls:
                    tasks.append(
                        asyncio.create_task(self._download_image_task(url, files))
                    )
                    message.content = message.content.replace(url, "")

                # extract keomo images
                kemono_match = self._match_kemono(message)
                if kemono_match:
                    files.extend(await self._fetch_kemono_images(kemono_match.group()))

                # auto spoiler attachments
                files.extend(
                    [
                        await attachment.to_file(spoiler=True)
                        for attachment in message.attachments
                    ]
                )

                await asyncio.gather(*tasks, return_exceptions=True)

                # send the files in chunks of 10
                split_files = split_list_to_chunks(files, 10)
                for split_file in split_files:
                    webhooks = await message.channel.webhooks()
                    webhook = discord.utils.get(webhooks, name="Auto Spoiler")
                    if webhook is None:
                        webhook = await message.channel.create_webhook(
                            name="Auto Spoiler"
                        )

                    await webhook.send(
                        content=message.content,
                        username=message.author.display_name.replace(
                            " (Embed Fixer)", ""
                        ),
                        avatar_url=message.author.display_avatar.url,
                        files=split_file,
                    )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WebhookCog(bot))
