import uuid

import discord
from discord import app_commands, utils
from discord.ext import commands

from dev.model import BotModel, DefaultEmbed, ErrorEmbed, Inter


def dance_check():
    async def predicate(i: discord.Interaction) -> bool:
        assert isinstance(i.channel, discord.TextChannel)
        result = i.channel.name.startswith("練舞頻道")
        if not result:
            embed = ErrorEmbed("你必須在練舞頻道裡才能使用這個指令")
            await i.response.send_message(embed=embed, ephemeral=True)
        return result

    return app_commands.check(predicate)


def dance_owner_check():
    async def predicate(inter: discord.Interaction) -> bool:
        i: Inter = inter  # type: ignore
        assert isinstance(i.channel, discord.TextChannel)
        owner_id: int = await i.client.pool.fetchval(
            "SELECT owner_id FROM dance WHERE channel_id = $1", i.channel.id
        )
        if i.user.id != owner_id:
            embed = ErrorEmbed("你不是此練舞頻道的擁有者", f"擁有者: <@{owner_id}>")
            await i.response.send_message(embed=embed, ephemeral=True)
            return False
        else:
            return True

    return app_commands.check(predicate)


class DanceCog(commands.GroupCog, name="dance"):
    def __init__(self, bot):
        self.bot: BotModel = bot

    @app_commands.guild_only()
    @app_commands.command(name="new", description="生成練舞頻道")
    async def dance_new(self, i: discord.Interaction):
        assert isinstance(i.channel, discord.TextChannel)
        assert isinstance(i.user, discord.Member)
        assert i.guild

        if i.channel.name.startswith("練舞頻道"):
            embed = DefaultEmbed("你已經在練舞頻道裡了")
            return await i.response.send_message(embed=embed, ephemeral=True)

        special_category = utils.get(i.guild.categories, id=1061947246893092874)
        assert special_category
        channel = await special_category.create_text_channel(
            name=f"練舞頻道-{str(uuid.uuid4())[0:4]}"
        )
        await channel.set_permissions(
            i.guild.default_role,
            view_channel=False,
        )

        traveler = i.guild.get_role(1061880147952812052)
        assert traveler
        await channel.set_permissions(
            traveler, send_messages=False, view_channel=True, read_message_history=True
        )
        await channel.set_permissions(
            i.user, send_messages=True, view_channel=True, read_message_history=True
        )

        warn_embed = DefaultEmbed(
            "⚠️ 本練舞頻道內可以互相指罵，但不可以對對方造成威脅、恐嚇。",
            "如情況失控可以找 <@&1061879820369272862>\n請就事論事，冷靜討論",
        )
        await channel.send(embed=warn_embed)

        embed = DefaultEmbed("練舞頻道已生成", f"[點我前往]({channel.jump_url})")
        await i.response.send_message(embed=embed, ephemeral=True)

        await self.bot.pool.execute(
            "INSERT INTO dance (channel_id, owners) VALUES ($1, $2)",
            channel.id,
            [i.user.id],
        )

    @dance_check()
    @dance_owner_check()
    @app_commands.command(name="invite", description="邀請其他人加入練舞頻道")
    @app_commands.rename(member="被邀請者")
    @app_commands.describe(member="被邀請者加入後可以在頻道中發言")
    async def dance_invite(self, i: discord.Interaction, member: discord.Member):
        channel = i.channel
        assert isinstance(channel, discord.TextChannel)
        await channel.set_permissions(member, send_messages=True)
        embed = DefaultEmbed(f"已將 {member} 加入練舞頻道")
        await i.response.send_message(embed=embed, content=member.mention)

    @dance_check()
    @dance_owner_check()
    @app_commands.command(name="delete", description="刪除練舞頻道")
    async def dance_delete(self, i: discord.Interaction):
        assert isinstance(i.channel, discord.TextChannel)
        channel = i.channel
        await channel.delete()
        embed = DefaultEmbed("練舞頻道已刪除")
        await i.response.send_message(embed=embed, ephemeral=True)
        await self.bot.pool.execute(
            "DELETE FROM dance WHERE channel_id = $1", channel.id
        )

    @dance_check()
    @dance_owner_check()
    @app_commands.command(name="transfer", description="轉移練舞頻道擁有權")
    async def dance_transfer(self, i: discord.Interaction, member: discord.Member):
        assert isinstance(i.channel, discord.TextChannel)
        channel = i.channel
        await self.bot.pool.execute(
            "UPDATE dance SET owner_id = $1 WHERE channel_id = $2",
            member.id,
            channel.id,
        )
        embed = DefaultEmbed(f"已將練舞頻道轉移給 {member}")
        await i.response.send_message(embed=embed, ephemeral=True)

    @dance_check()
    @dance_owner_check()
    @app_commands.command(name="kick", description="踢出練舞頻道")
    @app_commands.rename(member="被踢者")
    @app_commands.describe(member="被踢者將無法在頻道中發言")
    async def dance_kick(self, i: discord.Interaction, member: discord.Member):
        assert isinstance(i.channel, discord.TextChannel)
        channel = i.channel
        await channel.set_permissions(member, send_messages=False)
        embed = DefaultEmbed(f"已將 {member} 從練舞頻道踢出")
        await i.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(DanceCog(bot))
