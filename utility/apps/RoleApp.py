import asyncio
from datetime import datetime
import aiosqlite
import discord
from utility.utils import defaultEmbed, errEmbed
from pytz import timezone


class View(discord.ui.View):
    def __init__(self, author: discord.Member, tier: int):
        super().__init__(timeout=500)
        custom_color = CustomColor()
        custom_color.disabled = False if tier == 0 else True
        custom_role_name = CustomRoleName()
        custom_role_name.disabled = False if tier == 1 else True
        custom_role_emoji = CustomRoleEmoji()
        custom_role_emoji.disabled = False if tier == 2 else True
        change_name_or_color = ChangeNameOrColor()
        change_name_or_color.disabled = True if tier == 0 else False
        self.add_item(custom_color)
        self.add_item(custom_role_name)
        self.add_item(custom_role_emoji)
        self.add_item(change_name_or_color)
        self.author = author
        self.tier = tier

    async def interaction_check(self, i: discord.Interaction) -> bool:
        if i.user.id == self.author.id:
            return True
        else:
            await i.response.send_message(
                emebd=errEmbed(message="這不是給你按的").set_author(
                    name="抱歉", icon_url=i.user.display_avatar.url
                ),
                ephemeral=True,
            )
            return False

    async def on_error(self, i: discord.Interaction, error: Exception, item) -> None:
        await i.response.send_message(
            embed=errEmbed(message="出錯了餒")
            .set_author(name="哭啊", icon_url=i.user.display_avatar.url)
            .add_field(name="錯誤訊息", value=error),
            ephemeral=True,
        )

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        await self.message.edit(view=self)


class CustomColor(discord.ui.Button):
    def __init__(self):
        super().__init__(label="自訂顏色", emoji="🎨", row=1)

    async def callback(self, i: discord.Interaction):
        await i.response.send_modal(CustomColorModal(self.view))


class CustomColorModal(discord.ui.Modal):
    color_code = discord.ui.TextInput(label="顏色代碼", placeholder="請輸入顏色代碼, 例如 #2596be")

    def __init__(self, view: View):
        super().__init__(title="自訂身份組顏色", timeout=500)
        self.view = view

    async def on_submit(self, i: discord.Interaction) -> None:
        try:
            color = discord.Color.from_str(self.color_code.value)
        except ValueError:
            return await i.response.send_message(
                embed=errEmbed(message="例如: #2596be").set_author(
                    name="請輸入正確的顏色代碼", icon_url=i.user.display_avatar.url
                ),
                ephemeral=True,
            )
        role = await i.guild.create_role(
            name=f"temp-{self.color_code.value}",
            color=color,
        )
        await i.user.add_roles(role)
        self.view.clear_items()
        self.view.add_item(ConfirmColor(self.color_code.value))
        self.view.add_item(CancelColor(role))
        await i.response.edit_message(
            embed=defaultEmbed(message="你有 1 分鐘的時間可以體驗這個顏色, 如果你不滿意, 可以現在更換").set_author(
                name=f"已為你創建一個顏色為 {self.color_code.value} 的身份組",
                icon_url=i.user.display_avatar.url,
            ),
            view=self.view,
        )
        await asyncio.sleep(60)
        try:
            await i.user.remove_roles(role)
            await role.delete()
        except (discord.Forbidden, discord.HTTPException):
            pass


class ConfirmColor(discord.ui.Button):
    def __init__(self, color_code: str):
        super().__init__(label="確認", style=discord.ButtonStyle.green)
        self.color_code = color_code

    async def callback(self, i: discord.Interaction):
        now = datetime.now()
        now += timezone("Asia/Taipei").utcoffset(now)
        await flow_transaction(i, i.user.id, 150, i.client.db)
        try:
            color = discord.Color.from_str(self.color_code)
        except ValueError:
            return await i.response.send_message(
                embed=errEmbed(message="例如: #2596be").set_author(
                    name="請輸入正確的顏色代碼", icon_url=i.user.display_avatar.url
                ),
                ephemeral=True,
            )
        role = await i.guild.create_role(name=self.color_code, color=color, hoist=True)
        async with i.client.db.cursor() as c:
            c: aiosqlite.Cursor
            await c.execute(
                "UPDATE custom_role SET tier = 1, role_id = ?, last_pay_time = ? WHERE user_id = ?",
                (
                    role.id,
                    datetime.strftime(now, "%Y/%m/%d %H:%M:%S"),
                    i.user.id,
                ),
            )
            await i.client.db.commit()
        await i.user.add_roles(role)
        for item in self.view.children:
            item.disabled = True
        await i.response.edit_message(
            embed=defaultEmbed().set_author(
                name="已給予身份組", icon_url=i.user.display_avatar.url
            ),view=self.view
        )
        await asyncio.sleep(1.5)
        await return_custom_role(i, i.client.db)


