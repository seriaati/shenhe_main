import typing
import uuid

import discord
from discord import ui

from dev.model import BaseView, DefaultEmbed, ErrorEmbed, Inter


class GuessNumView(BaseView):
    def __init__(
        self,
        embed: discord.Embed,
        authors: typing.Tuple[discord.Member, discord.Member],
        flow: typing.Optional[int] = None,
    ):
        super().__init__(timeout=600.0)
        self.embed = embed
        self.authors: typing.Tuple[discord.Member, discord.Member] = authors
        self.flow = flow

        self.p1_num: typing.Optional[str] = None
        self.p2_num: typing.Optional[str] = None

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
    number = ui.TextInput(
        placeholder="數字之間不可重複", min_length=4, max_length=4, label="輸入數字"
    )

    def __init__(self, is_p1: bool, gn_view: GuessNumView):
        super().__init__(title="輸入自己的數字", timeout=60.0)

        self.is_p1 = is_p1
        self.gn_view = gn_view

    async def on_submit(self, i: Inter, /) -> None:
        if not self.number.value.isdigit():
            return await i.response.send_message(
                embed=ErrorEmbed("請勿輸入數字以外的內容"), ephemeral=True
            )
        if len(set(self.number.value)) != 4:
            return await i.response.send_message(
                embed=ErrorEmbed("數字之間不可重複", "如：1122, 3344"), ephemeral=True
            )

        await i.response.defer(ephemeral=True)

        p1 = self.gn_view.authors[0]
        p2 = self.gn_view.authors[1]
        if self.is_p1 and i.user.id != self.gn_view.authors[0].id:
            return await i.followup.send(
                embed=ErrorEmbed("你不是玩家一", f"{p1.mention} 是玩家一（遊戲發起者）"),
                ephemeral=True,
            )
        elif not self.is_p1 and i.user.id != self.gn_view.authors[1].id:
            return await i.followup.send(
                embed=ErrorEmbed("你不是玩家二", f"{p2.mention} 是玩家二"),
                ephemeral=True,
            )

        p1_button: ui.Button = discord.utils.get(
            self.gn_view.children, custom_id="player_one"  # type: ignore
        )
        p2_button: ui.Button = discord.utils.get(
            self.gn_view.children, custom_id="player_two"  # type: ignore
        )
        assert p1_button and p2_button
        if self.is_p1:
            p1_button.disabled = True
            p2_button.disabled = False
        else:
            p2_button.disabled = True

        assert self.gn_view.message
        await self.gn_view.message.edit(view=self.gn_view)

        embed = self.gn_view.embed
        if self.is_p1:
            embed.set_field_at(
                0,
                name="玩家一",
                value=f"{p1.mention} - **設定完成**",
                inline=False,
            )
        else:
            embed.set_field_at(
                1,
                name="玩家二",
                value=f"{p2.mention} - **設定完成**",
                inline=False,
            )
        await i.edit_original_response(embed=embed)

        await i.followup.send(
            embed=DefaultEmbed("設定成功", f"你的數字為 {self.number.value}"), ephemeral=True
        )
        if p1_button.disabled and p2_button.disabled:
            thread = await self.gn_view.message.create_thread(
                name=f"猜數字-{str(uuid.uuid4())[:4]}"
            )
            await thread.add_user(p1)
            await thread.add_user(p2)
            await i.client.pool.execute(
                """
                INSERT INTO guess_num
                (channel_id, player_one, player_two,
                flow, player_one_num, player_two_num)
                VALUES ($1, $2, $3, $4)
                """,
                thread.id,
                p1.id,
                p2.id,
                self.gn_view.flow,
                self.gn_view.p1_num,
                self.gn_view.p2_num,
            )

            await thread.send(
                content=f"{p1.mention} {p2.mention}",
                embed=DefaultEmbed("遊戲開始", "玩家一和玩家二都已設定數字\n直接在此頻道輸入任何四位數字即可開始猜測"),
            )
