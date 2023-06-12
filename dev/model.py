import datetime
import logging
import typing

import aiohttp
import asyncpg
import discord
from discord.ext import commands
from pydantic import BaseModel, validator


class BotModel(commands.Bot):
    user: discord.ClientUser
    session: aiohttp.ClientSession
    pool: asyncpg.Pool
    debug: bool = False
    guild_id = 1061877505067327528

    prev: bool = False


class ShenheEmbed(discord.Embed):
    def __init__(
        self,
        title: typing.Optional[str] = None,
        description: typing.Optional[str] = None,
        color: typing.Optional[int] = 0xA68BD3,
    ):
        super().__init__(title=title, description=description, color=color)


class DefaultEmbed(ShenheEmbed):
    def __init__(
        self,
        title: typing.Optional[str] = None,
        description: typing.Optional[str] = None,
    ):
        super().__init__(title=title, description=description, color=0xA68BD3)


class ErrorEmbed(ShenheEmbed):
    def __init__(
        self,
        title: typing.Optional[str] = None,
        description: typing.Optional[str] = None,
    ):
        super().__init__(title=title, description=description, color=0xFC5165)


class BaseView(discord.ui.View):
    def __init__(
        self,
        timeout: typing.Optional[float] = 600.0,
    ):
        super().__init__(timeout=timeout)
        self.message: typing.Optional[discord.Message] = None
        self.author: typing.Optional[typing.Union[discord.User, discord.Member]] = None

    def disable_items(self):
        """Disable all buttons and selects in the view."""
        for child in self.children:
            if isinstance(child, (discord.ui.Button, discord.ui.Select)):
                child.disabled = True

    def enable_items(self):
        """Enable all buttons and selects in the view."""
        for child in self.children:
            if isinstance(child, (discord.ui.Button, discord.ui.Select)):
                child.disabled = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.author is None:
            return True
        elif interaction.user.id == self.author.id:
            return True
        else:
            embed = ErrorEmbed("權限不足", f"只有 {self.author.mention} 才能跟此訊息互動")
            try:
                await interaction.response.send_message(embed=embed, ephemeral=True)
            except discord.InteractionResponded:
                await interaction.followup.send(embed=embed)
            except Exception:
                pass
            return False

    async def on_timeout(self) -> None:
        if self.message is not None:
            for child in self.children:
                if isinstance(child, (discord.ui.Button, discord.ui.Select)):
                    child.disabled = True
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        item: discord.ui.Item[typing.Any],
        /,
    ) -> None:
        logging.error(
            f"An error occurred while handling {item.__class__.__name__}: {error}",
            exc_info=error,
        )
        embed = ErrorEmbed(
            "錯誤", f"在處理 `{item.__class__.__name__}` 時發生錯誤:\n```py\n{error}\n```"
        )
        try:
            await interaction.response.send_message(
                embed=embed,
                ephemeral=True,
            )
        except discord.InteractionResponded:
            await interaction.followup.send(embed=embed)
        except Exception:
            pass


class BaseModal(discord.ui.Modal):
    async def on_error(
        self, interaction: discord.Interaction, error: Exception, /
    ) -> None:
        logging.error(
            f"An error occurred while handling {self.__class__.__name__}: {error}",
            exc_info=error,
        )
        embed = ErrorEmbed(
            "錯誤", f"在處理 `{self.__class__.__name__}` 時發生錯誤:\n```py\n{error}\n```"
        )
        try:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.InteractionResponded:
            await interaction.followup.send(embed=embed)
        except Exception:
            pass


class Inter(discord.Interaction):
    client: BotModel


class GuessNumMatch(BaseModel):
    p1: int
    p2: int

    p1_num: typing.Optional[str] = None
    p2_num: typing.Optional[str] = None

    p1_guess: int
    p2_guess: int

    channel_id: int
    flow: typing.Optional[int] = None

    @staticmethod
    def from_row(row: asyncpg.Record) -> "GuessNumMatch":
        return GuessNumMatch(
            p1=row["player_one"],
            p2=row["player_two"],
            p1_num=row["player_one_num"],
            p2_num=row["player_two_num"],
            p1_guess=row["player_one_guess"],
            p2_guess=row["player_two_guess"],
            channel_id=row["channel_id"],
            flow=row["flow"],
        )


class GameHistory(BaseModel):
    p1: int
    p2: int
    p1_win: typing.Optional[bool]
    match_time: datetime.datetime
    flow: typing.Optional[int]

    @staticmethod
    def from_row(row: asyncpg.Record) -> "GameHistory":
        return GameHistory(
            p1=row["p1"],
            p2=row["p2"],
            p1_win=row["p1_win"],
            match_time=row["time"],
            flow=row["flow"],
        )


class GamePlayer(BaseModel):
    user_id: int
    win: int
    lose: int
    win_rate: float

    @staticmethod
    def from_row(row: asyncpg.Record) -> "GamePlayer":
        return GamePlayer(
            user_id=row["user_id"],
            win=row["win"],
            lose=row["lose"],
            win_rate=0,
        )

    @validator("win_rate", pre=True, always=True, allow_reuse=True)
    def calc_win_rate(cls, _, values):
        if values["win"] == 0 and values["lose"] == 0:
            return 0
        return values["win"] / (values["win"] + values["lose"])


class ConnectFourMatch(BaseModel):
    channel_id: int
    board_link: str
    sticky_id: typing.Optional[int] = None

    @staticmethod
    def from_row(row: asyncpg.Record) -> "ConnectFourMatch":
        return ConnectFourMatch(
            channel_id=row["channel_id"],
            board_link=row["board_link"],
            sticky_id=row["sticky_id"],
        )