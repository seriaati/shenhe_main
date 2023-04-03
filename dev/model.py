import logging
import typing

import aiohttp
import asyncpg
import discord
from discord.ext import commands


class BotModel(commands.Bot):
    user: discord.ClientUser
    session: aiohttp.ClientSession
    pool: asyncpg.Pool
    debug: bool = False
    guild_id: int = 1061877505067327528

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

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.author is None:
            return True
        elif interaction.user.id == self.author.id:
            return True
        else:
            embed = ErrorEmbed("錯誤", "你不是指令發送者")
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
            await self.message.edit(view=self)

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
