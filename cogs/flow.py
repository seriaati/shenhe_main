from datetime import time
from random import randint
from typing import List, Optional

import discord
from discord import app_commands
from discord.ext import commands

import apps.flow as flow_app
from dev.enum import TimeType
from dev.model import BotModel, DefaultEmbed, ErrorEmbed, Inter
from utility.paginator import GeneralPaginator
from utility.utils import divide_chunks


class FlowCog(commands.Cog, name="flow"):
    def __init__(self, bot) -> None:
        self.bot: BotModel = bot
        self.debug = self.bot.debug

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        user_id = message.author.id
        if message.author.bot:
            return

        morning_keywords = ("早", "good morning", "gm", "morning")
        noon_keywords = ("午", "good noon", "noon", "gn")
        night_keywords = ("晚", "good night", "good evening", "gn")

        content = message.content.lower()

        if "早午晚" in message.content:
            return

        await flow_app.register_flow_account(user_id, self.bot.pool)
        if any(keyword in content for keyword in morning_keywords):
            start = time(0, 0, 0)
            end = time(11, 59, 59)
            gave = await flow_app.free_flow(
                user_id, start, end, TimeType.MORNING, self.bot.pool
            )
            if gave:
                await message.add_reaction("<:morning:982608491426508810>")
        elif any(keyword in content for keyword in noon_keywords):
            start = time(12, 0, 0)
            end = time(16, 59, 59)
            gave = await flow_app.free_flow(
                user_id, start, end, TimeType.NOON, self.bot.pool
            )
            if gave:
                await message.add_reaction("<:noon:982608493313929246>")
        elif any(keyword in content for keyword in night_keywords):
            start = time(17, 0, 0)
            end = time(23, 59, 59)
            gave = await flow_app.free_flow(
                user_id, start, end, TimeType.NIGHT, self.bot.pool
            )
            if gave:
                await message.add_reaction("<:night:982608497290125366>")

    @discord.app_commands.checks.cooldown(1, 900, key=lambda i: (i.guild_id, i.user.id))
    @discord.app_commands.command(name="poke", description="戳戳")
    @discord.app_commands.rename(member="使用者")
    @discord.app_commands.describe(member="被戳的使用者")
    async def poke(self, i: discord.Interaction, member: discord.Member):
        await flow_app.register_flow_account(member.id, self.bot.pool)

        success = True if randint(1, 2) == 1 else False
        flow_num = randint(1, 3)
        flow_member = await flow_app.get_user_flow(member.id, self.bot.pool)
        if flow_member < 0:
            return await i.response.send_message(
                embed=ErrorEmbed("對方的暴幣不足 (小於0)"), ephemeral=True
            )
        if success and flow_member < flow_num:
            flow_num = flow_member

        await flow_app.flow_transaction(
            member.id, -flow_num if success else flow_num, self.bot.pool
        )
        await flow_app.flow_transaction(
            i.user.id, flow_num if success else -flow_num, self.bot.pool
        )
        flow_member = await flow_app.get_user_flow(member.id, self.bot.pool)
        flow_user = await flow_app.get_user_flow(i.user.id, self.bot.pool)
        if success:
            message = f"""
            {i.user.mention} 戳到了 {member.mention}
            
            {i.user.mention} | **{flow_user}** (+{flow_num})
            {member.mention} | **{flow_member}** (-{flow_num})
            """
        else:
            message = f"""
            {i.user.mention} 想戳 {member.mention} 但是戳到了自己
            
            {i.user.mention} | **{flow_user}** (-{flow_num})
            {member.mention} | **{flow_member}** (+{flow_num})
            """
        embed = DefaultEmbed(f"{i.user.display_name} 👉 {member.display_name}", message)
        await i.response.send_message(embed=embed)

    @poke.error
    async def poke_error(self, i: discord.Interaction, error):
        if isinstance(error, app_commands.CommandOnCooldown):
            await i.response.send_message(content="十五分鐘最多戳一次哦", ephemeral=True)
        else:
            await self.bot.tree.on_error(i, error)

    @discord.app_commands.guild_only()
    @discord.app_commands.command(name="give", description="給予暴幣")
    @discord.app_commands.rename(member="使用者")
    @discord.app_commands.describe(member="被給予暴幣的使用者")
    async def give(self, i: discord.Interaction, member: discord.Member, amount: int):
        await flow_app.register_flow_account(member.id, self.bot.pool)
        await flow_app.flow_transaction(member.id, amount, self.bot.pool)
        await flow_app.flow_transaction(i.user.id, -amount, self.bot.pool)
        flow_member = await flow_app.get_user_flow(member.id, self.bot.pool)
        flow_user = await flow_app.get_user_flow(i.user.id, self.bot.pool)
        message = f"""
        {i.user.mention} 給了 {member.mention} {amount} 暴幣
        
        {i.user.mention} | **{flow_user}** (-{amount})
        {member.mention} | **{flow_member}** (+{amount})
        """
        embed = DefaultEmbed(f"{i.user.display_name} 💵 {member.display_name}", message)
        await i.response.send_message(embed=embed)

    @discord.app_commands.guild_only()
    @discord.app_commands.command(name="acc", description="查看暴幣帳號")
    @discord.app_commands.rename(member="使用者")
    @discord.app_commands.describe(member="查看其他使用者的暴幣帳號")
    async def acc(
        self, i: discord.Interaction, member: Optional[discord.Member] = None
    ):
        assert isinstance(i.user, discord.Member)
        member = member or i.user
        await flow_app.register_flow_account(member.id, self.bot.pool)
        row = await self.bot.pool.fetchrow(
            "SELECT morning, noon, night FROM flow_accounts WHERE user_id = $1",
            member.id,
        )
        flow = await flow_app.get_user_flow(member.id, self.bot.pool)
        value = ""
        emojis = [
            "<:morning:982608491426508810>",
            "<:noon:982608493313929246>",
            "<:night:982608497290125366>",
        ]
        data = (row["morning"], row["noon"], row["night"])
        for index in range(3):
            formated_time = data[index].strftime("%Y-%m-%d %H:%M:%S")
            value += f"{emojis[index]} {formated_time}\n"
        embed = DefaultEmbed()
        embed.add_field(name=f"{flow} 暴幣", value=value)
        embed.set_author(name="暴幣帳號", icon_url=member.avatar)
        await i.response.send_message(embed=embed)

    @discord.app_commands.command(name="take", description="將一個使用者的 暴幣轉回銀行")
    @discord.app_commands.rename(member="使用者", flow="要拿取的暴幣數量", private="私人訊息")
    @app_commands.describe(private="是否要顯示給使用者看 (預設為是)")
    @discord.app_commands.choices(
        private=[
            app_commands.Choice(name="是", value=1),
            app_commands.Choice(name="否", value=0),
        ]
    )
    @discord.app_commands.checks.has_permissions(manage_guild=True)
    async def take(
        self,
        i: discord.Interaction,
        member: discord.Member,
        flow: int,
        private: int = 0,
    ):
        await flow_app.register_flow_account(member.id, self.bot.pool)
        await flow_app.flow_transaction(member.id, -flow, self.bot.pool)

        embed = DefaultEmbed(
            "已成功施展「反」摩拉克斯的力量",
            f"{i.user.mention} 從 {member.mention} 的帳戶裡拿走了 {flow} 枚 暴幣",
        )
        ephemeral = True if private == 1 else False
        await i.response.send_message(embed=embed, ephemeral=ephemeral)

    @discord.app_commands.command(name="make", description="從銀行轉出暴幣給某位使用者")
    @discord.app_commands.rename(member="使用者", flow="要給予的暴幣數量", private="私人訊息")
    @app_commands.describe(private="是否要顯示給使用者看 (預設為是)")
    @discord.app_commands.choices(
        private=[
            app_commands.Choice(name="是", value=1),
            app_commands.Choice(name="否", value=0),
        ]
    )
    @discord.app_commands.checks.has_permissions(manage_guild=True)
    async def make(
        self,
        i: discord.Interaction,
        member: discord.Member,
        flow: int,
        private: int = 0,
    ):
        await flow_app.register_flow_account(member.id, self.bot.pool)
        await flow_app.flow_transaction(member.id, -flow, self.bot.pool)

        embed = DefaultEmbed(
            "已成功施展摩拉克斯的力量",
            f"{i.user.mention} 給了 {member.mention} {flow} 枚 暴幣",
        )
        ephemeral = True if private == 1 else False
        await i.response.send_message(embed=embed, ephemeral=ephemeral)

    @discord.app_commands.command(name="total", description="查看目前群組帳號及銀行 暴幣分配情況")
    async def total(self, i: discord.Interaction):
        bank = await flow_app.get_blank_flow(self.bot.pool)
        acc_count = await self.bot.pool.fetchval("SELECT COUNT(*) FROM flow_accounts")
        flow_sum = await self.bot.pool.fetchval("SELECT SUM(flow) FROM flow_accounts")
        embed = DefaultEmbed(
            f"目前共 {acc_count} 個 暴幣帳號",
            f"用戶 {flow_sum} + 銀行 {bank} = {flow_sum+bank} 枚暴幣",
        )
        await i.response.send_message(embed=embed)

    @discord.app_commands.guild_only()
    @discord.app_commands.command(name="flow_leaderboard", description="查看 暴幣排行榜")
    async def flow_leaderboard(self, inter: discord.Interaction):
        i: Inter = inter  # type: ignore
        assert i.guild is not None
        rows = await i.client.pool.fetch(
            "SELECT user_id, flow FROM flow_accounts ORDER BY flow DESC"
        )
        embeds: List[discord.Embed] = []
        div_rows = list(divide_chunks(rows, 10))

        rank = 1
        for page_number, page in enumerate(div_rows):
            embed = DefaultEmbed(f"暴幣排行榜 (第 {page_number+1} 頁)")
            embed.description = ""
            for row in page:
                discord_user = i.guild.get_member(row["user_id"])
                if discord_user is None:
                    user_name = "(已離開伺服器)"
                    await flow_app.remove_flow_account(row["user_id"], i.client.pool)
                else:
                    user_name = discord_user.display_name
                embed.description += f"{rank}. {user_name} | {row['flow']}\n"
                rank += 1
            embeds.append(embed)
        await GeneralPaginator(i, embeds).start()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(FlowCog(bot))
