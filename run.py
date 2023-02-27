# shenhe-bot by seria

import platform
import os
import sys
import traceback
from pathlib import Path

import aiohttp
import aiosqlite
from discord import (Intents, Interaction, Message, app_commands, Game)
from discord.ext import commands
from dotenv import load_dotenv

from cogs.welcome import WelcomeCog
from debug import DebugView
from utility.utils import error_embed, log

load_dotenv()
if platform.system() == "Windows":
    token = os.getenv('YELAN_TOKEN')
    prefix = ['?']
    application_id = os.getenv('YELAN_APP_ID')
    debug_toggle = True
else:
    token = os.getenv('SHENHE_MAIN_TOKEN')
    prefix = ['!']
    application_id = os.getenv('SHENHE_MAIN_APP_ID')
    debug_toggle = False

# 前綴, token, intents
intents = Intents.default()
intents.members = True
intents.reactions = True
intents.message_content = True
intents.presences = True


class ShenheBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=prefix,
            intents=intents,
            application_id=application_id,
            chunk_guilds_at_startup=False,
            activity=Game(name="私訊來知會管理員")
        )

    async def setup_hook(self) -> None:
        self.session = aiohttp.ClientSession()
        self.db = await aiosqlite.connect('main.db')
        self.guild_id = 1061877505067327528
        self.repeat = False
        self.prev = False
        self.debug_toggle = debug_toggle
        self.gv_role_blacklist = []
        self.gv_role_name = ""
        
        await self.load_extension('jishaku')
        for filepath in Path('./cogs').glob('**/*.py'):
            cog_name = Path(filepath).stem
            await self.load_extension(f'cogs.{cog_name}')
            
        self.add_view(WelcomeCog.AcceptRules())

    async def on_ready(self):
        print(log(True, False, 'Bot', f'Logged in as {self.user}'))

    async def on_message(self, message: Message):
        if message.author.id == self.user.id:
            return
        await self.process_commands(message)

    async def on_command_error(self, ctx, error) -> None:
        if hasattr(ctx.command, 'on_error'):
            return
        ignored = (commands.CommandNotFound, )
        error = getattr(error, 'original', error)
        if isinstance(error, ignored):
            return
        else:
            print('Ignoring exception in command {}:'.format(
                ctx.command), file=sys.stderr)
            traceback.print_exception(
                type(error), error, error.__traceback__, file=sys.stderr)

    async def close(self) -> None:
        await self.db.close()
        await self.session.close()
        return await super().close()


bot = ShenheBot()

@bot.before_invoke
async def before_invoke(ctx):
    if ctx.guild is not None and not ctx.guild.chunked:
        await ctx.guild.chunk()

tree = bot.tree


@tree.error
async def err_handle(i: Interaction, e: app_commands.AppCommandError):
    if isinstance(e, app_commands.errors.CheckFailure):
        return
    
    seria = i.client.get_user(410036441129943050)
    view = DebugView(traceback.format_exc())
    embed = error_embed(message=f'```py\n{e}\n```').set_author(
        name='未知錯誤', icon_url=i.user.display_avatar.url)
    await i.channel.send(content=f'{seria.mention} 系統已將錯誤回報給小雪, 請耐心等待修復', embed=embed, view=view)

@tree.interaction_check
async def check(i: Interaction):
    if i.guild is not None and not i.guild.chunked:
        await i.guild.chunk()

bot.run(token)
