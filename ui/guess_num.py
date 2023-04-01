import logging
import typing

import discord
from discord import ui

from dev.model import BaseView, DefaultEmbed, ErrorEmbed, Inter


class GuessNumView(BaseView):
    def __init__(self):
        super().__init__(timeout=600.0)
        self.channel: discord.Thread
        self.authors: typing.Tuple[discord.Member, discord.Member]

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user in self.authors:
            return True
        else:
            await interaction.response.send_message(
                embed=ErrorEmbed("錯誤", "你不是這個遊戲的玩家之一"), ephemeral=True
            )
            return False

    @ui.button(label="玩家一", style=discord.ButtonStyle.primary, custom_id="player_one")
    async def player_one(self, i: discord.Interaction, _: ui.Button):
        modal = GuessNumModal(True, self)
        await i.response.send_modal(modal)

    @ui.button(
        label="玩家二",
        style=discord.ButtonStyle.green,
        custom_id="player_two",
        disabled=True,
    )
    async def player_two(self, i: discord.Interaction, _: ui.Button):
        modal = GuessNumModal(False, self)
        await i.response.send_modal(modal)


class GuessNumModal(ui.Modal):
    number = ui.TextInput(placeholder="不可包含0", min_length=4, max_length=4, label="輸入數字")

    def __init__(self, is_p1: bool, guess_num_view: GuessNumView):
        super().__init__(title="輸入自己的數字", timeout=60.0)

        self.is_p1 = is_p1
        self.guess_num_view = guess_num_view

    async def on_submit(self, i: Inter, /) -> None:
        if "0" in self.number.value:
            return await i.response.send_message(
                embed=ErrorEmbed("數字不可包含0"), ephemeral=True
            )
        if not self.number.value.isdigit():
            return await i.response.send_message(
                embed=ErrorEmbed("請勿輸入數字以外的內容"), ephemeral=True
            )

        await i.response.defer(ephemeral=True)

        p1 = self.guess_num_view.authors[0]
        p2 = self.guess_num_view.authors[1]
        if self.is_p1 and i.user.id != self.guess_num_view.authors[0].id:
            return await i.followup.send(
                embed=ErrorEmbed("你不是玩家一", f"{p1.mention} 是玩家一（遊戲發起者）"),
                ephemeral=True,
            )
        elif not self.is_p1 and i.user.id != self.guess_num_view.authors[1].id:
            return await i.followup.send(
                embed=ErrorEmbed("你不是玩家二", f"{p2.mention} 是玩家二"),
                ephemeral=True,
            )

        query = "player_one" if self.is_p1 else "player_two"
        await i.client.pool.execute(
            f"UPDATE guess_num SET {query}_num = $1 WHERE channel_id = $2",
            int(self.number.value),
            self.guess_num_view.channel.id,
        )

        p1_button: ui.Button = discord.utils.get(
            self.guess_num_view.children, custom_id="player_one"  # type: ignore
        )
        p2_button: ui.Button = discord.utils.get(
            self.guess_num_view.children, custom_id="player_two"  # type: ignore
        )
        assert p1_button and p2_button
        if self.is_p1:
            p1_button.disabled = True
            p2_button.disabled = False
        else:
            p2_button.disabled = True

        assert self.guess_num_view.message
        await self.guess_num_view.message.edit(view=self.guess_num_view)

        await i.followup.send(
            embed=DefaultEmbed("設定成功", f"你的數字為 {self.number.value}"), ephemeral=True
        )
        if p1_button.disabled and p2_button.disabled:
            await self.guess_num_view.channel.send(
                content=f"{p1.mention} {p2.mention}",
                embeds=[
                    DefaultEmbed("遊戲開始", "玩家一和玩家二都已設定數字\n直接在此頻道輸入任何四位數字即可開始猜測"),
                    DefaultEmbed(
                        "📕 規則",
                        "鍵入四個數字猜數。\n如果猜對一個數字且位置相同，則得1A\n。如果猜對一個數字，但是位置不同，則得1B。\n例如，如果答案是1234，而你猜4321，則得到0A4B。",
                    ),
                ],
            )
