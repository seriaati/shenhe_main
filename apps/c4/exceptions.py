class InvalidColumn(Exception):
    pass


class ColumnFull(Exception):
    pass


class GameOver(Exception):
    def __init__(self, winner: str):
        self.winner = winner


class Draw(Exception):
    pass
