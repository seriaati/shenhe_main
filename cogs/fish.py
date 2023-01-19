import asyncio
import random
from random import randint
from typing import List

import aiosqlite
from discord import ButtonStyle, Interaction, Message, Thread
from discord.ext import commands
from discord.ui import Button

from apps.flow import flow_transaction, get_user_flow
from data.fish.fish_data import fish_data
from debug import DefaultView
from utility.utils import ayaaka_embed


class FishCog(commands.Cog):
    def __init__(self, bot):
        self.bot: commands.Bot = bot
        self.debug_toggle = self.bot.debug_toggle

    def generate_fish_embed(self, fish: str, group: bool):  # 製造摸魚embed
        flow = fish_data[fish]["flow"]
        adj_list = [
            "可愛",
            "奇怪",
            "神奇",
            "變態",
            "色色",
            "野生",
            "開心",
            "傷心",
            "生氣",
            "長長",
            "短短",
            "大大",
            "小小",
        ]

        group_str = "一群" if group else ""
        fish_adj = "十分可愛" if fish_data[fish]["cute"] else random.choice(adj_list)
        fish_name = f"**{fish_adj}的{fish}**"
        if group or fish_data[fish]["type_0"]:
            result = ayaaka_embed(
                group_str + fish_name,
                f"是{group_str}{fish_name}! 要摸摸看嗎?\n"
                f"摸{group_str}{fish_name}有機率獲得 {'5' if group else flow} flow幣",
            )
            # e.g. 是(一群)可愛的鮭魚！要摸摸看嗎?
            # 摸鮭魚有機率獲得 2 flow幣
        else:
            result = ayaaka_embed(
                group_str + fish_name,
                f"是{fish_name}! 要摸摸看嗎?\n" f"摸{fish_name}有機率獲得或損失 {flow} flow幣",
            )
            # e.g. 是野生的達達利鴨！要摸摸看嗎?
            # 摸達達利鴨有機率獲得或損失 20 flow幣
        result.set_thumbnail(url=fish_data[fish]["image_url"])
        return result, fish_adj

    class OneFish(Button):  # 摸魚按鈕
        def __init__(self, db: aiosqlite.Connection, fish_name: str):
            super().__init__(style=ButtonStyle.blurple, label=f"撫摸{fish_name}")

            self.fish_name = fish_name
            self.db = db

        async def callback(self, i: Interaction):
            self.view: FishCog.TouchFish
            self.view.stop()

            await i.response.defer()

            fish = fish_data[self.fish_name]
            flow = fish["flow"]
            image_url = fish["image_url"]

            value = randint(1, 100)  # Picks a random number from 1 - 100

            if fish["type_0"]:
                if value <= 50:
                    await flow_transaction(i.user.id, int(flow), self.db)

                    embed = ayaaka_embed(
                        f"✅ {i.user.display_name} 摸到了!!",
                        f"{i.user.mention} 摸 **{self.fish_name}** 摸到 **__{flow}__** flow幣!",
                    )
                else:
                    embed = ayaaka_embed(
                        f"⛔ {i.user.display_name} 沒摸到...",
                        f"{i.user.mention} 單純的摸 **{self.fish_name}** 而已，沒有摸到flow幣!",
                    )
            else:
                verb = fish["verb"]
                if value <= 50:
                    await flow_transaction(i.user.id, int(flow), self.db)

                    embed = ayaaka_embed(
                        f"✅ {i.user.display_name} 摸到了!!",
                        f"{i.user.mention} 摸 **{self.fish_name}** 摸到 **__{flow}__** flow幣!",
                    )
                else:
                    await flow_transaction(i.user.id, -int(flow), self.db)

                    embed = ayaaka_embed(
                        f"⚔️ {i.user.display_name} 被攻擊了 oAo !!",
                        f"{i.user.mention} 被 **{self.fish_name}** {random.choice(verb)}，損失了 **__{flow}__** flow幣!",
                    )

            embed.add_field(
                name="目前 flow 幣",
                value=f"{await get_user_flow(i.user.id, self.db)} flow",
                inline=False,
            )
            embed.set_thumbnail(url=image_url)

            await i.edit_original_response(
                embed=embed,
                view=None,
            )
            await asyncio.sleep(7)
            await i.edit_original_response(
                content=f"**{self.fish_name}** 在被 {i.user.mention} 摸到後默默的游走了...",
                embed=None,
                view=None,
            )
            await asyncio.sleep(5)
            await i.delete_original_response()

    class FishGroup(Button):
        def __init__(self, db: aiosqlite.Connection, fish_name: str):
            super().__init__(style=ButtonStyle.blurple, label=f"撫摸一群{fish_name}")

            self.db = db
            self.fish_name = fish_name
            self.touched: List[int] = []

        async def callback(self, i: Interaction):
            embed = i.message.embeds[0]

            if i.user.id not in self.touched:
                self.touched.append(i.user.id)
                embed.clear_fields()
                embed.add_field(
                    name="摸到的人",
                    value=" ".join(f"<@{i}>" for i in self.touched),
                    inline=False,
                )

                await i.response.edit_message(embed=embed)
            else:
                await i.response.defer()

    class TouchFishView(DefaultView):  # 摸魚view
        def __init__(
            self,
            db: aiosqlite.Connection,
            fish_name: str,
            group: bool,
        ):
            super().__init__(timeout=60.0)
            self.group = group
            self.fish_name = fish_name

            if group:
                self.add_item(FishCog.FishGroup(db, fish_name))
            else:
                self.add_item(FishCog.OneFish(db, fish_name))

        async def on_timeout(self) -> None:
            if self.group:
                self.message: Message
                button: FishCog.FishGroup = self.children[0]
                winners: List[int] = []
                if len(button.touched) < 5:
                    winners.append(random.choice(button.touched))
                else:
                    for _ in range(len(button.touched) // 5):
                        winners.append(random.choice(button.touched))

                embed = self.message.embeds[0]
                embed.title = f"一群**{self.fish_name}**被 {len(button.touched)} 個人摸到了!!"
                embed.clear_fields()
                embed.add_field(
                    name="獲得 5 flow幣的人",
                    value="\n".join([f"<@{winner}>" for winner in winners]),
                    inline=False,
                )
                await self.message.delete()
                message = await self.message.channel.send(embed=embed)
                for winner in winners:
                    await flow_transaction(winner, 5, button.db)
                await asyncio.sleep(7)
                await message.delete()

    @commands.Cog.listener()
    async def on_message(self, message: Message):  # 機率放魚
        if message.author.id == self.bot.user.id:
            return
        if isinstance(message.channel, Thread):
            return
        if message.channel.guild is None:
            return
        if message.channel.name in ["心裡諮商", "練舞室"]:
            return

        rand_int = randint(1, 100)
        if rand_int == 1:
            await self.summon_fish(message, rand_int)

    @commands.is_owner()
    @commands.command(name="fish")
    async def fish(self, ctx: commands.Context, rand_int: int):
        message = await ctx.send("ok")
        await self.summon_fish(message, rand_int)

    async def summon_fish(self, message, rand_int):
        fish = random.choice(list(fish_data.keys()))
        embed, fish_adj = self.generate_fish_embed(fish, rand_int <= 50)
        view = FishCog.TouchFishView(self.bot.db, f"{fish_adj}的{fish}", rand_int <= 50)
        view.message = await message.channel.send(embed=embed, view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(FishCog(bot))
