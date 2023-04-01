from random import randint

import discord
from discord import app_commands
from discord.ext import commands

from dev.model import BotModel, DefaultEmbed, ErrorEmbed, Inter
from ui.guess_num import GuessNumView


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


class GuessNumCog(commands.Cog):
    def __init__(self, bot: BotModel):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if (
            message.author.bot
            or not message.content.isdigit()
            or not isinstance(message.channel, discord.Thread)
            or "猜數字" not in message.channel.name
        ):
            return

        row = await self.bot.pool.fetchrow(
            "SELECT * FROM guess_num WHERE channel_id = $1 AND player_one_num IS NOT NULL AND player_two_num IS NOT NULL",
            message.channel.id,
        )
        if row is None:
            return

        p1: int = row["player_one"]
        p1_num: int = row["player_one_num"]
        p1_guess: int = row["player_one_guess"]
        p2: int = row["player_two"]
        p2_num: int = row["player_two_num"]
        p2_guess: int = row["player_two_guess"]

        if p2_guess + 1 > p1_guess and message.author.id != p1:
            return await message.reply(embed=ErrorEmbed("現在是輪到玩家一猜測"))
        if p1_guess + 1 > p2_guess + 1 and message.author.id != p2:
            return await message.reply(embed=ErrorEmbed("現在是輪到玩家二猜測"))

        answer = None
        is_p_one = False
        guess = "?"
        if message.author.id == p1:
            answer = str(p2_num)
            guess = p1_guess + 1
            is_p_one = True
        elif message.author.id == p2:
            answer = str(p1_num)
            guess = p2_guess + 1

        if answer:
            query = "player_one" if is_p_one else "player_two"
            await self.bot.pool.execute(
                f"UPDATE guess_num SET {query}_guess = {query}_guess + 1 WHERE channel_id = $1",
                message.channel.id,
            )
            a, b = return_a_b(answer, message.content)
            await message.reply(embed=DefaultEmbed(f"{a}A{b}B", f"第{guess}次猜測"))

            if a == 4:
                await message.reply(
                    embed=DefaultEmbed(
                        "恭喜答對, 遊戲結束, 資料已刪除",
                        f"玩家一: {p1_num}\n 玩家二: {p2_num}",
                    )
                )
                await self.bot.pool.execute(
                    "DELETE FROM guess_num WHERE channel_id = $1", message.channel.id
                )
                await message.channel.edit(name="猜數字-已結束", locked=True, archived=True)

    @app_commands.command(name="guess-num", description="猜數字遊戲")
    @app_commands.guild_only()
    @app_commands.rename(opponent="對手")
    @app_commands.describe(opponent="猜數字的對手（玩家二）")
    async def guess_num(self, inter: discord.Interaction, opponent: discord.Member):
        i: Inter = inter  # type: ignore

        if opponent.bot:
            return await i.response.send_message(
                embed=ErrorEmbed("錯誤", "對手不能是機器人 （雖然那樣會蠻酷的）"), ephemeral=True
            )
        if opponent == i.user:
            return await i.response.send_message(
                embed=ErrorEmbed("錯誤", "對手不能是自己"), ephemeral=True
            )

        view = GuessNumView()
        await i.response.send_message(
            content=f"{i.user.mention} 邀請 {opponent.mention} 來玩猜數字",
            embed=DefaultEmbed(
                "請雙方設定數字",
                f"點按按鈕即可設定數字，玩家二需等待玩家一設定完畢才可設定數字\n\n玩家一: {i.user.mention}\n玩家二: {opponent.mention}",
            ).set_footer(text="設定完後請在討論串中猜測數字"),
            view=view,
            allowed_mentions=discord.AllowedMentions(users=True),
        )
        view.message = await i.original_response()

        assert isinstance(i.user, discord.Member)
        view.authors = (i.user, opponent)

        view.channel = await view.message.create_thread(name=f"猜數字-{randint(100, 999)}")
        await view.channel.add_user(i.user)
        await view.channel.add_user(opponent)

        await i.client.pool.execute(
            "INSERT INTO guess_num (channel_id, player_one, player_two) VALUES ($1, $2, $3)",
            view.channel.id,
            i.user.id,
            opponent.id,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GuessNumCog(bot))  # type: ignore
