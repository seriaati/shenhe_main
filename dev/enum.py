from enum import Enum


class TimeType(Enum):
    MORNING = "morning"
    NOON = "noon"
    NIGHT = "night"


class ShopAction(Enum):
    DELETE = "delete"
    BUY = "buy"


class GameType(Enum):
    GUESS_NUM = "guess_num"
    CONNECT_FOUR = "connect_four"
