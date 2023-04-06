import asyncio
import typing
import uuid

import discord
from discord import app_commands, utils
from discord.ext import commands

import dev.model as model
from apps.flow import flow_transaction, get_user_flow
from ui.guess_num import GuessNumView
from utility.paginator import GeneralPaginator
from utility.utils import divide_chunks, get_dt_now


def return_a_b(answer: str, guess: str) -> tuple[int, int]:
    """a: 猜對位置, b: 猜對數字

    Args:
        answer (str): 正確答案
        guess (str): 猜測答案

    Returns:
        tuple[int, int]: A 和 B
    """
    a = 0
    b = 0
    for char in answer:
        if char in guess:
            if answer.index(char) == guess.index(char):
                a += 1
            else:
                b += 1
    return a, b


class GuessNumCog(commands.GroupCog, name="gn"):
    def __init__(self, bot):
        self.bot: model.BotModel = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if (
            message.author.bot
            or not message.content.isdigit()
            or not isinstance(message.channel, discord.Thread)
            or "猜數字" not in message.channel.name
            or len(set(message.content)) != 4
        ):
            return

        row = await self.bot.pool.fetchrow(
            "SELECT * FROM guess_num WHERE channel_id = $1 AND player_one_num IS NOT NULL AND player_two_num IS NOT NULL",
            message.channel.id,
        )
        if row is None:
            return
        match = model.GuessNumMatch.from_row(row)

        if match.p2_guess + 1 > match.p1_guess and message.author.id != match.p1:
            return await message.reply(embed=model.ErrorEmbed("現在是輪到玩家一猜測"))
        if match.p1_guess + 1 > match.p2_guess + 1 and message.author.id != match.p2:
            return await message.reply(embed=model.ErrorEmbed("現在是輪到玩家二猜測"))

        answer = None
        is_p1 = False
        guess = "?"
        if message.author.id == match.p1:
            answer = match.p2_num
            guess = match.p1_guess + 1
            is_p1 = True
        elif message.author.id == match.p2:
            answer = match.p1_num
            guess = match.p2_guess + 1

        if answer:
            query = "player_one" if is_p1 else "player_two"
            await self.bot.pool.execute(
                f"UPDATE guess_num SET {query}_guess = {query}_guess + 1 WHERE channel_id = $1",
                message.channel.id,
            )
            a, b = return_a_b(answer, message.content)
            await message.reply(embed=model.DefaultEmbed(f"{a}A{b}B", f"第{guess}次猜測"))

            if a == 4:
                embed = model.DefaultEmbed(
                    "恭喜答對, 遊戲結束",
                    f"玩家一: {match.p1_num}\n 玩家二: {match.p2_num}",
                )
                embed.set_footer(text="此討論串將在十分鐘後關閉")
                if match.flow:
                    embed.add_field(name="賭注", value=f"{match.flow}暴幣")
                    embed.set_footer(text="暴幣已經轉入獲勝者的帳戶")
                await message.reply(embed=embed)
                if match.flow:
                    await flow_transaction(
                        match.p1, match.flow if is_p1 else -match.flow, self.bot.pool
                    )
                    await flow_transaction(
                        match.p2,
                        match.flow if not is_p1 else -match.flow,
                        self.bot.pool,
                    )

                await self.bot.pool.execute(
                    "DELETE FROM guess_num WHERE channel_id = $1", message.channel.id
                )
                await self.bot.pool.execute(
                    "INSERT INTO gn_history (p1, p2, p1_win, time, flow) VALUES ($1, $2, $3, $4, $5)",
                    match.p1,
                    match.p2,
                    is_p1,
                    get_dt_now(),
                    match.flow,
                )

                await self.bot.pool.execute(
                    "INSERT INTO gn_win_lose (user_id, win, lose) VALUES ($1, $2, $3) ON CONFLICT (user_id) DO UPDATE SET win = gn_win_lose.win + $2, lose = gn_win_lose.lose + $3",
                    match.p1,
                    1 if is_p1 else 0,
                    1 if not is_p1 else 0,
                )
                await self.bot.pool.execute(
                    "INSERT INTO gn_win_lose (user_id, win, lose) VALUES ($1, $2, $3) ON CONFLICT (user_id) DO UPDATE SET win = gn_win_lose.win + $2, lose = gn_win_lose.lose + $3",
                    match.p2,
                    1 if not is_p1 else 0,
                    1 if is_p1 else 0,
                )

                await asyncio.sleep(600.0)
                await message.channel.delete()

    @app_commands.guild_only()
    @app_commands.command(name="start", description="猜數字遊戲")
    @app_commands.rename(opponent="對手", flow="賭注")
    @app_commands.describe(opponent="猜數字的對手（玩家二）", flow="要下賭的暴幣數量")
    async def start(
        self,
        inter: discord.Interaction,
        opponent: discord.Member,
        flow: typing.Optional[int] = None,
    ):
        i: model.Inter = inter  # type: ignore

        user_flow = await get_user_flow(i.user.id, self.bot.pool)
        if flow and flow > user_flow:
            return await i.response.send_message(
                embed=model.ErrorEmbed("你擁有的暴幣不足以承擔這個賭注", f"所需暴幣: {flow}"),
                ephemeral=True,
            )

        if opponent.bot:
            return await i.response.send_message(
                embed=model.ErrorEmbed("錯誤", "對手不能是機器人 （雖然那樣會蠻酷的）"), ephemeral=True
            )
        if opponent == i.user:
            return await i.response.send_message(
                embed=model.ErrorEmbed("錯誤", "對手不能是自己"), ephemeral=True
            )

        embed = model.DefaultEmbed(
            "請雙方設定數字",
            "點按按鈕即可設定數字，玩家二需等待玩家一設定完畢才可設定數字",
        )
        embed.set_footer(text="設定完後請在討論串中猜測數字")
        embed.add_field(name="玩家一", value=f"{i.user.mention} - *設定中...*", inline=False)
        embed.add_field(
            name="玩家二", value=f"{opponent.mention} - *設定中...*", inline=False
        )
        if flow:
            embed.add_field(name="賭注", value=f"{flow} 暴幣", inline=False)

        view = GuessNumView(embed)

        await i.response.send_message(
            content=f"{i.user.mention} 邀請 {opponent.mention} 來玩猜數字",
            embed=embed,
            view=view,
            allowed_mentions=discord.AllowedMentions(users=True),
        )
        view.message = await i.original_response()

        assert isinstance(i.user, discord.Member)
        view.authors = (i.user, opponent)

        view.channel = await view.message.create_thread(
            name=f"猜數字-{str(uuid.uuid4())[:4]}"
        )
        await view.channel.add_user(i.user)
        await view.channel.add_user(opponent)

        await i.client.pool.execute(
            "INSERT INTO guess_num (channel_id, player_one, player_two, flow) VALUES ($1, $2, $3, $4)",
            view.channel.id,
            i.user.id,
            opponent.id,
            flow,
        )

    @app_commands.guild_only()
    @app_commands.command(name="rules", description="查看猜數字遊戲規則")
    async def rule(self, inter: discord.Interaction):
        i: model.Inter = inter  # type: ignore
        embed = model.DefaultEmbed(
            description="""
            開始： `/gn start <對手>`
            雙方各設定一個四位數字，數字之間不可重複，可包含0。
            例如 1234、5678、9012、3456、7890等等。
            
            猜數：在討論串中進行
            鍵入 __四個數字__ 猜數。
            如果猜對一個數字且位置相同，則得 **1A**
            如果猜對一個數字，但是位置不同，則得 **1B**
            例如，如果答案是1234，而你猜4321，則得到0A4B。
            """,
        ).set_author(name="📕 規則")

        await i.response.send_message(embed=embed)

    @app_commands.guild_only()
    @app_commands.command(name="leaderboard", description="查看猜數字遊戲排行榜")
    async def leaderboard(self, inter: discord.Interaction):
        i: model.Inter = inter  # type: ignore
        await i.response.defer(thinking=False)

        rows = await i.client.pool.fetch("SELECT * FROM gn_win_lose")
        all_players: typing.List[model.GuessNumPlayer] = [
            model.GuessNumPlayer.from_row(row) for row in rows
        ]
        # sort by win_rate attribute, desc
        all_players = sorted(all_players, key=lambda x: x.win_rate, reverse=True)
        div_players = divide_chunks(all_players, 10)

        embeds: typing.List[discord.Embed] = []
        rank = 0
        player_rank = None
        for players in div_players:
            embed = model.DefaultEmbed()
            embed.description = ""
            embed.set_author(name="🏆 猜數字排行榜")
            for player in players:
                rank += 1
                if player.user_id == i.user.id:
                    player_rank = rank

                embed.description += f"{rank}. <@{player.user_id}> {player.win}勝{player.lose}敗 ({player.win / (player.win + player.lose) * 100:.2f}%)\n"
            embeds.append(embed)
        for embed in embeds:
            embed.set_footer(text=f"你的排名：{player_rank}")

        if not embeds:
            return await i.followup.send(
                embed=model.ErrorEmbed("錯誤", "目前沒有排行榜資料"), ephemeral=True
            )

        await GeneralPaginator(i, embeds).start(followup=True)

    @app_commands.guild_only()
    @app_commands.rename(member="玩家")
    @app_commands.describe(member="要查看的玩家")
    @app_commands.command(name="history", description="查看猜數字對戰紀錄")
    async def history(
        self, inter: discord.Interaction, member: typing.Optional[discord.Member] = None
    ):
        i: model.Inter = inter  # type: ignore
        assert isinstance(i.user, discord.Member) and i.guild
        member = member or i.user
        await i.response.defer(thinking=False)

        rows = await self.bot.pool.fetch(
            "SELECT * FROM gn_history WHERE p1 = $1 OR p2 = $1 ORDER by time DESC",
            member.id,
        )
        histories: typing.List[model.GuessNumHistory] = [
            model.GuessNumHistory.from_row(row) for row in rows
        ]
        div_histories = divide_chunks(histories, 10)

        embeds: typing.List[discord.Embed] = []
        for histories in div_histories:
            embed = model.DefaultEmbed()
            embed.set_author(name=f"📜 {member.display_name} 的對戰紀錄")
            for history in histories:
                p1 = i.guild.get_member(history.p1) or await i.guild.fetch_member(
                    history.p1
                )
                p2 = i.guild.get_member(history.p2) or await i.guild.fetch_member(
                    history.p2
                )
                p1_name = (
                    f"{p1.display_name} （勝）" if history.p1_win else p1.display_name
                )
                p2_name = (
                    f"{p2.display_name} （勝）" if not history.p1_win else p2.display_name
                )
                flow = f"賭注: **{history.flow}暴幣**" if history.flow else ""
                embed.add_field(
                    name=f"{p1_name} vs {p2_name}",
                    value=f"{utils.format_dt(history.match_time)}\n{flow}",
                    inline=False,
                )
            embeds.append(embed)

        if not embeds:
            return await i.followup.send(
                embed=model.ErrorEmbed("錯誤", "你目前沒有對戰紀錄"), ephemeral=True
            )

        await GeneralPaginator(i, embeds).start(followup=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GuessNumCog(bot))  # type: ignore