class CancelColor(discord.ui.Button):
    def __init__(self, role: discord.Role):
        super().__init__(label="更換")
        self.role = role

    async def callback(self, i: discord.Interaction):
        try:
            await i.user.remove_roles(self.role)
        except (discord.Forbidden, discord.HTTPException):
            pass
        await i.response.send_modal(CustomColorModal(self.view))


class CustomRoleName(discord.ui.Button):
    def __init__(self):
        super().__init__(label="自訂身份組名稱", emoji="📝", row=1)
    
    async def callback(self, i: discord.Interaction):
        await i.response.send_modal(CustomRoleNameModal(self.view))

class CustomRoleNameModal(discord.ui.Modal):
    role_name = discord.ui.TextInput(label="身份組名稱", placeholder="請輸入身份組名稱, 例如: 機機好可愛", max_length=20)

    def __init__(self, view: View):
        super().__init__(title="自訂身份組顏色", timeout=500)
        self.view = view

    async def on_submit(self, i: discord.Interaction) -> None:
        try:
            color = discord.Color.from_str(self.color_code.value)
        except ValueError:
            return await i.response.send_message(
                embed=errEmbed(message="例如: #2596be").set_author(
                    name="請輸入正確的顏色代碼", icon_url=i.user.display_avatar.url
                ),
                ephemeral=True,
            )
        role = await i.guild.create_role(
            name=f"temp-{self.color_code.value}",
            color=color,
        )
        await i.user.add_roles(role)
        self.view.clear_items()
        self.view.add_item(ConfirmColor(self.color_code.value))
        self.view.add_item(CancelColor(role))
        await i.response.edit_message(
            embed=defaultEmbed(message="你有 1 分鐘的時間可以體驗這個顏色, 如果你不滿意, 可以現在更換").set_author(
                name=f"已為你創建一個顏色為 {self.color_code.value} 的身份組",
                icon_url=i.user.display_avatar.url,
            ),
            view=self.view,
        )
        await asyncio.sleep(60)
        try:
            await i.user.remove_roles(role)
            await role.delete()
        except (discord.Forbidden, discord.HTTPException):
            pass


class CustomRoleEmoji(discord.ui.Button):
    def __init__(self):
        super().__init__(label="自訂身份組圖示", emoji="🖼️", row=1)


class ChangeNameOrColor(discord.ui.Button):
    def __init__(self):
        super().__init__(label="更改身份組名稱或顏色", emoji="🔧", row=3)


async def flow_transaction(
    i: discord.Interaction, user_id: int, flow_num: int, db: aiosqlite.Connection
):
    now = datetime.now()
    now += timezone("Asia/Taipei").utcoffset(now)
    async with db.cursor() as c:
        await c.execute(
            "INSERT INTO flow_accounts (user_id) VALUES (?) ON CONFLICT DO NOTHING",
            (user_id,),
        )
        await c.execute("SELECT flow FROM flow_accounts WHERE user_id = ?", (user_id,))
        (flow,) = await c.fetchone()
        if flow < flow_num:
            await i.response.send_message(
                embed=errEmbed(message=f"需要: {flow_num} flow 幣").set_author(
                    name="你的 flow 幣數量不足已承擔這個交易", icon_url=i.user.display_avatar.url
                ),
                ephemeral=True,
            )
        else:
            await c.execute(
                "UPDATE flow_accounts SET flow = flow - ?, last_trans = ? WHERE user_id = ?",
                (
                    flow_num,
                    datetime.strftime(now, "%Y/%m/%d %H:%M:%S"),
                    user_id,
                ),
            )
            await db.commit()


async def return_custom_role(i: discord.Interaction, db: aiosqlite.Connection):
    async with db.cursor() as c:
        await c.execute(
            "INSERT INTO custom_role (user_id) VALUES (?) ON CONFLICT DO NOTHING",
            (i.user.id,),
        )
        await c.execute("SELECT tier FROM custom_role WHERE user_id = ?", (i.user.id,))
        (tier,) = await c.fetchone()
        await db.commit()
    view = View(i.user, tier)
    embed = defaultEmbed(
        message="• 分階級制，每個階級都有不同的功能\n"
        "• 第 1 級: 自訂身份組顏色 | 150 flow\n"
        "• 第 2 級: 自訂身份組名稱 | 100 flow\n"
        "• 第 3 級: 自訂身份組圖示 | 50 flow\n"
        "• 每月支付 80 flow 以維持級數\n"
        "• 如 flow 幣不足將會移除身份組但保留原階級及設定",
    )
    embed.set_author(name="自訂身份組", icon_url=i.user.display_avatar.url)
    embed.add_field(name="目前階級", value=f"第 {tier} 級")
    try:
        await i.response.send_message(embed=embed, view=view)
        view.message = await i.original_response()
    except discord.errors.InteractionResponded:
        await i.edit_original_response(embed=embed, view=view)
