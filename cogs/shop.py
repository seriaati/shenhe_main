import typing
import uuid

import aiosqlite
import discord
from discord import app_commands, ui
from discord.ext import commands

from apps.flow import flow_transaction, get_user_flow
from cogs.flow import has_flow_account
from debug import DefaultView
from utility.utils import default_embed, error_embed


class ShopItemView(DefaultView):
    def __init__(
        self,
        item_names: typing.List,
        action: str,
        db: aiosqlite.Connection,
        author: discord.Member,
    ):
        super().__init__(timeout=None)
        self.author = author
        self.add_item(ShopItemSelect(item_names, action, db))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.author.id != interaction.user.id:
            await interaction.response.send_message(
                embed=error_embed().set_author(
                    name="這不是你的操作視窗", icon_url=interaction.user.avatar
                ),
                ephemeral=True,
            )
        return self.author.id == interaction.user.id


class ShopItemSelect(ui.Select):
    def __init__(self, item_names: typing.List, action: str, db: aiosqlite.Connection):
        self.action = action
        self.db = db
        options = []
        for item_name in item_names:
            options.append(discord.SelectOption(label=item_name, value=item_name))
        super().__init__(
            placeholder="選擇要購買的商品", min_values=1, max_values=1, options=options
        )

    async def callback(self, i: discord.Interaction) -> typing.Any:
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
            item_max = data[2]
            user_flow = await get_user_flow(i.user.id, i.client.db)
            if user_flow < flow:
                return await i.response.send_message(
                    embed=error_embed().set_author(
                        name="你的暴幣不足夠購買這項商品", icon_url=i.user.display_avatar.url
                    ),
                    ephemeral=True,
                )
            if current == item_max:
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
            thread = await msg.create_thread(name=f"{i.user} • {self.values[0]} 購買討論串")
            await thread.add_user(i.user)
            lulu_r = i.client.get_user(665092644883398671)
            await thread.add_user(lulu_r)
            embed = default_embed(
                "📜 購買證明",
                f"購買人: {i.user.mention}\n"
                f"商品: {self.values[0]}\n"
                f"收據UUID: {log_uuid}\n"
                f"價格: {flow}",
            )
            await thread.send(embed=embed)


class ShopCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        super().__init__()
        self.bot = bot

    @has_flow_account()
    @app_commands.command(name="shop", description="暴幣商店")
    async def show(self, i: discord.Interaction):
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
        view = ShopItemView(item_names, "buy", i.client.db, i.user)
        await i.response.send_message(embed=embed, view=view)

    @app_commands.command(name="additem", description="新增商品")
    @app_commands.rename(item="商品名稱", flow="價格", max="最大購買次數")
    @app_commands.checks.has_role("猜猜我是誰")
    async def additem(self, i: discord.Interaction, item: str, flow: int, max: int):
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
    async def removeitem(self, i: discord.Interaction):
        async with i.client.db.execute("SELECT name FROM flow_shop") as cursor:
            data = await cursor.fetchall()
        item_names = []
        for _, tpl in enumerate(data):
            item_names.append(tpl[0])
        view = ShopItemView(item_names, "remove", self.bot.db, i.user)
        await i.response.send_message(view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ShopCog(bot))
