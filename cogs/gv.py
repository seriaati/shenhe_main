from apps.giveaway import View, return_giveaway_embed
from discord import Interaction, app_commands, SelectOption
from discord.ext import commands


class GiveAwayCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.debug_toggle = self.bot.debug_toggle
        self.gv_channel_id = (
            965517075508498452 if not self.debug_toggle else 909595117952856084
        )

    @app_commands.command(name="gv", description="設置抽獎")
    @app_commands.checks.has_role("小雪團隊")
    async def start_giveaway(self, i: Interaction):
        select_options = []
        for role in i.guild.roles:
            if "λ" in role.name:
                select_options.append(SelectOption(label=role.name, value=role.id))
        await i.response.send_message(embed=await return_giveaway_embed(i), view=View(select_options))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GiveAwayCog(bot))
