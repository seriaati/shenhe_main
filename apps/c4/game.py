import typing

import discord

from apps.c4.exceptions import ColumnFull, Draw, GameOver
from dev.model import DefaultEmbed


class ConnectFour:
    def __init__(
        self,
        players: typing.Tuple[
            typing.Union[discord.User, discord.Member],
            typing.Union[discord.User, discord.Member],
        ],
    ):
        self.board = [["⚫ " for _ in range(7)] for _ in range(6)]
        self.current_player = "🟡 "
        self.players = players

    def get_board(self) -> discord.Embed:
        embed = DefaultEmbed(
            f"屏風式四子棋 | {self.players[0].display_name} vs {self.players[1].display_name}"
        )
        embed.description = ""
        for row in self.board:
            embed.description += "".join(row) + "\n"
        embed.description += "1️⃣ 2️⃣ 3️⃣ 4️⃣ 5️⃣ 6️⃣ 7️⃣"
        embed.set_footer(text=f"現在是 {self.current_player} 的回合")
        member = self.players[0] if self.current_player == "🟡 " else self.players[1]
        embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
        return embed

    def play(self, col: int):
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

        self.current_player = "🔵 " if self.current_player == "🟡 " else "🟡 "

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
