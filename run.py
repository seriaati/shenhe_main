# shenhe-bot by seria

import logging
import os
import platform
from pathlib import Path

import aiohttp
import asyncpg
import discord
from discord.ext import commands
from dotenv import load_dotenv

from dev.model import BotModel, ErrorEmbed

load_dotenv()
if platform.system() == "Windows":
    token = os.getenv("YELAN_TOKEN")
    prefix = ["?"]
    application_id = os.getenv("YELAN_APP_ID")
    debug = True
else:
    token = os.getenv("SHENHE_MAIN_TOKEN")
    prefix = ["!"]
    application_id = os.getenv("SHENHE_MAIN_APP_ID")
    debug = False

intents = discord.Intents.default()
intents.members = True
intents.reactions = True
intents.message_content = True
intents.presences = True

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler("log.log"),
        logging.StreamHandler(),
    ],
)


class ShenheCommandTree(discord.app_commands.CommandTree):
    def __init__(self, bot: commands.Bot):
        super().__init__(bot)

    async def on_error(
        self, i: discord.Interaction, e: discord.app_commands.AppCommandError, /
    ) -> None:
        logging.error(f"Error in command {i.command}: {type(e)} {e}")

        embed = ErrorEmbed("錯誤", str(e))
        try:
            await i.response.send_message(embed=embed, ephemeral=True)
        except discord.InteractionResponded:
            await i.followup.send(embed=embed, ephemeral=True)
        except Exception:
            pass


class ShenheBot(BotModel):
    def __init__(self):
        super().__init__(
            command_prefix=prefix,
            intents=intents,
            application_id=application_id,
        )

    async def setup_hook(self) -> None:
        self.session = aiohttp.ClientSession()
        self.debug = debug
        if self.debug:
            logging.basicConfig(level=logging.DEBUG)

        pool = await asyncpg.create_pool(os.getenv("DATABASE_URL"))
        assert pool
        self.pool = pool

        await self.load_extension("jishaku")
        for filepath in Path("./cogs").glob("**/*.py"):
            cog_name = Path(filepath).stem
            if cog_name in ("roll", "fish"):
                continue
            await self.load_extension(f"cogs.{cog_name}")

    async def on_ready(self):
        logging.info(f"Logged in as {self.user} (ID: {self.user.id})")

    async def on_message(self, message: discord.Message):
        if self.user and message.author.id == self.user.id:
            return
        await self.process_commands(message)

    async def on_command_error(self, ctx, error) -> None:
        if hasattr(ctx.command, "on_error"):
            return
        ignored = (commands.CommandNotFound,)
        error = getattr(error, "original", error)
        if isinstance(error, ignored):
            return
        else:
            logging.error(f"Error in command {ctx.command}: {error}")

    async def close(self) -> None:
        await self.pool.close()
        await self.session.close()
        return await super().close()


bot = ShenheBot()
assert token
bot.run(token)
