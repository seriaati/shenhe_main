import os
from typing import List

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from saucenao_api import AIOSauceNao
from saucenao_api.saucenao_api import SauceResponse

from dev.model import DefaultEmbed
from utility.paginator import GeneralPaginator

from .image_manager import url_pattern


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

    def _make_embeds(self, resp: SauceResponse) -> List[discord.Embed]:
        embeds: List[discord.Embed] = []

        for result in resp.results:
            urls = [f"• {url}" for url in result.urls]
            embed = DefaultEmbed(result.title, "\n".join(urls))
            if result.author:
                embed.set_author(name=result.author)
            embed.set_image(url=result.thumbnail)
            embed.set_footer(text=f"相似度: {result.similarity:.2f}%")
            embeds.append(embed)

        return embeds

    async def _search(self, url: str) -> SauceResponse:
        client = AIOSauceNao(self.api_key)
        async with client:
            resp = await client.from_url(url)
            return resp

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
        await self._make_search_response(i, True)
        urls: List[str] = url_pattern.findall(message.content)
        resp = await self._search(urls[0])
        embeds = self._make_embeds(resp)
        await self._return_results(i, embeds)

    sauce = app_commands.Group(name="sauce", description="查找圖片來源")

    @sauce.command(name="url", description="透過圖片連結查找圖片來源")
    @app_commands.rename(url="連結", ephemeral="隱藏訊息")
    @app_commands.describe(url="圖片連結", ephemeral="是否隱藏訊息（預設為否）")
    @app_commands.choices(
        ephemeral=[
            app_commands.Choice(name="是", value=True),
            app_commands.Choice(name="否", value=False),
        ]
    )
    async def slash_search_sauce_url(
        self, i: discord.Interaction, url: str, ephemeral: bool = False
    ):
        await self._make_search_response(i, ephemeral)
        resp = await self._search(url)
        embeds = self._make_embeds(resp)
        await self._return_results(i, embeds)

    @sauce.command(name="image", description="透過圖片查找圖片來源")
    @app_commands.rename(image="圖片", ephemeral="隱藏訊息")
    @app_commands.describe(image="圖片", ephemeral="是否隱藏訊息（預設為否）")
    @app_commands.choices(
        ephemeral=[
            app_commands.Choice(name="是", value=True),
            app_commands.Choice(name="否", value=False),
        ]
    )
    async def slash_search_sauce_image(
        self, i: discord.Interaction, image: discord.Attachment, ephemeral: bool = False
    ):
        await self._make_search_response(i, ephemeral)
        resp = await self._search(image.url)
        embeds = self._make_embeds(resp)
        await self._return_results(i, embeds)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SauceNao(bot))
