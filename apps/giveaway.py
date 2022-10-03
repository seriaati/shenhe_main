import ast
import asyncio
import random
from typing import List, Tuple

from discord import ButtonStyle, Interaction, SelectOption, ui, utils
from utility.utils import default_embed, error_embed

from apps.flow import flow_transaction, get_user_flow


class View(ui.View):
    def __init__(self, options: List[SelectOption]):
        super().__init__(timeout=1200)
        self.add_item(AddGift())
        self.add_item(RemoveGift())
        self.add_item(Start())
        self.add_item(SetRoleName())
        self.add_item(RoleSelect(options))

    async def on_error(self, i: Interaction, error, item):
        embed = error_embed(message=f"```\n{error}\n```").set_author(
            name="未知錯誤", icon_url=i.user.display_avatar.url
        )
        await i.response.send_message(embed=embed)

    async def interaction_check(self, i: Interaction) -> bool:
        role = utils.find(lambda r: r.name == "小雪團隊", i.guild.roles)
        return role in i.user.roles


class AddGift(ui.Button):
    def __init__(self):
        super().__init__(label="新增獎品", style=ButtonStyle.green, custom_id="add_gift")

    async def callback(self, i: Interaction):
        await i.response.send_modal(Modal())


class RemoveGift(ui.Button):
    def __init__(self):
        super().__init__(label="移除獎品", style=ButtonStyle.red, custom_id="remove_gift")

    async def callback(self, i: Interaction):
        self.view: View
        async with i.client.db.execute("SELECT * FROM giveaway_gifts") as cursor:
            gifts = await cursor.fetchall()
        if not gifts:
            await i.response.send_message(
                embed=error_embed(message="沒有獎品可以移除"), ephemeral=True
            )
        else:
            gift_options = []
            for gift in gifts:
                gift_options.append(SelectOption(label=gift[0], value=str(gift[0])))
            self.view.clear_items()
            self.view.add_item(Select(gift_options))
            await i.response.edit_message(view=self.view)


class Modal(ui.Modal):
    name = ui.TextInput(label="獎品名稱", placeholder="請輸入獎品名稱")
    num = ui.TextInput(label="數量", placeholder="最少數量的獎品會被當作大獎")

    def __init__(self):
        super().__init__(title="新增獎品", custom_id="add_gift")

    async def on_error(self, i: Interaction, error):
        embed = error_embed(message=f"```\n{error}\n```").set_author(
            name="未知錯誤", icon_url=i.user.display_avatar.url
        )
        await i.response.send_message(embed=embed)

    async def on_submit(self, i: Interaction):
        await i.client.db.execute(
            "INSERT INTO giveaway_gifts (name, num) VALUES (?, ?) ON CONFLICT (name) DO UPDATE SET num = ? WHERE name = ?",
            (self.name.value, self.num.value, self.num.value, self.name.value),
        )
        await i.client.db.commit()
        await i.response.edit_message(embed=await return_giveaway_embed(i))


class SetRoleName(ui.Button):
    def __init__(self):
        super().__init__(
            label="設定身份組名稱", style=ButtonStyle.gray, custom_id="set_role_name"
        )

    async def callback(self, i: Interaction):
        await i.response.send_modal(SetRoleNameModal())


class SetRoleNameModal(ui.Modal):
    role_name = ui.TextInput(
        label="身份組名稱", placeholder="此抽獎的得獎人（們）會獲得的身份組之名稱", default="名稱內請包含「λ」字符"
    )

    def __init__(self):
        super().__init__(title="設定身份組名稱", custom_id="set_role_name_modal")

    async def on_submit(self, i: Interaction):
        i.client.gv_role_name = self.role_name.value
        await i.response.edit_message(embed=await return_giveaway_embed(i))


