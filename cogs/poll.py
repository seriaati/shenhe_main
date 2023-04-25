from typing import Dict, List

import discord
from discord import app_commands, ui
from discord.ext import commands

from dev.model import BaseModal, BaseView, DefaultEmbed


class PollView(BaseView):
    def __init__(self, question: str, options: List[str]):
        super().__init__()

        self.question = question
        self.options = options
        self.result: Dict[str, int] = {option: 0 for option in options}

        for option in options:
            self.add_item(OptionButton(option))

    async def start(self, i: discord.Interaction):
        self.author = i.user

        embed = DefaultEmbed(self.question)
        embed.description = ""
        for option, count in self.result.items():
            embed.description += f"{option}: {count}\n"
        try:
            await i.response.send_message(embed=embed, view=self)
        except discord.InteractionResponded:
            self.message = await i.edit_original_response(embed=embed, view=self)
        else:
            self.message = await i.original_response()


class OptionButton(ui.Button):
    def __init__(self, label: str):
        super().__init__(label=label)
        self.view: PollView

    async def callback(self, i: discord.Interaction):
        assert self.label
        self.view.result[self.label] += 1
        await self.view.start(i)


class OptionEditView(BaseView):
    def __init__(self, question: str):
        super().__init__()

        self.question = question
        self.options: List[str] = []

    async def start(self, i: discord.Interaction):
        self.author = i.user

        embed = DefaultEmbed("投票設定")
        embed.add_field(name="問題", value=self.question, inline=False)
        if self.options:
            embed.add_field(name="選項", value="\n".join(self.options), inline=False)
            self.option_select.options = [
                discord.SelectOption(label=option, value=option)
                for option in self.options
            ]
        self.option_select.disabled = not self.options
        self.start_poll.disabled = not self.options

        try:
            await i.response.send_message(embed=embed, view=self)
        except discord.InteractionResponded:
            self.message = await i.edit_original_response(embed=embed, view=self)
        else:
            self.message = await i.original_response()

    @ui.button(
        label="新增選項", style=discord.ButtonStyle.green, custom_id="add_option", row=0
    )
    async def add_option(self, i: discord.Interaction, _: ui.Button):
        modal = NewOptionModal()
        await i.response.send_modal(modal)
        await modal.wait()
        self.options.append(modal.option.value)
        await self.start(i)

    @ui.button(
        label="開始投票",
        style=discord.ButtonStyle.blurple,
        custom_id="start_poll",
        row=0,
        disabled=True,
    )
    async def start_poll(self, i: discord.Interaction, _: ui.Button):
        view = PollView(self.question, self.options)
        await view.start(i)

    @ui.select(
        placeholder="選擇要刪除的選項...",
        max_values=1,
        row=1,
        custom_id="option_select",
        disabled=True,
        options=[discord.SelectOption(label="空", value="空")],
    )
    async def option_select(self, i: discord.Interaction, select: ui.Select):
        self.options.remove(select.values[0])
        await self.start(i)


class NewOptionModal(BaseModal):
    option = ui.TextInput(label="選項名稱", placeholder="輸入選項名稱")

    def __init__(self):
        super().__init__(title="新增選項")

    async def on_submit(self, i: discord.Interaction):
        await i.response.defer()
        self.stop()


class PollCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.guild_only()
    @app_commands.rename(question="問題")
    @app_commands.describe(question="投票的問題")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.command(name="poll", description="開始一個投票")
    async def poll(self, i: discord.Interaction, question: str):
        view = OptionEditView(question)
        await view.start(i)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PollCog(bot))
