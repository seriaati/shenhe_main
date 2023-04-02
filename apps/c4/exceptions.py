class InvalidColumn(Exception):
    pass


class ColumnFull(Exception):
    pass


class GameOver(Exception):
    def __init__(self, winner):
        self.winner = winner


class Draw(Exception):
    pass
