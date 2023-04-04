import random
from typing import List

import discord
from discord import ui

from data.constants import image_urls
from dev.model import BaseView, DefaultEmbed


class AcceptRules(BaseView):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(
        label="同意以上規則", style=discord.ButtonStyle.green, custom_id="accept_rule_button"
    )
    async def accept_rules(self, i: discord.Interaction, _: ui.Button):
        assert i.guild

        traveler = i.guild.get_role(1061880147952812052)
        assert traveler is not None

        assert isinstance(i.user, discord.Member)
        if traveler in i.user.roles:
            return await i.response.send_message(
                embed=DefaultEmbed("您已同意過上述規則了", "不須再次同意"),
                ephemeral=True,
            )

        await i.response.send_message(
            embed=DefaultEmbed("✅ 您已同意上述規則", "歡迎來到往生堂團隊！"),
            ephemeral=True,
        )
        await i.user.add_roles(traveler)


class Welcome(BaseView):
    def __init__(self, member: discord.Member):
        super().__init__()
        self.member = member
        self.pressed: List[int] = []

    @ui.button(
        label="歡迎~", style=discord.ButtonStyle.blurple, custom_id="welcome_button"
    )
    async def welcome(self, i: discord.Interaction, _: ui.Button):
        if i.user.id in self.pressed:
            return await i.response.defer()
        self.pressed.append(i.user.id)

        image_url = random.choice(image_urls)
        embed = DefaultEmbed(
            f"{self.member.name} 歡迎歡迎~", "<:Penguin_hug:1062081072449466498>"
        )
        embed.set_thumbnail(url=image_url)
        embed.set_author(name=i.user.name, icon_url=i.user.display_avatar.url)
        await i.response.send_message(embed=embed)
