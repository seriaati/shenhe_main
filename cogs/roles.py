import asyncio
from typing import List
import discord
from discord import ui
from discord.ext import commands
from utility.utils import default_embed


class ReactionRole(ui.View):
    def __init__(self, roles: List[discord.Role]):
        super().__init__(timeout=None)
        
        for index, role in enumerate(roles):
            self.add_item(RoleButton(role, index // 3))


class RoleButton(ui.Button[ReactionRole]):
    def __init__(self, role: discord.Role, row:int):
        self.role = role
        super().__init__(
            label=f"{role.name} ({len(role.members)})",
            style=discord.ButtonStyle.blurple,
            custom_id=f"role_{role.id}",
            row=row,
        )

    async def callback(self, i: discord.Interaction):
        if self.role in i.user.roles:
            await i.user.remove_roles(self.role)
        else:
            await i.user.add_roles(self.role)
        self.label = f"{self.role.name} ({len(self.role.members)})"
        await i.response.edit_message(view=self.view)


class ReactionRoles(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    async def cog_load(self):
        self.bot.loop.create_task(self.add_view_task())

    async def add_view_task(self):
        await self.bot.wait_until_ready()
        role_ids = (
            1075026929448652860,
            1075027016132345916,
            1075027069832015943,
            1075027095786365009,
            1075027124454440992,
        )
        guild = self.bot.get_guild(1061877505067327528)
        view = ReactionRole([guild.get_role(id) for id in role_ids])
        self.bot.add_view(view)

    @commands.command()
    @commands.is_owner()
    async def reaction_roles(self, ctx: commands.Context):
        embed = default_embed("獲取想要的通知身份組", "點擊下方的按鈕來獲取身份組")
        embed.add_field(name="目前可選的通知身份組", value="\n".join([f"<@&{id}>" for id in self.role_ids]))
        await ctx.send(embed=embed, view=self.view)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ReactionRoles(bot))


# memories
# embed.add_field(
#     name=':dango: 兔兔島',
#     value='在一片迷霧之中 隱藏了一座世外桃源的島嶼\n'
#     '可愛活潑的兔島主會在聊天台和語音中歡迎你的到來\n\n'
#     '熱情的的兔兔島民們非常歡迎每位新朋友來到這個脫離現實的美好世界\n'
#     '島民都親如家人 和睦相處 相信你也會很快融入並成為其中的一份子\n\n'
#     '兔兔島除了有帶你跑圖鋤地賺取摩拉的人外\n'
#     '偶然也會舉辦小小的抽獎回饋各位島民的支持和陪伴\n'
#     '還不出發到這座溫馨小島嗎?兔兔島萬歲!!',
#     inline=False
# )
# embed.add_field(
#     name=':snowflake: 小雪國',
#     value='在遠方的冰天雪地 有一個國度 可愛與純真並重的小雪女皇：小雪國\n'
#     '這是一個來自充滿雪花、由小雪女皇統治的一個大型群組，而且是一個群內知名的大國\n'
#     '而小雪女皇是一個純真、可愛的女孩，這裡的申鶴機器人就是又她一手研發的\n'
#     '但小雪國不只是知名於這些地方，小雪女皇不時也會發放國民福利，小雪國民是享有最多福利的群眾，很吸引人吧！\n'
#     '快加入！你不會後悔的，\n'
#     '「小雪國萬歲喵！」',
#     inline=False
# )
# embed.add_field(
#     name=':two_hearts: 羽嶼',
#     value='一個寧靜平凡、與世無爭的小島\n'
#     '島民的性格都跟這條介紹一樣懶散隨和\n'
#     '是一個如同蒙德一樣自由的小漁村\n'
#     '來羽嶼釣魚賞櫻吧～',
#     inline=False
# )
