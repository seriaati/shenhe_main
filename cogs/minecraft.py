from typing import Dict, List, Optional

import aiohttp
import asyncpg
import discord
from attr import define
from discord import app_commands, ui
from discord.ext import commands
from pydantic import BaseModel, validator
from seria.utils import split_list_to_chunks

from dev.model import BaseModal, BaseView, BotModel, DefaultEmbed, Inter
from utility.paginator import GeneralPaginator


class Player(BaseModel):
    name: str
    id: str


class Players(BaseModel):
    max: int
    now: int
    sample: List[Player]

    @validator("sample", pre=True, allow_reuse=True)
    def form_sample(cls, v):
        if isinstance(v, list):
            return [Player(**p) for p in v]
        return v


class Server(BaseModel):
    name: Optional[str]
    protocol: int


class APIResponse(BaseModel):
    status: str
    online: bool
    motd: str
    motd_json: Optional[Dict[str, str]]
    favicon: Optional[str]
    error: Optional[str]
    players: Players
    server: Server
    last_updated: str
    duration: str

    @validator("players", pre=True, allow_reuse=True)
    def form_players(cls, v):
        if isinstance(v, dict):
            return Players(**v)
        return v

    @validator("server", pre=True, allow_reuse=True)
    def form_server(cls, v):
        if isinstance(v, dict):
            return Server(**v)
        return v


class ServerStatus(BaseView):
    def __init__(self):
        super().__init__(timeout=None)

        self.server_ip = "34.81.237.15"

    async def _fetch_data(self, session: aiohttp.ClientSession) -> APIResponse:
        url = f"https://mcapi.us/server/status?ip={self.server_ip}"
        async with session.get(url) as resp:
            return APIResponse(**await resp.json())

    def create_embed(self, response: APIResponse) -> DefaultEmbed:
        embed = DefaultEmbed(
            "Minecraft 伺服器狀態", f"{'🟢 線上' if response.online else '🔴 離線'}"
        )
        embed.add_field(name="IP", value=self.server_ip)
        embed.add_field(name="版本", value=response.server.name or "未知")
        embed.add_field(
            name="人數", value=f"{response.players.now}/{response.players.max}"
        )
        if response.players.sample:
            embed.add_field(
                name="玩家",
                value="\n".join([f"`{p.name}`" for p in response.players.sample]),
            )
        return embed

    @ui.button(label="重整", style=discord.ButtonStyle.blurple)
    async def refresh(self, inter: discord.Interaction, _):
        i: Inter = inter  # type: ignore
        await i.response.defer()
        resp = await self._fetch_data(i.client.session)
        embed = self.create_embed(resp)
        await i.edit_original_response(embed=embed)


@define
class Coord:
    id: int
    name: str
    x: int
    y: int
    z: int


class AddCoord(BaseModal):
    name = ui.TextInput(
        label="座標名稱", placeholder="輸入座標名稱", min_length=1, max_length=50
    )
    x = ui.TextInput(label="X", placeholder="輸入X座標", min_length=1, max_length=50)
    y = ui.TextInput(label="Y", placeholder="輸入Y座標", min_length=1, max_length=50)
    z = ui.TextInput(label="Z", placeholder="輸入Z座標", min_length=1, max_length=50)

    def __init__(self):
        super().__init__(title="新增座標", custom_id="add_coord")

    async def on_submit(self, inter: discord.Interaction):
        i: Inter = inter  # type: ignore
        await i.response.defer()
        await i.client.pool.execute(
            """
            INSERT INTO coords(name, x, y, z) VALUES($1, $2, $3, $4)
            """,
            self.name.value,
            int(self.x.value),
            int(self.y.value),
            int(self.z.value),
        )
        self.stop()


class RemoveCord(BaseModal):
    coord_id = ui.TextInput(
        label="座標ID", placeholder="輸入座標ID", min_length=1, max_length=50
    )

    def __init__(self):
        super().__init__(title="移除座標", custom_id="remove_coord")

    async def on_submit(self, inter: discord.Interaction):
        i: Inter = inter  # type: ignore
        await i.response.defer()
        await i.client.pool.execute(
            """
            DELETE FROM coords WHERE id = $1
            """,
            int(self.coord_id.value),
        )
        self.stop()


class CoordsSystem(BaseView):
    def __init__(self, pool: asyncpg.Pool):
        super().__init__()
        self.pool = pool

    async def create_table_in_db(self) -> None:
        await self.pool.execute(
            """CREATE TABLE IF NOT EXISTS coords(
            id SERIAL PRIMARY KEY,
            name VARCHAR(50) NOT NULL,
            x INTEGER NOT NULL,
            y INTEGER NOT NULL,
            z INTEGER NOT NULL
            )"""
        )

    async def _make_coords_embeds(self) -> List[DefaultEmbed]:
        coords = await self.pool.fetch("""SELECT * FROM coords""")
        coords = [Coord(**coord) for coord in coords]
        if not coords:
            return [DefaultEmbed("座標系統", "目前沒有座標")]

        div_coords = split_list_to_chunks(coords, 9)
        embeds: List[DefaultEmbed] = []
        for div in div_coords:
            embed = DefaultEmbed("座標系統")
            for coord in div:
                embed.add_field(
                    name=coord.name,
                    value=f"座標: {coord.x} {coord.y} {coord.z}\nID: {coord.id}",
                )
            embeds.append(embed)
        return embeds

    async def _update_interaction(self, i: discord.Interaction) -> None:
        embeds = await self._make_coords_embeds()
        paginator = GeneralPaginator(i, embeds, self.children)  # type: ignore
        await paginator.start(edit=True)

    @ui.button(
        label="新增座標", style=discord.ButtonStyle.green, custom_id="add_coord_btn"
    )
    async def add_coord(self, i: discord.Interaction, _):
        modal = AddCoord()
        await i.response.send_modal(modal)
        await modal.wait()
        await self._update_interaction(i)

    @ui.button(
        label="刪除座標", style=discord.ButtonStyle.red, custom_id="remove_coord_btn"
    )
    async def remove_coord(self, i: discord.Interaction, _):
        modal = RemoveCord()
        await i.response.send_modal(modal)
        await modal.wait()
        await self._update_interaction(i)


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

    @app_commands.command(name="coords", description="座標系統")
    async def coords_slash(self, i: discord.Interaction):
        await i.response.defer()
        view = CoordsSystem(self.bot.pool)
        await view.create_table_in_db()
        await view._update_interaction(i)


async def setup(bot: commands.Bot):
    await bot.add_cog(Minecraft(bot))
