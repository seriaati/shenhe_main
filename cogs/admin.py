import asyncio
import io
import aiosqlite

from discord import (
    File,
    Interaction,
    Member,
    Message,
    NotFound,
    app_commands,
)
from discord.ext import commands
from utility.utils import default_embed, error_embed, get_dt_now, time_in_range
import importlib
import sys


class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot: commands.Bot = bot
        self.debug: bool = self.bot.debug_toggle

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
    async def on_message(self, message: Message):
        if message.author.id == self.bot.user.id:
            return
        if message.guild.id != 1061875024136503318:
            return
        sese_channel = (
            self.bot.get_channel(984792329426714677)
            if self.debug
            else self.bot.get_channel(965842415913152522)
        )
        if message.channel == sese_channel and len(message.attachments) != 0:
            c: aiosqlite.Cursor = await self.bot.db.cursor()
            await c.execute(
                "INSERT INTO sese_leaderboard (user_id, sese_count) VALUES (?, ?) ON CONFLICT (user_id) DO UPDATE SET sese_count = sese_count + ? WHERE user_id = ?",
                (
                    message.author.id,
                    len(message.attachments),
                    len(message.attachments),
                    message.author.id,
                ),
            )
            await self.bot.db.commit()
            for attachment in message.attachments:
                if not attachment.is_spoiler():
                    try:
                        await message.delete()
                    except NotFound:
                        pass
                    async with self.bot.session.get(attachment.proxy_url) as resp:
                        bytes_obj = io.BytesIO(await resp.read())
                        file = File(
                            bytes_obj, filename=attachment.filename, spoiler=True
                        )
                    await message.channel.send(
                        content=f"??? <@{message.author.id}> ??????", file=file
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
    #             "(????????????)" if len(payload.cached_message.attachments) != 0 else ""
    #         )
    #         embed = default_embed(
    #             "????????????",
    #             f"???{payload.cached_message.content} {attachment_str}???\n\n"
    #             f"??????: {payload.cached_message.author.mention}\n"
    #             f"??????: {payload.cached_message.channel.mention}\n"
    #             f'??????: {now.strftime("%m/%d/%Y %H:%M:%S")}\n'
    #             f"????????????: {payload.cached_message.jump_url}",
    #         )
    #         embed.set_footer(text=f"?????? ID: {payload.cached_message.author.id}\n")
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
    #         "??????", f"??????: {member.mention}\n" f'??????: {now.strftime("%m/%d/%Y %H:%M:%S")}\n'
    #     )
    #     embed.set_author(name=member, icon_url=member.avatar)
    #     embed.set_footer(text=f"?????? ID: {member.id}")
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
    #         "??????", f"??????: {member.mention}\n" f'??????: {now.strftime("%m/%d/%Y %H:%M:%S")}\n'
    #     )
    #     embed.set_author(name=member, icon_url=member.avatar)
    #     embed.set_footer(text=f"?????? ID: {member.id}")
    #     await c.send(embed=embed)
    

    @app_commands.command(name="mute", description="??????")
    @app_commands.rename(member="??????", minute="?????????")
    @app_commands.describe(member="?????????????????????", minute="????????????????????????")
    @app_commands.checks.has_any_role("?????????", "??????", "????????????(????????????)")
    async def mute(self, i: Interaction, member: Member, minute: int):
        role = (
            i.guild.get_role(994934185179488337)
            if not self.bot.debug_toggle
            else i.guild.get_role(994943569313935370)
        )
        await member.add_roles(role)
        await i.response.send_message(
            embed=default_embed(
                message=f"{member.mention} ?????? {i.user.mention} ?????? {minute} ??????"
            ).set_author(name="??????", icon_url=member.avatar)
        )
        await asyncio.sleep(minute * 60)
        await member.remove_roles(role)

    @app_commands.command(name="unmute", description="????????????")
    @app_commands.rename(member="??????")
    @app_commands.describe(member="???????????????????????????")
    @app_commands.checks.has_any_role("?????????", "??????", "????????????(????????????)")
    async def unmute(self, i: Interaction, member: Member):
        role = (
            i.guild.get_role(994934185179488337)
            if not self.bot.debug_toggle
            else i.guild.get_role(994943569313935370)
        )
        await member.remove_roles(role)
        await i.response.send_message(
            embed=default_embed(
                message=f"{i.user.mention} ????????? {member.mention} ?????????"
            ).set_author(name="????????????", icon_url=member.avatar)
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AdminCog(bot))
