import logging
import os
from contextlib import suppress

import discord
import pomice
from discord.ext import commands
from dotenv import load_dotenv


class Player(pomice.Player):
    """Custom pomice Player class."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue = pomice.Queue()

    async def do_next(self) -> None:
        try:
            track: pomice.Track = self.queue.get()
        except pomice.QueueEmpty:
            return await self.teardown()

        await self.play(track)

    async def teardown(self):
        """Clear internal states and disconnect."""
        with suppress((discord.HTTPException), (KeyError)):
            await self.destroy()


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

        # In order to initialize a node, or really do anything in this library,
        # you need to make a node pool
        self.pomice = pomice.NodePool()

        # Start the node
        bot.loop.create_task(self.start_nodes())

    async def start_nodes(self):
        # Waiting for the bot to get ready before connecting to nodes.
        await self.bot.wait_until_ready()

        load_dotenv()
        password = os.getenv("lavalink")
        spotify_client_id = os.getenv("spotify_client")
        spotify_client_secret = os.getenv("spotify_secret")
        if not password:
            raise EnvironmentError("Missing Lavalink password")
        if not spotify_client_id:
            raise EnvironmentError("Missing Spotify client ID")
        if not spotify_client_secret:
            raise EnvironmentError("Missing Spotify client secret")

        await self.pomice.create_node(
            bot=self.bot,
            host="localhost",
            port=7009,
            password=password,
            spotify_client_id=spotify_client_id,
            spotify_client_secret=spotify_client_secret,
            identifier="MAIN",
        )
        logging.info("Connected to MAIN node.")

    @commands.Cog.listener()
    async def on_pomice_track_end(self, player: Player, track, _):
        await player.do_next()

    @commands.Cog.listener()
    async def on_pomice_track_stuck(self, player: Player, track, _):
        await player.do_next()

    @commands.Cog.listener()
    async def on_pomice_track_exception(self, player: Player, track, _):
        await player.do_next()


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
