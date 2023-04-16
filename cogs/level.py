import datetime
from typing import List, Optional, Union

import discord
from discord import app_commands
from discord.ext import commands, tasks

from dev.model import BotModel, DefaultEmbed, ErrorEmbed
from utility.paginator import GeneralPaginator
from utility.utils import divide_chunks, get_dt_now


class LevelCog(commands.GroupCog, name="level"):
    def __init__(self, bot):
        self.bot: BotModel = bot

    async def cog_load(self):
        self.clear_today_earn.start()

    async def cog_unload(self):
        self.clear_today_earn.cancel()

    # clear today_earn every day
    @tasks.loop(hours=1)
    async def clear_today_earn(self):
        if get_dt_now().hour == 0:
            await self.bot.pool.execute(
                """
                UPDATE levels
                SET today_earn = 0
                """
            )

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

    # text xp level system
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if (
            message.author.bot
            or not message.guild
            or not isinstance(message.author, discord.Member)
        ):
            return
        await self.create_level_user(message.author)

        last_get = await self.get_last_get(message.author)
        if (get_dt_now() - last_get).total_seconds() < 30:
            return

        today_earn = await self.get_today_earn(message.author)
        if today_earn >= 400:
            return

        await self.update_xp(message.author, 1)

    async def get_today_earn(self, member: discord.Member) -> int:
        today_earn = await self.bot.pool.fetchval(
            """
            SELECT today_earn
            FROM levels
            WHERE user_id = $1
            AND guild_id = $2
            """,
            member.id,
            member.guild.id,
        )

        return today_earn

    async def get_last_get(self, member: discord.Member) -> datetime.datetime:
        last_get = await self.bot.pool.fetchval(
            """
            SELECT last_get
            FROM levels
            WHERE user_id = $1
            AND guild_id = $2
            """,
            member.id,
            member.guild.id,
        )

        return last_get

    async def create_level_user(self, member: discord.Member):
        await self.bot.pool.execute(
            """
            INSERT INTO levels (user_id, guild_id, start_date, last_get)
            VALUES ($1, $2, $3, $3)
            ON CONFLICT DO NOTHING
            """,
            member.id,
            member.guild.id,
            get_dt_now(),
        )

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
            SET {query} = {query} + $1, last_get = $4, today_earn = today_earn + $1
            WHERE user_id = $2 AND guild_id = $3
            """,
            xp,
            member.id,
            member.guild.id,
            get_dt_now(),
        )

    @app_commands.guild_only()
    @app_commands.command(name="check", description="查看等級")
    @app_commands.rename(m="用戶")
    @app_commands.describe(m="要查看等級的用戶")
    async def level(self, i: discord.Interaction, m: Optional[discord.Member] = None):
        await i.response.defer()
        member = m or i.user
        assert isinstance(member, discord.Member)

        assert i.guild is not None
        stats = await self.bot.pool.fetchrow(
            "SELECT * FROM levels WHERE user_id = $1 AND guild_id = $2",
            member.id,
            i.guild.id,
        )
        if stats is None:
            embed = ErrorEmbed("該用戶目前沒有資料", "不同的伺服器等級是分開計算的")
            return await i.followup.send(embed=embed)

        chat_xp: int = stats["chat_xp"]
        chat_level = round(chat_xp**0.2)
        voice_xp: int = stats["voice_xp"]
        voice_level = round(voice_xp**0.2)
        start_date: datetime.datetime = stats["start_date"]

        days_passed = (get_dt_now() - start_date).days
        if days_passed == 0:
            days_passed = 1
        avg_chat_xp = round(chat_xp / days_passed, 2)
        avg_voice_xp = round(voice_xp / days_passed, 2)

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
        embed.set_footer(text="一則訊息 1 經驗，一分鐘語音 1 經驗\n等級=經驗^(0.2)")

        await i.followup.send(embed=embed)

    @app_commands.guild_only()
    @app_commands.rename(order_by_chat="排序方式")
    @app_commands.describe(order_by_chat="要依據聊天等級還是語音等級排序")
    @app_commands.choices(
        order_by_chat=[
            app_commands.Choice(name="聊天等級", value=1),
            app_commands.Choice(name="語音等級", value=0),
        ]
    )
    @app_commands.command(name="leaderboard", description="查看等級排行榜")
    async def leaderboard(self, i: discord.Interaction, order_by_chat: int):
        await i.response.defer()

        order_by_chat = bool(order_by_chat)
        assert i.guild is not None
        stats = await self.bot.pool.fetch(
            "SELECT user_id, chat_xp, voice_xp FROM levels WHERE guild_id = $1",
            i.guild.id,
        )

        if not stats:
            embed = ErrorEmbed("目前排行榜沒有資料")
            return await i.followup.send(embed=embed)

        query = "chat_xp" if order_by_chat else "voice_xp"
        stats.sort(key=lambda x: x[query], reverse=True)

        embeds: List[discord.Embed] = []
        div_stats = list(divide_chunks(stats, 10))
        word = "聊天" if order_by_chat else "語音"
        for div in div_stats:
            embed = DefaultEmbed(f"{word}等級排行榜")
            assert i.guild.icon
            embed.set_author(name=i.guild.name, icon_url=i.guild.icon.url)
            for rank, stat in enumerate(div, start=1):
                member = i.guild.get_member(stat["user_id"])
                if member is None:
                    member = await i.guild.fetch_member(stat["user_id"])
                embed.add_field(
                    name=f"{rank}. {member.display_name}",
                    value=f"Lv.{round(stat[query]**0.2)} ({round(stat[query], 2)})",
                    inline=False,
                )
            embeds.append(embed)

        await GeneralPaginator(i, embeds).start(followup=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(LevelCog(bot))
