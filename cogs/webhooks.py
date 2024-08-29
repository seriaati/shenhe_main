import asyncio
import contextlib
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

    def _match_kemono(self, message: discord.Message) -> re.Match[str] | None:
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

    async def _download_kemono_images(self, kemono_url: str) -> list[discord.File]:
        api_url = "https://kemono.su/api/v1/"
        request_url = kemono_url.replace("https://kemono.su/", api_url)
        async with self.bot.session.get(request_url) as resp:
            data = await resp.json()

        attachments: list[dict[str, str]] = data.get("attachments", [])
        files: list[discord.File] = []
        async with asyncio.TaskGroup() as tg:
            for attachment in attachments:
                url = f"https://img.kemono.su/thumbnail/data/{attachment['path']}"
                tg.create_task(self._download_image(url, files, attachment["name"]))

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
            await asyncio.sleep(1.0)
            await self.add_reactions_to_message(message)

    @staticmethod
    async def add_reactions_to_message(message: discord.Message) -> None:
        assert message.guild is not None
        embed_fixer = message.guild.get_member(770144963735453696)
        with contextlib.suppress(discord.HTTPException):
            await message.add_reaction("👍")
            await message.add_reaction("🤔")
            await message.add_reaction("<a:ganyuLick:1154951202073739364>")
            await message.add_reaction("<:hasuhasu:1067657689846534275>")
            await message.add_reaction("<:noseBleed:1226758169846616064>")
            if embed_fixer is not None:
                await message.remove_reaction("<:delete_message:1278557435090698345>", embed_fixer)

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

                # extract keomo images
                kemono_match = self._match_kemono(message)
                if kemono_match:
                    files.extend(await self._download_kemono_images(kemono_match.group()))

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
