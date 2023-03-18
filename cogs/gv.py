import random
import typing

import discord
from discord import app_commands, ui
from discord.ext import commands

from utility.paginators.paginator import GeneralPaginator
from utility.utils import default_embed
import traceback


def create_gv_embed(
    prize: str,
    author: discord.Member,
    prize_num: int,
    extra_info: typing.Optional[str] = None,
) -> discord.Embed:
    embed = default_embed(prize, "點按 🎉 按鈕來參加抽獎！")
    embed.add_field(name="主辦人", value=author.mention, inline=False)
    embed.add_field(name="獎品數量", value=str(prize_num), inline=False)
    if extra_info:
        embed.add_field(name="其他資訊", value=extra_info, inline=False)

    return embed


class GiveAwayView(ui.View):
    def __init__(
        self,
        prize: str,
        author: discord.Member,
        prize_num: int,
        extra_info: typing.Optional[str] = None,
    ) -> None:
        super().__init__(timeout=None)

        self.participants: typing.List[discord.Member] = []
        self.prize = prize
        self.author = author
        self.prize_num = prize_num
        self.extra_info = extra_info

    async def on_error(
        self,
        i: discord.Interaction,
        error: Exception,
        item: ui.Item[typing.Any],
    ) -> None:
        await i.response.send_message(
            f"```py\n{traceback.format_exc()}\n```", ephemeral=True
        )

    async def update_embed_and_view(self, i: discord.Interaction):
        embed = create_gv_embed(
            self.prize, self.author, self.prize_num, self.extra_info
        )
        await i.response.edit_message(embed=embed, view=self)

    async def announce_winners(self, i: discord.Interaction):
        winners = random.sample(self.participants, self.prize_num)

        embed = i.message.embeds[0]
        embed.color = discord.Color.red()
        embed.clear_fields()
        embed.add_field(name="主辦人", value=self.author.mention, inline=False)
        embed.add_field(name="得獎者", value="\n".join(w.mention for w in winners))

        self.join_gv.disabled = True
        await i.response.edit_message(embed=embed, view=self, content="**🎊 抽獎結束！ 🎊**")

        winner_mentions = ", ".join(w.mention for w in winners)
        winner_embed = default_embed(
            message=f"恭喜 {winner_mentions} 贏得了 [{self.prize}]({i.message.jump_url})！"
        )
        await i.channel.send(
            embed=winner_embed,
            content=f"恭喜 {winner_mentions} 🎉",
        )

    @ui.button(
        style=discord.ButtonStyle.blurple, custom_id="join_gv", emoji="🎉", label="0"
    )
    async def join_gv(self, i: discord.Interaction, button: ui.Button):
        if i.user in self.participants:
            self.participants.remove(i.user)
        else:
            self.participants.append(i.user)
        button.label = str(len(self.participants))
        await self.update_embed_and_view(i)

    @ui.button(
        label="參加者",
        style=discord.ButtonStyle.grey,
        custom_id="participants_gv",
        emoji="👥",
    )
    async def participants_gv(self, i: discord.Interaction, _: ui.Button):
        if not self.participants:
            await i.response.send_message("當前沒有任何人參加抽獎", ephemeral=True)
        else:
            # 5 participants per embed
            embeds: typing.List[discord.Embed] = []
            for index in range(0, len(self.participants), 5):
                description = "\n".join(
                    p.mention for p in self.participants[index : index + 5]
                )
                embed = default_embed(
                    "參加者",
                    f"{description}\n\n共 **{len(self.participants)}** 位參加者",
                )
                embeds.append(embed)

            await GeneralPaginator(i, embeds).start(ephemeral=True)

    @ui.button(label="結束抽獎", style=discord.ButtonStyle.red, custom_id="end_gv")
    async def end_gv(self, i: discord.Interaction, button: ui.Button):
        if i.user.id != self.author.id:
            await i.response.send_message("你不是主辦人，無法結束抽獎", ephemeral=True)
        else:
            if not self.participants:
                await i.response.send_message("沒有人參加抽獎，無法結束", ephemeral=True)
            else:
                self.remove_item(button)
                await self.announce_winners(i)
                self.add_item(RerollWinners())
                await i.edit_original_response(view=self)


class RerollWinners(ui.Button[GiveAwayView]):
    def __init__(self) -> None:
        super().__init__(
            label="重新抽獎",
            style=discord.ButtonStyle.green,
            custom_id="reroll_winners",
            emoji="🎲",
        )

    async def callback(self, i: discord.Interaction) -> typing.Any:
        if i.user.id != self.author.id:
            await i.response.send_message("你不是主辦人，無法結束抽獎", ephemeral=True)
        else:
            await self.view.announce_winners(i)


class GiveAwayCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    @app_commands.rename(prize="獎品名稱", prize_num="獎品數量", extra_info="其他資訊")
    @app_commands.describe(
        prize="要抽獎的獎品名稱", prize_num="要抽獎的獎品數量", extra_info="其他資訊 (選填)"
    )
    @app_commands.command(name="gv", description="開始一個抽獎")
    async def gv(
        self,
        i: discord.Interaction,
        prize: str,
        prize_num: int,
        extra_info: typing.Optional[str] = None,
    ):
        embed = create_gv_embed(prize, i.user, prize_num, extra_info)
        view = GiveAwayView(prize, i.user, prize_num, extra_info)
        await i.response.send_message(embed=embed, view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GiveAwayCog(bot))
