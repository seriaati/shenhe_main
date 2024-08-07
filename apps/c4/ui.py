import asyncio
import typing
from uuid import uuid4

import discord
from discord import ui
from loguru import logger

from apps.flow import flow_transaction
from dev.model import BaseView, DefaultEmbed, ErrorEmbed, Inter
from utility.utils import get_dt_now

from .exceptions import ColumnFullError, DrawError, GameOverError, NotYourTurnError
from .game import ConnectFour

if typing.TYPE_CHECKING:
    import asyncpg


class ConnectFourView(BaseView):
    def __init__(self, game: ConnectFour, flow: int | None = None) -> None:
        super().__init__(timeout=None)
        self.game = game
        self.flow = flow

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

    async def add_history(self, pool: "asyncpg.Pool", winner: str | None = None) -> None:
        game = self.game
        p1_win = None if winner is None else winner == game.p1_color
        await pool.execute(
            """
            INSERT INTO game_history
            (p1, p2, p1_win,
            time, flow, game)
            VALUES ($1, $2, $3, $4, $5, 'connect_four')
            """,
            game.p1.id,
            game.p2.id,
            p1_win,
            get_dt_now(),
            self.flow,
        )

    async def add_win_lose(self, pool: "asyncpg.Pool", winner: str) -> None:
        game = self.game
        p1_win = winner == game.p1_color
        await pool.execute(
            """
            INSERT INTO game_win_lose
            (user_id, win, lose, game)
            VALUES ($1, $2, $3, 'connect_four')
            ON CONFLICT (user_id, game)
            DO UPDATE SET
                win = game_win_lose.win + $2, lose = game_win_lose.lose + $3
            """,
            game.p1.id,
            1 if p1_win else 0,
            1 if not p1_win else 0,
        )
        await pool.execute(
            """
            INSERT INTO game_win_lose
            (user_id, win, lose, game)
            VALUES ($1, $2, $3, 'connect_four')
            ON CONFLICT (user_id, game)
            DO UPDATE SET
                win = game_win_lose.win + $2, lose = game_win_lose.lose + $3
            """,
            game.p2.id,
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
        if isinstance(error, ColumnFullError):
            await i.response.send_message(embed=ErrorEmbed("這一列已經滿了"), ephemeral=True)
        elif isinstance(error, GameOverError):
            await i.response.edit_message(embed=self.game.get_board(), view=None)

            winner = self.game.players[error.winner]
            loser = next(p for p in self.game.players.values() if p != winner)
            embed = DefaultEmbed(
                "遊戲結束",
                f"獲勝者: {error.winner} {winner.mention}",
            )
            embed.set_footer(text="討論串將會在十分鐘後刪除")
            await i.followup.send(embed=embed)

            if self.flow:
                await flow_transaction(winner.id, self.flow, i.client.pool)
                await flow_transaction(loser.id, -self.flow, i.client.pool)

            await self.add_history(i.client.pool, error.winner)
            await self.add_win_lose(i.client.pool, error.winner)
            await self.delete_thread(i)
        elif isinstance(error, DrawError):
            await i.response.edit_message(embed=self.game.get_board(), view=None)

            embed = DefaultEmbed("平手")
            embed.set_footer(text="討論串將會在十分鐘後刪除")
            await i.followup.send(embed=embed)

            await self.add_history(i.client.pool)
            await self.delete_thread(i)
        elif isinstance(error, NotYourTurnError):
            await i.response.send_message(
                embed=ErrorEmbed("現在不是你的回合", f"現在是 {self.game.current_player} 的回合"),
                ephemeral=True,
            )
        else:
            logger.error(
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
    ) -> None:
        super().__init__(style=style, label=str(column), row=row)
        self.column = column
        self.view: ConnectFourView

    async def callback(self, i: discord.Interaction) -> None:
        game = self.view.game

        color = ""
        player = None
        for player in game.players.values():
            if i.user == player:
                break
        game.play(self.column - 1, color)

        self.view.clear_items()
        style = (
            discord.ButtonStyle.blurple
            if player != next(iter(game.players.values()))
            else discord.ButtonStyle.green
        )
        for column in range(1, 8):
            self.view.add_item(ColumnButton(column, column // 5, style))
        await i.response.edit_message(embed=game.get_board(), view=self.view)


class ColorSelectView(BaseView):
    def __init__(
        self,
        p1: discord.Member,
        p2: discord.Member,
        embed: discord.Embed,
        flow: int | None = None,
    ) -> None:
        super().__init__(timeout=600.0)
        self.p1 = p1
        self.p2 = p2
        self.p1_color: str | None = None
        self.p2_color: str | None = None

        self.embed = embed
        self.flow = flow

        self.add_item(ColorSelect())

    async def interaction_check(self, i: discord.Interaction) -> bool:
        if i.user in {self.p1, self.p2}:
            return True
        else:
            await i.response.send_message(
                embed=ErrorEmbed("錯誤", "你不是這個遊戲的玩家之一"), ephemeral=True
            )
            return False


class ColorSelect(ui.Select):
    def __init__(self, selected: str | None = None) -> None:
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
        if view.p1_color is not None and view.p2_color is None and i.user.id != view.p2.id:
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
            view = ConnectFourView(game, self.view.flow)
            board = await thread.send(
                embed=game.get_board(),
                view=view,
            )

            await i.client.pool.execute(
                "INSERT INTO connect_four (channel_id, board_link) VALUES ($1, $2)",
                thread.id,
                board.jump_url,
            )
