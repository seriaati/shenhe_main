import datetime

import discord
from dotenv import load_dotenv

load_dotenv()


def default_embed(title: str = "", message: str = "") -> discord.Embed:
    return discord.Embed(title=title, description=message, color=0xA68BD3)


def ayaaka_embed(title: str = "", message: str = "") -> discord.Embed:
    return discord.Embed(title=title, description=message, color=0xADC6E5)


def error_embed(title: str = "", message: str = "") -> discord.Embed:
    return discord.Embed(title=title, description=message, color=0xFC5165)


def time_in_range(start: datetime.time, end: datetime.time, x: datetime.time) -> bool:
    """Return true if x is in the range [start, end]"""
    if start <= end:
        return start <= x <= end
    else:
        return start <= x or x <= end


def get_dt_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).replace(
        tzinfo=None
    )
