import contextlib
import io
from typing import Dict, List, Optional

import aiohttp
import discord
from discord.ext import commands
from pydantic import BaseModel

from dev.model import BaseView, BotModel
from utility.utils import divide_chunks, find_urls, has_image_url


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
        if message.guild is None or message.guild.id != self.bot.guild_id:
            return

        if message.channel.id not in (1061881404167815249, 1061898394446069852):
            return

        # check for attachments
        if message.attachments or has_image_url(message.content):
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
        if (
            message.author.bot
            or not isinstance(message.channel, discord.TextChannel)
            or message.guild is None
            or message.guild.id != self.bot.guild_id
            or message.channel.id != 1061898394446069852
        ):
            return

        files: List[discord.File] = []

        # auto spoiler url images or videos
        urls = find_urls(message.content)
        webs = (
            "twitter.com",
            "fxtwitter.com",
            "phixiv.net",
            "pixiv.net",
            "x.com",
            "fixupx.com",
        )
        exts = ("png", "jpg", "jpeg", "gif", "webp", "mp4")
        for url in urls:
            if any(w in url for w in webs) or any(f".{e}" in url for e in exts):
                await self.del_message(message)
                message.content = message.content.replace(url, f"<{url}>")
                filename = url.split("/")[-1].split("?")[0]

                if "pixiv.net" in url or "phixiv.net" in url:
                    artwork = await fetch_artwork_info(filename)
                    urls_ = artwork.image_proxy_urls
                elif "twitter.com" in url:
                    if "fxtwitter.com" not in url:
                        url = url.replace("twitter.com", "d.fxtwitter.com")
                    elif "vxtwitter.com" in url:
                        url = url.replace("vxtwitter.com", "d.fxtwitter.com")
                    else:
                        url = url.replace("fxtwitter.com", "d.fxtwitter.com")
                    urls_ = [url]
                elif "x.com" in url:
                    if "fixupx.com" not in url:
                        url = url.replace("x.com", "d.fixupx.com")
                    else:
                        url = url.replace("fixupx.com", "d.fixupx.com")
                    urls_ = [url]
                else:
                    urls_ = [url]

                for index, u in enumerate(urls_):
                    file_ = await self.download_image(u, f"{filename}_{index}")
                    if file_ is None:
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
            await self.download_image(url, filename)
            for filename, url in url_dict.items()
        ]
        files.extend([i for i in images if i is not None])

        if files:
            await self.del_message(message)
        split_files: List[List[discord.File]] = list(divide_chunks(files, 10))

        for split in split_files:
            await self.fake_user_send(
                message.channel,
                message.author,
                message.content,
                message.reference,
                files=split,
            )

    # use fxtwitter and phixiv
    @commands.Cog.listener("on_message")
    async def embed_fixer(self, message: discord.Message):
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
            if "pixiv" in url or "phixiv" in url:
                await self.del_message(message)

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
            elif "twitter.com" in url and "fxtwitter.com" not in url:
                await self.del_message(message)

                await self.fake_user_send(
                    message.channel,
                    message.author,
                    url.replace("twitter.com", "d.fxtwitter.com"),
                    message.reference,
                    sauce=url if message.channel.id == 1061881404167815249 else None,
                )
            elif "x.com" in url and "fixupx.com" not in url:
                await self.del_message(message)

                await self.fake_user_send(
                    message.channel,
                    message.author,
                    url.replace("x.com", "d.fixupx.com"),
                    message.reference,
                    sauce=url if message.channel.id == 1061881404167815249 else None,
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

    async def download_image(self, url: str, filename: str) -> Optional[discord.File]:
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

    async def del_message(self, message: discord.Message) -> None:
        try:
            await message.delete()
        except discord.NotFound:
            pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WebhookCog(bot))
