import logging
import typing

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
        if i.user in self.game.players:
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
        await i.response.edit_message(embed=self.game.get_board())
        if isinstance(error, ColumnFull):
            await i.followup.send(embed=ErrorEmbed("錯誤", "這一列已經滿了"), ephemeral=True)
        elif isinstance(error, GameOver):
            await i.followup.send(embed=DefaultEmbed("遊戲結束", f"獲勝者: {error.winner}"))
        elif isinstance(error, Draw):
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
