import typing

import discord
from discord import app_commands, ui
from discord.ext import commands

import assets.constants as constants
from utility.utils import default_embed


class FindView(ui.View):
    def __init__(self, author: discord.Member, embed: discord.Embed):
        super().__init__(timeout=None)

        self.members: typing.List[discord.Member] = []
        self.author = author
        self.embed = embed

    async def update_embed(self, i):
        embed = self.embed
        embed.remove_field(-1)
        value = "\n".join(member.mention for member in self.members)
        if not self.members:
            value = "_"
        embed.add_field(
            name=f"已加入 ({len(self.members)})",
            value=value,
            inline=False,
        )
        await i.response.edit_message(embed=embed)

    @ui.button(label="加入", style=discord.ButtonStyle.green)
    async def join(self, i: discord.Interaction, button: ui.Button):
        if i.user in self.members:
            await i.response.send_message("你已經加入了", ephemeral=True)
        else:
            self.members.append(i.user)
            await self.update_embed(i)

    @ui.button(label="退出", style=discord.ButtonStyle.red)
    async def leave(self, i: discord.Interaction, button: ui.Button):
        if i.user not in self.members:
            await i.response.send_message("你還沒有加入過", ephemeral=True)
        else:
            self.members.remove(i.user)
            await self.update_embed(i)

    @ui.button(label="結束", style=discord.ButtonStyle.grey)
    async def end(self, i: discord.Interaction, button: ui.Button):
        if i.user.id != self.author.id:
            await i.response.send_message("你不是發起人", ephemeral=True)
        else:
            await i.message.delete()


class FindCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="find", description="尋找其他玩家")
    @app_commands.rename(game="遊戲", room_num="房號", extra_info="其他資訊")
    @app_commands.describe(
        game="要尋找的遊戲", room_num="房號 (選填)", extra_info="如時間等其他資訊 (選填)"
    )
    async def find(
        self,
        i: discord.Interaction,
        game: str,
        extra_info: typing.Optional[str] = None,
        room_num: typing.Optional[app_commands.Range[int, 0, 99999]] = None,
    ):
        games = {
            str(role_id): i.guild.get_role(role_id).name
            for role_id in constants.game_role_ids
        }
        if game not in games:
            return await i.response.send_message("該遊戲尚未支援", ephemeral=True)

        embed = default_embed(message=extra_info).set_author(name="⛳ 一起來玩遊戲！")
        embed.add_field(name="遊戲", value=games.get(game))
        if room_num is not None:
            embed.add_field(name="房號", value=room_num)
        embed.add_field(name="發起人", value=i.user.mention)
        embed.add_field(name="已加入 (0)", value="_", inline=False)
        embed.set_footer(text="點擊下方的按鈕加入或退出")

        find_channel = i.guild.get_channel(1085138080849207336)
        view = FindView(i.user, embed)
        await find_channel.send(embed=embed, view=view, content=f"<@&{game}>")
        await i.response.send_message("已發送", ephemeral=True)

    @find.autocomplete("game")
    async def find_game(self, i: discord.Interaction, current: str):
        games = {
            str(role_id): i.guild.get_role(role_id).name
            for role_id in constants.game_role_ids
        }
        return [
            app_commands.Choice(name=game_name, value=game_id)
            for game_id, game_name in games.items()
            if current.lower() in game_name.lower()
        ][:25]


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(FindCog(bot))
