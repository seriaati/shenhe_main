import typing

from apps.c4.exceptions import ColumnFullError, DrawError, GameOverError, NotYourTurnError
from dev.model import DefaultEmbed

if typing.TYPE_CHECKING:
    import discord


class ConnectFour:
    def __init__(
        self,
        players: dict[str, "discord.Member"],
    ) -> None:
        self.board = [["⚫ " for _ in range(7)] for _ in range(6)]
        self.players = players

        keys = list(players.keys())
        self.p1_color = keys[0]
        self.p2_color = keys[1]
        self.current_player = self.p1_color

        values = list(players.values())
        self.p1 = values[0]
        self.p2 = values[1]

    def get_board(self) -> "discord.Embed":
        embed = DefaultEmbed(f"{self.p1.display_name} vs {self.p2.display_name}")
        embed.description = ""
        for row in self.board:
            embed.description += "".join(row) + "\n"
        embed.description += "1️⃣ 2️⃣ 3️⃣ 4️⃣ 5️⃣ 6️⃣ 7️⃣"

        embed.set_footer(text="點擊下方按鈕來選擇要下的位置")
        embed.set_author(name=f"現在是 {self.current_player} 的回合")

        return embed

    def play(self, col: int, color: str) -> None:
        if color != self.current_player:
            raise NotYourTurnError

        row = 5
        while row >= 0:
            if self.board[row][col] == "⚫ ":
                self.board[row][col] = self.current_player
                break
            row -= 1
        else:
            raise ColumnFullError

        if self.check_win(row, col):
            raise GameOverError(self.current_player)
        elif self.check_draw():
            raise DrawError

        self.current_player = (
            self.p2_color if self.current_player == self.p1_color else self.p1_color
        )

    def check_win(self, row: int, col: int) -> bool:
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
            and "".join([self.board[row + i][col + i] for i in range(4)]).count(player * 4)
        ):
            return True
        if (
            col <= 3
            and row >= 3
            and "".join([self.board[row - i][col + i] for i in range(4)]).count(player * 4)
        ):
            return True
        if (
            col >= 3
            and row <= 2
            and "".join([self.board[row + i][col - i] for i in range(4)]).count(player * 4)
        ):
            return True
        return bool(
            col >= 3
            and row >= 3
            and "".join([self.board[row - i][col - i] for i in range(4)]).count(player * 4)
        )

    def check_draw(self) -> bool:
        return all(cell != "⚫ " for row in self.board for cell in row)
