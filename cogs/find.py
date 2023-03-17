import typing

import discord
from discord import app_commands, ui
from discord.ext import commands

import data.constants as constants
from utility.utils import default_embed


class FindView(ui.View):
    def __init__(self, author: discord.Member, embed: discord.Embed):
        super().__init__(timeout=3600)

        self.members: typing.List[discord.Member] = [author]
        self.author = author
        self.embed = embed
        self.message: discord.Message

    async def on_timeout(self) -> None:
        try:
            embed = self.edit_embed(self.message.embeds[0])
            for child in self.children:
                child.disabled = True
            await self.message.edit(embed=embed, view=self)
        except discord.NotFound:
            pass

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

    @ui.button(label="加入", style=discord.ButtonStyle.green, custom_id="join")
    async def join(self, i: discord.Interaction, _: ui.Button):
        if i.user in self.members:
            await i.response.send_message("你已經加入了", ephemeral=True)
        else:
            self.members.append(i.user)
            await self.update_embed(i)

    @ui.button(label="退出", style=discord.ButtonStyle.red, custom_id="leave")
    async def leave(self, i: discord.Interaction, _: ui.Button):
        if i.user not in self.members:
            await i.response.send_message("你還沒有加入過", ephemeral=True)
        else:
            self.members.remove(i.user)
            await self.update_embed(i)

    @ui.button(label="結束", style=discord.ButtonStyle.grey, custom_id="end")
    async def end(self, i: discord.Interaction, _: ui.Button):
        if i.user.id != self.author.id:
            await i.response.send_message("你不是發起人", ephemeral=True)
        else:
            embed = self.edit_embed(i.message.embeds[0])
            for child in self.children:
                child.disabled = True
            await i.response.edit_message(embed=embed, view=self)

    def edit_embed(self, embed) -> discord.Embed:
        embed.color = discord.Color.light_gray()
        embed.set_author(name="⛳ (已結束)")
        return embed


class FindCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self) -> None:
        self.bot.loop.create_task(self.load_games())

    async def load_games(self) -> None:
        await self.bot.wait_until_ready()

        guild = self.bot.get_guild(constants.guild_id)
        if not guild.chunked:
            await guild.chunk()

        self.games = {
            role_id: guild.get_role(role_id).name for role_id in constants.game_role_ids
        }

    @commands.Cog.listener(name="on_message")
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        for role in message.role_mentions:
            if role.id in constants.game_role_ids:
                embed = self.make_find_embed(
                    message.author,
                    role.id,
                    message.content.replace(role.mention, ""),
                    None,
                )
                view = FindView(message.author, embed)
                await message.reply(embed=embed, view=view)
                break

    @app_commands.command(name="find", description="尋找其他玩家")
    @app_commands.rename(game="遊戲", room_num="房號", extra_info="其他資訊")
    @app_commands.describe(
        game="要尋找的遊戲", room_num="房號 (選填)", extra_info="如時間等其他資訊 (選填)"
    )
    async def find(
        self,
        i: discord.Interaction,
        game: int,
        extra_info: typing.Optional[str] = None,
        room_num: typing.Optional[app_commands.Range[int, 0, 99999]] = None,
    ):

        if game not in self.games:
            return await i.response.send_message("該遊戲尚未支援", ephemeral=True)

        embed = self.make_find_embed(i.user, game, extra_info, room_num)

        find_channel = i.guild.get_channel(1085138080849207336)
        view = FindView(i.user, embed)
        message = await find_channel.send(embed=embed, view=view, content=f"<@&{game}>")
        view.message = message
        await i.response.send_message("已發送", ephemeral=True)

    def make_find_embed(
        self,
        author: discord.Member,
        game: int,
        extra_info: typing.Optional[str] = None,
        room_num: typing.Optional[int] = None,
    ):
        if not extra_info:
            extra_info = None

        embed = default_embed(message=extra_info).set_author(name="⛳ 一起來玩遊戲！")
        embed.add_field(name="遊戲", value=self.games.get(game))
        if room_num is not None:
            embed.add_field(name="房號", value=room_num)
        embed.add_field(name="發起人", value=author.mention)
        embed.add_field(name="已加入 (1)", value=author.mention, inline=False)
        embed.set_footer(text="點擊下方的按鈕加入或退出")
        return embed

    @find.autocomplete("game")
    async def find_game(self, _: discord.Interaction, current: str):
        return [
            app_commands.Choice(name=game_name, value=game_id)
            for game_id, game_name in self.games.items()
            if current.lower() in game_name.lower()
        ][:25]


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(FindCog(bot))
