import re
import typing

import discord
from discord import app_commands
from discord.ext import commands

from dev.model import BotModel, DefaultEmbed, ErrorEmbed
from utility.paginator import GeneralPaginator
from utility.utils import divide_chunks, get_dt_now


class EmojiStatsCog(commands.Cog):
    def __init__(self, bot):
        self.bot: BotModel = bot

    async def cog_load(self) -> None:
        rows = await self.bot.pool.fetch("SELECT * FROM emoji_stats")
        self.emoji_strs: typing.List[str] = []
        for row in rows:
            name = row["emoji_name"]
            e_id = row["emoji_id"]
            animated = row["animated"]
            self.emoji_strs.append(f"<{'a' if animated else ''}:{name}:{e_id}>")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if (
            message.guild is None
            or message.guild.id != self.bot.guild_id
            or message.author.bot
        ):
            return

        # extract emoji IDs from message content with regex
        emoji_ids = re.findall(r"<a?:.*:(\d+)>", message.content)
        for e_id in emoji_ids:
            if e_id not in self.emoji_strs:
                emoji = self.bot.get_emoji(int(e_id))
                if emoji:
                    await self.bot.pool.execute(
                        "INSERT INTO emoji_stats (emoji_id, emoji_name, animated) VALUES ($1, $2, $3)",
                        emoji.id,
                        emoji.name,
                        emoji.animated,
                    )
                    self.emoji_strs.append(
                        f"<{'a' if emoji.animated else ''}:{emoji.name}:{emoji.id}>"
                    )
            else:
                await self.bot.pool.execute(
                    "UPDATE emoji_stats SET count = count + 1 WHERE emoji_id = $1", e_id
                )

    @app_commands.guild_only()
    @app_commands.command(name="emoji-stats", description="統計伺服器表情符號使用次數")
    async def emoji_stats(self, i: discord.Interaction):
        assert i.guild and i.guild.icon

        rows = await self.bot.pool.fetch("SELECT * FROM emoji_stats")
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
                name = row["emoji_name"]
                e_id = row["emoji_id"]
                animated = row["animated"]
                count = row["count"]
                embed.description += (
                    f"<{'a' if animated else ''}:{name}:{e_id}> | {count}\n"
                )
            embeds.append(embed)

        await GeneralPaginator(i, embeds).start()


async def setup(bot: commands.Bot):
    await bot.add_cog(EmojiStatsCog(bot))
