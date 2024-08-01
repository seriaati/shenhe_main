import calendar
import datetime

import discord
from discord.ext import commands, tasks

from utility.utils import default_embed


class Schedule(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.notif_task.start()

    async def cog_unload(self) -> None:
        self.notif_task.cancel()

    @tasks.loop(hours=1)
    async def notif_task(self) -> None:
        notif_channel = self.bot.get_channel(1075025670981296211)
        assert isinstance(notif_channel, discord.TextChannel)
        now = datetime.datetime.now()

        # every week's monday
        if now.weekday() == 0 and now.hour == 4:
            await notif_channel.send(
                content="<@&1075026929448652860>",
                embed=default_embed(
                    "💙 今天是星期一,一週的開始,記得打原神週本喔!",
                    "💙 Today is Monday, start of the week, remember to farm the weekly bosses!",
                ),
            )
            await notif_channel.send(
                content="<@&1075027016132345916>",
                embed=default_embed(
                    "🃏 牌友們,今天又有新的對手啦!",
                    "🃏 TCG players, there are new opponents today!",
                ),
            )
            await notif_channel.send(
                content="<@&1075027069832015943>",
                embed=default_embed(
                    "🛖 原神裡的居民們需要幫助!記得去幫忙喔!",
                    "🛖 The residents in Genshin need your help!",
                ),
            )

        month_max_day = calendar.monthrange(now.year, now.month)[1]
        if now.day == 16 and now.hour == 4:
            await notif_channel.send(
                content="<@&1075027095786365009>",
                embed=default_embed(
                    "🌙 深淵玩家們,開幹啦!!\n(有原石喔 owob)",
                    "🌙 Spiral abyss players, let's go!!\n(There are primogems owob)",
                ),
            )
        elif now.day == 15 and now.hour == 4:
            await notif_channel.send(
                content="<@&1075027095786365009>",
                embed=default_embed(
                    "🌙 深淵明天重置,還沒打的趕快去打!",
                    "🌙 Spiral abyss resets tomorrow, go do it if you haven't!",
                ),
            )
        elif now.day == 1 and now.hour == 4:
            await notif_channel.send(
                content="<@&1075027095786365009>",
                embed=default_embed(
                    "🎭 幻想真境劇詩重置了,快去打!",
                    "🎭 Imaginarium theater resets, go do it!",
                ),
            )
        elif now.day == month_max_day and now.hour == 4:
            await notif_channel.send(
                content="<@&1268514208572506144>",
                embed=default_embed(
                    "🎭 幻想真境劇詩明天重置,還沒打的快去打!",
                    "🎭 Imaginarium theater resets tomorrow, go do it if you haven't!",
                ),
            )
        elif now.day == 1 and now.hour == 4:
            await notif_channel.send(
                content="<@&1075027124454440992>",
                embed=default_embed("🎉 今天是月初,記得去兌換粉球哦!"),
            )

    @notif_task.before_loop
    async def before_notif_task(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Schedule(bot))
