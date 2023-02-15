from discord.ext import commands, tasks
import datetime

class Schedule(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    async def cog_load(self):
        guild = self.bot.get_guild(1061877505067327528)
        self.notif_channel = guild.get_channel(1075025670981296211)
        
        self.notif_task.start()
    
    @tasks.loop(hours=1)
    async def notif_task(self):
        now = datetime.datetime.now()
        
        # every week's monday
        if now.weekday() == 0 and now.hour == 4:
            await self.notif_channel.send("<@&1075026929448652860>\n 💙 今天是藍色星期一，一週的開始，記得打原神週本喔！")
            await self.notif_channel.send("<@&1075027016132345916>\n 🃏 牌友們，今天又有新的對手啦！")
            await self.notif_channel.send("<@&1075027081007452160>\n 😣 原神裡的居民們需要幫助！記得去幫忙喔！")
        
        # every month's 1st and 16th
        if now.day in (1, 16) and now.hour == 4:
            await self.notif_channel.send("<@&1075027095786365009>\n 🌙 深淵玩家們，開幹啦！！！（有原石喔 owob）")
            if now.day == 1:
                await self.notif_channel.send("<@&1075027124454440992>\n 🎉 今天是月初，記得去兌換粉球哦！")
        
        

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Schedule(bot))