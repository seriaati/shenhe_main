from discord import Interaction, SelectOption, app_commands
from discord.ext import commands
from discord.ui import Select

from debug import DefaultView
from utility.utils import default_embed


class Dropdown(Select):
    def __init__(self, bot: commands.Bot):
        options = [
            SelectOption(label="flow系統", description="交易方式, 發布委託等", emoji="🌊"),
            SelectOption(label="其他", description="其他指令", emoji="🙂"),
            SelectOption(label="語音台", description="語音台相關指令", emoji="🎙️"),
            SelectOption(label="音樂系統", description="音樂系統相關指令", emoji="🎵"),
        ]
        super().__init__(placeholder="你想要什麼樣的幫助呢?", options=options)
        self.bot = bot

    async def callback(self, i: Interaction):
        index = 0
        cogs = ["flow", "other", "voice", "music"]
        for index, option in enumerate(self.options):
            if option.value == self.values[0]:
                selected_option = option
                index = index
                break
        command_cog = self.bot.get_cog(cogs[index])
        if command_cog is None:
            raise ValueError(f"Cog {cogs[index]} not found")
        commands = command_cog.__cog_app_commands__
        is_group = command_cog.__cog_is_app_commands_group__
        group_name = command_cog.__cog_group_name__
        app_commands = await self.bot.tree.fetch_commands()
        app_command_dict = {}
        for app_command in app_commands:
            app_command_dict[app_command.name] = app_command.id

        embed = default_embed(f"{selected_option.emoji} {selected_option.label}")
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


class DropdownView(DefaultView):
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
