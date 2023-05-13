import io
import re
from typing import List

import discord
from discord.ext import commands

from cogs.image_manager import pixiv_to_direct, twitter_to_direct
from data.constants import fix_embeds
from dev.model import BaseView, BotModel


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

        url_pattern = re.compile(
            r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
        )
        if url_pattern.search(message.content):
            websites = ("twitter", "fxtwitter", "phixiv", "pixiv")
            image_extensions = ("png", "jpg", "jpeg", "gif", "webp")
            if any(website in message.content for website in websites) or any(
                ext in message.content for ext in image_extensions
            ):
                await message.delete()
                urls: List[str] = url_pattern.findall(message.content)
                for url in urls:
                    if "twitter" in url:
                        direct_url = twitter_to_direct(url)
                    elif "pixiv" in url or "phixiv" in url:
                        direct_url = pixiv_to_direct(url)
                    else:
                        direct_url = url

                    if direct_url:
                        file_ = await self.download_image(
                            direct_url, "auto_spoiler.jpg"
                        )
                        files.append(file_)
                        message.content = message.content.replace(url, f"<{url}>")

        if any(not a.is_spoiler() for a in message.attachments):
            await message.delete()

            for attachment in message.attachments:
                if not attachment.is_spoiler():
                    url = attachment.proxy_url
                    file_name = attachment.filename
                    file_ = await self.download_image(url, file_name)
                    files.append(file_)
                else:
                    files.append(await attachment.to_file())

        if files:
            webhooks = await message.channel.webhooks()
            if not webhooks:
                webhook = await message.channel.create_webhook(name="Auto-Spoiler")
            else:
                webhook = webhooks[0]

            view = DeleteMessage()
            view.author = message.author

            view.message = await webhook.send(
                content=message.content,
                files=files,
                username=message.author.display_name,
                avatar_url=message.author.display_avatar.url,
                view=view,
            )

    async def download_image(self, url, file_name):
        async with self.bot.session.get(url) as resp:
            bytes_obj = io.BytesIO(await resp.read())
            file_ = discord.File(bytes_obj, filename=file_name, spoiler=True)

        return file_

    # use fxtwitter and phixiv to send tweet
    @commands.Cog.listener("on_message")
    async def use_fxtwitter(self, message: discord.Message):
        if message.author.bot:
            return
        if message.guild and message.guild.id != self.bot.guild_id:
            return
        if not isinstance(message.channel, discord.TextChannel):
            return
        if message.channel.id == 1061898394446069852:
            return

        # check if message.content contains a URL using regex
        if not re.search(r"(https?://[^\s]+)", message.content):
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


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WebhookCog(bot))
