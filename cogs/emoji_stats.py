import asyncio
import re
from typing import Dict, List

import discord
from discord import app_commands
from discord.ext import commands, tasks
from pydantic import BaseModel, Field

from dev.model import BotModel, DefaultEmbed, ErrorEmbed
from utility.paginator import GeneralPaginator
from utility.utils import divide_chunks, get_dt_now


class EmojiStatsModel(BaseModel):
    name: str = Field(alias="emoji_name")
    id: int = Field(alias="emoji_id")
    count: int = 1
    animated: bool


class EmojiStatsCog(commands.GroupCog, name="emoji"):
    def __init__(self, bot):
        self.bot: BotModel = bot
        self.guild: discord.Guild
        self.guild_emojis: Dict[int, discord.Emoji] = {}

    async def cog_load(self) -> None:
        asyncio.create_task(self.load_guild())

    async def load_guild(self) -> None:
        await self.bot.wait_until_ready()
        self.guild = self.bot.get_guild(self.bot.guild_id)  # type: ignore

    @tasks.loop(hours=1)
    async def update_guild_emojis(self) -> None:
        self.guild_emojis = {e.id: e for e in await self.guild.fetch_emojis()}

    @update_guild_emojis.before_loop
    async def before_update_guild_emojis(self) -> None:
        await self.bot.wait_until_ready()

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
        emoji_ids: List[str] = re.findall(r"<a?:\w+:(\d+)>", message.content)

        for e_id in emoji_ids:
            emoji_id = int(e_id)
            emoji = self.guild_emojis.get(emoji_id)
            if emoji is not None:
                await self.bot.pool.execute(
                    "INSERT INTO emoji_stats (emoji_id, emoji_name, animated) VALUES ($1, $2, $3) ON CONFLICT DO UPDATE SET count = emoji_stats.count + 1",
                    emoji.id,
                    emoji.name,
                    emoji.animated,
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
        await i.response.defer()
        emojis = [EmojiStatsModel(**row) for row in rows]

        embeds: List[discord.Embed] = []
        div_emojis: List[List[EmojiStatsModel]] = list(divide_chunks(emojis, 10))
        guild_emojis: List[int] = [e.id for e in i.guild.emojis]

        for emojis in div_emojis:
            embed = DefaultEmbed("表情符號統計")
            embed.description = ""
            embed.set_author(name=i.guild.name, icon_url=i.guild.icon.url)
            embed.set_footer(text=f"統計時間: {get_dt_now().strftime('%Y-%m-%d %H:%M:%S')}")
            for emoji in emojis:
                if emoji.id in guild_emojis:
                    emoji_string = (
                        f"<{'a' if emoji.animated else ''}:{emoji.name}:{emoji.id}>"
                    )
                    embed.description += f"{emoji_string} | {emoji.count}\n\n"
            embeds.append(embed)

        await GeneralPaginator(i, embeds).start(followup=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(EmojiStatsCog(bot))
