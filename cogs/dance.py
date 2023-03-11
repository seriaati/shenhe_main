import discord
from discord import app_commands, utils
from discord.ext import commands
import uuid

from utility.utils import default_embed


def dance_check():
    async def the_check(i: discord.Interaction):
        result = i.channel.name.startswith("練舞頻道")
        if not result:
            embed = default_embed("你必須在練舞頻道裡才能用這個指令")
            await i.response.send_message(embed=embed, ephemeral=True)
        return result

    return app_commands.check(the_check)


class DanceCog(commands.GroupCog, name="dance"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        super().__init__()

    @app_commands.command(name="new", description="生成練舞頻道")
    async def dance_new(self, i: discord.Interaction):
        special_category = utils.get(i.guild.categories, name="特殊頻道")
        channel = await special_category.create_text_channel(
            name=f"練舞頻道-{str(uuid.uuid4())[2]}"
        )
        await channel.set_permissions(i.guild.default_role, read_messages=False)
        traveler = utils.get(i.guild.roles, name="旅行者")
        await channel.set_permissions(traveler, read_messages=False)
        await channel.set_permissions(i.user, read_messages=True)

        warn_embed = default_embed(
            "⚠️ 本練舞頻道內可以互相指罵，但不可以對對方造成威脅、恐嚇。\n如情況失控可以找管理員", "請就事論事，冷靜討論"
        )
        await channel.send(embed=warn_embed)

        embed = default_embed("練舞頻道已生成", f"[點我前往]({channel.jump_url})")
        await i.response.send_message(embed=embed, ephemeral=True)

    @dance_check()
    @app_commands.command(name="invite", description="邀請其他人加入練舞頻道")
    async def dance_invite(self, i: discord.Interaction, member: discord.Member):
        channel = i.channel
        await channel.set_permissions(member, read_messages=True)
        embed = default_embed(f"已將 {member.mention} 加入練舞頻道")
        await i.response.send_message(embed=embed, ephemeral=True)

    @dance_check()
    @app_commands.command(name="delete", description="刪除練舞頻道")
    async def dance_delete(self, i: discord.Interaction):
        channel = i.channel
        await channel.delete()
        embed = default_embed("練舞頻道已刪除")
        await i.response.send_message(embed=embed, ephemeral=True)

    @dance_check()
    @app_commands.command(name="leave", description="離開練舞頻道")
    async def dance_leave(self, i: discord.Interaction):
        await i.response.defer(ephemeral=True)
        channel = i.channel
        await channel.set_permissions(i.user, read_messages=False)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(DanceCog(bot))
