import asyncio
import logging
import typing
from uuid import uuid4

import asyncpg
import discord
from discord import ui

from dev.model import BaseView, DefaultEmbed, ErrorEmbed, Inter
from utility.utils import get_dt_now

from .exceptions import *
from .game import ConnectFour


class ConnectFourView(BaseView):
    def __init__(self, game: ConnectFour):
        super().__init__(timeout=None)
        self.game = game

        for column in range(1, 8):
            self.add_item(ColumnButton(column, column // 5))

    async def interaction_check(self, i: discord.Interaction) -> bool:
        if i.user in self.game.players.values():
            return True
        else:
            await i.response.send_message(
                embed=ErrorEmbed("錯誤", "你不是這個遊戲的玩家之一"), ephemeral=True
            )
            return False

    async def delete_thread(self, i: discord.Interaction) -> None:
        await asyncio.sleep(600)
        assert isinstance(i.channel, discord.Thread)
        await i.channel.delete()

    async def add_history(
        self, pool: asyncpg.Pool, winner: typing.Optional[str] = None
    ) -> None:
        game = self.game
        await pool.execute(
            "INSERT INTO game_history (p1, p2, p1_win, time, flow, game) VALUES ($1, $2, $3, $4, $5, 'connect_four')",
            game.p1,
            game.p2,
            winner or (winner == game.p1_color),
            get_dt_now(),
            game.flow,
        )

    async def add_win_lose(self, pool: asyncpg.Pool, winner: str) -> None:
        game = self.game
        p1_win = winner == game.p1_color
        await pool.execute(
            "INSERT INTO game_win_lose (user_id, win, lose, game) VALUES ($1, $2, $3, 'guess_num') ON CONFLICT (user_id) DO UPDATE SET win = game_win_lose.win + $2, lose = game_win_lose.lose + $3",
            game.p1,
            1 if p1_win else 0,
            1 if not p1_win else 0,
        )
        await pool.execute(
            "INSERT INTO game_win_lose (user_id, win, lose, game) VALUES ($1, $2, $3, 'guess_num') ON CONFLICT (user_id) DO UPDATE SET win = game_win_lose.win + $2, lose = game_win_lose.lose + $3",
            game.p2,
            0 if p1_win else 1,
            0 if not p1_win else 1,
        )

    async def on_error(
        self,
        inter: discord.Interaction,
        error: Exception,
        item: discord.ui.Item[typing.Any],
        /,
    ) -> None:
        i: Inter = inter  # type: ignore
        if isinstance(error, ColumnFull):
            await i.response.send_message(embed=ErrorEmbed("這一列已經滿了"), ephemeral=True)
        elif isinstance(error, GameOver):
            await i.response.edit_message(embed=self.game.get_board(), view=None)

            embed = DefaultEmbed(
                "遊戲結束",
                f"獲勝者: {error.winner} {self.game.players[error.winner].mention}",
            )
            embed.set_author(name="討論串將會在十分鐘後刪除")
            await i.followup.send(embed=embed)

            await self.add_history(i.client.pool, error.winner)
            await self.add_win_lose(i.client.pool, error.winner)
            await self.delete_thread(i)
        elif isinstance(error, Draw):
            await i.response.edit_message(embed=self.game.get_board(), view=None)

            embed = DefaultEmbed("平手")
            embed.set_footer(text="討論串將會在十分鐘後刪除")
            await i.followup.send(embed=embed)

            await self.add_history(i.client.pool)
            await self.delete_thread(i)
        elif isinstance(error, NotYourTurn):
            await i.response.send_message(
                embed=ErrorEmbed("現在不是你的回合", f"現在是 {self.game.current_player} 的回合"),
                ephemeral=True,
            )
        else:
            logging.error(
                f"An error occurred while handling {item.__class__.__name__}: {error}",
                exc_info=error,
            )
            await i.response.send_message(
                embed=ErrorEmbed("錯誤", "發生了一個未知的錯誤"), ephemeral=True
            )


class ColumnButton(ui.Button):
    def __init__(
        self,
        column: int,
        row: int,
        style: discord.ButtonStyle = discord.ButtonStyle.blurple,
    ):
        super().__init__(style=style, label=str(column), row=row)
        self.column = column
        self.view: ConnectFourView

    async def callback(self, i: discord.Interaction):
        game = self.view.game

        color = ""
        player = None
        for color, player in game.players.items():
            if i.user == player:
                break
        game.play(self.column - 1, color)

        self.view.clear_items()
        style = (
            discord.ButtonStyle.blurple
            if player != list(game.players.values())[0]
            else discord.ButtonStyle.green
        )
        for column in range(1, 8):
            self.view.add_item(ColumnButton(column, column // 5, style))
        await i.response.edit_message(embed=game.get_board(), view=self.view)


class ColorSelectView(BaseView):
    def __init__(self, p1: discord.Member, p2: discord.Member):
        super().__init__(timeout=600.0)
        self.p1 = p1
        self.p2 = p2
        self.p1_color: typing.Optional[str] = None
        self.p2_color: typing.Optional[str] = None
        self.embed: discord.Embed

        self.add_item(ColorSelect())

    async def interaction_check(self, i: discord.Interaction) -> bool:
        if i.user in (self.p1, self.p2):
            return True
        else:
            await i.response.send_message(
                embed=ErrorEmbed("錯誤", "你不是這個遊戲的玩家之一"), ephemeral=True
            )
            return False


class ColorSelect(ui.Select):
    def __init__(self, selected: typing.Optional[str] = None):
        options = [
            discord.SelectOption(label="紅色", value="🔴", emoji="🔴"),
            discord.SelectOption(label="黃色", value="🟡", emoji="🟡"),
            discord.SelectOption(label="綠色", value="🟢", emoji="🟢"),
            discord.SelectOption(label="藍色", value="🔵", emoji="🔵"),
            discord.SelectOption(label="紫色", value="🟣", emoji="🟣"),
            discord.SelectOption(label="白色", value="⚪", emoji="⚪"),
        ]
        selected_option = discord.utils.get(options, value=selected)
        if selected_option is not None:
            options.remove(selected_option)

        super().__init__(
            placeholder="選擇你的棋子顏色",
            options=options,
        )
        self.view: ColorSelectView

    async def callback(self, i: Inter) -> typing.Any:
        view = self.view
        if view.p1_color is None and i.user.id != view.p1.id:
            return await i.response.send_message(
                embed=ErrorEmbed("錯誤", "請等待玩家一選擇顏色"), ephemeral=True
            )
        if (
            view.p1_color is not None
            and view.p2_color is None
            and i.user.id != view.p2.id
        ):
            return await i.response.send_message(
                embed=ErrorEmbed("錯誤", "現在已經輪到玩家二選擇顏色"), ephemeral=True
            )

        embed = view.embed
        if i.user.id == view.p1.id:
            view.p1_color = self.values[0] + " "
            embed.set_field_at(
                0,
                name="玩家一",
                value=f"{view.p1.mention} - {view.p1_color}",
                inline=False,
            )

            view.clear_items()
            view.add_item(ColorSelect(self.values[0]))

        elif i.user.id == view.p2.id:
            view.p2_color = self.values[0] + " "
            embed.set_field_at(
                1,
                name="玩家二",
                value=f"{view.p2.mention} - {view.p2_color}",
                inline=False,
            )

        await i.response.edit_message(embed=embed, view=view)

        if view.p1_color is not None and view.p2_color is not None:
            self.disabled = True
            await i.edit_original_response(view=view)
            message = await i.original_response()
            thread = await message.create_thread(name=f"四子棋-{str(uuid4())[:4]}")

            game = ConnectFour({view.p1_color: view.p1, view.p2_color: view.p2})
            view = ConnectFourView(game)
            board = await thread.send(
                embed=game.get_board(),
                view=view,
            )

            await i.client.pool.execute(
                "INSERT INTO connect_four (channel_id, message_link) VALUES ($1, $2)",
                thread.id,
                board.jump_url,
            )
