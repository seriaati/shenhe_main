import io
from typing import Dict, List, Optional

import aiohttp
import discord
from discord.ext import commands
from pydantic import BaseModel

from cogs.image_manager import post_url_to_image_url
from dev.model import BaseView, BotModel
from utility.utils import divide_chunks, find_urls


class Author(BaseModel):
    id: str
    name: str


class Artwork(BaseModel):
    urls: List[str]
    title: str
    description: str
    tags: List[str]
    author: Author


async def fetch_artwork_info(id: str) -> Artwork:
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://www.phixiv.net/api/info?id={id}") as resp:
            return Artwork(**await resp.json())


class DeleteMessage(BaseView):
    def __init__(self):
        super().__init__(timeout=600.0)

    @discord.ui.button(label="刪除", style=discord.ButtonStyle.red)
    async def delete_message(self, i: discord.Interaction, _: discord.ui.Button):
        await i.response.defer()
        if i.message:
            await i.message.delete()


class WebhookCog(commands.Cog):
    def __init__(self, bot):
        self.bot: BotModel = bot

    # auto spoiler
    @commands.Cog.listener("on_message")
    async def auto_spoiler(self, message: discord.Message):
        if (
            message.author.bot
            or not isinstance(message.channel, discord.TextChannel)
            or message.guild is None
            or message.guild.id != self.bot.guild_id
            or message.channel.id != 1061898394446069852
        ):
            return

        files: List[discord.File] = []

        urls = find_urls(message.content)
        if urls:
            websites = ("twitter", "fxtwitter", "phixiv", "pixiv")
            file_extensions = ("png", "jpg", "jpeg", "gif", "webp", "mp4")
            if any(website in message.content for website in websites) or any(
                ext in message.content for ext in file_extensions
            ):
                await message.delete()
                for url in urls:
                    filename = url.split("/")[-1].split("?")[0]
                    image_url = post_url_to_image_url(url)
                    message.content = message.content.replace(url, f"<{url}>")

                    if "phixiv" in image_url:
                        artwork = await fetch_artwork_info(filename)
                        urls_ = artwork.urls
                    else:
                        urls_ = [image_url]

                    for index, u in enumerate(urls_):
                        file_ = await self.download_image(u, f"{filename}_{index}")
                        if file_ is None:
                            await self.fake_user_send(
                                message.channel,
                                message.author,
                                message.content,
                            )
                        else:
                            files.append(file_)

        if any(not a.is_spoiler() for a in message.attachments):
            url_dict: Dict[str, str] = {}
            for a in message.attachments:
                if not a.is_spoiler():
                    url_dict[a.filename] = a.url
                else:
                    files.append(await a.to_file())

            await message.delete()
            images = [
                await self.download_image(url, filename)
                for filename, url in url_dict.items()
            ]
            files.extend([i for i in images if i is not None])

        split_files: List[List[discord.File]] = list(divide_chunks(files, 10))
        for split in split_files:
            ref_message = message.reference.resolved if message.reference else None
            if isinstance(ref_message, discord.Message):
                message.content = f"⬅️ 回應 {ref_message.author.mention} 的訊息 ({ref_message.jump_url})\n\n{message.content}"

            await self.fake_user_send(
                message.channel,
                message.author,
                message.content,
                files=split,
            )

    async def download_image(self, url: str, file_name: str) -> Optional[discord.File]:
        allowed_content_types = ("image", "video", "application/octet-stream")
        async with self.bot.session.get(url) as resp:
            if not any(
                (content_type in resp.content_type)
                for content_type in allowed_content_types
            ):
                return None
            bytes_obj = io.BytesIO(await resp.read())
            if resp.content_type == "application/octet-stream":
                file_name += ".png"
            else:
                file_name += f".{resp.content_type.split('/')[-1]}"
            file_ = discord.File(bytes_obj, filename=file_name, spoiler=True)

        return file_

    async def fake_user_send(
        self,
        channel: discord.TextChannel,
        user: discord.User | discord.Member,
        message: str,
        **kwargs,
    ) -> None:
        webhooks = await channel.webhooks()
        if not webhooks:
            webhook = await channel.create_webhook(name="Fake User")
        else:
            webhook = webhooks[0]

        view = DeleteMessage()
        view.author = user
        view.message = await webhook.send(
            content=message,
            username=user.display_name,
            avatar_url=user.display_avatar.url,
            view=view,
            **kwargs,
        )

    # use fxtwitter and phixiv
    @commands.Cog.listener("on_message")
    async def fix_embed(self, message: discord.Message):
        if (
            message.author.bot
            or message.guild is None
            or message.guild.id != self.bot.guild_id
            or not isinstance(message.channel, discord.TextChannel)
            or message.channel.id == 1061898394446069852
        ):
            return

        urls = find_urls(message.content)
        for url in urls:
            if any((website in message.content for website in ("pixiv", "phixiv"))):
                try:
                    await message.delete()
                except discord.NotFound:
                    pass
                artwork_id = url.split("/")[-1].split("?")[0]
                artwork = await fetch_artwork_info(artwork_id)
                if "R-18" in artwork.tags:
                    await message.channel.send(
                        content=f"{message.author.mention} 這張圖片包含 R-18 標籤，請在 <#1061898394446069852> 分享！",
                        delete_after=10,
                    )
                else:
                    for index in range(1, len(artwork.urls) + 1):
                        await self.fake_user_send(
                            message.channel,
                            message.author,
                            message.content.replace(
                                url,
                                url.replace(
                                    artwork_id, f"{artwork_id}/{index}"
                                ).replace("pixiv", "phixiv"),
                            ),
                        )

            if "twitter" in message.content and "fxtwitter" not in message.content:
                try:
                    await message.delete()
                except discord.NotFound:
                    pass

                await self.fake_user_send(
                    message.channel,
                    message.author,
                    message.content.replace("twitter", "fxtwitter"),
                )

    # webhook reply
    @commands.Cog.listener("on_message")
    async def on_webhook(self, message: discord.Message) -> None:
        ref = message.reference.resolved if message.reference else None
        if not isinstance(ref, discord.Message) or message.guild is None:
            return
        if not ref.webhook_id:
            return

        author_name = ref.author.display_name
        author = message.guild.get_member_named(author_name)
        if author:
            await message.reply(
                content=f"⬅️ 回應 {author.mention} 的訊息 ({ref.jump_url})",
                mention_author=False,
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WebhookCog(bot))
