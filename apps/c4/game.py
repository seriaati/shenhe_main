import typing

import discord

from apps.c4.exceptions import ColumnFull, Draw, GameOver, NotYourTurn
from dev.model import DefaultEmbed


class ConnectFour:
    def __init__(
        self,
        players: typing.Dict[str, discord.Member],
    ):
        self.board = [["⚫ " for _ in range(7)] for _ in range(6)]
        self.players = players

        keys = list(players.keys())
        self.p1_color = keys[0]
        self.p2_color = keys[1]
        self.current_player = self.p1_color

        values = list(players.values())
        self.p1 = values[0]
        self.p2 = values[1]

    def get_board(self) -> discord.Embed:
        embed = DefaultEmbed("屏風式四子棋")
        embed.description = ""
        for row in self.board:
            embed.description += "".join(row) + "\n"
        embed.description += "1️⃣ 2️⃣ 3️⃣ 4️⃣ 5️⃣ 6️⃣ 7️⃣"
        embed.set_footer(text=f"現在是 {self.current_player} 的回合")
        embed.set_author(name=f"{self.p1.display_name} vs {self.p2.display_name}")

        return embed

    def play(self, col: int, color: str):
        if color != self.current_player:
            raise NotYourTurn

        row = 5
        while row >= 0:
            if self.board[row][col] == "⚫ ":
                self.board[row][col] = self.current_player
                break
            row -= 1
        else:
            raise ColumnFull

        if self.check_win(row, col):
            raise GameOver(self.current_player)
        elif self.check_draw():
            raise Draw

        self.current_player = (
            self.p2_color if self.current_player == self.p1_color else self.p1_color
        )

    def check_win(self, row, col):
        player = self.board[row][col]
        # check horizontal
        if "".join(self.board[row]).count(player * 4):
            return True
        # check vertical
        if "".join([self.board[i][col] for i in range(6)]).count(player * 4):
            return True
        # check diagonal
        if (
            col <= 3
            and row <= 2
            and "".join([self.board[row + i][col + i] for i in range(4)]).count(
                player * 4
            )
        ):
            return True
        if (
            col <= 3
            and row >= 3
            and "".join([self.board[row - i][col + i] for i in range(4)]).count(
                player * 4
            )
        ):
            return True
        if (
            col >= 3
            and row <= 2
            and "".join([self.board[row + i][col - i] for i in range(4)]).count(
                player * 4
            )
        ):
            return True
        if (
            col >= 3
            and row >= 3
            and "".join([self.board[row - i][col - i] for i in range(4)]).count(
                player * 4
            )
        ):
            return True
        return False

    def check_draw(self):
        return all([cell != "⚫ " for row in self.board for cell in row])
