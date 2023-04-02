import typing

import discord

from dev.model import DefaultEmbed


class ConnectFour:
    def __init__(
        self,
        players: typing.Tuple[
            typing.Union[discord.User, discord.Member],
            typing.Union[discord.User, discord.Member],
        ],
    ):
        self.board = [[" " for _ in range(7)] for _ in range(6)]
        self.current_player = "🟡"
        self.players = players

    def get_board(self) -> discord.Embed:
        embed = DefaultEmbed("屏風式四子棋")
        embed.description = ""
        for row in self.board:
            embed.description += " ".join(row) + "\n"
        embed.description += "-------------"
        return embed

    def get_column(self):
        while True:
            col = input(f"{self.current_player}, choose a column (1-7): ")
            if col.isdigit() and 1 <= int(col) <= 7:
                return int(col) - 1

    def play(self):
        while True:
            self.print_board()
            col = self.get_column()
            row = 5
            while row >= 0:
                if self.board[row][col] == " ":
                    self.board[row][col] = self.current_player
                    break
                row -= 1
            else:
                print("Column is full, try again")
                continue

            if self.check_win(row, col):
                self.print_board()
                print(f"{self.current_player} wins!")
                return
            elif self.check_draw():
                self.print_board()
                print("Draw!")
                return

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
        return all([cell != " " for row in self.board for cell in row])
