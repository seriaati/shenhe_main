import io
import re
from typing import Dict, List, Optional

import discord
from discord.ext import commands

from cogs.image_manager import post_url_to_image_url
from data.constants import fix_embeds
from dev.model import BaseView, BotModel
from utility.utils import find_urls


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
            or (message.guild and message.guild.id != self.bot.guild_id)
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
                    if "phixiv" in image_url:
                        files.extend(
                            await self.download_pixiv_images(image_url, filename)
                        )
                    else:
                        file_ = await self.download_image(image_url, filename)
                        if file_ is not None:
                            files.append(file_)
                    message.content = message.content.replace(url, f"<{url}>")

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

        if files:
            webhooks = await message.channel.webhooks()
            if not webhooks:
                webhook = await message.channel.create_webhook(name="Auto-Spoiler")
            else:
                webhook = webhooks[0]

            ref_message = message.reference.resolved if message.reference else None
            if isinstance(ref_message, discord.Message):
                message.content = f"⬅️ 回應 {ref_message.author.mention} 的訊息 ({ref_message.jump_url})\n\n{message.content}"

            view = DeleteMessage()
            view.author = message.author

            view.message = await webhook.send(
                content=message.content,
                files=files,
                username=message.author.display_name,
                avatar_url=message.author.display_avatar.url,
                view=view,
            )

    async def download_image(self, url: str, file_name: str) -> Optional[discord.File]:
        allowed_content_types = ("image", "video")
        async with self.bot.session.get(url) as resp:
            if not any(
                (content_type in resp.content_type)
                for content_type in allowed_content_types
            ):
                return None
            bytes_obj = io.BytesIO(await resp.read())
            file_name += f".{resp.content_type.split('/')[-1]}"
            file_ = discord.File(bytes_obj, filename=file_name, spoiler=True)

        return file_

    async def download_pixiv_images(
        self, url: str, filename: str
    ) -> List[discord.File]:
        images: List[discord.File] = []
        async with self.bot.session.get(url) as resp:
            if resp.status != 200:
                return images
            index = 0
            while True:
                bytes_obj = io.BytesIO(await resp.read())
                file_ = discord.File(
                    bytes_obj, filename=f"{filename}_{index}.png", spoiler=True
                )
                images.append(file_)
                index += 1
                async with self.bot.session.get(
                    str(resp.url).replace(f"p{index-1}", f"p{index}")
                ) as resp:
                    if resp.status != 200:
                        break

        return images

    # use fxtwitter and phixiv
    @commands.Cog.listener("on_message")
    async def use_fxtwitter(self, message: discord.Message):
        if (
            message.author.bot
            or message.guild is None
            or message.guild.id != self.bot.guild_id
            or not isinstance(message.channel, discord.TextChannel)
            or message.channel.id != 1061898394446069852
        ):
            return

        # check if message.content contains a URL using regex
        if not find_urls(message.content):
            return

        for website, fix in fix_embeds.items():
            if website in message.content and fix not in message.content:
                webhooks = await message.channel.webhooks()
                if not webhooks:
                    webhook = await message.channel.create_webhook(name="Fix Embed")
                else:
                    webhook = webhooks[0]

                await message.delete()

                view = DeleteMessage()
                view.author = message.author

                view.message = await webhook.send(
                    content=message.content.replace(website, fix),
                    username=message.author.display_name,
                    avatar_url=message.author.display_avatar.url,
                    view=view,
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
