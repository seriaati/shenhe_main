from typing import List, Optional

import discord
from discord import Emoji, ui
from discord.ext import commands

from utility.utils import default_embed


class ReactionRole(ui.View):
    def __init__(
        self, roles: List[discord.Role], emojis: Optional[List[discord.Emoji]] = None
    ):
        super().__init__(timeout=None)

        for index, role in enumerate(roles):
            self.add_item(
                RoleButton(role, index // 3, emojis[index] if emojis else None)
            )


class RoleButton(ui.Button[ReactionRole]):
    def __init__(self, role: discord.Role, row: int, emoji: Optional[Emoji] = None):
        self.role = role
        super().__init__(
            label=f"{role.name} ({len(role.members)})",
            style=discord.ButtonStyle.blurple,
            custom_id=f"role_{role.id}",
            row=row,
            emoji=emoji,
        )

    async def callback(self, i: discord.Interaction):
        if self.role in i.user.roles:
            await i.user.remove_roles(self.role)
        else:
            await i.user.add_roles(self.role)
        self.label = f"{self.role.name} ({len(self.role.members)})"
        await i.response.edit_message(view=self.view)


class ReactionRoles(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.loop.create_task(self.add_view_task())

    async def add_view_task(self):
        await self.bot.wait_until_ready()
        guild = self.bot.get_guild(1061877505067327528)

        self.role_ids = (
            1075026929448652860,
            1075027016132345916,
            1075027069832015943,
            1075027095786365009,
            1075027124454440992,
        )
        self.notif_view = ReactionRole([guild.get_role(id) for id in self.role_ids])
        self.bot.add_view(self.notif_view)

        self.game_role_ids = (1083175433052372992, 1083175539369582663)
        self.game_view = ReactionRole([guild.get_role(id) for id in self.game_role_ids])
        self.bot.add_view(self.game_view)

        self.city_role_ids = (
            1082902939779223663,
            1082903068477231104,
            1082903324338171904,
            1082903383272325160,
        )
        self.city_emojis = (
            1071728354178379827,
            1071728358095863881,
            1071728361514213377,
            1071728366077616169,
        )
        self.city_view = ReactionRole(
            [guild.get_role(id) for id in self.city_role_ids],
            [guild.get_emoji(id) for id in self.city_emojis],
        )
        self.bot.add_view(self.city_view)

        self.element_ids = (
            1084739406897889322,
            1084739562468810763,
            1084739636200472696,
            1084739703137378375,
            1084739772687319130,
            1084739855558385755,
            1084739910721871902,
        )
        self.element_emojis = (
            1063524352466894919,
            1063524354761179157,
            1063524366832373780,
            1063524361434304512,
            1063524370162651178,
            1063524363351101510,
            1063524358070468628,
        )

    @commands.command(name="reacton_roles", aliases=["rr"])
    @commands.is_owner()
    async def reacton_roles(self, ctx: commands.Context, id_type: str):
        await ctx.message.delete()

        embed_description = "點擊下方的按鈕來獲取身份組"
        if id_type == "notif":
            embed_title = "🔔 通知身份組"
            view = self.view
        elif id_type == "game":
            embed_title = "⛳ 遊戲身份組"
            view = self.game_view
        elif id_type == "city":
            embed_title = "🛖 城市身份組"
            view = self.city_view
        elif id_type == "element":
            embed_title = "🪄 元素身份組"
            view = self.element_view

        embed = default_embed(embed_title, embed_description)
        await ctx.send(embed=embed, view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ReactionRoles(bot))
