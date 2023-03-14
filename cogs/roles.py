from typing import List, Optional

import discord
from discord import Emoji, ui
from discord.ext import commands

from utility.utils import default_embed


class ReactionRole(ui.View):
    def __init__(
        self,
        roles: List[discord.Role],
        emojis: Optional[List[discord.Emoji]] = None,
        style: discord.ButtonStyle = discord.ButtonStyle.blurple,
    ):
        super().__init__(timeout=None)

        for index, role in enumerate(roles):
            self.add_item(
                RoleButton(role, index // 3, style, emojis[index] if emojis else None)
            )


class RoleButton(ui.Button[ReactionRole]):
    def __init__(
        self,
        role: discord.Role,
        row: int,
        style: discord.ButtonStyle,
        emoji: Optional[Emoji] = None,
    ):
        self.role = role
        super().__init__(
            label=f"{role.name} ({len(role.members)})",
            custom_id=f"role_{role.id}",
            row=row,
            emoji=emoji,
            style=style,
        )

    async def callback(self, i: discord.Interaction):
        member: discord.Member = i.user  # type: ignore

        if self.role in member.roles:
            await member.remove_roles(self.role)
        elif (
            self.label
            and "神之眼" in self.label
            and any("神之眼" in role.name for role in member.roles)
        ):
            await i.response.send_message("你已經擁有神之眼了", ephemeral=True)
        else:
            await member.add_roles(self.role)

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

        self.notif_role_ids = (
            1075026929448652860,
            1075027016132345916,
            1075027069832015943,
            1075027095786365009,
            1075027124454440992,
        )
        self.notif_view = ReactionRole(
            [guild.get_role(id) for id in self.notif_role_ids]
        )
        self.bot.add_view(self.notif_view)

        self.game_role_ids = (
            1083175433052372992,
            1083175539369582663,
            1085146432622821408,
        )
        self.game_view = ReactionRole([guild.get_role(id) for id in self.game_role_ids])
        self.bot.add_view(self.game_view)

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
        self.element_view = ReactionRole(
            [guild.get_role(id) for id in self.element_ids],
            [self.bot.get_emoji(id) for id in self.element_emojis],
            style=discord.ButtonStyle.gray,
        )
        self.bot.add_view(self.element_view)

    @commands.command(name="reacton_roles", aliases=["rr"])
    @commands.is_owner()
    async def reacton_roles(self, ctx: commands.Context, id_type: str):
        await ctx.message.delete()
        view = None
        embed_title = ""
        embed_description = "點擊下方的按鈕來獲取身份組"

        if id_type == "notif":
            embed_title = "🔔 通知身份組"
            view = self.notif_view
        elif id_type == "game":
            embed_title = "⛳ 遊戲身份組"
            view = self.game_view
        elif id_type == "element":
            embed_title = "🪄 元素身份組"
            view = self.element_view

        embed = default_embed(message=embed_description).set_author(name=embed_title)
        await ctx.send(embed=embed, view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ReactionRoles(bot))
