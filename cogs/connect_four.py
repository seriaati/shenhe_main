import discord
from discord import app_commands
from discord.ext import commands

from apps.c4.ui import ColorSelectView
from dev.model import DefaultEmbed, ErrorEmbed


class ConnectFourCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.guild_only()
    @app_commands.rename(opponent="對手")
    @app_commands.command(name="c4", description="開始一場屏風式四子棋遊戲")
    async def connect_four(self, i: discord.Interaction, opponent: discord.Member):
        assert isinstance(i.user, discord.Member)
        if i.user == opponent:
            return await i.response.send_message(
                embed=ErrorEmbed("你不能和自己對戰"), ephemeral=True
            )
        if opponent.bot:
            return await i.response.send_message(
                embed=ErrorEmbed("你不能和機器人對戰"), ephemeral=True
            )

        embed = DefaultEmbed(
            f"{i.user.display_name} 邀請 {opponent.display_name} 來玩屏風式四子棋"
        )
        embed.add_field(name="玩家一", value=f"{i.user.mention} - *正在選擇顏色*", inline=False)
        embed.add_field(
            name="玩家二", value=f"{opponent.mention} - *正在選擇顏色*", inline=False
        )

        await i.response.send_message(
            content=f"{i.user.mention} {opponent.mention}",
            embed=embed,
            view=ColorSelectView(i.user, opponent),
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(ConnectFourCog(bot))
