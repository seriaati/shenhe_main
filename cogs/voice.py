import aiosqlite
import wavelink
from discord import (
    ChannelType,
    Interaction,
    Member,
    NotFound,
    VoiceChannel,
    VoiceState,
    app_commands,
    utils,
)
from discord.ext import commands

from utility.utils import default_embed, error_embed


def check_in_vc():
    async def predicate(i: Interaction):
        result = i.user.voice is not None
        if not result:
            await i.response.send_message(
                embed=error_embed().set_author(
                    name="你必須在語音台裡才能用這個指令", icon_url=i.user.display_avatar.url
                ),
                ephemeral=True,
            )
        return result

    return app_commands.check(predicate)


class VoiceCog(commands.GroupCog, name="vc"):
    def __init__(self, bot):
        self.bot: commands.Bot = bot
        super().__init__()

    @commands.Cog.listener()
    async def on_voice_state_update(
        self, member: Member, before: VoiceState, after: VoiceState
    ):
        make_vc = utils.get(member.guild.channels, name="創建語音台")
        vc_role = utils.get(member.guild.roles, name="正在使用語音台")
        old_channel: VoiceChannel = before.channel
        new_channel: VoiceChannel = after.channel
        c: aiosqlite.Cursor = await self.bot.db.cursor()
        if (
            new_channel is None
            and old_channel is not None
            and len(old_channel.members) == 1
            and old_channel.members[0].id == self.bot.user.id
        ):
            make_vc: wavelink.Player = member.guild.voice_client
            make_vc.queue.clear()
            await make_vc.stop()
            await make_vc.disconnect()
        if new_channel is not None:
            await member.add_roles(vc_role)
        if new_channel == make_vc:
            member_vc = await member.guild.create_voice_channel(
                name=f"{member.display_name}的語音台", category=make_vc.category
            )
            await member.move_to(member_vc)
            await member.add_roles(vc_role)
            await c.execute(
                "INSERT INTO voice (owner_id, channel_id) VALUES (?, ?)",
                (member.id, member_vc.id),
            )
        if new_channel is None:
            await member.remove_roles(vc_role)
            await c.execute(
                "SELECT * FROM voice WHERE owner_id = ? AND channel_id = ?",
                (member.id, old_channel.id),
            )
            owner = await c.fetchone()
            if owner is not None and len(old_channel.members) != 0:
                await c.execute(
                    "UPDATE voice SET owner_id = ? WHERE channel_id = ?",
                    (old_channel.members[0].id, old_channel.id),
                )
        if (
            old_channel is not None
            and old_channel != make_vc
            and len(old_channel.members) == 0
        ):
            if old_channel.type is ChannelType.stage_voice:
                return
            try:
                await old_channel.delete()
            except NotFound:
                pass
            await c.execute("DELETE FROM voice WHERE channel_id = ?", (old_channel.id,))
        await self.bot.db.commit()

    async def check_owner(self, channel_id: int, user_id: int):
        c: aiosqlite.Cursor = await self.bot.db.cursor()
        await c.execute(
            "SELECT owner_id FROM voice WHERE channel_id = ?", (channel_id,)
        )
        owner_id = await c.fetchone()
        owner_id = owner_id[0]
        if user_id == owner_id:
            return True, None
        else:
            return False, error_embed().set_author(
                name="你不是這個語音台的擁有者", icon_url=self.bot.get_user(user_id).avatar
            )

    @check_in_vc()
    @app_commands.command(name="rename", description="重新命名語音台")
    @app_commands.rename(new="新名稱")
    @app_commands.describe(new="新的語音台名稱")
    async def vc_rename(self, i: Interaction, new: str):
        current_vc = i.user.voice.channel
        owner, err_msg = await self.check_owner(current_vc.id, i.user.id)
        if not owner:
            return await i.response.send_message(embed=err_msg, ephemeral=True)
        await current_vc.edit(name=new)
        await i.response.send_message(
            embed=default_embed(message=f"新名稱: {new}").set_author(
                name="語音台名稱更改成功", icon_url=i.user.display_avatar.url
            ),
            ephemeral=True,
        )

    @check_in_vc()
    @app_commands.command(name="lock", description="鎖上語音台")
    async def vc_lock(self, i: Interaction):
        current_vc = i.user.voice.channel
        owner, err_msg = await self.check_owner(current_vc.id, i.user.id)
        if not owner:
            return await i.response.send_message(embed=err_msg, ephemeral=True)
        for member in current_vc.members:
            await current_vc.set_permissions(member, connect=True)
        traveler = utils.get(i.guild.roles, name="旅行者")
        await current_vc.set_permissions(traveler, connect=False)
        await i.response.send_message(embed=default_embed(f"{current_vc.name}被鎖上了"))

    @check_in_vc()
    @app_commands.command(name="unlock", description="解鎖語音台")
    async def vc_unlock(self, i: Interaction):
        current_vc = i.user.voice.channel
        owner, err_msg = await self.check_owner(current_vc.id, i.user.id)
        if not owner:
            return await i.response.send_message(embed=err_msg, ephemeral=True)
        traveler = utils.get(i.guild.roles, name="旅行者")
        await current_vc.set_permissions(traveler, connect=True)
        await i.response.send_message(embed=default_embed(f"{current_vc.name}的封印被解除了"))

    @check_in_vc()
    @app_commands.command(name="transfer", description="移交房主權")
    @app_commands.rename(new="新房主")
    @app_commands.describe(new="新的房主")
    async def vc_transfer(self, i: Interaction, new: Member):
        current_vc = i.user.voice.channel
        owner, err_msg = await self.check_owner(current_vc.id, i.user.id)
        if not owner:
            return await i.response.send_message(embed=err_msg, ephemeral=True)
        c: aiosqlite.Cursor = await self.bot.db.cursor()
        await c.execute(
            "UPDATE voice SET owner_id = ? WHERE channel_id = ?",
            (new.id, current_vc.id),
        )
        await self.bot.db.commit()
        await i.response.send_message(
            content=f"{i.user.mention} {new.mention}",
            embed=default_embed(
                "房主換人啦",
                f" {i.user.mention} 將 {current_vc.name} 的房主權移交給了 {new.mention}",
            ),
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(VoiceCog(bot))
