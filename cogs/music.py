import asyncio
import os

import discord
import wavelink
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from wavelink.ext import spotify

from apps import music
from dev.model import BotModel, ErrorEmbed

load_dotenv()


class MusicCog(commands.Cog, name="music"):
    def __init__(self, bot):
        super().__init__()
        self.bot: BotModel = bot
        if not self.bot.debug:
            self.bot.loop.create_task(self.connect_nodes())

    async def connect_nodes(self):
        await self.bot.wait_until_ready()
        password = os.getenv("lavalink")
        client_id = os.getenv("spotify_client")
        client_secret = os.getenv("spotify_secret")
        assert password and client_id and client_secret

        node = wavelink.Node(uri="localhost:7009", password=password)
        spotify_client = spotify.SpotifyClient(
            client_id=client_id, client_secret=client_secret
        )
        await wavelink.NodePool.connect(
            client=self.bot, nodes=[node], spotify=spotify_client
        )

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEventPayload):
        player = payload.player

        if not player.queue.is_empty:
            await player.play(player.queue.get())
        try:
            await self.bot.wait_for("wavelink_track_start", timeout=300)
        except asyncio.TimeoutError:
            await player.disconnect()

    @app_commands.guild_only()
    @app_commands.command(name="music", description="播放音樂")
    async def music(self, i: discord.Interaction):
        await i.response.defer(ephemeral=True)

        assert isinstance(i.user, discord.Member)
        if i.user.voice is None or i.user.voice.channel is None:
            return await i.followup.send(
                embed=ErrorEmbed("請在語音台中使用此指令"),
                ephemeral=True,
            )

        assert i.guild
        if not i.guild.voice_client:
            player: wavelink.Player = await i.user.voice.channel.connect(
                cls=wavelink.Player  # type: ignore
            )
        else:
            player: wavelink.Player = i.guild.voice_client  # type: ignore

        assert player.channel
        if player.channel.id != i.user.voice.channel.id:
            if player.is_playing():
                return await i.followup.send(
                    embed=ErrorEmbed(
                        "錯誤", "你跟目前申鶴所在的語音台不同，且申鶴目前正在為那邊的使用者播歌\n請等待至對方播放完畢"
                    ),
                    ephemeral=True,
                )
            else:
                await player.disconnect()
                player: wavelink.Player = await i.user.voice.channel.connect(
                    cls=wavelink.Player  # type: ignore
                )
        await music.return_music_embed(i, player)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MusicCog(bot))
