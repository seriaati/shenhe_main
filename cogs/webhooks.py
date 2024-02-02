import contextlib
import io
from typing import Dict, List, Optional

import aiohttp
import discord
from discord.ext import commands
from pydantic import BaseModel

from dev.model import BaseView, BotModel
from utility.utils import divide_chunks, find_urls, has_media_url


class Artwork(BaseModel):
    ai_generated: bool
    author_id: str
    author_name: str
    description: str
    image_proxy_urls: List[str]
    tags: List[str]
    title: str
    url: str


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

    # auto add reactions
    @commands.Cog.listener("on_message")
    async def auto_add_reactions(self, message: discord.Message):
        """
        Automatically add reactions to messages with medias.
        Works in all channels.
        """
        if message.guild is None or message.guild.id != self.bot.guild_id:
            return

        # check for attachments
        content = message.content
        if (
            message.attachments
            or has_media_url(content)
            or "d.fxtwitter.com" in content
        ):
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

        files: List[discord.File] = []
        media_urls: List[str] = []

        # auto spoiler url images or videos
        urls = find_urls(message.content)
        for url in urls:
            message.content = message.content.replace(url, f"<{url}>")
            filename = url.split("/")[-1].split("?")[0]

            # extracts image from pixiv, twitter, and x
            if "pixiv.net" in url or "phixiv.net" in url:
                artwork = await fetch_artwork_info(filename)
                media_urls.extend(artwork.image_proxy_urls)
            elif "twitter.com" in url:
                if "fxtwitter.com" in url or "vxtwitter.com" in url:
                    url = url.replace("fxtwitter.com", "d.fxtwitter.com").replace(
                        "vxtwitter.com", "d.fxtwitter.com"
                    )
                else:
                    url = url.replace("twitter.com", "d.fxtwitter.com")
                media_urls.append(url)
            elif "x.com" in url:
                if "fixupx.com" in url:
                    url = url.replace("fixupx.com", "d.fixupx.com")
                else:
                    url = url.replace("x.com", "d.fixupx.com")
                media_urls.append(url)

            # normal media url
            elif has_media_url(url):
                media_urls.append(url)

            for index, u in enumerate(media_urls):
                file_ = await self.download_media(u, f"{filename}_{index}")
                if file_ is None:
                    # download failed, send the message as is
                    await self.fake_user_send(
                        message.channel,
                        message.author,
                        message.content,
                        message.reference,
                    )
                else:
                    files.append(file_)

        # auto spoiler attachments
        url_dict: Dict[str, str] = {a.filename: a.url for a in message.attachments}
        images = [
            await self.download_media(url, filename)
            for filename, url in url_dict.items()
        ]
        files.extend([i for i in images if i is not None])

        if files:
            await self.delete_message(message)
        split_files: List[List[discord.File]] = list(divide_chunks(files, 10))

        # send the files in chunks of 10
        for split in split_files:
            await self.fake_user_send(
                message.channel,
                message.author,
                message.content,
                message.reference,
                files=split,
            )

    @commands.Cog.listener("on_message")
    async def art_extractor(self, message: discord.Message) -> None:
        """
        Extract image URLs from pixiv, twitter, and x.
        Only works in 美圖展版.
        """
        if (
            message.author.bot
            or message.guild is None
            or message.guild.id != self.bot.guild_id
            or not isinstance(message.channel, discord.TextChannel)
            or message.channel.id != 1061881404167815249  # 美圖展版
        ):
            return

        content = message.content
        urls = find_urls(content)
        for url in urls:
            if "twitter.com" in url and "status" in url:
                await self.delete_message(message)
                if "fxtwitter.com" in url or "vxtwitter.com" in url:
                    await self.fake_user_send(
                        message.channel,
                        message.author,
                        url.replace("fxtwitter.com", "d.fxtwitter.com").replace(
                            "vxtwitter.com", "d.fxtwitter.com"
                        ),
                        message.reference,
                        sauce=url,
                    )
                else:
                    await self.fake_user_send(
                        message.channel,
                        message.author,
                        url.replace("twitter.com", "d.fxtwitter.com"),
                        message.reference,
                        sauce=url,
                    )
            elif ("pixiv" in url or "phixiv" in url) and "artworks" in url:
                await self.delete_message(message)
                artwork_id = url.split("/")[-1].split("?")[0]
                artwork = await fetch_artwork_info(artwork_id)

                if "#R-18" in artwork.tags:
                    await message.channel.send(
                        content=f"{message.author.mention} 你所傳送的圖片包含 R-18 標籤, 請在 <#1061898394446069852> 分享。",
                        delete_after=10,
                    )
                else:
                    for image_url in artwork.image_proxy_urls:
                        await self.fake_user_send(
                            message.channel,
                            message.author,
                            image_url,
                            message.reference,
                            sauce=url,
                        )
            elif "x.com" in url and "status" in url:
                await self.delete_message(message)
                await self.fake_user_send(
                    message.channel,
                    message.author,
                    url.replace("x.com", "d.fixupx.com"),
                    message.reference,
                    sauce=url,
                )

    @commands.Cog.listener("on_message")
    async def embed_fixer(self, message: discord.Message):
        """
        Fix embeds for twitter (with fxtwitter.com), x (with fixupx.com), and pixiv (with phixiv.net).
        Works in channels other than 美圖展版 and 色即是空.
        """
        if (
            message.author.bot
            or message.guild is None
            or message.guild.id != self.bot.guild_id
            or not isinstance(message.channel, discord.TextChannel)
            or message.channel.id
            in (1061881404167815249, 1061898394446069852)  # 美圖展版, 色即是空
        ):
            return

        urls = find_urls(message.content)
        for url in urls:
            if "pixiv" in url and "phixiv" not in url:
                await self.delete_message(message)
                await self.fake_user_send(
                    message.channel,
                    message.author,
                    url.replace("pixiv.net", "phixiv.net"),
                    message.reference,
                )
            elif (
                "twitter.com" in url
                and "fxtwitter.com" not in url
                and "vxtwitter.com" not in url
            ):
                await self.delete_message(message)
                await self.fake_user_send(
                    message.channel,
                    message.author,
                    url.replace("twitter.com", "d.fxtwitter.com"),
                    message.reference,
                )
            elif "x.com" in url and "fixupx.com" not in url:
                await self.delete_message(message)
                await self.fake_user_send(
                    message.channel,
                    message.author,
                    url.replace("x.com", "d.fixupx.com"),
                    message.reference,
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
        if author and not author.bot:
            await message.reply(
                content=f"⬅️ 回應 {author.mention} 的訊息 ({ref.jump_url})",
                mention_author=False,
            )

    async def download_media(self, url: str, filename: str) -> Optional[discord.File]:
        allowed_content_types = ("image", "video", "application/octet-stream")
        async with self.bot.session.get(url) as resp:
            if not any(
                (content_type in resp.content_type)
                for content_type in allowed_content_types
            ):
                return None

            bytes_obj = io.BytesIO(await resp.read())
            if resp.content_type == "application/octet-stream":
                filename += ".png"
            else:
                filename += f".{resp.content_type.split('/')[-1]}"
            file_ = discord.File(bytes_obj, filename=filename, spoiler=True)

        return file_

    async def fake_user_send(
        self,
        channel: discord.TextChannel,
        user: discord.User | discord.Member,
        content: str,
        reference: Optional[discord.MessageReference],
        *,
        sauce: Optional[str] = None,
        **kwargs,
    ) -> None:
        webhooks = await channel.webhooks()
        if not webhooks:
            webhook = await channel.create_webhook(name="Fake User")
        else:
            webhook = webhooks[0]

        ref_message = reference.resolved if reference else None
        if isinstance(ref_message, discord.Message):
            content = f"⬅️ 回應 {ref_message.author.mention} 的訊息 ({ref_message.jump_url})\n\n{content}"

        view = DeleteMessage()
        view.author = user
        if sauce:
            view.add_item(discord.ui.Button(label="醬汁", url=sauce))
        view.message = await webhook.send(
            content=content,
            username=user.display_name,
            avatar_url=user.display_avatar.url,
            view=view,
            **kwargs,
        )

    async def delete_message(self, message: discord.Message) -> None:
        try:
            await message.delete()
        except discord.NotFound:
            pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WebhookCog(bot))
