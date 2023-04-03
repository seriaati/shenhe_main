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

        await webhook.send(
            content=message.content.replace("twitter.com", "fxtwitter.com"),
            username=message.author.display_name,
            avatar_url=message.author.display_avatar.url,
        )

    # better reply
    # @commands.Cog.listener("on_message")
    # async def better_reply(self, message: discord.Message):
    #     if message.author.id == self.bot.user.id:
    #         return
    #     if not message.guild:
    #         return
    #     if message.guild.id != self.bot.guild_id:
    #         return
    #     if not isinstance(message.channel, discord.TextChannel):
    #         return

    #     if message.reference and isinstance(
    #         message.reference.resolved, discord.Message
    #     ):
    #         ref = message.reference.resolved
    #         if ref.author.bot:
    #             real_author = discord.utils.get(
    #                 message.guild.members,
    #                 display_name=ref.author.name,
    #             )
    #             if real_author is None:
    #                 real_author = ref.author
    #         else:
    #             real_author = ref.author

    #         if isinstance(real_author, discord.Member):
    #             roles = [r for r in real_author.roles if "神之眼" in r.name]
    #         else:
    #             roles = []
    #         embed = discord.Embed(
    #             color=roles[0].color if roles else None,
    #             description=ref.content,
    #             timestamp=ref.created_at,
    #         )
    #         embed.set_author(
    #             name=real_author.display_name, icon_url=real_author.display_avatar.url
    #         )

    #         await message.delete()

    #         webhooks = await message.channel.webhooks()
    #         if not webhooks:
    #             webhook = await message.channel.create_webhook(name="Better-Reply")
    #         else:
    #             webhook = webhooks[0]

    #         await webhook.send(
    #             content=message.content + f" <@{real_author.id}>",
    #             embed=embed,
    #             username=message.author.display_name,
    #             avatar_url=message.author.display_avatar.url,
    #             allowed_mentions=discord.AllowedMentions(users=True),
    #         )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WebhookCog(bot))
