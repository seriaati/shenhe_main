import datetime
from typing import Optional, Union

import discord
from discord import app_commands
from discord.ext import commands

from dev.model import BotModel, DefaultEmbed, ErrorEmbed
from utility.utils import get_dt_now


class LevelCog(commands.Cog):
    def __init__(self, bot):
        self.bot: BotModel = bot

    # voice xp level system
    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        if member.bot or not member.guild or before.channel == after.channel:
            return

        await self.create_level_user(member)
        await self.create_voice_user(member)

        # if the user joins a voice channel
        if before.channel is None and after.channel is not None:
            await self.set_joined_at(member, after.channel)

        # if the user leaves a voice channel
        elif before.channel is not None and after.channel is None:
            joined_at = await self.get_joined_at(member)
            if joined_at is None:
                return
            await self.give_voice_xp(member, joined_at)

        # if the user switches voice channels
        elif before.channel is not None and after.channel is not None:
            joined_at = await self.get_joined_at(member)
            if joined_at is None:
                return
            await self.give_voice_xp(member, joined_at)
            await self.set_joined_at(member, after.channel)

    async def create_voice_user(self, member: discord.Member):
        await self.bot.pool.execute(
            """
            INSERT INTO voice_xp (user_id, guild_id)
            VALUES ($1, $2)
            ON CONFLICT DO NOTHING
            """,
            member.id,
            member.guild.id,
        )

    async def get_joined_at(self, member) -> Optional[datetime.datetime]:
        joined_at = await self.bot.pool.fetchval(
            """
            SELECT joined_at
            FROM voice_xp
            WHERE user_id = $1
            AND guild_id = $2
            """,
            member.id,
            member.guild.id,
        )

        return joined_at

    async def set_joined_at(
        self,
        member: discord.Member,
        channel: Union[discord.VoiceChannel, discord.StageChannel],
    ):
        await self.bot.pool.execute(
            """
            UPDATE voice_xp
            SET joined_at = $1, channel_id = $2
            WHERE user_id = $3
            AND guild_id = $4
            """,
            get_dt_now(),
            channel.id,
            member.id,
            member.guild.id,
        )

    async def give_voice_xp(self, member: discord.Member, joined_at: datetime.datetime):
        # calculate xp
        second = int((get_dt_now() - joined_at).total_seconds())
        xp = second // 60

        # add xp to user
        await self.update_xp(member, xp, is_voice=True)

        # calculate level
        level = await self.calculate_level(member, is_voice=True)

        # update level
        await self.update_level(member, level, is_voice=True)

    # text xp level system
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        # add xp to user
        assert isinstance(message.author, discord.Member)
        await self.create_level_user(message.author)
        await self.give_chat_xp(message.author)

    async def create_level_user(self, member: discord.Member):
        await self.bot.pool.execute(
            """
            INSERT INTO levels (user_id, guild_id, start_date)
            VALUES ($1, $2, $3)
            ON CONFLICT DO NOTHING
            """,
            member.id,
            member.guild.id,
            get_dt_now(),
        )

    async def give_chat_xp(self, member: discord.Member):
        # add xp to user
        await self.update_xp(member, 1)

        # calculate level
        level = await self.calculate_level(member)

        # update level
        await self.update_level(member, level)

    async def update_xp(
        self,
        member: discord.Member,
        xp: int,
        *,
        is_voice: bool = False,
    ):
        query = "voice_xp" if is_voice else "chat_xp"
        await self.bot.pool.execute(
            f"""
            UPDATE levels
            SET {query} = {query} + $1
            WHERE user_id = $2 AND guild_id = $3
            """,
            xp,
            member.id,
            member.guild.id,
        )

    async def calculate_level(self, member: discord.Member, *, is_voice: bool = False):
        query = "voice_xp" if is_voice else "chat_xp"
        current_xp = await self.bot.pool.fetchval(
            f"SELECT {query} FROM levels WHERE user_id = $1 AND guild_id = $2",
            member.id,
            member.guild.id,
        )
        level = int(current_xp**0.25)
        return level

    async def update_level(
        self,
        member: discord.Member,
        level: int,
        *,
        is_voice: bool = False,
    ):
        query = "voice_level" if is_voice else "chat_level"
        await self.bot.pool.execute(
            f"""
            UPDATE levels
            SET {query} = $1
            WHERE user_id = $2 AND guild_id = $3
            """,
            level,
            member.id,
            member.guild.id,
        )

    @app_commands.guild_only()
    @app_commands.command(name="level", description="查看等級")
    @app_commands.rename(member="用戶")
    @app_commands.describe(member="要查看等級的用戶")
    async def level(self, i: discord.Interaction, member: discord.Member):
        await i.response.defer()
        member = member or i.user

        assert i.guild is not None
        stats = await self.bot.pool.fetchrow(
            "SELECT * FROM levels WHERE user_id = $1 AND guild_id = $2",
            member.id,
            i.guild.id,
        )
        if stats is None:
            embed = ErrorEmbed("該用戶目前沒有資料", "不同的伺服器等級是分開計算的")
            return await i.followup.send(embed=embed)

        chat_level: int = stats["chat_level"]
        chat_xp: int = stats["chat_xp"]
        voice_level: int = stats["voice_level"]
        voice_xp: int = stats["voice_xp"]
        start_date: datetime.datetime = stats["start_date"]

        days_passed = (get_dt_now() - start_date).days
        avg_chat_xp = chat_xp / days_passed
        avg_voice_xp = voice_xp / days_passed

        embed = DefaultEmbed("聊天/語音等級")
        embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
        embed.add_field(
            name="聊天等級", value=f"Lv.{chat_level} ({chat_xp} 經驗)", inline=False
        )
        embed.add_field(
            name="語音等級", value=f"Lv.{voice_level} ({voice_xp} 經驗)", inline=False
        )
        embed.add_field(
            name="平均每日經驗", value=f"聊天: {avg_chat_xp} | 語音: {avg_voice_xp}", inline=False
        )
        embed.add_field(
            name="等級計算起始日", value=discord.utils.format_dt(start_date, style="R")
        )
        if member.joined_at:
            embed.add_field(
                name="加入群組日期",
                value=discord.utils.format_dt(member.joined_at, style="R"),
            )
        embed.set_footer(text="一則訊息 1 經驗值，一分鐘語音 1 經驗值\n等級=經驗值^(0.25)")

        await i.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(LevelCog(bot))
