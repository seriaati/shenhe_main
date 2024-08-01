class InvalidColumnError(Exception):
    pass


class ColumnFullError(Exception):
    pass


class GameOverError(Exception):
    def __init__(self, winner: str) -> None:
        self.winner = winner


class DrawError(Exception):
    pass


class NotYourTurnError(Exception):
    pass
