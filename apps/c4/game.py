import typing

import discord

from .exceptions import *


class ConnectFour:
    def __init__(
        self,
        players: typing.Tuple[
            typing.Union[discord.Member, discord.User],
            typing.Union[discord.Member, discord.User],
        ],
    ):
        self.board = [["x" for _ in range(7)] for _ in range(6)]
        self.players = players
        self.current_player = "🟡"

    def get_board(self) -> discord.Embed:
        embed = discord.Embed(title="遊戲板", description="1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣\n")
        assert embed.description is not None
        for row in self.board:
            embed.description += "|".join(row)
        embed.description += "\n"
        return embed

    def get_column(self, col: str):
        if col.isdigit() and 1 <= int(col) <= 7:
            return int(col) - 1
        else:
            raise InvalidColumn

    def play(self):
        while True:
            self.get_board()
            col = self.get_column()
            row = 5
            while row >= 0:
                if self.board[row][col] == "⚫":
                    self.board[row][col] = self.current_player
                    break
                row -= 1
            else:
                raise ColumnFull

            if self.check_win(row, col):
                self.get_board()
                raise GameOver(self.current_player)
            elif self.check_draw():
                self.get_board()
                raise Draw

            self.current_player = "🔵" if self.current_player == "🟡" else "🟡"

    def check_win(self, row, col):
        player = self.board[row][col]
        # check horizontal
        if "".join(self.board[row]).count(player * 4):
            return True
        # check vertical
        if "".join([self.board[i][col] for i in range(6)]).count(player * 4):
            return True
        # check diagonal
        for _ in range(3):
            if "".join([self.board[row + i][col + i] for i in range(4)]).count(
                player * 4
            ):
                return True
            if "".join([self.board[row - i][col + i] for i in range(4)]).count(
                player * 4
            ):
                return True
        return False

    def check_draw(self):
        return all([cell != " " for row in self.board for cell in row])
