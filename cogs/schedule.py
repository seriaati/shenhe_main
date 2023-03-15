import datetime

from discord.ext import commands, tasks
import calendar

from utility.utils import default_embed


class Schedule(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        self.notif_task.start()

    async def cog_unload(self):
        self.notif_task.cancel()

    @tasks.loop(hours=1)
    async def notif_task(self):
        notif_channel = self.bot.get_channel(1075025670981296211)
        now = datetime.datetime.now()

        # every week's monday
        if now.weekday() == 0 and now.hour == 4:
            await notif_channel.send(
                content="<@&1075026929448652860>",
                embed=default_embed("💙 今天是藍色星期一，一週的開始，記得打原神週本喔！"),
            )
            await notif_channel.send(
                content="<@&1075027016132345916>",
                embed=default_embed("🃏 牌友們，今天又有新的對手啦！"),
            )
            await notif_channel.send(
                content="<@&1075027069832015943>",
                embed=default_embed("🛖 原神裡的居民們需要幫助！記得去幫忙喔！"),
            )

        max_day_in_month = calendar.monthrange(now.year, now.month)[1]
        # every month's 1st and 16th
        if now.day in (1, 16) and now.hour == 4:
            await notif_channel.send(
                content="<@&1075027095786365009>",
                embed=default_embed("🌙 深淵玩家們，開幹啦！！\n（有原石喔 owob）"),
            )
            if now.day == 1:
                await notif_channel.send(
                    content="<@&1075027124454440992>",
                    embed=default_embed("🎉 今天是月初，記得去兌換粉球哦！"),
                )
        elif now.day in (max_day_in_month, 15) and now.hour == 4:
            await notif_channel.send(
                content="<@&1075027095786365009>",
                embed=default_embed("🌙 深淵明天重置，還沒打的趕快去打！"),
            )

    @notif_task.before_loop
    async def before_notif_task(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Schedule(bot))
