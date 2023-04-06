import logging
import typing
from uuid import uuid4

import discord
from discord import ui

from dev.model import BaseView, DefaultEmbed, ErrorEmbed

from .exceptions import *
from .game import ConnectFour


class ConnectFourView(BaseView):
    def __init__(self, game: ConnectFour):
        super().__init__(timeout=60.0)
        self.game = game

        for column in range(1, 8):
            self.add_item(ColumnButton(column, column // 4))

    async def interaction_check(self, i: discord.Interaction) -> bool:
        if i.user in self.game.players.values():
            return True
        else:
            await i.response.send_message(
                embed=ErrorEmbed("錯誤", "你不是這個遊戲的玩家之一"), ephemeral=True
            )
            return False

    async def on_error(
        self,
        i: discord.Interaction,
        error: Exception,
        item: discord.ui.Item[typing.Any],
        /,
    ) -> None:
        if isinstance(error, ColumnFull):
            await i.response.edit_message(embed=self.game.get_board())
            await i.followup.send(embed=ErrorEmbed("錯誤", "這一列已經滿了"), ephemeral=True)
        elif isinstance(error, GameOver):
            await i.response.edit_message(embed=self.game.get_board(), view=None)
            await i.followup.send(
                embed=DefaultEmbed(
                    "遊戲結束",
                    f"獲勝者: {error.winner} {self.game.players[error.winner].mention}",
                )
            )
        elif isinstance(error, Draw):
            await i.response.edit_message(embed=self.game.get_board(), view=None)
            await i.followup.send(embed=DefaultEmbed("平手"))
        else:
            logging.error(
                f"An error occurred while handling {item.__class__.__name__}: {error}",
                exc_info=error,
            )
            await i.response.send_message(
                embed=ErrorEmbed("錯誤", "發生了一個未知的錯誤"), ephemeral=True
            )


class ColumnButton(ui.Button):
    def __init__(self, column: int, row: int):
        super().__init__(style=discord.ButtonStyle.blurple, label=str(column), row=row)
        self.column = column
        self.view: ConnectFourView

    async def callback(self, i: discord.Interaction):
        game = self.view.game
        game.play(self.column - 1)
        await i.response.edit_message(embed=game.get_board())


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
    def __init__(self):
        super().__init__(
            placeholder="選擇你的顏色",
            options=[
                discord.SelectOption(label="紅色", value="🔴 ", emoji="🔴"),
                discord.SelectOption(label="黃色", value="🟡 ", emoji="🟡"),
                discord.SelectOption(label="綠色", value="🟢 ", emoji="🟢"),
                discord.SelectOption(label="藍色", value="🔵 ", emoji="🔵"),
                discord.SelectOption(label="紫色", value="🟣 ", emoji="🟣"),
                discord.SelectOption(label="白色", value="⚪ ", emoji="⚪"),
            ],
        )
        self.view: ColorSelectView

    async def callback(self, i: discord.Interaction) -> typing.Any:
        view = self.view
        if view.p1_color is None and i.user.id != view.p1.id:
            return await i.response.send_message(
                embed=ErrorEmbed("錯誤", "請等待玩家一選擇顏色"), ephemeral=True
            )
        elif view.p2_color is None and i.user.id != view.p2.id:
            return await i.response.send_message(
                embed=ErrorEmbed("錯誤", "現在已經輪到玩家二選擇顏色"), ephemeral=True
            )

        embed = view.embed
        if i.user.id == view.p1.id:
            view.p1_color = self.values[0]
            embed.set_field_at(
                0, name="玩家一", value=f"{view.p1.mention} ({view.p1_color})"
            )
        elif i.user.id == view.p2.id:
            view.p2_color = self.values[0]
            embed.set_field_at(
                1, name="玩家二", value=f"{view.p2.mention} ({view.p2_color})"
            )

        await i.response.edit_message(embed=embed, view=view)

        if view.p1_color is not None and view.p2_color is not None:
            message = await i.original_response()
            thread = await message.create_thread(name=f"四子棋-{str(uuid4())[:4]}")
            game = ConnectFour({view.p1_color: view.p1, view.p2_color: view.p2})
            view = ConnectFourView(game)
            await thread.send(
                embed=game.get_board(),
                view=view,
            )
