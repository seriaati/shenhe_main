import importlib
import io
import sys
from typing import List

import discord
from discord.ext import commands

from utility.utils import error_embed


class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot: commands.Bot = bot
        self.debug: bool = self.bot.debug_toggle

    @commands.is_owner()
    @commands.command(name="cleanup")
    async def cleanup(self, ctx: commands.Context, amount: int):
        await ctx.channel.purge(
            limit=amount + 1, check=lambda m: m.author == self.bot.user
        )

    @commands.is_owner()
    @commands.command(name="reload")
    async def reload(self, ctx: commands.Context):
        modules = list(sys.modules.values())
        for module in modules:
            if module is None:
                continue
            if module.__name__.startswith(("cogs.", "utility.", "apps.", "data.")):
                try:
                    importlib.reload(module)
                except Exception as e:
                    return await ctx.send(
                        embed=error_embed(module.__name__, f"```{e}```"),
                        ephemeral=True,
                    )
        await ctx.send("Reloaded")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.id == self.bot.user.id:
            return
        if message.guild.id != self.bot.guild_id:
            return

        if message.channel.id == 1061898394446069852 and message.attachments:
            files: List[discord.File] = []
            await message.delete()

            for attachment in message.attachments:
                if not attachment.is_spoiler():
                    async with self.bot.session.get(attachment.proxy_url) as resp:
                        bytes_obj = io.BytesIO(await resp.read())
                        file = discord.File(
                            bytes_obj, filename=attachment.filename, spoiler=True
                        )
                        files.append(file)

            await message.channel.send(
                content=f"由 <@{message.author.id}> 寄出", files=files
            )

    # @commands.Cog.listener()
    # async def on_raw_message_delete(self, payload: RawMessageDeleteEvent):
    #     now = get_dt_now()
    #     if payload.guild_id != 1061875024136503318:
    #         return
    #     if payload.channel_id == 965842415913152522:
    #         return
    #     c: TextChannel = (
    #         self.bot.get_channel(988698669442269184)
    #         if not self.bot.debug_toggle
    #         else self.bot.get_channel(909595117952856084)
    #     )
    #     if payload.cached_message is not None:
    #         if payload.cached_message.author.id == self.bot.user.id:
    #             return
    #         if payload.cached_message.content == "!q":
    #             return
    #         attachment_str = (
    #             "(含有附件)" if len(payload.cached_message.attachments) != 0 else ""
    #         )
    #         embed = default_embed(
    #             "訊息刪除",
    #             f"「{payload.cached_message.content} {attachment_str}」\n\n"
    #             f"用戶: {payload.cached_message.author.mention}\n"
    #             f"頻道: {payload.cached_message.channel.mention}\n"
    #             f'時間: {now.strftime("%m/%d/%Y %H:%M:%S")}\n'
    #             f"附近訊息: {payload.cached_message.jump_url}",
    #         )
    #         embed.set_footer(text=f"用戶 ID: {payload.cached_message.author.id}\n")
    #         embed.set_author(
    #             name=payload.cached_message.author,
    #             icon_url=payload.cached_message.author.avatar,
    #         )
    #         await c.send(embed=embed)
    #         if len(payload.cached_message.attachments) != 0:
    #             for a in payload.cached_message.attachments:
    #                 await c.send(file=await a.to_file(use_cached=True))

    # @commands.Cog.listener()
    # async def on_member_join(self, member: Member):
    #     now = get_dt_now()
    #     if member.guild.id != 1061875024136503318:
    #         return
    #     c: TextChannel = (
    #         self.bot.get_channel(988698669442269184)
    #         if not self.bot.debug_toggle
    #         else self.bot.get_channel(909595117952856084)
    #     )
    #     embed = default_embed(
    #         "進群", f"用戶: {member.mention}\n" f'時間: {now.strftime("%m/%d/%Y %H:%M:%S")}\n'
    #     )
    #     embed.set_author(name=member, icon_url=member.avatar)
    #     embed.set_footer(text=f"用戶 ID: {member.id}")
    #     await c.send(embed=embed)

    # @commands.Cog.listener()
    # async def on_member_remove(self, member: Member):
    #     now = get_dt_now()
    #     if member.guild.id != 1061875024136503318:
    #         return
    #     c: TextChannel = (
    #         self.bot.get_channel(988698669442269184)
    #         if not self.bot.debug_toggle
    #         else self.bot.get_channel(909595117952856084)
    #     )
    #     embed = default_embed(
    #         "退群", f"用戶: {member.mention}\n" f'時間: {now.strftime("%m/%d/%Y %H:%M:%S")}\n'
    #     )
    #     embed.set_author(name=member, icon_url=member.avatar)
    #     embed.set_footer(text=f"用戶 ID: {member.id}")
    #     await c.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AdminCog(bot))
