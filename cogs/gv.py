import random
import typing

import discord
from attrs import define, field
from discord import app_commands, ui
from discord.ext import commands
from seria.utils import split_list_to_chunks

from apps.flow import flow_transaction, get_balance
from dev.model import BotModel, DefaultEmbed, ErrorEmbed, Inter
from utility.paginator import GeneralPaginator

if typing.TYPE_CHECKING:
    import asyncpg


@define
class Giveaway:
    prize: str
    author: int
    prize_num: int
    message_id: int | None = field(default=None)
    participants: list[int] = field(default=[])
    extra_info: str | None = field(default=None)
    bao: int = field(default=0)

    async def create(self, pool: "asyncpg.Pool") -> None:
        await pool.execute(
            """
            INSERT INTO gv (message_id, prize, author, prize_num, participants, extra_info, bao)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            self.message_id,
            self.prize,
            self.author,
            self.prize_num,
            self.participants,
            self.extra_info,
            self.bao,
        )

    async def update_participants(self, pool: "asyncpg.Pool") -> None:
        await pool.execute(
            """
            UPDATE gv
            SET participants = $1
            WHERE message_id = $2
            """,
            self.participants,
            self.message_id,
        )

    async def delete(self, pool: "asyncpg.Pool") -> None:
        await pool.execute(
            """
            DELETE FROM gv
            WHERE message_id = $1
            """,
            self.message_id,
        )

    def create_embed(self) -> DefaultEmbed:
        embed = DefaultEmbed(self.prize, "點按 🎉 按鈕來參加抽獎!")
        embed.add_field(name="主辦人", value=f"<@{self.author}>", inline=False)
        embed.add_field(name="獎品數量", value=str(self.prize_num), inline=False)
        if self.extra_info:
            embed.add_field(name="其他資訊", value=self.extra_info, inline=False)
        if self.bao > 0:
            embed.add_field(
                name="暴幣", value=f"參加此抽獎需支付 **{self.bao}** 暴幣", inline=False
            )
            embed.add_field(
                name="募得的總暴幣數",
                value=f"**{self.bao * len(self.participants)}** 暴幣",
                inline=False,
            )

        return embed


class GiveAwayView(ui.View):
    def __init__(
        self,
        gv: Giveaway,
    ) -> None:
        super().__init__(timeout=None)
        self.gv = gv

    async def update_embed_and_view(self, i: discord.Interaction) -> None:
        embed = self.gv.create_embed()
        await i.response.edit_message(embed=embed, view=self)

    async def announce_winners(self, i: discord.Interaction) -> None:
        winners = random.sample(self.gv.participants, self.gv.prize_num)

        assert i.message, "Interaction message is None"
        embed = i.message.embeds[0]
        embed.color = discord.Color.red()
        embed.clear_fields()
        embed.add_field(name="主辦人", value=f"<@{self.gv.author}>", inline=False)
        embed.add_field(name="得獎者", value="\n".join(f"<@{w}>" for w in winners))

        self.join_gv.disabled = True
        await i.response.edit_message(
            embed=embed, view=self, content="**🎊 抽獎結束! 🎊**"
        )

        winner_mentions = ", ".join(f"<@{w}>" for w in winners)
        winner_embed = DefaultEmbed(
            description=f"恭喜 {winner_mentions} 贏得了 [{self.gv.prize}]({i.message.jump_url})!"
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

        if self.gv.bao > 0 and i.user.id not in self.gv.participants:
            bao = await get_balance(i.user.id, i.client.pool)
            if bao < self.gv.bao:
                embed = ErrorEmbed(
                    "暴幣不足",
                    f"你的暴幣不足以參加此抽獎\n需要 **{self.gv.bao}** 暴幣,你現在有 **{bao}** 暴幣",
                )
                return await i.response.send_message(embed=embed, ephemeral=True)

        if i.user.id in self.gv.participants:
            self.gv.participants.remove(i.user.id)
            await flow_transaction(i.user.id, self.gv.bao, i.client.pool)
        else:
            self.gv.participants.append(i.user.id)
            await flow_transaction(i.user.id, -self.gv.bao, i.client.pool)

        button.label = str(len(self.gv.participants))
        await self.gv.update_participants(i.client.pool)
        await self.update_embed_and_view(i)

    @ui.button(
        label="參加者",
        style=discord.ButtonStyle.grey,
        custom_id="participants_gv",
        emoji="👥",
    )
    async def participants_gv(self, i: discord.Interaction, _: ui.Button) -> None:
        if not self.gv.participants:
            embed = ErrorEmbed("沒有參加者", "當前沒有任何人參加抽獎")
            await i.response.send_message(embed=embed, ephemeral=True)
        else:
            # 10 participants per embed
            embeds: list[discord.Embed] = []
            participants = split_list_to_chunks(self.gv.participants.copy(), 10)
            index = 1
            for div in participants:
                embed = DefaultEmbed("參加者")
                embed.description = ""
                for p in div:
                    embed.description += f"{index}. <@{p}>\n"
                    index += 1
                embed.description += f"\n共 **{len(self.gv.participants)}** 位參加者"
                embeds.append(embed)

            await GeneralPaginator(i, embeds).start(ephemeral=True)

    @ui.button(label="結束抽獎", style=discord.ButtonStyle.red, custom_id="end_gv")
    async def end_gv(self, i: discord.Interaction, button: ui.Button) -> None:
        if i.user.id != self.gv.author:
            embed = ErrorEmbed(
                "你不是主辦人,無法結束抽獎", f"主辦人: <@{self.gv.author}>"
            )
            await i.response.send_message(embed=embed, ephemeral=True)
        elif not self.gv.participants:
            embed = ErrorEmbed("沒有參加者", "當前沒有任何人參加抽獎,無法結束抽獎")
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
            embed = ErrorEmbed(
                "你不是主辦人,無法重新抽獎", f"主辦人: <@{self.view.gv.author}>"
            )
            await i.response.send_message(embed=embed, ephemeral=True)
        else:
            await self.view.announce_winners(i)


class GiveAwayCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot: BotModel = bot

    async def cog_load(self) -> None:
        rows = await self.bot.pool.fetch("SELECT * FROM gv")
        for row in rows:
            gv = Giveaway(**row)
            self.bot.add_view(GiveAwayView(gv), message_id=gv.message_id)

    @app_commands.rename(
        prize="獎品名稱", prize_num="獎品數量", extra_info="其他資訊", bao="暴幣"
    )
    @app_commands.describe(
        prize="要抽獎的獎品名稱",
        prize_num="要抽獎的獎品數量",
        extra_info="其他資訊 (選填)",
        bao="參加此抽獎需要支付的暴幣數量 (選填)",
    )
    @app_commands.command(name="gv", description="開始一個抽獎")
    async def gv(
        self,
        i: discord.Interaction,
        prize: str,
        prize_num: app_commands.Range[int, 0],
        extra_info: str | None = None,
        bao: app_commands.Range[int, 0] | None = 0,
    ) -> None:
        if i.channel and i.channel.id != 1084301366031302656:
            await i.response.send_message(
                "請在 <#1084301366031302656> 頻道使用此指令", ephemeral=True
            )
            return

        gv = Giveaway(prize, i.user.id, prize_num, extra_info=extra_info, bao=bao or 0)
        view = GiveAwayView(gv)
        await i.response.send_message(embed=gv.create_embed(), view=view)
        gv.message_id = (await i.original_response()).id
        await gv.create(self.bot.pool)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GiveAwayCog(bot))
