from datetime import time
from random import randint

import discord
from dateutil import parser
from discord import app_commands
from discord.ext import commands

import apps.flow as flow_app
from utility.paginators.paginator import GeneralPaginator
from utility.utils import default_embed, divide_chunks


def has_flow_account():
    async def predicate(i: discord.Interaction) -> bool:
        check = await flow_app.check_flow_account(i.user.id, i.client.db)
        if not check:
            await flow_app.register_flow_account(i.user.id, i.client.db)
        return True

    return discord.app_commands.check(predicate)


class FlowCog(commands.Cog, name="flow"):
    def __init__(self, bot) -> None:
        self.bot: commands.Bot = bot
        self.debug_toggle = self.bot.debug_toggle

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
            return await message.add_reaction("<:PaimonSeria:958341967698337854>")
        check = await flow_app.check_flow_account(user_id, self.bot.db)
        if not check:
            await flow_app.register_flow_account(user_id, self.bot.db)
        if any(keyword in content for keyword in morning_keywords):
            start = time(0, 0, 0)
            end = time(11, 59, 59)
            gave = await flow_app.free_flow(user_id, start, end, "morning", self.bot.db)
            if gave:
                await message.add_reaction("<:morning:982608491426508810>")
        elif any(keyword in content for keyword in noon_keywords):
            start = time(12, 0, 0)
            end = time(16, 59, 59)
            gave = await flow_app.free_flow(user_id, start, end, "noon", self.bot.db)
            if gave:
                await message.add_reaction("<:noon:982608493313929246>")
        elif any(keyword in content for keyword in night_keywords):
            start = time(17, 0, 0)
            end = time(23, 59, 59)
            gave = await flow_app.free_flow(user_id, start, end, "night", self.bot.db)
            if gave:
                await message.add_reaction("<:night:982608497290125366>")

    @has_flow_account()
    @discord.app_commands.checks.cooldown(
        1, 3600, key=lambda i: (i.guild_id, i.user.id)
    )
    @discord.app_commands.command(name="poke", description="戳戳")
    @discord.app_commands.rename(member="使用者")
    @discord.app_commands.describe(member="被戳的使用者")
    async def poke(self, i: discord.Interaction, member: discord.Member):
        success = True if randint(1, 100) <= 50 else False
        flow_num = randint(1, 3)
        if not success:
            new_member = i.user
        else:
            new_member = member
        flow = await flow_app.get_user_flow(new_member.id, i.client.db)
        await flow_app.flow_transaction(new_member.id, 0 - flow_num, i.client.db)
        if success:
            message = (
                f"{member.mention} 被 {i.user.mention}戳了一下，剩下 __{flow - flow_num}__ 枚暴幣"
            )
        else:
            message = f"{i.user.mention} 想偷戳 {member.mention} 但戳到了自己，剩下 __{flow - flow_num}__ 枚暴幣"
        embed = default_embed("戳戳", message)
        await i.response.send_message(
            content=f"{i.user.mention}, {member.mention}", embed=embed
        )

    @poke.error
    async def poke_error(self, i: discord.Interaction, error):
        if isinstance(error, app_commands.CommandOnCooldown):
            await i.response.send_message(content="一小時最多戳一次哦", ephemeral=True)
        else:
            await self.bot.tree.on_error(i, error)

    @has_flow_account()
    @discord.app_commands.command(name="acc", description="查看暴幣帳號")
    @discord.app_commands.rename(member="使用者")
    @discord.app_commands.describe(member="查看其他使用者的暴幣帳號")
    async def acc(self, i: discord.Interaction, member: discord.Member = None):
        member = member or i.user
        async with i.client.db.execute(
            "SELECT morning, noon, night FROM flow_accounts WHERE user_id = ?",
            (member.id,),
        ) as cursor:
            data = await cursor.fetchone()
        flow = await flow_app.get_user_flow(member.id, i.client.db)
        value = ""
        emojis = [
            "<:morning:982608491426508810>",
            "<:noon:982608493313929246>",
            "<:night:982608497290125366>",
        ]
        for index in range(3):
            datetime_obj = parser.parse(data[index])
            formated_time = datetime_obj.strftime("%Y-%m-%d %H:%M:%S")
            value += f"{emojis[index]} {formated_time}\n"
        embed = default_embed()
        embed.add_field(name=f"{flow} 暴幣", value=value)
        embed.set_author(name="暴幣帳號", icon_url=member.avatar)
        await i.response.send_message(embed=embed)

    @discord.app_commands.command(name="take", description="將一個使用者的 暴幣轉回銀行")
    @discord.app_commands.rename(member="使用者", flow="要拿取的暴幣數量", private="私人訊息")
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
        private: int = 1,
    ):
        check = await flow_app.check_flow_account(member.id, i.client.db)
        if not check:
            await flow_app.register_flow_account(member.id, i.client.db)
        await flow_app.flow_transaction(member.id, -flow, i.client.db)
        embed = default_embed(
            "已成功施展「反」摩拉克斯的力量",
            f"{i.user.mention} 從 {member.mention} 的帳戶裡拿走了 {flow} 枚 暴幣",
        )
        ephemeral = True if private == 1 else False
        await i.response.send_message(embed=embed, ephemeral=ephemeral)

    @discord.app_commands.command(name="make", description="從銀行轉出暴幣給某位使用者")
    @discord.app_commands.rename(member="使用者", flow="要給予的暴幣數量", private="私人訊息")
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
        private: int = 1,
    ):
        check = await flow_app.check_flow_account(member.id, i.client.db)
        if not check:
            await flow_app.register_flow_account(member.id, i.client.db)
        await flow_app.flow_transaction(member.id, flow, i.client.db)
        embed = default_embed(
            "已成功施展摩拉克斯的力量",
            f"{i.user.mention} 給了 {member.mention} {flow} 枚 暴幣",
        )
        ephemeral = True if private == 1 else False
        await i.response.send_message(embed=embed, ephemeral=ephemeral)

    @discord.app_commands.command(name="total", description="查看目前群組帳號及銀行 暴幣分配情況")
    async def total(self, i: discord.Interaction):
        bank = await flow_app.get_blank_flow(i.client.db)
        async with i.client.db.execute(
            "SELECT COUNT(user_id) FROM flow_accounts"
        ) as cursor:
            user_count = (await cursor.fetchone())[0]
            await cursor.execute("SELECT SUM(flow) FROM flow_accounts")
            flow_sum = (await cursor.fetchone())[0]
        embed = default_embed(
            f"目前共 {user_count} 個 暴幣帳號",
            f"用戶 {flow_sum} + 銀行 {bank} = {flow_sum+bank} 枚 暴幣",
        )
        await i.response.send_message(embed=embed)

    @discord.app_commands.command(name="flow_leaderboard", description="查看 暴幣排行榜")
    async def flow_leaderboard(self, i: discord.Interaction):
        async with i.client.db.execute(
            "SELECT user_id, flow FROM flow_accounts ORDER BY flow DESC"
        ) as cursor:
            data = await cursor.fetchall()
        embeds = []
        data = list(divide_chunks(data, 10))
        rank = 1
        for page_number, page in enumerate(data):
            embed = default_embed(f"暴幣排行榜 (第 {page_number+1} 頁)")
            for _, user in enumerate(page):
                discord_user = i.client.get_user(user[0])
                if discord_user is None:
                    user_name = "(已離開伺服器)"
                else:
                    user_name = discord_user.display_name
                embed.description += f"{rank}. {user_name} | {user[1]}\n"
                rank += 1
            embeds.append(embed)
        await GeneralPaginator(i, embeds).start()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(FlowCog(bot))
