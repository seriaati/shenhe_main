from discord import Interaction, SelectOption, app_commands, utils
from discord.ext import commands
from discord.ui import Select

from dev.model import BaseView
from utility.utils import default_embed


class Dropdown(Select):
    def __init__(self, bot: commands.Bot):
        options = [
            SelectOption(label="暴幣系統", emoji="🪙", value="bao"),
            SelectOption(label="小遊戲系統", emoji="��🏓", value="game"),
            SelectOption(label="語音台系統", emoji="🎙️", value="vc"),
            SelectOption(label="音樂系統", emoji="🎵", value="music"),
            SelectOption(label="練舞系統", emoji="🕺", value="dance"),
            SelectOption(label="商店系統", emoji="🛒", value="shop"),
            SelectOption(label="其他", emoji="🙂", value="other"),
        ]
        super().__init__(placeholder="你想要什麼樣的幫助呢?", options=options)
        self.bot = bot

    async def callback(self, i: Interaction):
        selected = utils.get(self.options, value=self.values[0])
        if selected is None:
            raise ValueError(f"Option {self.values[0]} not found")
        cog = self.bot.get_cog(self.values[0])
        if cog is None:
            raise ValueError(f"Cog {self.values[0]} not found")
        commands = cog.__cog_app_commands__
        is_group = cog.__cog_is_app_commands_group__
        group_name = cog.__cog_group_name__
        app_commands = await self.bot.tree.fetch_commands()
        app_command_dict = {}
        for app_command in app_commands:
            app_command_dict[app_command.name] = app_command.id

        embed = default_embed(f"{selected.emoji} {selected.label}")
        for command in commands:
            value = command.description
            if is_group:
                embed.add_field(
                    name=f"</{group_name} {command.name}:{app_command_dict[group_name]}>",
                    value=value,
                )
            else:
                embed.add_field(
                    name=f"</{command.name}:{app_command_dict[command.name]}>",
                    value=value,
                )
        await i.response.edit_message(embed=embed)


class DropdownView(BaseView):
    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.add_item(Dropdown(bot))


class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="獲得幫助")
    async def help(self, interaction: Interaction):
        view = DropdownView(self.bot)
        await interaction.response.send_message(view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(HelpCog(bot))
