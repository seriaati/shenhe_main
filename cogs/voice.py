import random

import discord
import wavelink
from discord import app_commands
from discord.ext import commands

from dev.model import BotModel, DefaultEmbed, ErrorEmbed, Inter


def check_in_vc():
    async def predicate(i: discord.Interaction) -> bool:
        assert isinstance(i.user, discord.Member)
        if i.user.voice is None:
            await i.response.send_message(
                embed=ErrorEmbed("你必須在語音台裡才能使用這個指令"),
                ephemeral=True,
            )
            return False
        else:
            return True

    return app_commands.check(predicate)


def check_owner():
    async def predicate(inter: discord.Interaction) -> bool:
        i: Inter = inter  # type: ignore
        assert (
            isinstance(i.user, discord.Member) and i.user.voice and i.user.voice.channel
        )
        owner_id = await i.client.pool.fetchval(
            "SELECT owner_id FROM voice WHERE channel_id = $1", i.user.voice.channel.id
        )
        if owner_id is None or owner_id != i.user.id:
            await i.response.send_message(
                embed=ErrorEmbed("錯誤", f"你不是語音台的擁有者\n擁有者: <@{owner_id}>"),
                ephemeral=True,
            )
            return False
        else:
            return True

    return app_commands.check(predicate)


class VoiceCog(commands.GroupCog, name="vc"):
    def __init__(self, bot):
        self.bot: BotModel = bot
        super().__init__()

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        if member.guild.id != self.bot.guild_id:
            return
        
        guild = member.guild
        make_vc = guild.get_channel(1061881611450322954)
        assert make_vc
        vc_role = guild.get_role(1061955528349188147)
        assert vc_role

        old = before.channel
        new = after.channel

        if (
            new is None
            and old is not None
            and len(old.members) == 1
            and old.members[0].id == self.bot.user.id
            and member.guild.voice_client
        ):
            player: wavelink.Player = member.guild.voice_client  # type: ignore
            player.queue.clear()
            await player.stop()
            await player.disconnect()

        if new is not None:
            await member.add_roles(vc_role)

        if new == make_vc:
            member_vc = await member.guild.create_voice_channel(
                name=f"{member.display_name}的語音台", category=make_vc.category
            )
            await member.move_to(member_vc)
            await member.add_roles(vc_role)
            await self.bot.pool.execute(
                "INSERT INTO voice (owner_id, channel_id) VALUES ($1, $2)",
                member.id,
                member_vc.id,
            )

        if new is None:
            await member.remove_roles(vc_role)
            owner = await self.bot.pool.fetchrow(
                "SELECT 1 FROM voice WHERE owner_id = $1", member.id
            )
            if owner is not None and old is not None and len(old.members) != 0:
                await self.bot.pool.execute(
                    "UPDATE voice SET owner_id = $1 WHERE channel_id = $2",
                    random.choice(old.members).id,
                    old.id,
                )
        if old is not None and old != make_vc and len(old.members) == 0:
            if old.type is discord.ChannelType.stage_voice:
                return
            try:
                await old.delete()
            except discord.NotFound:
                pass
            await self.bot.pool.execute(
                "DELETE FROM voice WHERE channel_id = $1", old.id
            )

    @check_in_vc()
    @check_owner()
    @app_commands.command(name="rename", description="重新命名語音台")
    @app_commands.rename(new="新名稱")
    @app_commands.describe(new="新的語音台名稱")
    async def vc_rename(self, i: discord.Interaction, new: str):
        assert isinstance(i.user, discord.Member) and i.user.voice
        current_vc = i.user.voice.channel
        assert current_vc
        await current_vc.edit(name=new)
        await i.response.send_message(
            embed=DefaultEmbed("成功", f"語音台已經重新命名為 {new}"),
            ephemeral=True,
        )

    @check_in_vc()
    @check_owner()
    @app_commands.command(name="lock", description="鎖上語音台")
    async def vc_lock(self, i: discord.Interaction):
        assert isinstance(i.user, discord.Member) and i.user.voice
        current_vc = i.user.voice.channel
        assert current_vc
        for member in current_vc.members:
            await current_vc.set_permissions(member, connect=True, view_channel=True)

        assert i.guild
        traveler = i.guild.get_role(1061880147952812052)
        assert traveler
        await current_vc.set_permissions(traveler, connect=False, view_channel=True)
        await i.response.send_message(
            embed=DefaultEmbed("成功", "此語音台已被牢牢鎖上 (誰都別想進來！)"), ephemeral=True
        )

    @check_in_vc()
    @check_owner()
    @app_commands.command(name="unlock", description="解鎖語音台")
    async def vc_unlock(self, i: discord.Interaction):
        assert isinstance(i.user, discord.Member) and i.user.voice
        current_vc = i.user.voice.channel
        assert current_vc and i.guild

        traveler = i.guild.get_role(1061880147952812052)
        assert traveler
        await current_vc.set_permissions(traveler, connect=True, view_channel=True)
        await i.response.send_message(
            embed=DefaultEmbed("成功", "此語音台的封印已被解除"), ephemeral=True
        )

    @check_in_vc()
    @check_owner()
    @app_commands.command(name="transfer", description="移交房主權")
    @app_commands.rename(new="新房主")
    @app_commands.describe(new="新的房主")
    async def vc_transfer(self, inter: discord.Interaction, new: discord.Member):
        i: Inter = inter  # type: ignore
        assert isinstance(i.user, discord.Member) and i.user.voice
        current_vc = i.user.voice.channel
        assert current_vc
        await i.client.pool.execute(
            "UPDATE voice SET owner_id = $1 WHERE channel_id = $2",
            new.id,
            current_vc.id,
        )

        await i.response.send_message(
            content=f"{i.user.mention} {new.mention}",
            embed=DefaultEmbed("成功", f"{i.user.mention} 已將房主權限移交給 {new.mention}"),
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(VoiceCog(bot))
