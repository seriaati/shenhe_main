from enum import Enum


class TimeType(Enum):
    MORNING = "morning"
    NOON = "noon"
    NIGHT = "night"


class ShopAction(Enum):
    DELETE = "delete"
    BUY = "buy"
