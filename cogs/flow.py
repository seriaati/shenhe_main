import uuid
from datetime import datetime, time
from typing import Any, List

import aiosqlite
import discord
from apps.flow import (
    check_flow_account,
    flow_transaction,
    free_flow,
    get_blank_flow,
    get_user_flow,
    register_flow_account,
)
from dateutil import parser
from debug import DefaultView
from discord import Button, Interaction, Member, SelectOption, TextStyle, app_commands
from discord.app_commands import Choice
from discord.ext import commands
from discord.ui import Modal, Select, TextInput
from utility.paginators.paginator import GeneralPaginator
from utility.utils import default_embed, divide_chunks, error_embed


class FlowCog(commands.Cog, name="flow"):
    def __init__(self, bot) -> None:
        self.bot: commands.Bot = bot
        self.debug_toggle = self.bot.debug_toggle

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        user_id = message.author.id
        if message.author.bot:
            return

        morning_keywords = ["早", "good morning", "gm", "morning"]
        noon_keywords = ["午", "good noon"]
        night_keywords = ["晚", "good night", "good evening", "gn"]

        content = message.content.lower()

        if "早午晚" in message.content:
            return await message.add_reaction("<:PaimonSeria:958341967698337854>")
        check = await check_flow_account(user_id, self.bot.db)
        if not check:
            await register_flow_account(user_id, self.bot.db)
        if any(keyword in content for keyword in morning_keywords):
            start = time(0, 0, 0)
            end = time(11, 59, 59)
            gave = await free_flow(user_id, start, end, "morning", self.bot.db)
            if gave:
                await message.add_reaction("<:morning:982608491426508810>")
        elif any(keyword in content for keyword in noon_keywords):
            start = time(12, 0, 0)
            end = time(16, 59, 59)
            gave = await free_flow(user_id, start, end, "noon", self.bot.db)
            if gave:
                await message.add_reaction("<:noon:982608493313929246>")
        elif any(keyword in content for keyword in night_keywords):
            start = time(17, 0, 0)
            end = time(23, 59, 59)
            gave = await free_flow(user_id, start, end, "night", self.bot.db)
            if gave:
                await message.add_reaction("<:night:982608497290125366>")

    def has_flow_account():
        async def predicate(i: Interaction) -> bool:
            check = await check_flow_account(i.user.id, i.client.db)
            if not check:
                await register_flow_account(i.user.id, i.client.db)
            return True

        return app_commands.check(predicate)

    @has_flow_account()
    @app_commands.command(name="acc", description="查看暴幣帳號")
    @app_commands.rename(member="使用者")
    @app_commands.describe(member="查看其他使用者的暴幣帳號")
    async def acc(self, i: Interaction, member: Member = None):
        member = member or i.user
        async with i.client.db.execute(
            "SELECT morning, noon, night FROM flow_accounts WHERE user_id = ?",
            (member.id,),
        ) as cursor:
            data = await cursor.fetchone()
        flow = await get_user_flow(member.id, i.client.db)
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
        embed.set_author(name=f"暴幣帳號", icon_url=member.avatar)
        await i.response.send_message(embed=embed)

    @has_flow_account()
    @app_commands.command(name="give", description="給其他人暴幣")
    @app_commands.rename(member="使用者", flow="要給予的暴幣數量")
    async def give(self, i: Interaction, member: Member, flow: int):
        if flow < 0:
            return await i.response.send_message(
                embed=error_embed(
                    message="<:PaimonSeria:958341967698337854> 還想學 <:Yeastken_ttosdog:1059516840210083880> 跟ceye洗錢啊!"
                ).set_author(name="不可以給負數 暴幣", icon_url=i.user.display_avatar.url),
                ephemeral=True,
            )
        user_flow = await get_user_flow(i.user.id, i.client.db)
        if user_flow < flow:
            return await i.response.send_message(
                embed=error_embed(f"需要至少: {flow} 暴幣").set_author(
                    name="暴幣不足", icon_url=i.user.display_avatar.url
                ),
                ephemeral=True,
            )
        await flow_transaction(i.user.id, -flow, i.client.db)
        await flow_transaction(member.id, flow, i.client.db)
        embed = default_embed(
            message=f"{i.user.mention} | -{flow} 暴幣\n" f"{member.mention} | +{flow} 暴幣"
        ).set_author(name="交易成功", icon_url=i.user.display_avatar.url)
        await i.response.send_message(
            content=f"{i.user.mention} {member.mention}", embed=embed
        )

    @app_commands.command(name="take", description="將一個使用者的 暴幣轉回銀行")
    @app_commands.rename(member="使用者", flow="要拿取的暴幣數量", private="私人訊息")
    @app_commands.choices(
        private=[Choice(name="是", value=1), Choice(name="否", value=0)]
    )
    @app_commands.checks.has_role("猜猜我是誰")
    async def take(self, i: Interaction, member: Member, flow: int, private: int = 1):
        check = await check_flow_account(member.id, i.client.db)
        if not check:
            await register_flow_account(member.id, i.client.db)
        await flow_transaction(member.id, -flow, i.client.db)
        embed = default_embed(
            "已成功施展「反」摩拉克斯的力量",
            f"{i.user.mention} 從 {member.mention} 的帳戶裡拿走了 {flow} 枚 暴幣",
        )
        ephemeral = True if private == 1 else False
        await i.response.send_message(embed=embed, ephemeral=ephemeral)

    @app_commands.command(name="make", description="從銀行轉出暴幣給某位使用者")
    @app_commands.rename(member="使用者", flow="要給予的暴幣數量", private="私人訊息")
    @app_commands.choices(
        private=[Choice(name="是", value=1), Choice(name="否", value=0)]
    )
    @app_commands.checks.has_role("猜猜我是誰")
    async def make(self, i: Interaction, member: Member, flow: int, private: int = 1):
        check = await check_flow_account(member.id, i.client.db)
        if not check:
            await register_flow_account(member.id, i.client.db)
        await flow_transaction(member.id, flow, i.client.db)
        embed = default_embed(
            "已成功施展摩拉克斯的力量",
            f"{i.user.mention} 給了 {member.mention} {flow} 枚 暴幣",
        )
        ephemeral = True if private == 1 else False
        await i.response.send_message(embed=embed, ephemeral=ephemeral)

    @app_commands.command(name="total", description="查看目前群組帳號及銀行 暴幣分配情況")
    async def total(self, i: Interaction):
        bank = await get_blank_flow(i.client.db)
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

    @app_commands.command(name="flow_leaderboard", description="查看 暴幣排行榜")
    async def flow_leaderboard(self, i: Interaction):
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

    class ShopItemView(DefaultView):
        def __init__(
            self,
            item_names: List,
            action: str,
            db: aiosqlite.Connection,
            author: Member,
        ):
            super().__init__(timeout=None)
            self.author = author
            self.add_item(FlowCog.ShopItemSelect(item_names, action, db))

        async def interaction_check(self, interaction: Interaction) -> bool:
            if self.author.id != interaction.user.id:
                await interaction.response.send_message(
                    embed=error_embed().set_author(
                        name="這不是你的操作視窗", icon_url=interaction.user.avatar
                    ),
                    ephemeral=True,
                )
            return self.author.id == interaction.user.id

    class ShopItemSelect(Select):
        def __init__(self, item_names: List, action: str, db: aiosqlite.Connection):
            self.action = action
            self.db = db
            options = []
            for item_name in item_names:
                options.append(SelectOption(label=item_name, value=item_name))
            super().__init__(
                placeholder=f"選擇要購買的商品", min_values=1, max_values=1, options=options
            )

        async def callback(self, i: Interaction) -> Any:
            if self.action == "remove":
                await i.client.db.execute(
                    "DELETE FROM flow_shop WHERE name = ?", (self.values[0],)
                )
                await i.client.db.commit()
                await i.response.send_message(
                    f"商品 **{self.values[0]}** 移除成功", ephemeral=True
                )
            elif self.action == "buy":
                async with i.client.db.execute(
                    "SELECT flow, current, max FROM flow_shop WHERE name= ?",
                    (self.values[0],),
                ) as cursor:
                    data = await cursor.fetchone()
                flow = data[0]
                current = data[1]
                max = data[2]
                user_flow = await get_user_flow(i.user.id, i.client.db)
                if user_flow < flow:
                    return await i.response.send_message(
                        embed=error_embed().set_author(
                            name="你的暴幣不足夠購買這項商品", icon_url=i.user.display_avatar.url
                        ),
                        ephemeral=True,
                    )
                if current == max:
                    return await i.response.send_message(
                        embed=error_embed().set_author(
                            name="此商品已售罄", icon_url=i.user.display_avatar.url
                        ),
                        ephemeral=True,
                    )
                log_uuid = str(uuid.uuid4())
                async with i.client.db.execute(
                    "UPDATE flow_shop SET current = ? WHERE name = ?",
                    (current + 1, self.values[0]),
                ) as cursor:
                    await cursor.execute(
                        "INSERT INTO flow_shop_log (log_uuid) VALUES (?)", (log_uuid,)
                    )
                    await cursor.execute(
                        "UPDATE flow_shop_log SET flow = ?, item = ?, buyer_id = ? WHERE log_uuid = ?",
                        (int(flow), self.values[0], int(i.user.id), str(log_uuid)),
                    )
                    await i.client.db.commit()
                await flow_transaction(i.user.id, -flow, i.client.db)
                await i.response.send_message(
                    f"<:wish:982419859117838386> {i.user.mention} 商品 **{self.values[0]}** 購買成功, 請等候律律來交付商品"
                )
                msg = await i.original_response()
                thread = await msg.create_thread(
                    name=f"{i.user} • {self.values[0]} 購買討論串"
                )
                await thread.add_user(i.user)
                lulurR = i.client.get_user(665092644883398671)
                await thread.add_user(lulurR)
                embed = default_embed(
                    "📜 購買證明",
                    f"購買人: {i.user.mention}\n"
                    f"商品: {self.values[0]}\n"
                    f"收據UUID: {log_uuid}\n"
                    f"價格: {flow}",
                )
                await thread.send(embed=embed)

    @has_flow_account()
    @app_commands.command(name="shop", description="暴幣商店")
    async def show(self, i: Interaction):
        async with i.client.db.execute(
            "SELECT name, flow, current, max FROM flow_shop"
        ) as cursor:
            data = await cursor.fetchall()
        item_str = ""
        item_names = []
        for _, tpl in enumerate(data):
            item_names.append(tpl[0])
            item_str += f"• {tpl[0]} - **{tpl[1]}** 暴幣 ({tpl[2]}/{tpl[3]})\n\n"
        embed = default_embed("🛒 暴幣商店", item_str)
        view = FlowCog.ShopItemView(item_names, "buy", i.client.db, i.user)
        await i.response.send_message(embed=embed, view=view)

    @app_commands.command(name="additem", description="新增商品")
    @app_commands.rename(item="商品名稱", flow="價格", max="最大購買次數")
    @app_commands.checks.has_role("猜猜我是誰")
    async def additem(self, i: Interaction, item: str, flow: int, max: int):
        async with i.client.db.execute(
            "INSERT INTO flow_shop (name) VALUES (?)", (item,)
        ) as cursor:
            await cursor.execute(
                "UPDATE flow_shop SET flow = ?, current = 0, max = ? WHERE name = ?",
                (flow, max, item),
            )
            await i.client.db.commit()
        await i.response.send_message(f"商品 **{item}** 新增成功", ephemeral=True)

    @app_commands.command(name="removeitem", description="刪除商品")
    @app_commands.checks.has_role("猜猜我是誰")
    async def removeitem(self, i: Interaction):
        async with i.client.db.execute("SELECT name FROM flow_shop") as cursor:
            data = await cursor.fetchall()
        item_names = []
        for _, tpl in enumerate(data):
            item_names.append(tpl[0])
        view = FlowCog.ShopItemView(item_names, "remove", self.bot.db, i.user)
        await i.response.send_message(view=view, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(FlowCog(bot))
