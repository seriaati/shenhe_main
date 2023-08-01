import asyncio
from typing import Any

import discord
from discord.ext import commands

from utility.utils import find_urls

CHANNEL_ID = 1061899087525458031


class TextForum(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener("on_message")
    async def auto_create_forum(self, message: discord.Message) -> Any:
        if message.channel.id != CHANNEL_ID:
            return

        urls = find_urls(message.content)
        if not urls:
            return await self.delete_after_5_sec(message, "請在討論串中討論影片相關內容，此頻道只用於發布影片連結")
        keywords = ("youtube", "youtu.be")
        if not any((keyword in message.content.lower() for keyword in keywords)):
            return await self.delete_after_5_sec(message, "目前只支援 YouTube 連結")

        thread = await message.create_thread(
            name=f"影片討論-{urls[0][-4:]}",
            auto_archive_duration=1440,
            reason="自動創建影片討論串",
        )
        await thread.send(
            f"由 {message.author.mention} 發起的影片討論串，請在這裡討論影片相關內容",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    async def delete_after_5_sec(self, message: discord.Message, content: str) -> None:
        await message.reply(f"{content} （此訊息將在 5 秒後刪除）", delete_after=5)
        await asyncio.sleep(5)
        await message.delete()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TextForum(bot))
