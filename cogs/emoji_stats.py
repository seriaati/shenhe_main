import asyncio
import re
import typing

import discord
from discord import app_commands
from discord.ext import commands

from dev.model import BotModel, DefaultEmbed, ErrorEmbed
from utility.paginator import GeneralPaginator
from utility.utils import divide_chunks, get_dt_now


class EmojiStatsCog(commands.GroupCog, name="emoji"):
    def __init__(self, bot):
        self.bot: BotModel = bot
        self.guild: discord.Guild
        self.emoji_ids: typing.List[str] = []

    async def cog_load(self) -> None:
        rows = await self.bot.pool.fetch("SELECT * FROM emoji_stats")
        self.emoji_ids = [str(r["emoji_id"]) for r in rows]
        asyncio.create_task(self.load_guild())

    async def load_guild(self) -> None:
        await self.bot.wait_until_ready()
        self.guild = self.bot.get_guild(self.bot.guild_id)  # type: ignore

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if (
            message.guild is None
            or message.guild.id != self.bot.guild_id
            or message.author.bot
        ):
            return

        # extract ALL emoji IDs from message content with regex
        # if there are two emojis with the same ID, count it as two
        # if there are multiple emojis in the message, extract all of their IDs
        emoji_ids: typing.List[str] = re.findall(r"<a?:\w+:(\d+)>", message.content)

        for e_id in emoji_ids:
            if e_id not in self.emoji_ids:
                try:
                    emoji = await self.guild.fetch_emoji(int(e_id))
                except discord.NotFound:
                    continue
                await self.bot.pool.execute(
                    "INSERT INTO emoji_stats (emoji_id, emoji_name, animated) VALUES ($1, $2, $3)",
                    emoji.id,
                    emoji.name,
                    emoji.animated,
                )
                self.emoji_ids.append(e_id)
            else:
                await self.bot.pool.execute(
                    "UPDATE emoji_stats SET count = count + 1 WHERE emoji_id = $1",
                    int(e_id),
                )

    @app_commands.guild_only()
    @app_commands.rename(order="排序方式")
    @app_commands.describe(order="表情符號使用數量的排序方式")
    @app_commands.choices(
        order=[
            app_commands.Choice(name="高到低", value="DESC"),
            app_commands.Choice(name="低到高", value="ASC"),
        ]
    )
    @app_commands.command(name="stats", description="統計伺服器表情符號使用次數")
    async def emoji_stats(self, i: discord.Interaction, order: str = "DESC"):
        assert i.guild and i.guild.icon

        rows = await self.bot.pool.fetch(
            f"SELECT * FROM emoji_stats ORDER BY count {order}"
        )
        if not rows:
            return await i.response.send_message(
                embed=ErrorEmbed("錯誤", "目前沒有任何表情符號數據"), ephemeral=True
            )

        embeds: typing.List[discord.Embed] = []
        rows = sorted(rows, key=lambda x: x["count"], reverse=True)
        div_rows = divide_chunks(rows, 10)

        for rows in div_rows:
            embed = DefaultEmbed("表情符號統計")
            embed.description = ""
            embed.set_author(name=i.guild.name, icon_url=i.guild.icon.url)
            embed.set_footer(text=f"統計時間: {get_dt_now().strftime('%Y-%m-%d %H:%M:%S')}")
            for row in rows:
                try:
                    emoji = await i.guild.fetch_emoji(int(row["emoji_id"]))
                except discord.NotFound:
                    await self.bot.pool.execute(
                        "DELETE FROM emoji_stats WHERE emoji_id = $1", row["emoji_id"]
                    )
                else:
                    count = row["count"]
                    emoji_string = (
                        f"<{'a' if emoji.animated else ''}:{emoji.name}:{emoji.id}>"
                    )
                    embed.description += f"{emoji_string} | {count}\n\n"
            embeds.append(embed)

        await GeneralPaginator(i, embeds).start()


async def setup(bot: commands.Bot):
    await bot.add_cog(EmojiStatsCog(bot))
