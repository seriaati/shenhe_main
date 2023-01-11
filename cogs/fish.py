import asyncio
import random
from random import randint

import aiosqlite
from apps.flow import flow_transaction, get_user_flow
from data.fish.fish_data import fish_data
from debug import DefaultView
from discord import (
    ButtonStyle,
    Interaction,
    Member,
    Message,
    Thread,
    User,
    app_commands,
)
from discord.ext import commands
from discord.ui import Button
from utility.utils import ayaaka_embed


class FishCog(commands.Cog):
    def __init__(self, bot):
        self.bot: commands.Bot = bot
        self.debug_toggle = self.bot.debug_toggle

    global adj_list

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

    # fish_type = 1 扣幣
    # fish_type = 0 不扣幣

    def generate_fish_embed(self, fish: str):  # 製造摸魚embed
        flow = fish_data[fish]["flow"]
        fish_adj = random.choice(adj_list) if not fish_data[fish]["cute"] else "十分可愛"
        if fish_data[fish]["type_0"]:
            result = ayaaka_embed(
                fish,
                f"是**{fish_adj}的{fish}**！要摸摸看嗎?\n"
                f"摸**{fish_adj}的{fish}**有機率獲得 {flow} flow幣",
            )
            # e.g. 是可愛的鮭魚！要摸摸看嗎?
            # 摸鮭魚有機率獲得 2 flow幣
        else:
            result = ayaaka_embed(
                fish,
                f"是**{fish_adj}的{fish}**！要摸摸看嗎?\n"
                f"摸**{fish_adj}的{fish}**有機率獲得或損失 {flow} flow幣",
            )
            # e.g. 是野生的達達利鴨！要摸摸看嗎?
            # 摸達達利鴨有機率獲得或損失 20 flow幣
        result.set_thumbnail(url=fish_data[fish]["image_url"])
        return result, fish_adj

    class TouchFishButton(Button):  # 摸魚按鈕
        def __init__(
            self,
            fish: str,
            db: aiosqlite.Connection,
            fish_adj: str,
            author: User | Member,
        ):
            super().__init__(style=ButtonStyle.blurple, label=f"撫摸{fish_adj}的{fish}")
            self.fish = fish
            self.fish_adj = fish_adj
            self.author = author
            self.db = db

        async def callback(self, i: Interaction):
            self.view: FishCog.TouchFish
            self.view.stop()

            await i.response.defer()

            fish = fish_data[self.fish]
            flow = fish["flow"]
            image_url = fish["image_url"]
            fish_name = f"{self.fish_adj}的{self.fish}"

            value = randint(1, 100)  # Picks a random number from 1 - 100

            if fish["type_0"]:
                if value <= 50:
                    await flow_transaction(i.user.id, int(flow), self.db)

                    embed = ayaaka_embed(
                        f"✅ {i.user.display_name} 摸到了!!",
                        f"{i.user.mention} 摸 **{fish_name}** 摸到 **__{flow}__** flow幣!",
                    )
                else:
                    embed = ayaaka_embed(
                        f"⛔ {i.user.display_name} 沒摸到...",
                        f"{i.user.mention} 單純的摸 **{fish_name}** 而已，沒有摸到flow幣!",
                    )
            else:
                verb = fish["verb"]
                if value <= 50:
                    await flow_transaction(i.user.id, int(flow), self.db)

                    embed = ayaaka_embed(
                        f"✅ {i.user.display_name} 摸到了!!",
                        f"{i.user.mention} 摸 **{fish_name}** 摸到 **__{flow}__** flow幣!",
                    )
                else:
                    await flow_transaction(i.user.id, -int(flow), self.db)

                    embed = ayaaka_embed(
                        f"⚔️ {i.user.display_name} 被攻擊了 oAo !!",
                        f"{i.user.mention} 被 **{fish_name}** {random.choice(verb)}，損失了 **__{flow}__** flow幣!",
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
                content=f"**{self.fish_adj}的{self.fish}** 在被 {i.user.mention} 摸到後默默的游走了...",
                embed=None,
                view=None,
            )
            await asyncio.sleep(5)
            await i.delete_original_response()

    class TouchFish(DefaultView):  # 摸魚view
        def __init__(
            self,
            index: str,
            db: aiosqlite.Connection,
            fish_adj: str,
            author: User | Member,
        ):
            super().__init__(timeout=None)
            self.add_item(FishCog.TouchFishButton(index, db, fish_adj, author))

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

        random_number = randint(1, 100)
        if random_number == 1:
            fish = random.choice(list(fish_data.keys()))
            embed, fish_adj = self.generate_fish_embed(fish)
            view = FishCog.TouchFish(fish, self.bot.db, fish_adj, message.author)
            await message.channel.send(embed=embed, view=view)

    # /releasefish
    @app_commands.command(name="releasefish放魚", description="緊急放出一條魚讓人摸")
    @app_commands.rename(fish_type="魚種")
    @app_commands.describe(fish_type="選擇要放出的魚種")
    @app_commands.checks.has_role("小雪團隊")
    async def release_fish(self, i: Interaction, fish_type: str):
        embed, fish_adj = self.generate_fish_embed(fish_type)
        view = FishCog.TouchFish(fish_type, self.bot.db, fish_adj, i.user)
        await i.response.send_message(embed=embed, view=view)

    @release_fish.autocomplete("fish_type")
    async def release_fish_autocomplete(self, i: Interaction, current: str):
        choices = []
        for fish_name, _ in fish_data.items():
            if current in fish_name:
                choices.append(app_commands.Choice(name=fish_name, value=fish_name))
        return choices[:25]


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(FishCog(bot))
    #
