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
    async def on_message(self, message: discord.Message):
        if (
            message.guild is None
            or message.author.bot
            or message.guild.id != self.bot.guild_id
            or message.channel.id != 1093484799278190673
            or not message.content.isdigit()
            or not isinstance(message.author, discord.Member)
        ):
            return

        uid = message.content
        if len(uid) != 9:
            return await message.reply(
                embed=model.ErrorEmbed("UID 是一個 9 位數的數字"), delete_after=10
            )
        if not uid.startswith("9"):
            return await message.reply(
                embed=model.ErrorEmbed("UID 開頭必須是 9"), delete_after=10
            )

        await message.reply(embed=model.DefaultEmbed("UID 正確", f"UID: {uid}"))
        traveler = message.guild.get_role(1061880147952812052)
        if traveler is None:
            raise ValueError("Traveler role not found")
        await message.author.add_roles(traveler)

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

    @commands.is_owner()
    @commands.command(name="welcome")
    async def welcome(self, ctx: commands.Context):
        content = "旅行者們，歡迎來到「往生堂專業團隊」。\n在這裡你能收到提瓦特的二手消息, 還能找到志同道合的旅行者結伴同行。\n準備好踏上旅途了嗎? 出發前請先閱讀下方的「旅行者須知」。\n"
        rules = model.DefaultEmbed(
            "🔖 旅行者須知",
            """
            ⚠️ 觸犯以下任何一條規則將予以處分:
            
            1. 惡意滋擾群友 (包括引戰、霸凌、發布垃圾訊息等)
            2. 交易遊戲帳號、外掛
            3. 張貼侵權網址或載點
            4. 在 <#1061898394446069852> 以外發表色情或大尺度內容
            5. 假冒他人身份 
            """,
        )
        view = self.accept_view
        await ctx.send(content=content, embed=rules, view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WelcomeCog(bot))  # type: ignore
