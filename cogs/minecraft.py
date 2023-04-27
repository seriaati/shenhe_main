from typing import Dict, List, Optional

import aiohttp
import discord
from attr import define
from discord import app_commands, ui
from discord.ext import commands

from dev.model import BaseView, BotModel, DefaultEmbed, Inter


@define
class Player:
    name: str
    id: str


@define
class Players:
    max: int
    now: int
    sample: List[Player]


@define
class Server:
    name: str
    protocol: int


@define
class APIResponse:
    status: str
    online: bool
    motd: str
    motd_json: Dict[str, str]
    favicon: Optional[str]
    error: Optional[str]
    players: Players
    server: Server
    last_updated: str
    duration: str


class ServerStatus(BaseView):
    def __init__(self):
        super().__init__(timeout=None)

        self.server_ip = "65.109.114.175"

    async def _fetch_data(self, session: aiohttp.ClientSession) -> APIResponse:
        url = f"https://mcapi.us/server/status?ip={self.server_ip}"
        async with session.get(url) as resp:
            return APIResponse(**await resp.json())

    def create_embed(self, response: APIResponse) -> DefaultEmbed:
        embed = DefaultEmbed(
            "Minecraft 伺服器狀態", f"{'🟢 線上' if response.online else '🔴 離線'}"
        )
        embed.add_field(name="IP", value=self.server_ip)
        embed.add_field(name="版本", value=response.server.name)
        embed.add_field(
            name="人數", value=f"{response.players.now}/{response.players.max}"
        )
        if response.players.sample:
            embed.add_field(
                name="玩家", value=", ".join([p.name for p in response.players.sample])
            )
        return embed

    @ui.button(label="重整", style=discord.ButtonStyle.blurple)
    async def refresh(self, inter: discord.Interaction, _):
        i: Inter = inter  # type: ignore
        await i.response.defer()
        resp = await self._fetch_data(i.client.session)
        embed = self.create_embed(resp)
        await i.edit_original_response(embed=embed)


class Minecraft(commands.Cog):
    def __init__(self, bot):
        self.bot: BotModel = bot

    @commands.is_owner()
    @commands.command(name="mc")
    async def mc(self, ctx: commands.Context):
        await ctx.message.delete()
        view = ServerStatus()
        await ctx.send(
            embed=view.create_embed(await view._fetch_data(self.bot.session)), view=view
        )
        self.bot.add_view(view)

    @app_commands.command(name="mc", description="查看麥塊伺服器狀態")
    async def mc_slash(self, i: discord.Interaction):
        view = ServerStatus()
        await i.response.send_message(
            embed=view.create_embed(await view._fetch_data(self.bot.session))
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Minecraft(bot))
