import datetime
import re
from typing import List

import discord
from dotenv import load_dotenv

load_dotenv()


def default_embed(title: str = "", message: str = ""):
    return discord.Embed(title=title, description=message, color=0xA68BD3)


def ayaaka_embed(title: str = "", message: str = ""):
    return discord.Embed(title=title, description=message, color=0xADC6E5)


def error_embed(title: str = "", message: str = ""):
    return discord.Embed(title=title, description=message, color=0xFC5165)


def time_in_range(start: datetime.time, end: datetime.time, x: datetime.time) -> bool:
    """Return true if x is in the range [start, end]"""
    if start <= end:
        return start <= x <= end
    else:
        return start <= x or x <= end


def log(is_system: bool, is_error: bool, log_type: str, log_msg: str):
    now = get_dt_now()
    today = datetime.datetime.today()
    current_date = today.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M:%S")
    system = "SYSTEM"
    if not is_system:
        system = "USER"
    if not is_error:
        log_str = f"<{current_date} {current_time}> [{system}] ({log_type}) {log_msg}"
    else:
        log_str = (
            f"<{current_date} {current_time}> [{system}] [ERROR] ({log_type}) {log_msg}"
        )
    with open("log.txt", "a+", encoding="utf-8") as f:
        f.write(f"{log_str}\n")
    return log_str


def get_dt_now() -> datetime.datetime:
    return datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=8))
    ).replace(tzinfo=None)


def divide_chunks(list_, n):
    for i in range(0, len(list_), n):
        yield list_[i : i + n]


def find_urls(string: str) -> List[str]:
    url_pattern = re.compile(
        r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
    )
    urls = re.findall(url_pattern, string)
    return urls
