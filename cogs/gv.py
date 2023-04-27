import random
import typing

import discord
from discord import app_commands, ui
from discord.ext import commands

from dev.model import BotModel, DefaultEmbed, ErrorEmbed, Giveaway, Inter
from utility.paginator import GeneralPaginator


class GiveAwayView(ui.View):
    def __init__(
        self,
        gv: Giveaway,
    ) -> None:
        super().__init__(timeout=None)
        self.gv = gv

    async def update_embed_and_view(self, i: discord.Interaction):
        embed = self.gv.create_embed()
        await i.response.edit_message(embed=embed, view=self)

    async def announce_winners(self, i: discord.Interaction):
        winners = random.sample(self.gv.participants, self.gv.prize_num)

        assert i.message, "Interaction message is None"
        embed = i.message.embeds[0]
        embed.color = discord.Color.red()
        embed.clear_fields()
        embed.add_field(name="主辦人", value=f"<@{self.gv.author}>", inline=False)
        embed.add_field(name="得獎者", value="\n".join(f"<@{w}>" for w in winners))

        self.join_gv.disabled = True
        await i.response.edit_message(embed=embed, view=self, content="**🎊 抽獎結束！ 🎊**")

        winner_mentions = ", ".join(f"<@{w}>" for w in winners)
        winner_embed = DefaultEmbed(
            description=f"恭喜 {winner_mentions} 贏得了 [{self.gv.prize}]({i.message.jump_url})！"
        )
        assert isinstance(
            i.channel, discord.TextChannel
        ), "Interaction channel is not a TextChannel"
        await i.channel.send(
            embed=winner_embed,
            content=f"恭喜 {winner_mentions} 🎉",
        )

    @ui.button(
        style=discord.ButtonStyle.blurple, custom_id="join_gv", emoji="🎉", label="0"
    )
    async def join_gv(self, inter: discord.Interaction, button: ui.Button):
        i: Inter = inter  # type: ignore
        if i.user in self.gv.participants:
            self.gv.participants.remove(i.user)
        else:
            self.gv.participants.append(i.user.id)
        button.label = str(len(self.gv.participants))
        await self.gv.update_db(i.client.pool)
        await self.update_embed_and_view(i)

    @ui.button(
        label="參加者",
        style=discord.ButtonStyle.grey,
        custom_id="participants_gv",
        emoji="👥",
    )
    async def participants_gv(self, i: discord.Interaction, _: ui.Button):
        if not self.gv.participants:
            embed = ErrorEmbed("沒有參加者", "當前沒有任何人參加抽獎")
            await i.response.send_message(embed=embed, ephemeral=True)
        else:
            # 10 participants per embed
            embeds: typing.List[discord.Embed] = []
            for index in range(0, len(self.gv.participants), 10):
                description = "\n".join(
                    f"<@{p}>" for p in self.gv.participants[index : index + 5]
                )
                embed = DefaultEmbed(
                    "參加者",
                    f"{description}\n\n共 **{len(self.gv.participants)}** 位參加者",
                )
                embeds.append(embed)

            await GeneralPaginator(i, embeds).start(ephemeral=True)

    @ui.button(label="結束抽獎", style=discord.ButtonStyle.red, custom_id="end_gv")
    async def end_gv(self, i: discord.Interaction, button: ui.Button):
        if i.user.id != self.gv.author:
            embed = ErrorEmbed("你不是主辦人，無法結束抽獎", f"主辦人: <@{self.gv.author}>")
            await i.response.send_message(embed=embed, ephemeral=True)
        else:
            if not self.gv.participants:
                embed = ErrorEmbed("沒有參加者", "當前沒有任何人參加抽獎，無法結束抽獎")
                await i.response.send_message(embed=embed, ephemeral=True)
            else:
                self.remove_item(button)
                await self.announce_winners(i)
                self.add_item(RerollWinners())
                await i.edit_original_response(view=self)


class RerollWinners(ui.Button):
    def __init__(self) -> None:
        super().__init__(
            label="重新抽獎",
            style=discord.ButtonStyle.green,
            custom_id="reroll_winners",
            emoji="🎲",
        )
        self.view: GiveAwayView

    async def callback(self, i: discord.Interaction) -> typing.Any:
        if i.user.id != self.view.gv.author:
            embed = ErrorEmbed("你不是主辦人，無法重新抽獎", f"主辦人: <@{self.view.gv.author}>")
            await i.response.send_message(embed=embed, ephemeral=True)
        else:
            await self.view.announce_winners(i)


class GiveAwayCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot: BotModel = bot

    async def cog_load(self):
        await self.bot.wait_until_ready()
        rows = await self.bot.pool.fetch("SELECT * FROM gv")
        for row in rows:
            gv = Giveaway(**row)
            self.bot.add_view(GiveAwayView(gv), message_id=gv.message_id)

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
        if i.channel and i.channel.id != 1084301366031302656:
            await i.response.send_message(
                "請在 <#1084301366031302656> 頻道使用此指令", ephemeral=True
            )
            return

        gv = Giveaway(prize, i.user.id, prize_num, extra_info=extra_info)
        view = GiveAwayView(gv)
        await i.response.send_message(embed=gv.create_embed(), view=view)
        gv.message_id = (await i.original_response()).id
        await gv.insert_to_db(self.bot.pool)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GiveAwayCog(bot))
