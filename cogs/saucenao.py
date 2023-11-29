import os
import re
from typing import List

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from pysaucenao import SauceNao as SauceNaoAPI
from pysaucenao.containers import SauceNaoResults

from dev.model import DefaultEmbed, ErrorEmbed
from utility.paginator import GeneralPaginator

url_pattern = re.compile(
    r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
)


class SauceNao(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

        load_dotenv()
        self.api_key = os.getenv("SAUCENAO_API_KEY")

    async def cog_load(self) -> None:
        self.ctx_menu = app_commands.ContextMenu(
            name="查找圖片來源", callback=self.search_sauce_ctx
        )
        self.bot.tree.add_command(self.ctx_menu)

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

    def _make_embeds(self, results: SauceNaoResults) -> List[discord.Embed]:
        embeds: List[discord.Embed] = []

        for result in results.results:
            embed = DefaultEmbed(result.title, result.url)
            embed.set_footer(text=f"相似度: {result.similarity:.2f}%")
            embeds.append(embed)

        return embeds

    async def _search(self, url: str) -> SauceNaoResults:
        client = SauceNaoAPI(api_key=self.api_key)
        results = await client.from_url(url)
        return results

    async def _make_search_response(self, i: discord.Interaction, ephemeral: bool):
        embed = DefaultEmbed()
        embed.set_author(name="搜尋中...", icon_url="https://i.imgur.com/V76M9Wa.gif")
        await i.response.send_message(embed=embed, ephemeral=ephemeral)

    async def _return_results(
        self, i: discord.Interaction, embeds: List[discord.Embed]
    ):
        paginator = GeneralPaginator(i, embeds)
        await paginator.start(edit=True)

    async def search_sauce_ctx(self, i: discord.Interaction, message: discord.Message):
        await self._make_search_response(i, False)
        urls: List[str] = url_pattern.findall(message.content)
        urls.extend([a.url for a in message.attachments])

        # filter out non-image urls
        urls = [
            url
            for url in urls
            if url.endswith((".jpg", ".png", ".gif", ".webp", ".jpeg"))
        ]
        if not urls:
            embed = ErrorEmbed("找不到圖片連結", "請確認訊息內是否有圖片連結")
            return await i.followup.send(embed=embed)

        embeds: List[discord.Embed] = []
        for url in urls:
            resp = await self._search(url)
            results = self._make_embeds(resp)
            if not results:
                continue
            embeds.append(results[0])
        await self._return_results(i, embeds)

    sauce = app_commands.Group(name="sauce", description="查找圖片來源")

    @sauce.command(name="url", description="透過圖片連結查找圖片來源")
    @app_commands.rename(url="連結", ephemeral="隱藏訊息")
    @app_commands.describe(url="圖片連結", ephemeral="是否隱藏訊息（預設為否）")
    @app_commands.choices(
        ephemeral=[
            app_commands.Choice(name="是", value=1),
            app_commands.Choice(name="否", value=0),
        ]
    )
    async def slash_search_sauce_url(
        self, i: discord.Interaction, url: str, ephemeral: int = 0
    ):
        await self._make_search_response(i, bool(ephemeral))
        resp = await self._search(url)
        embeds = self._make_embeds(resp)

        if not embeds:
            embed = ErrorEmbed("找不到圖片來源", "請確認連結是否正確")
            return await i.followup.send(embed=embed)
        await self._return_results(i, embeds)

    @sauce.command(name="image", description="透過圖片查找圖片來源")
    @app_commands.rename(image="圖片", ephemeral="隱藏訊息")
    @app_commands.describe(image="圖片", ephemeral="是否隱藏訊息（預設為否）")
    @app_commands.choices(
        ephemeral=[
            app_commands.Choice(name="是", value=1),
            app_commands.Choice(name="否", value=0),
        ]
    )
    async def slash_search_sauce_image(
        self, i: discord.Interaction, image: discord.Attachment, ephemeral: int = 0
    ):
        await self._make_search_response(i, bool(ephemeral))
        resp = await self._search(image.url)
        embeds = self._make_embeds(resp)
        if not embeds:
            embed = ErrorEmbed("找不到圖片來源", "請確認連結是否正確")
            return await i.followup.send(embed=embed)

        await self._return_results(i, embeds)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SauceNao(bot))