class RoleSelect(ui.Select):
    def __init__(self, options: List[SelectOption]):
        disabled = False
        if not options:
            options = [SelectOption(label="沒有身份組", value="None")]
            disabled = True
        super().__init__(
            placeholder="不可以參加這個抽獎的身份組",
            options=options,
            min_values=0,
            max_values=len(options),
            custom_id="role_select",
            disabled=disabled,
        )

    async def callback(self, i: Interaction):
        for value in self.values:
            if value in i.client.gv_role_blacklist:
                i.client.gv_role_blacklist.remove(value)
            else:
                i.client.gv_role_blacklist.append(value)
        await i.response.edit_message(embed=await return_giveaway_embed(i))


class Select(ui.Select):
    def __init__(self, options: List[SelectOption]):
        super().__init__(placeholder="選擇獎品", options=options)

    async def callback(self, i: Interaction):
        await i.client.db.execute(
            "DELETE FROM giveaway_gifts WHERE name = ?", (self.values[0],)
        )
        await i.client.db.commit()
        await i.response.edit_message(embed=await return_giveaway_embed(i))


class Start(ui.Button):
    def __init__(self):
        super().__init__(label="開始抽獎", style=ButtonStyle.blurple, custom_id="start")

    async def callback(self, i: Interaction):
        if i.client.gv_role_name == "":
            return await i.response.send_message(
                embed=error_embed().set_author(
                    name="請先設定身份組名稱", icon_url=i.user.display_avatar.url
                ),
                ephemeral=True,
            )
        await i.response.send_modal(StartModal())


class StartModal(ui.Modal):
    goal = ui.TextInput(label="目標金額", placeholder="請輸入目標金額")
    ticket = ui.TextInput(label="參加抽獎所需金額", placeholder="請輸入參加抽獎所需金額")

    def __init__(self):
        super().__init__(title="開始抽獎", custom_id="start")

    async def on_error(self, i: Interaction, error):
        embed = error_embed(message=f"```\n{error}\n```").set_author(
            name="未知錯誤", icon_url=i.user.display_avatar.url
        )
        await i.response.send_message(embed=embed)

    async def on_submit(self, i: Interaction):
        await i.client.db.execute(
            "INSERT INTO giveaway (id, goal, ticket, current, members) VALUES (1, ?, ?, 0, ?) ON CONFLICT (id) DO UPDATE SET goal = ?, ticket = ?, current = 0, members = ? WHERE id = 1",
            (
                self.goal.value,
                self.ticket.value,
                "[]",
                self.goal.value,
                self.ticket.value,
                "[]",
            ),
        )
        await i.client.db.commit()
        await i.response.send_message(
            embed=default_embed().set_author(
                name="抽獎已開始", icon_url=i.user.display_avatar.url
            ),
            ephemeral=True,
        )
        channel_id = i.channel.id if i.client.debug_toggle else 965517075508498452
        channel = i.client.get_channel(channel_id)
        await channel.send(
            embed=await return_giveaway_progress_embed(i), view=Giveaway()
        )


async def return_giveaway_embed(i: Interaction):
    embed = default_embed("抽獎設置")
    async with i.client.db.execute("SELECT * FROM giveaway_gifts") as cursor:
        gifts = await cursor.fetchall()
    value = ""
    if not gifts:
        value = "目前沒有獎品可以抽, 請先新增獎品"
    else:
        for gift in gifts:
            value += f"• {gift[0]} - {gift[1]}份\n"
    embed.add_field(name="獎品", value=value, inline=False)
    value = ""
    gv_role_blacklist = i.client.gv_role_blacklist
    if not gv_role_blacklist:
        value = "目前沒有身分組被設定為不能參加抽獎"
    else:
        for role in gv_role_blacklist:
            role = i.guild.get_role(int(role))
            value += f"• {role.mention}\n"
    embed.add_field(name="不可以參加這個抽獎的身份組", value=value, inline=False)
    value = ""
    gv_role_name = i.client.gv_role_name
    if gv_role_name == "":
        value = "目前沒有設定身份組名稱"
    else:
        value = gv_role_name
    embed.add_field(name="身份組名稱", value=value, inline=False)
    return embed


