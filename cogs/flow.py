import uuid
from datetime import datetime, time
from typing import Any, List

import aiosqlite
import discord
from apps.flow import (check_flow_account, flow_transaction, free_flow,
                       get_blank_flow, get_user_flow, register_flow_account)
from dateutil import parser
from debug import DefaultView
from discord import (Button, Interaction, Member, SelectOption, TextStyle,
                     app_commands)
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
    async def on_message(self, message):
        user_id = message.author.id
        if message.author.bot:
            return

        if "早" in message.content or "午" in message.content or "晚" in message.content:
            if "早午晚" in message.content:
                return await message.add_reaction("<:PaimonSeria:958341967698337854>")
            check = await check_flow_account(user_id, self.bot.db)
            if not check:
                await register_flow_account(user_id, self.bot.db)
            if "早" in message.content:
                start = time(0, 0, 0)
                end = time(11, 59, 59)
                gave = await free_flow(user_id, start, end, "morning", self.bot.db)
                if gave:
                    await message.add_reaction("<:morning:982608491426508810>")
            elif "午" in message.content:
                start = time(12, 0, 0)
                end = time(16, 59, 59)
                gave = await free_flow(user_id, start, end, "noon", self.bot.db)
                if gave:
                    await message.add_reaction("<:noon:982608493313929246>")
            elif "晚" in message.content:
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
    @app_commands.command(name="acc", description="查看 flow 帳號")
    @app_commands.rename(member="使用者")
    @app_commands.describe(member="查看其他使用者的flow帳號")
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
        embed.add_field(name=f"{flow} flow", value=value)
        embed.set_author(name=f"flow 帳號", icon_url=member.avatar)
        await i.response.send_message(embed=embed)

    @has_flow_account()
    @app_commands.command(name="give", description="給其他人flow幣")
    @app_commands.rename(member="使用者", flow="要給予的flow幣數量")
    async def give(self, i: Interaction, member: Member, flow: int):
        if flow < 0:
            return await i.response.send_message(
                embed=error_embed(
                    message="<:PaimonSeria:958341967698337854> 還想學土司跟ceye洗錢啊!"
                ).set_author(name="不可以給負數 flow 幣", icon_url=i.user.display_avatar.url),
                ephemeral=True,
            )
        user_flow = await get_user_flow(i.user.id, i.client.db)
        if user_flow < flow:
            return await i.response.send_message(
                embed=error_embed(f"需要至少: {flow} flow").set_author(
                    name="flow 幣不足", icon_url=i.user.display_avatar.url
                ),
                ephemeral=True,
            )
        await flow_transaction(i.user.id, -flow, i.client.db)
        await flow_transaction(member.id, flow, i.client.db)
        embed = default_embed(
            message=f"{i.user.mention} | -{flow} flow\n"
            f"{member.mention} | +{flow} flow"
        ).set_author(name="交易成功", icon_url=i.user.display_avatar.url)
        await i.response.send_message(
            content=f"{i.user.mention} {member.mention}", embed=embed
        )

    @app_commands.command(name="take", description="將一個使用者的 flow 幣轉回銀行")
    @app_commands.rename(member="使用者", flow="要拿取的flow幣數量", private="私人訊息")
    @app_commands.choices(
        private=[Choice(name="是", value=1), Choice(name="否", value=0)]
    )
    @app_commands.checks.has_role("小雪團隊")
    async def take(self, i: Interaction, member: Member, flow: int, private: int = 1):
        check = await check_flow_account(member.id, i.client.db)
        if not check:
            await register_flow_account(member.id, i.client.db)
        await flow_transaction(member.id, -flow, i.client.db)
        embed = default_embed(
            "已成功施展「反」摩拉克斯的力量",
            f"{i.user.mention} 從 {member.mention} 的帳戶裡拿走了 {flow} 枚 flow 幣",
        )
        ephemeral = True if private == 1 else False
        await i.response.send_message(embed=embed, ephemeral=ephemeral)

    @app_commands.command(name="make", description="從銀行轉出flow幣給某位使用者")
    @app_commands.rename(member="使用者", flow="要給予的flow幣數量", private="私人訊息")
    @app_commands.choices(
        private=[Choice(name="是", value=1), Choice(name="否", value=0)]
    )
    @app_commands.checks.has_role("小雪團隊")
    async def make(self, i: Interaction, member: Member, flow: int, private: int = 1):
        check = await check_flow_account(member.id, i.client.db)
        if not check:
            await register_flow_account(member.id, i.client.db)
        await flow_transaction(member.id, flow, i.client.db)
        embed = default_embed(
            "已成功施展摩拉克斯的力量",
            f"{i.user.mention} 給了 {member.mention} {flow} 枚 flow 幣",
        )
        ephemeral = True if private == 1 else False
        await i.response.send_message(embed=embed, ephemeral=ephemeral)

    @app_commands.command(name="total", description="查看目前群組帳號及銀行 flow 幣分配情況")
    async def total(self, i: Interaction):
        bank = await get_blank_flow(i.client.db)
        async with i.client.db.execute(
            "SELECT COUNT(user_id) FROM flow_accounts"
        ) as cursor:
            user_count = (await cursor.fetchone())[0]
            await cursor.execute("SELECT SUM(flow) FROM flow_accounts")
            flow_sum = (await cursor.fetchone())[0]
        embed = default_embed(
            f"目前共 {user_count} 個 flow 帳號",
            f"用戶 {flow_sum} + 銀行 {bank} = {flow_sum+bank} 枚 flow 幣",
        )
        await i.response.send_message(embed=embed)

    @app_commands.command(name="flow_leaderboard", description="查看 flow 幣排行榜")
    async def flow_leaderboard(self, i: Interaction):
        async with i.client.db.execute(
            "SELECT user_id, flow FROM flow_accounts ORDER BY flow DESC"
        ) as cursor:
            data = await cursor.fetchall()
        embeds = []
        data = list(divide_chunks(data, 10))
        rank = 1
        for page_number, page in enumerate(data):
            embed = default_embed(f"flow 幣排行榜 (第 {page_number+1} 頁)")
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
                            name="你的flow幣不足夠購買這項商品", icon_url=i.user.display_avatar.url
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
    @app_commands.command(name="shop", description="flow 商店")
    async def show(self, i: Interaction):
        async with i.client.db.execute(
            "SELECT name, flow, current, max FROM flow_shop"
        ) as cursor:
            data = await cursor.fetchall()
        item_str = ""
        item_names = []
        for _, tpl in enumerate(data):
            item_names.append(tpl[0])
            item_str += f"• {tpl[0]} - **{tpl[1]}** flow ({tpl[2]}/{tpl[3]})\n\n"
        embed = default_embed("🛒 flow商店", item_str)
        view = FlowCog.ShopItemView(item_names, "buy", i.client.db, i.user)
        await i.response.send_message(embed=embed, view=view)

    @app_commands.command(name="additem", description="新增商品")
    @app_commands.rename(item="商品名稱", flow="價格", max="最大購買次數")
    @app_commands.checks.has_role("小雪團隊")
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
    @app_commands.checks.has_role("小雪團隊")
    async def removeitem(self, i: Interaction):
        async with i.client.db.execute("SELECT name FROM flow_shop") as cursor:
            data = await cursor.fetchall()
        item_names = []
        for _, tpl in enumerate(data):
            item_names.append(tpl[0])
        view = FlowCog.ShopItemView(item_names, "remove", self.bot.db, i.user)
        await i.response.send_message(view=view, ephemeral=True)

    def in_find_channel():
        async def predicate(i: Interaction) -> bool:
            find_channel_id = (
                909595117952856084 if i.client.debug_toggle else 960861105503232030
            )
            return i.channel.id == find_channel_id

        return app_commands.check(predicate)

    async def check_flow(self, user_id: int, flow: int):
        user_flow = await get_user_flow(user_id, self.bot.db)
        if user_flow < 0 and flow >= 0:
            return True, None
        if flow < 0:
            result = error_embed("發布失敗, 請輸入大於 0 的flow幣")
            return False, result
        elif user_flow < int(flow):
            result = error_embed("發布失敗, 請勿輸入大於自己擁有數量的flow幣")
            return False, result
        else:
            return True, None

    class AcceptView(DefaultView):
        def __init__(self, db: aiosqlite.Connection, bot):
            super().__init__(timeout=None)
            self.db = db
            self.bot = bot

        async def interaction_check(self, i: Interaction) -> bool:
            c = await self.db.cursor()
            await c.execute(
                "SELECT author_id FROM find WHERE msg_id = ?", (i.message.id,)
            )
            author_id = await c.fetchone()
            author_id = author_id[0]
            if i.user.id == author_id:
                await i.response.send_message(
                    embed=error_embed().set_author(
                        name="不能自己接自己的委託", icon_url=i.user.display_avatar.url
                    ),
                    ephemeral=True,
                )
            return i.user.id != author_id

        @discord.ui.button(
            label="接受委託",
            style=discord.ButtonStyle.green,
            custom_id="accept_commision_button",
        )
        async def confirm(self, i: Interaction, button: discord.ui.Button):
            self.stop()
            button.disabled = True
            await i.response.edit_message(view=self)
            msg = i.message
            c = await self.db.cursor()
            await c.execute("SELECT * FROM find WHERE msg_id = ?", (msg.id,))
            result = await c.fetchone()
            flow = result[1]
            title = result[2]
            type = result[3]
            author_id = result[4]
            author = i.client.get_user(author_id)
            confirmer = i.client.get_user(i.user.id)
            await c.execute(
                "SELECT uid FROM genshin_accounts WHERE user_id = ?", (confirmer.id,)
            )
            uid = (await c.fetchone())[0]
            thread = await msg.create_thread(name=f"{author.name} • {title}")
            await thread.add_user(author)
            await thread.add_user(confirmer)
            if type == 2:
                await thread.send(
                    embed=default_embed(message=uid).set_author(
                        name="接受人 uid", icon_url=confirmer.avatar
                    )
                )
            action_str = ["委託", "素材委託", "委託", "幫助"]
            for index in range(1, 5):
                if type == index:
                    await i.followup.send(
                        embed=default_embed(
                            message=f"{confirmer.mention} 已接受 {author.mention} 的 **{title}** {action_str[index-1]}"
                        ).set_author(name="委託接受", icon_url=confirmer.avatar)
                    )
            if type == 4:
                embedDM = default_embed(
                    message=f"當{confirmer.mention}完成幫忙的內容時, 請按OK來結算flow幣\n"
                    f"按下後, 你的flow幣將會 **-{flow}**\n"
                    f"對方則會 **+{flow}**"
                )
            else:
                embedDM = default_embed(
                    message=f"當{confirmer.mention}完成委託的內容時, 請按OK來結算flow幣\n"
                    f"按下後, 你的flow幣將會 **-{flow}**\n"
                    f"對方則會 **+{flow}**"
                )
            embedDM.set_author(name="結算單", icon_url=author.avatar)
            view = FlowCog.ConfirmView(self.db)
            confirm_message = await thread.send(embed=embedDM, view=view)
            await c.execute(
                "UPDATE find SET msg_id = ?, confirmer_id = ? WHERE msg_ID = ?",
                (confirm_message.id, i.user.id, i.message.id),
            )
            await c.close()
            await self.db.commit()

    class ConfirmView(DefaultView):
        def __init__(self, db: aiosqlite.Connection):
            self.db = db
            super().__init__(timeout=None)

        async def interaction_check(self, i: Interaction) -> bool:
            async with i.client.db.execute(
                "SELECT author_id FROM find WHERE msg_id = ?", (i.message.id,)
            ) as cursor:
                author_id = (await cursor.fetchone())[0]
            if i.user.id != author_id:
                await i.response.send_message(
                    embed=error_embed("你不是這個委託的發布者!"), ephemeral=True
                )
            return i.user.id == author_id

        @discord.ui.button(
            label="OK", style=discord.ButtonStyle.blurple, custom_id="ok_confirm_button"
        )
        async def ok_confirm(self, i: Interaction, button: Button):
            self.stop()
            button.disabled = True
            await i.response.edit_message(view=self)
            c: aiosqlite.Cursor = await i.client.db.cursor()
            await c.execute("SELECT * FROM find WHERE msg_id = ?", (i.message.id,))
            result = await c.fetchone()
            flow = result[1]
            title = result[2]
            type = result[3]
            author_id = result[4]
            confirmer_id = result[5]
            check = await check_flow_account(confirmer_id, i.client.db)
            if not check:
                await register_flow_account(confirmer_id, i.client.db)
            str = ""
            author = i.client.get_user(author_id)
            confirmer = i.client.get_user(confirmer_id)
            await c.execute(
                "SELECT find_free_trial FROM flow_accounts WHERE user_id = ?",
                (author_id,),
            )
            author_free_trial = (await c.fetchone())[0]
            await c.execute(
                "SELECT find_free_trial FROM flow_accounts WHERE user_id = ?",
                (confirmer_id,),
            )
            confirmer_free_trial = (await c.fetchone())[0]
            if type == 4:
                new_flow = flow
                if confirmer_free_trial < 10 and flow >= 10:
                    new_flow = flow - 10
                    await c.execute(
                        "UPDATE flow_accounts SET find_free_trial = ? WHERE user_id = ?",
                        (confirmer_free_trial + 1, confirmer_id),
                    )
                    str = f"({confirmer.mention}受到 10 flow幣贊助)\n"
                    f"已使用 {confirmer_free_trial+1}/10 次贊助機會"
                await flow_transaction(author_id, flow, i.client.db)
                await flow_transaction(confirmer_id, -new_flow, i.client.db)
                embed = default_embed(
                    "🆗 結算成功",
                    f"幫忙名稱: {title}\n"
                    f"幫助人: {author.mention} **+{flow}** flow幣\n"
                    f"被幫助人: {confirmer.mention} **-{new_flow}** flow幣\n{str}",
                )
            else:
                new_flow = flow
                if author_free_trial < 10 and flow >= 10:
                    new_flow = flow - 10
                    await c.execute(
                        "UPDATE flow_accounts SET find_free_trial = ? WHERE user_id = ?",
                        (author_free_trial + 1, author_id),
                    )
                    str = f"({author.mention}受到 10 flow幣贊助)\n"
                    f"已使用 {author_free_trial+1}/10 次贊助機會"
                await flow_transaction(author_id, -new_flow, i.client.db)
                await flow_transaction(confirmer_id, flow, i.client.db)
                embed = default_embed(
                    "🆗 結算成功",
                    f"委託名稱: {title}\n"
                    f"委託人: {author.mention} **-{new_flow}** flow幣\n"
                    f"接收人: {confirmer.mention} **+{flow}** flow幣\n{str}",
                )
            await i.followup.send(embed=embed)
            t = i.guild.get_thread(i.channel.id)
            await t.edit(archived=True, locked=True)
            await c.execute("DELETE FROM find WHERE msg_id = ?", (i.message.id,))
            await c.close()
            await self.db.commit()

    class FindView(DefaultView):
        def __init__(self):
            super().__init__(timeout=None)
            self.title = ""
            self.description = ""
            self.flow = None
            self.type = None

            self.add_item(FlowCog.FindTypeSelect())

    class FindTypeSelect(Select):
        def __init__(self):
            options = [
                SelectOption(
                    label="1類委託", description="其他玩家進入你的世界(例如: 陪玩, 打素材等)", value=1
                ),
                SelectOption(label="2類委託", description="你進入其他玩家的世界(例如: 拿特產)", value=2),
                SelectOption(
                    label="3類委託", description="其他委託(例如: 打apex, valorant)", value=3
                ),
                SelectOption(label="4類委託", description="可以幫助別人(讓拿素材, 可幫打刀鐔等)", value=4),
            ]
            super().__init__(placeholder="選擇委託類型", options=options)

        async def callback(self, i: Interaction) -> Any:
            self.view: FlowCog.FindView
            modal = FlowCog.FindModal()
            await i.response.send_modal(modal)
            await modal.wait()
            self.view.type = self.values[0]
            self.view.title = modal.find_title.value
            self.view.description = modal.description.value
            self.view.flow = modal.flow.value
            self.view.stop()

    class FindModal(Modal):
        find_title = TextInput(label="標題", placeholder="跟公子以及他的同夥要錢錢！")
        description = TextInput(
            label="敘述", placeholder="打周本 x5", style=TextStyle.long, required=False
        )
        flow = TextInput(label="flow 幣數量", placeholder="100")

        def __init__(self) -> None:
            super().__init__(title="發布委託", timeout=None)

        async def on_submit(self, i: Interaction) -> None:
            if not self.flow.value.isnumeric():
                return await i.response.send_message(
                    embed=error_embed(message="例如 100, 1000, 10000").set_author(
                        name="flow 幣數量: 請輸入數字", icon_url=i.user.display_avatar.url
                    ),
                    ephemeral=True,
                )
            self.stop()
            await i.response.defer()

    @in_find_channel()
    @has_flow_account()
    @app_commands.command(name="find", description="發布委託")
    @app_commands.rename(tag="tag人開關")
    @app_commands.describe(tag="是否要tag 委託通知 身份組?")
    @app_commands.choices(
        tag=[Choice(name="不 tag", value=0), Choice(name="我 tag 爆", value=1)]
    )
    async def find(self, i: Interaction, tag: int = 1):
        channel = i.client.get_channel(962311051683192842)
        role_found = False
        if not self.debug_toggle:
            WLroles = []
            for index in range(1, 9):
                WLroles.append(
                    discord.utils.get(i.user.guild.roles, name=f"W{str(index)}")
                )
            for r in WLroles:
                if r in i.user.roles:
                    role_name = r.name
                    role_found = True
                    break

        view = FlowCog.FindView()
        await i.response.send_message(view=view, ephemeral=True)
        await view.wait()
        if "" in [view.title, view.flow]:
            return
        flow = int(view.flow)
        title = view.title
        description = view.description
        type = int(view.type)

        check, msg = await self.check_flow(i.user.id, flow)
        if check == False:
            await i.response.send_message(embed=msg, ephemeral=True)
            return

        if not role_found:
            role_str = f"請至 {channel.mention} 選擇世界等級身份組"
        else:
            if type == 1:
                if role_name == "W8":
                    role_str = role_name
                else:
                    role_str = f">= {role_name}"
            else:
                if role_name == "W1":
                    role_str = role_name
                else:
                    role_str = f"<= {role_name}"

        c: aiosqlite.Cursor = await i.client.db.cursor()
        await c.execute(
            "SELECT uid FROM genshin_accounts WHERE user_id = ?", (i.user.id,)
        )
        uid = await c.fetchone()
        uid = uid[0]

        embed = default_embed(title, description)
        if type == 1:
            embed.set_author(name="1 類委託 - 請求幫助")
            embed.add_field(
                name="資訊",
                value=f"發布者: {i.user.mention}\n"
                f"flow幣: {flow}\n"
                f"世界等級: {role_str}\n"
                f"發布者 UID: {uid}",
            )
        elif type == 2:
            embed.set_author(name="2 類委託 - 需要素材")
            embed.add_field(
                name="資訊",
                value=f"發布者: {i.user.mention}\n"
                f"flow幣: {flow}\n"
                f"世界等級: {role_str}\n"
                f"發布者 UID: {uid}",
            )
        elif type == 3:
            embed.set_author(name="3 類委託 - 其他")
            embed.add_field(
                name="資訊", value=f"發布者: {i.user.mention}\n" f"flow幣: {flow}"
            )
        elif type == 4:
            embed.set_author(name="1 類委託 - 可以幫助")
            embed.add_field(
                name="資訊",
                value=f"發布者: {i.user.mention}\n"
                f"flow幣: {flow}\n"
                f"世界等級: {role_name}\n"
                f"發布者 UID: {uid}",
            )
        view = self.AcceptView(self.bot.db, self.bot)
        msg = await i.channel.send(
            content="<@&965141973700857876>" if tag == 1 else "", embed=embed, view=view
        )
        await c.execute(
            "INSERT INTO find(msg_id, flow, title, type, author_id) VALUES (?, ?, ?, ?, ?)",
            (msg.id, flow, title, type, i.user.id),
        )
        await c.close()
        await self.bot.db.commit()
        
    # @app_commands.command(name="tidy_up", description="整理 flow 帳號")
    # async def tidy_up_flow_acc(self, i: Interaction):
    #     await i.response.send_message(content="整理中...", ephemeral=True)
    #     async with i.client.db.execute(
    #         "SELECT user_id, last_trans, flow FROM flow_accounts"
    #     ) as cursor:
    #         data = await cursor.fetchall()
    #     remove_ids = {}
    #     for _, tpl in enumerate(data):
    #         user_id = tpl[0]
    #         last_trans = tpl[1]
    #         flow = tpl[2]
    #         if flow == 0:
    #             continue
    #         discord_user = i.guild.get_member(user_id)
    #         if discord_user is None:
    #             remove_ids[user_id] = flow
    #         else:
    #             last_trans = parser.parse(last_trans)
    #             diff = datetime.now()-last_trans
    #             if diff.days > 7:
    #                 remove_ids[user_id] = flow
    #     for user_id, flow in remove_ids.items():
    #         await i.channel.send(content=f"<@{user_id}>",embed=default_embed(f'flow 帳號掰掰 ({flow} flow)','由於距離上次活躍時間已經超過 7 天，你的 flow 帳號已經被移除\n如果你想要拿回裡面的 flow 存款，請 tag <@410036441129943050>'))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(FlowCog(bot))
