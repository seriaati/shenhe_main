from discord.ext import commands
import discord
from discord import app_commands, ui, utils
import typing
import aiosqlite


class GuessNumView(ui.View):
    def __init__(self, author: discord.Member):
        super().__init__(timeout=60.0)

        self.author = author
        self.message: discord.Message

    async def on_error(
        self, i: discord.Interaction, error: Exception, item: ui.Item[typing.Any], /
    ) -> None:
        await i.response.send_message(f"發生錯誤: {error}", ephemeral=True)

    async def on_timeout(self) -> None:
        await self.message.delete()

    @ui.button(label="玩家一", style=discord.ButtonStyle.primary, custom_id="player_one")
    async def player_one(self, i: discord.Interaction, button: ui.Button):
        modal = GuessNumModal(True, self)
        await i.response.send_modal(modal)

    @ui.button(
        label="玩家二",
        style=discord.ButtonStyle.green,
        custom_id="player_two",
        disabled=True,
    )
    async def player_two(self, i: discord.Interaction, button: ui.Button):
        modal = GuessNumModal(False, self)
        await i.response.send_modal(modal)


class GuessNumModal(ui.Modal):
    number = ui.TextInput(placeholder="不可包含0", min_length=1, max_length=4, label="輸入數字")

    def __init__(self, player_one: bool, guess_num_view: GuessNumView):
        super().__init__(title="輸入自己的數字", timeout=60.0)

        self.player_one = player_one
        self.guess_num_view = guess_num_view

    async def on_submit(self, i: discord.Interaction, /) -> None:
        if "0" in self.number.value:
            return await i.response.send_message("數字不可包含0", ephemeral=True)

        await i.response.defer(ephemeral=True)
        
        if self.player_one and i.user.id != self.guess_num_view.author.id:
            return await i.followup.send("你不是玩家一, 發起挑戰者為玩家一", ephemeral=True)
        elif not self.player_one and i.user.id == self.guess_num_view.author.id:
            return await i.followup.send("你不是玩家二, 發起挑戰者為玩家一", ephemeral=True)
        
        db: aiosqlite.Connection = i.client.db
        query = "player_one" if self.player_one else "player_two"
        await db.execute(
            f"INSERT INTO guess_num ({query}, {query}_number) VALUES (?, ?)",
            (i.user.id, int(self.number.value)),
        )
        await db.commit()

        if self.player_one:
            player_one_button = utils.get(
                self.guess_num_view.children, custom_id="player_one"
            )
            player_one_button.disabled = True
            
            player_two_button = utils.get(
                self.guess_num_view.children, custom_id="player_two"
            )
            player_two_button.disabled = False
            
            await self.guess_num_view.message.edit(view=self.guess_num_view)
        
        await i.followup.send(f"設定成功, 你的數字為 {self.number.value}", ephemeral=True)

def return_a_b(answer: str, guess: str):
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
    def __init__(self, bot):
        self.bot: commands.Bot = bot
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        
        if not message.content.isdigit():
            return

        if message.channel.id != 1063136363190419476:
            return
        
        db: aiosqlite.Connection = self.bot.db
        async with db.execute("SELECT * FROM guess_num") as cursor:
            row = await cursor.fetchone()
            if not row:
                return
        
        player_one = row[0]
        player_one_num = row[1]
        player_two = row[2]
        player_two_num = row[3]
        
        answer = None
        if message.author.id == player_one:
            answer = player_two_num
        elif message.author.id == player_two:
            answer = player_one_num
        
        if answer:
            a,b = return_a_b(answer, message.content)
            await message.reply(f"{a}A{b}B")
        
            if a == 4:
                await message.reply("恭喜答對")
                await db.execute("DELETE FROM guess_num WHERE player_one = ? AND player_two = ?", (player_one, player_two))
                await db.commit()
            
    @app_commands.command(name="guess-num", description="猜數字遊戲")
    async def guess_num(self, i: discord.Interaction):
        db: aiosqlite.Connection = i.client.db
        await db.execute(
            "CREATE TABLE IF NOT EXISTS guess_num (player_one INTEGER, player_one_number INTEGER, player_two INTEGER, player_two_number INTEGER)"
        )
        await db.execute("DELETE FROM guess_num")
        await db.commit()

        view = GuessNumView(i.user)
        await i.response.send_message("請設定雙方數字", view=view)
        view.message = await i.original_response()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GuessNumCog(bot))
