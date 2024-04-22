import discord
from discord.ext import commands

from dev.model import BotModel


class ZZZStatusCog(commands.Cog):
    def __init__(self, bot):
        self.bot: BotModel = bot
        self.channel_id = 1232100232255373403
        self.user_ids = {410036441129943050, 546588835018964994}

    async def _send_start_playing_msg(self, user: discord.Member):
        channel = self.bot.get_channel(self.channel_id)
        if not isinstance(channel, discord.TextChannel):
            return
        await channel.send(f"{user.mention} started playing ZZZ")

    async def _send_stop_playing_msg(self, user: discord.Member):
        channel = self.bot.get_channel(self.channel_id)
        if not isinstance(channel, discord.TextChannel):
            return
        await channel.send(f"{user.mention} stopped playing ZZZ")

    @commands.Cog.listener()
    async def on_presence_update(self, before: discord.Member, after: discord.Member):
        if before.id not in self.user_ids:
            return

        in_before = False
        in_after = False

        for activity in before.activities:
            if isinstance(activity, discord.Game) and (
                "Zenless Zone Zero" in activity.name or "BlueStacks" in activity.name
            ):
                in_before = True
                break

        for activity in after.activities:
            if isinstance(activity, discord.Game) and (
                "Zenless Zone Zero" in activity.name or "BlueStacks" in activity.name
            ):
                in_after = True
                break

        if in_before and not in_after:
            await self._send_stop_playing_msg(after)
        elif not in_before and in_after:
            await self._send_start_playing_msg(after)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ZZZStatusCog(bot))
