import random

import discord
from discord import ui

from data.constants import image_urls
from dev.model import BaseView, DefaultEmbed


class AcceptRules(BaseView):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @ui.button(
        label="同意以上規則", style=discord.ButtonStyle.green, custom_id="accept_rule_button"
    )
    async def accept_rules(self, i: discord.Interaction, _: ui.Button) -> None:
        assert i.guild

        traveler = i.guild.get_role(1061880147952812052)

        assert isinstance(i.user, discord.Member)
        if traveler in i.user.roles:
            return await i.response.send_message(
                embed=DefaultEmbed("您已同意過上述規則了", "不須再次同意"),
                ephemeral=True,
            )

        await i.response.send_message(
            embed=DefaultEmbed("✅ 您已同意上述規則", "請至 <#1093484799278190673> 輸入 UID"),
            ephemeral=True,
        )
        unlock_uid = i.guild.get_role(1093484835349221397)
        if unlock_uid is None:
            msg = "Unlock UID Role not found"
            raise ValueError(msg)
        await i.user.add_roles(unlock_uid)


class Welcome(BaseView):
    def __init__(self, member: discord.Member) -> None:
        super().__init__()
        self.member = member
        self.pressed: list[int] = []

    @ui.button(label="歡迎~", style=discord.ButtonStyle.blurple, custom_id="welcome_button")
    async def welcome(self, i: discord.Interaction, _: ui.Button) -> None:
        if i.user.id in self.pressed:
            return await i.response.defer()
        self.pressed.append(i.user.id)

        image_url = random.choice(image_urls)
        embed = DefaultEmbed(f"{self.member.name} 歡迎歡迎~", "<:Penguin_hug:1062081072449466498>")
        embed.set_thumbnail(url=image_url)
        embed.set_author(name=i.user.name, icon_url=i.user.display_avatar.url)
        await i.response.send_message(embed=embed)
