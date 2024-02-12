import contextlib
import io
from typing import List

import discord
from discord.ext import commands

from dev.model import BotModel
from utility.utils import divide_chunks, extract_media_urls


class WebhookCog(commands.Cog):
    def __init__(self, bot):
        self.bot: BotModel = bot

    # auto add reactions
    @commands.Cog.listener("on_message")
    async def auto_add_reactions(self, message: discord.Message):
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
    async def add_reactions_to_message(message: discord.Message):
        with contextlib.suppress(discord.HTTPException):
            await message.add_reaction("👍")
            await message.add_reaction("🤔")
            await message.add_reaction("<a:ganyuLick:1154951202073739364>")
            await message.add_reaction("<:hasuhasu:1067657689846534275>")
            await message.add_reaction("<:poinkoHmm:1175282036286705674>")

    @commands.Cog.listener("on_message")
    async def auto_spoiler(self, message: discord.Message):
        """
        Automatically spoiler pixiv, twitter, and x images, uploaded images, and videos.
        Only works in 色即是空.
        """
        if (
            message.author.bot
            or not isinstance(message.channel, discord.TextChannel)
            or message.guild is None
            or message.guild.id != self.bot.guild_id
            or message.channel.id != 1061898394446069852  # 色即是空
        ):
            return

        media_urls = extract_media_urls(message.content)
        if media_urls or message.attachments:
            await message.delete()

        files: List[discord.File] = []

        # auto spoiler media urls
        for url in media_urls:
            async with self.bot.session.get(url) as resp:
                if resp.status != 200:
                    continue

                message.content = message.content.replace(url, "")
                files.append(
                    discord.File(
                        io.BytesIO(await resp.read()),
                        filename=url.split("/")[-1].split("?")[0],
                    )
                )

        # auto spoiler attachments
        files.extend(
            [
                await attachment.to_file(spoiler=not attachment.is_spoiler())
                for attachment in message.attachments
            ]
        )

        # send the files in chunks of 10
        split_files: List[List[discord.File]] = list(divide_chunks(files, 10))
        for split_file in split_files:
            webhooks = await message.channel.webhooks()
            webhook = discord.utils.get(webhooks, name="Auto Spoiler")
            if webhook is None:
                webhook = await message.channel.create_webhook(name="Auto Spoiler")

            await webhook.send(
                content=message.content,
                username=message.author.display_name,
                avatar_url=message.author.display_avatar.url,
                files=split_file,
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WebhookCog(bot))
