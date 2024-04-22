import logging
import random

import discord
from discord.ext import commands

import dev.model as model
from apps.flow import register_account, remove_account
from data.constants import welcome_strs
from ui.welcome import AcceptRules, Welcome
from utility.utils import default_embed


class WelcomeCog(commands.Cog):
    def __init__(self, bot: model.BotModel) -> None:
        self.bot = bot
        self.accept_view = AcceptRules()
        self.bot.add_view(self.accept_view)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if member.guild.id != self.bot.guild_id:
            return

        logging.info(f"discord.Member {member} left the server")
        await remove_account(member.id, self.bot.pool)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.guild.id != self.bot.guild_id or self.bot.debug:
            return

        traveler = before.guild.get_role(1061880147952812052)
        if traveler not in before.roles and traveler in after.roles:
            await register_account(after.id, self.bot.pool)
            public = after.guild.get_channel(1061881312790720602)
            assert isinstance(public, discord.TextChannel)
            view = Welcome(after)
            welcome_str = random.choice(welcome_strs)
            embed = default_embed(
                f"歡迎 {after.name} !", f"歡迎來到往生堂專業團隊(๑•̀ω•́)ノ\n {welcome_str}"
            )
            embed.set_thumbnail(url=after.avatar)
            await public.send(content=after.mention, embed=embed, view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WelcomeCog(bot))  # type: ignore
