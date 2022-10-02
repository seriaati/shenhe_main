import ast
import asyncio
import random
from typing import List, Tuple

from discord import ButtonStyle, Interaction, SelectOption, ui, utils
from utility.utils import default_embed, error_embed

from apps.flow import flow_transaction, get_user_flow


class View(ui.View):
    def __init__(self):
        super().__init__(timeout=1200)
        self.add_item(AddGift())
        self.add_item(RemoveGift())
        self.add_item(Start())

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
            "INSERT INTO giveaway_gifts (name, num) VALUES (?, ?) ON CONFLICT DO UPDATE SET num = ? WHERE name = ?",
            (self.name.value, self.num.value, self.num.value, self.name.value),
        )
        await i.client.db.commit()
        await i.response.edit_message(embed=await return_giveaway_embed(i), view=View())


class Select(ui.Select):
    def __init__(self, options: List[SelectOption]):
        super().__init__(placeholder="選擇獎品", options=options)

    async def callback(self, i: Interaction):
        await i.client.db.execute(
            "DELETE FROM giveaway_gifts WHERE name = ?", (self.values[0],)
        )
        await i.client.db.commit()
        await i.response.edit_message(embed=await return_giveaway_embed(i), view=View())


class Start(ui.Button):
    def __init__(self):
        super().__init__(label="開始抽獎", style=ButtonStyle.blurple, custom_id="start")

    async def callback(self, i: Interaction):
        await i.response.send_modal(StartModal())


class StartModal(ui.Modal):
    ticket = ui.TextInput(label="參加抽獎所需金額", placeholder="請輸入參加抽獎所需金額")

    def __init__(self):
        super().__init__(title="開始抽獎", custom_id="start")

    async def on_error(self, i: Interaction, error):
        embed = error_embed(message=f"```\n{error}\n```").set_author(
            name="未知錯誤", icon_url=i.user.display_avatar.url
        )
        await i.response.send_message(embed=embed)

    async def on_submit(self, i: Interaction):
        async with i.client.db.execute("SELECT SUM(num) FROM giveaway_gifts") as cursor:
            gift_sum = (await cursor.fetchone())[0]
        await i.client.db.execute(
            "INSERT INTO giveaway (id, goal, ticket, current, members) VALUES (1, ?, ?, 0, ?) ON CONFLICT DO UPDATE SET goal = ?, ticket = ?, current = 0, members = ? WHERE id = 1",
            (
                int(self.ticket.value)*int(gift_sum),
                self.ticket.value,
                "[]",
                int(self.ticket.value)*int(gift_sum),
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
    if not gifts:
        embed.description = "目前沒有獎品可以抽, 請先新增獎品"
    else:
        for gift in gifts:
            embed.description += f"• {gift[0]} - {gift[1]}份\n"
    return embed


class Giveaway(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Join())
        self.add_item(Leave())

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
        members: List = ast.literal_eval(members)
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
            winner = random.choice(members)
            members.remove(winner)
            msg = await i.channel.send(f"抽獎中... <@{random.choice(members)}>")
            await asyncio.sleep(1.5)
            for _ in range(3):
                await msg.edit(content=f"抽獎中... <@{random.choice(members)}>")
                await asyncio.sleep(1.5)
            await msg.edit(content=f"<@{winner}>")
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