class Giveaway(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Join())
        self.add_item(Leave())
        self.add_item(ForceEnd())

    async def on_error(self, i: Interaction, error, item):
        embed = error_embed(message=f"```\n{error}\n```").set_author(
            name="未知錯誤", icon_url=i.user.display_avatar.url
        )
        await i.response.send_message(embed=embed)


class Join(ui.Button):
    def __init__(self):
        super().__init__(label="參加抽獎", style=ButtonStyle.green, custom_id="join")

    async def callback(self, i: Interaction):
        async with i.client.db.execute(
            "SELECT members, ticket FROM giveaway"
        ) as cursor:
            data = await cursor.fetchone()
        members = data[0]
        members: List = ast.literal_eval(members)
        if i.user.id in members:
            return await i.response.send_message(
                embed=error_embed().set_author(
                    name="你已經參加過抽獎了", icon_url=i.user.display_avatar.url
                ),
                ephemeral=True,
            )
        for role_id in i.client.gv_role_blacklist:
            role = i.guild.get_role(int(role_id))
            if role in i.user.roles:
                return await i.response.send_message(
                    embed=error_embed(message=f"因為你有 {role.mention} 身份組").set_author(
                        name="你不能參加這個抽獎", icon_url=i.user.display_avatar.url
                    ),
                    ephemeral=True,
                )
        ticket = data[1]
        flow = await get_user_flow(i.user.id, i.client.db)
        if flow < int(ticket):
            return await i.response.send_message(
                embed=error_embed(message=f"需要 {ticket} flow").set_author(
                    name="金額不足", icon_url=i.user.display_avatar.url
                ),
                ephemeral=True,
            )
        await flow_transaction(i.user.id, -ticket, i.client.db)
        members.append(i.user.id)
        await i.client.db.execute(
            "UPDATE giveaway SET members = ?, current = current + ?",
            (str(members), ticket),
        )
        await i.client.db.commit()
        await i.response.edit_message(
            embed=await return_giveaway_progress_embed(i), view=Giveaway()
        )
        async with i.client.db.execute("SELECT goal, current FROM giveaway") as cursor:
            data = await cursor.fetchone()
        goal = data[0]
        current = data[1]
        if current >= goal:
            await i.message.delete()
            await reveal_giveaway_winner(i)


class Leave(ui.Button):
    def __init__(self):
        super().__init__(label="退出抽獎", style=ButtonStyle.red, custom_id="leave")

    async def callback(self, i: Interaction):
        async with i.client.db.execute(
            "SELECT members, ticket FROM giveaway"
        ) as cursor:
            data = await cursor.fetchone()
        members = data[0]
        ticket = data[1]
        members: List = ast.literal_eval(members)
        try:
            members.remove(i.user.id)
        except ValueError:
            return await i.response.send_message(
                embed=error_embed(message="那要怎麼退出").set_author(
                    name="你沒有參加這個抽獎", icon_url=i.user.display_avatar.url
                ),
                ephemeral=True,
            )
        await flow_transaction(i.user.id, ticket, i.client.db)
        await i.client.db.execute(
            "UPDATE giveaway SET members = ?, current = current - ?",
            (str(members), ticket),
        )
        await i.client.db.commit()
        await i.response.edit_message(
            embed=await return_giveaway_progress_embed(i), view=Giveaway()
        )


class ForceEnd(ui.Button):
    def __init__(self):
        super().__init__(label="強制結束", style=ButtonStyle.grey, custom_id="force_end")

    async def callback(self, i: Interaction):
        role = utils.find(lambda r: r.name == "小雪團隊", i.guild.roles)
        if role not in i.user.roles:
            return await i.response.send_message(
                embed=error_embed(message="你沒有權限").set_author(
                    name="權限不足", icon_url=i.user.display_avatar.url
                ),
                ephemeral=True,
            )
        async with i.client.db.execute("SELECT members FROM giveaway") as cursor:
            members = (await cursor.fetchone())[0]
        members = ast.literal_eval(members)
        async with i.client.db.execute("SELECT SUM(num) FROM giveaway_gifts") as cursor:
            gift_sum = (await cursor.fetchone())[0]
        if gift_sum > len(members):
            return await i.response.send_message(
                embed=error_embed(message="參與人數不足").set_author(
                    name="獎品總數量大於目前參與人數", icon_url=i.user.display_avatar.url
                ),
                ephemeral=True,
            )
        await i.message.delete()
        await reveal_giveaway_winner(i)


