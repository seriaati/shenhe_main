import asyncio
from typing import TYPE_CHECKING, Any

from discord import ButtonStyle, Interaction, Member, TextChannel, app_commands
from discord.ext import commands
from discord.ui import Button

from apps.flow import flow_transaction, get_balance, register_account
from apps.roll import RollApp
from data.roll.banner import banner
from dev.model import BaseView
from utility.utils import default_embed, error_embed, log

if TYPE_CHECKING:
    import aiosqlite


class RollCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.debug = self.bot.debug

    class RollView(BaseView):
        def __init__(self, author: Member, db: "aiosqlite.Connection", public: TextChannel) -> None:
            super().__init__(timeout=None)
            self.db = db
            self.roll_app = RollApp(self.db)
            self.author = author
            self.public = public
            self.add_item(RollCog.RollInfo(False))
            self.add_item(RollCog.RollHistory(False))
            self.add_item(RollCog.RollOnce(False))
            self.add_item(RollCog.RollTen(False))

        async def interaction_check(self, i: Interaction) -> bool:
            if i.user.id != self.author.id:
                await i.response.send_message(
                    embed=error_embed().set_author(
                        name="這不是你的祈願視窗", icon_url=i.user.display_avatar.url
                    ),
                    ephemeral=True,
                )
            return i.user.id == self.author.id

    class RollInfo(Button):
        def __init__(self, disabled: bool) -> None:
            super().__init__(label="詳情", disabled=disabled)

        async def callback(self, i: Interaction) -> None:
            embed = default_embed("祈願詳情")
            value = f"70抽之前: {banner['big_prize']['chance']}%\n"
            for guarantee in banner["big_prize_guarantee"]:
                value += f"{guarantee['min']} ~ {guarantee['max']} 抽: {guarantee['new_chance']}%\n"
            value += "90 抽: 100%"
            embed.add_field(
                name=f"限定 UP - {banner['big_prize']['name']}", value=value, inline=False
            )
            value = ""
            for prize, chance in banner["other_prizes"].items():
                value += f"{prize}: {chance}%\n"
            embed.add_field(name="其他獎品", value=value, inline=False)
            await i.response.send_message(embed=embed, ephemeral=True)

    class RollHistory(Button):
        def __init__(self, disabled: bool) -> None:
            super().__init__(label="歷史紀錄", disabled=disabled)

        async def callback(self, i: Interaction):
            c: aiosqlite.Cursor = await self.view.db.cursor()
            await c.execute("SELECT prize, count FROM roll_history WHERE user_id = ?", (i.user.id,))
            roll_history = await c.fetchall()
            if len(roll_history) == 0:
                return await i.response.send_message(
                    embed=error_embed().set_author(
                        name="你沒有進行過祈願!", icon_url=i.user.display_avatar.url
                    ),
                    ephemeral=True,
                )
            await c.execute(
                "SELECT SUM (count) FROM roll_guarantee WHERE user_id = ?", (i.user.id,)
            )
            guarantee_sum = (await c.fetchone())[0]
            message = ""
            history_sum = 0
            for _index, tuple in enumerate(roll_history):
                history_sum += tuple[1]
                message += f"{tuple[0]} | {tuple[1]}次\n"
            embed = default_embed(
                f"<:wish:982419859117838386> 祈願紀錄(目前距離保底{90 - guarantee_sum}抽)",
                f"總共{history_sum}抽\n{message}",
            )
            await i.response.send_message(embed=embed, ephemeral=True)

    class RollOnce(Button):
        def __init__(self, disabled: bool) -> None:
            super().__init__(label="祈願 x1", style=ButtonStyle.blurple, disabled=disabled)

        async def callback(self, i: Interaction):
            user_flow = await get_balance(i.user.id, i.client.db)
            if user_flow < banner["one_pull_price"]:
                return await i.response.send_message(
                    embed=error_embed(
                        message=f"**祈願 x1** 需花費 **{banner['one_pull_price']}** 暴幣\n目前: {user_flow}"
                    ).set_author(name="暴幣不足", icon_url=i.user.display_avatar.url),
                    ephemeral=True,
                )
            self.view.clear_items()
            self.view.add_item(RollCog.ConfirmRoll(False))
            self.view.add_item(RollCog.CancelRoll())
            await i.response.edit_message(view=self.view)

    class RollTen(Button):
        def __init__(self, disabled: bool = False) -> None:
            super().__init__(label="祈願 x10", style=ButtonStyle.blurple, disabled=disabled)

        async def callback(self, i: Interaction):
            user_flow = await get_balance(i.user.id, i.client.db)
            if user_flow < 10 * banner["one_pull_price"]:
                return await i.response.send_message(
                    embed=error_embed(
                        message=f"**祈願 x10** 需花費 **{10 * banner['one_pull_price']}** 暴幣\n目前: {user_flow}"
                    ).set_author(name="暴幣不足", icon_url=i.user.display_avatar.url),
                    ephemeral=True,
                )
            self.view.clear_items()
            self.view.add_item(RollCog.ConfirmRoll(True))
            self.view.add_item(RollCog.CancelRoll())
            await i.response.edit_message(view=self.view)

    class ConfirmRoll(Button):
        def __init__(self, is_ten_pull: bool) -> None:
            super().__init__(label="確認", style=ButtonStyle.green)
            self.is_ten_pull = is_ten_pull

        async def callback(self, i: Interaction) -> Any:
            if not self.is_ten_pull:
                await flow_transaction(i.user.id, -banner["one_pull_price"], i.client.db)
            else:
                await flow_transaction(i.user.id, -10 * banner["one_pull_price"], i.client.db)
            prizes = await self.view.roll_app.gu_system(i.user.id, self.is_ten_pull)
            await self.view.roll_app.give_money(i.user.id, prizes)
            if await self.view.roll_app.check_big_prize(i.user.id, prizes):
                log(True, False, "Roll", f"{i.user.id} got big prize")
                await self.view.public.send(f"🎉 恭喜 {i.user.mention} 抽到這期祈願的大獎!! 🎉")
            url, sleep_time = self.view.roll_app.choose_animation(prizes)
            result = await self.view.roll_app.write_history_and_gu(i.user.id, prizes)
            embed = default_embed(banner["name"]).set_image(url=url)
            self.view.clear_items()
            self.view.add_item(RollCog.RollInfo(True))
            self.view.add_item(RollCog.RollHistory(True))
            self.view.add_item(RollCog.RollOnce(True))
            self.view.add_item(RollCog.RollTen(True))
            await i.response.edit_message(embed=embed, view=self.view)
            await asyncio.sleep(sleep_time)
            embed = default_embed(
                "抽卡結果",
                result + f"\n目前 暴幣: {await get_balance(i.user.id, i.client.db)}",
            )
            await i.followup.send(embed=embed, ephemeral=True)
            embed = default_embed(banner["name"]).set_image(url=banner["icon"])
            self.view.clear_items()
            self.view.add_item(RollCog.RollInfo(False))
            self.view.add_item(RollCog.RollHistory(False))
            self.view.add_item(RollCog.RollOnce(False))
            self.view.add_item(RollCog.RollTen(False))
            await i.edit_original_response(embed=embed, view=self.view)

    class CancelRoll(Button):
        def __init__(self) -> None:
            super().__init__(label="取消")

        async def callback(self, i: Interaction) -> None:
            self.view.clear_items()
            self.view.add_item(RollCog.RollInfo(True))
            self.view.add_item(RollCog.RollHistory(True))
            self.view.add_item(RollCog.RollOnce(True))
            self.view.add_item(RollCog.RollTen(True))
            await i.response.edit_message(view=self.view)

    @app_commands.command(name="roll", description="暴幣祈願系統")
    async def roll(self, i: Interaction) -> None:
        check = await register_account(i.user.id, i.client.db)
        if not check:
            await register_account(i.user.id, i.client.db)
        public = (
            i.client.get_channel(916951131022843964)
            if not self.bot.debug
            else i.client.get_channel(909595117952856084)
        )
        view = RollCog.RollView(i.user, self.bot.db, public)
        embed = default_embed(banner["name"])
        embed.set_image(url=banner["icon"])
        await i.response.send_message(embed=embed, view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RollCog(bot))
