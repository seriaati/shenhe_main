import contextlib
import typing

import discord
from discord.ext import commands
from loguru import logger
from pydantic import BaseModel, field_validator

if typing.TYPE_CHECKING:
    import datetime

    import aiohttp
    import asyncpg


class BotModel(commands.Bot):
    user: discord.ClientUser
    session: "aiohttp.ClientSession"
    pool: "asyncpg.Pool"
    debug: bool = False
    guild_id = 1061877505067327528

    prev: bool = False


class ShenheEmbed(discord.Embed):
    def __init__(
        self,
        title: str | None = None,
        description: str | None = None,
        color: int | None = 0xA68BD3,
    ) -> None:
        super().__init__(title=title, description=description, color=color)


class DefaultEmbed(ShenheEmbed):
    def __init__(
        self,
        title: str | None = None,
        description: str | None = None,
    ) -> None:
        super().__init__(title=title, description=description, color=0xA68BD3)


class ErrorEmbed(ShenheEmbed):
    def __init__(
        self,
        title: str | None = None,
        description: str | None = None,
    ) -> None:
        super().__init__(title=title, description=description, color=0xFC5165)


class BaseView(discord.ui.View):
    def __init__(
        self,
        timeout: float | None = 600.0,
    ) -> None:
        super().__init__(timeout=timeout)
        self.message: discord.Message | None = None
        self.author: discord.User | discord.Member | None = None

    def disable_items(self) -> None:
        """Disable all buttons and selects in the view."""
        for child in self.children:
            if isinstance(child, discord.ui.Button | discord.ui.Select):
                child.disabled = True

    def enable_items(self) -> None:
        """Enable all buttons and selects in the view."""
        for child in self.children:
            if isinstance(child, discord.ui.Button | discord.ui.Select):
                child.disabled = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.author is None or interaction.user.id == self.author.id:
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
                if isinstance(child, discord.ui.Button | discord.ui.Select):
                    child.disabled = True
            with contextlib.suppress(Exception):
                await self.message.edit(view=self)

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        item: discord.ui.Item[typing.Any],
        /,
    ) -> None:
        logger.error(
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
    async def on_error(self, interaction: discord.Interaction, error: Exception, /) -> None:
        logger.error(
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

    p1_num: str | None = None
    p2_num: str | None = None

    p1_guess: int
    p2_guess: int

    channel_id: int
    flow: int | None = None

    @staticmethod
    def from_row(row: "asyncpg.Record") -> "GuessNumMatch":
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
    p1_win: bool | None
    match_time: "datetime.datetime"
    flow: int | None

    @staticmethod
    def from_row(row: "asyncpg.Record") -> "GameHistory":
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
    def from_row(row: "asyncpg.Record") -> "GamePlayer":
        return GamePlayer(
            user_id=row["user_id"],
            win=row["win"],
            lose=row["lose"],
            win_rate=0,
        )

    @field_validator("win_rate", mode="before")
    def calc_win_rate(self, _, values):
        if values["win"] == 0 and values["lose"] == 0:
            return 0
        return values["win"] / (values["win"] + values["lose"])


class ConnectFourMatch(BaseModel):
    channel_id: int
    board_link: str
    sticky_id: int | None = None

    @staticmethod
    def from_row(row: "asyncpg.Record") -> "ConnectFourMatch":
        return ConnectFourMatch(
            channel_id=row["channel_id"],
            board_link=row["board_link"],
            sticky_id=row["sticky_id"],
        )