async def return_giveaway_progress_embed(i: Interaction):
    embed = default_embed("🎉 抽獎啦 🎉")
    async with i.client.db.execute("SELECT * FROM giveaway") as cursor:
        giveaway = await cursor.fetchone()
    members = ast.literal_eval(giveaway[3])
    embed.add_field(name="參加人數", value=len(members))
    embed.add_field(name="目前金額", value=f"{giveaway[2]}/{giveaway[0]}")
    embed.add_field(name="參加抽獎所需金額", value=f"{giveaway[1]} flow")
    async with i.client.db.execute("SELECT * FROM giveaway_gifts") as cursor:
        gifts = await cursor.fetchall()
    if not gifts:
        value = "目前沒有獎品可以抽, 請先新增獎品"
    else:
        value = ""
        for gift in gifts:
            value += f"• {gift[0]} - {gift[1]}份\n"
    embed.add_field(name="獎品", value=value)
    return embed


async def reveal_giveaway_winner(i: Interaction):
    async with i.client.db.execute("SELECT members FROM giveaway") as cursor:
        members = (await cursor.fetchone())[0]
    members: List[int] = ast.literal_eval(members)
    content = ""
    for member in members:
        content += f"<@{member}> "
    async with i.client.db.execute(
        "SELECT * FROM giveaway_gifts ORDER BY num ASC"
    ) as cursor:
        gifts: List[Tuple] = await cursor.fetchall()
    value = ""
    gift_list = []
    for gift in gifts:
        for _ in range(gift[1]):
            gift_list.append(f"• {gift[0]}")
            value += f"• {gift[0]}\n"
    embed = default_embed("目標金額已達成, 開始抽獎")
    embed.add_field(name="獎品", value=value)
    message = await i.channel.send(content=content, embed=embed)
    gifts.reverse()
    gift_list.reverse()
    index = 0
    for gift in gifts:
        for _ in range(gift[1]):
            if not members:
                members = i.guild.members
            winner = random.choice(members)
            members.remove(winner)
            if not members:
                members = i.guild.members
            msg = await i.channel.send(f"可能是... <@{random.choice(members)}>")
            await asyncio.sleep(1.5)
            for _ in range(3):
                await msg.edit(content=f"可能是... <@{random.choice(members)}>")
                await asyncio.sleep(1.5)
            winner_user = i.guild.get_member(winner)
            winner_role = utils.find(
                lambda r: r.name == i.client.gv_role_name, i.guild.roles
            )
            if winner_role is None:
                winner_role = await i.guild.create_role(name=i.client.gv_role_name)
            await winner_user.add_roles(winner_role)
            await msg.edit(content=f"可能是... <@{winner}>")
            await asyncio.sleep(1.5)
            gift_list[index] = f"• {gift[0]} - <@{winner}>"
            value = ""
            gift_list.reverse()
            for v in gift_list:
                value += f"{v}\n"
            gift_list.reverse()
            embed.clear_fields()
            embed.add_field(name="獎品", value=value)
            await msg.edit(content=f"🎉 恭喜 <@{winner}> 獲得 {gift[0]} 🎉")
            await message.edit(embed=embed)
            index += 1
    await asyncio.sleep(2)
    await i.channel.send(embed=default_embed("抽獎結束, 感謝大家的參與"))
    await i.client.db.execute("DELETE FROM giveaway")
    await i.client.db.execute("DELETE FROM giveaway_gifts")
    await i.client.db.commit()
