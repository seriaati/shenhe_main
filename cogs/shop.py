import typing

import asyncpg
import discord
from discord import app_commands, ui
from discord.ext import commands

from apps.flow import flow_transaction, get_balance, register_account
from apps.shop import create_shop_item, delete_shop_item, get_item_names
from dev.enum import ShopAction
from dev.model import BaseView, DefaultEmbed, ErrorEmbed, Inter


class ShopItemView(BaseView):
    def __init__(
        self,
        item_names: typing.List,
        action: ShopAction,
        pool: asyncpg.Pool,
    ):
        super().__init__(timeout=None)
        self.add_item(ShopItemSelect(item_names, action, pool))


class ShopItemSelect(ui.Select):
    def __init__(self, item_names: typing.List, action: ShopAction, pool: asyncpg.Pool):
        self.action = action
        self.pool = pool
        options = []
        for item_name in item_names:
            options.append(discord.SelectOption(label=item_name, value=item_name))
        super().__init__(
            placeholder="選擇要購買的商品", min_values=1, max_values=1, options=options
        )

    async def callback(self, i: Inter) -> typing.Any:
        if self.action is ShopAction.DELETE:
            await delete_shop_item(self.values[0], self.pool)
            await i.response.send_message(
                f"商品 **{self.values[0]}** 移除成功", ephemeral=True
            )
        elif self.action is ShopAction.BUY:
            flow = await i.client.pool.fetchval(
                "SELECT flow FROM flow_shop WHERE name = $1", self.values[0]
            )
            user_flow = await get_balance(i.user.id, i.client.pool)
            if user_flow < flow:
                return await i.response.send_message(
                    embed=ErrorEmbed().set_author(
                        name="你的暴幣不足夠購買這項商品", icon_url=i.user.display_avatar.url
                    ),
                    ephemeral=True,
                )

            await flow_transaction(i.user.id, -flow, i.client.pool)
            await i.response.send_message(
                f"<:wish:982419859117838386> {i.user.mention} 商品 **{self.values[0]}** 購買成功, 請等候律律來交付商品"
            )

            msg = await i.original_response()
            thread = await msg.create_thread(name=f"{i.user} • {self.values[0]} 購買討論串")
            await thread.add_user(i.user)

            lulu_r = i.client.get_user(665092644883398671)
            assert lulu_r is not None
            await thread.add_user(lulu_r)

            embed = DefaultEmbed(
                "📜 購買證明",
                f"購買人: {i.user.mention}\n商品: {self.values[0]}\n價格: {flow}",
            )
            await thread.send(embed=embed)


class ShopCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        super().__init__()
        self.bot = bot

    @app_commands.command(name="shop", description="暴幣商店")
    async def show(self, inter: discord.Interaction):
        i: Inter = inter  # type: ignore
        await register_account(i.user.id, i.client.pool)
        rows = await i.client.pool.fetch("SELECT name, flow FROM flow_shop")
        item_str = ""
        item_names = []
        for row in rows:
            item_names.append(row["name"])
            item_str += f"• {row['name']} - **{row['flow']}** 暴幣\n\n"

        embed = DefaultEmbed("🛒 暴幣商店", item_str)
        view = ShopItemView(item_names, ShopAction.BUY, i.client.pool)
        view.author = i.user
        await i.response.send_message(embed=embed, view=view)
        view.message = await i.original_response()

    @app_commands.command(name="add-item", description="新增商品")
    @app_commands.rename(item="商品名稱", flow="價格")
    @app_commands.checks.has_permissions(administrator=True)
    async def additem(self, inter: discord.Interaction, item: str, flow: int):
        i: Inter = inter  # type: ignore

        await create_shop_item(item, flow, i.client.pool)
        embed = DefaultEmbed("商品新增成功", f"商品名稱: {item}\n價格: {flow}")
        await i.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="remove-item", description="刪除商品")
    @app_commands.checks.has_permissions(administrator=True)
    async def removeitem(self, inter: discord.Interaction):
        i: Inter = inter  # type: ignore
        item_names = await get_item_names(i.client.pool)
        view = ShopItemView(item_names, ShopAction.DELETE, i.client.pool)
        await i.response.send_message(view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ShopCog(bot))
