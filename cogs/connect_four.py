import discord
from discord import app_commands
from discord.ext import commands

import apps.c4.game as c4
from apps.c4.ui import ConnectFourView
from dev.model import ErrorEmbed


class ConnectFourCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.guild_only()
    @app_commands.rename(opponent="對手")
    @app_commands.command(name="connect-four", description="開始一場屏風式四子棋遊戲")
    async def connect_four(self, i: discord.Interaction, opponent: discord.Member):
        if i.user == opponent:
            return await i.response.send_message(
                embed=ErrorEmbed("你不能和自己對戰"), ephemeral=True
            )
        if opponent.bot:
            return await i.response.send_message(
                embed=ErrorEmbed("你不能和機器人對戰"), ephemeral=True
            )

        game = c4.ConnectFour((i.user, opponent))
        view = ConnectFourView(game)
        await i.response.send_message(embed=game.get_board(), view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(ConnectFourCog(bot))
