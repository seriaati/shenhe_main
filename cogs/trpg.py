from typing import Any, Dict, List, Optional, Union

import discord
import g4f
from discord import app_commands
from discord.ext import commands
from discord.interactions import Interaction
from discord.ui.item import Item


class ChoiceModal(discord.ui.Modal):
    response = discord.ui.TextInput(label="回答", placeholder="請輸入回答")

    async def on_submit(self, i: Interaction) -> None:
        await i.response.defer()
        self.stop()


class OpenChoiceModal(discord.ui.Button):
    async def callback(self, i: discord.Interaction) -> Any:
        modal = ChoiceModal()
        await i.response.send_modal(modal)
        await modal.wait()
        user_response = modal.response.value
        self.view: "ChoiceSelector"
        self.view.disable_all_items()
        await i.edit_original_response(content="正在生成劇情中...", view=self.view)
        response = await self.view.get_gpt_response(user_response)
        self.view.enable_all_items()
        await i.edit_original_response(content=response, view=self.view)


class ChoiceButton(discord.ui.Button):
    def __init__(self, label: str):
        super().__init__(style=discord.ButtonStyle.primary, label=label)
        self.button_label = label

    async def callback(self, i: discord.Interaction) -> Any:
        self.view: "ChoiceSelector"
        self.view.disable_all_items()
        await i.response.edit_message(content="正在生成劇情中...", view=self.view)
        response = await self.view.get_gpt_response(self.button_label)
        self.view.enable_all_items()
        await i.edit_original_response(content=response, view=self.view)


class ChoiceSelector(discord.ui.View):
    def __init__(self, author: Union[discord.User, discord.Member]):
        super().__init__()
        self.messages: List[Dict[str, str]] = []
        self.author = author
        self.message: Optional[discord.Message] = None
        self.add_item(ChoiceButton("一"))
        self.add_item(ChoiceButton("二"))
        self.add_item(ChoiceButton("三"))
        self.add_item(OpenChoiceModal())

    def disable_all_items(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True

    def enable_all_items(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = False

    async def on_timeout(self) -> None:
        if self.message:
            self.disable_all_items()
            await self.message.edit(view=self)

    async def interaction_check(self, interaction: Interaction) -> bool:
        return self.author.id == interaction.user.id

    async def on_error(
        self, interaction: Interaction, error: Exception, _: Item[Any]
    ) -> None:
        try:
            await interaction.response.send_message(f"出現錯誤：{error}", ephemeral=True)
        except discord.InteractionResponded:
            await interaction.followup.send(f"出現錯誤：{error}", ephemeral=True)

    async def get_gpt_response(self, prompt: str) -> str:
        self.messages.append({"role": "user", "content": prompt})
        response = await g4f.ChatCompletion.create_async(
            model="gpt-3.5-turbo", messages=self.messages
        )
        if not isinstance(response, str):
            raise ValueError
        self.messages.append({"role": "narrator", "content": response})
        return response


class TRPG(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="trpg", description="開始一個文字 RPG 遊戲")
    @app_commands.rename(starting_prompt="額外提示")
    @app_commands.describe(starting_prompt="例如指定 RPG 遊戲的背景故事、你的角色名稱、目標等等")
    async def trpg_command(
        self, i: discord.Interaction, starting_prompt: Optional[str] = None
    ) -> Any:
        await i.response.defer()
        base_prompt = "用戶將在你的幫助下玩一款文字角色扮演冒險遊戲。 你是這個遊戲的敘述者。 您將提供故事情節供用戶遊玩。 每次講完故事後，您都會給出三個選項供用戶選擇以繼續遊戲，用戶會回答「一」、「二」、或「三」來表示他的選擇。用戶同時也會用文字和你互動對話，因此你可以給出謎題相關的故事情節來增加趣味性。現在，產生一個基礎故事，供用戶開始他的冒險。故事將會在十次選擇後結束，你將會寫出「結局」二字來表示遊戲已結束。"
        if starting_prompt:
            base_prompt += f"另外，用戶提供了額外的資訊來定義這個冒險中世界的樣貌：{starting_prompt}。"

        view = ChoiceSelector(i.user)
        response = await view.get_gpt_response(base_prompt)
        await i.followup.send(response, view=view)
        view.message = await i.original_response()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TRPG(bot))
