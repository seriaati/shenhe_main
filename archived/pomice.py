import contextlib
import math
import os
from typing import Any

import discord
import pomice
from discord import app_commands, ui
from discord.ext import commands
from dotenv import load_dotenv
from loguru import logger

load_dotenv()


class Player(pomice.Player):
    """Custom pomice Player class."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.queue = pomice.Queue()

    async def do_next(self) -> pomice.Track | None:
        # Queue up the next track, else destroy the player
        try:
            track: pomice.Track = self.queue.get()
        except pomice.QueueEmpty:
            await self.destroy()
        else:
            await self.play(track)
            return track


class PlayerView(ui.View):
    def __init__(self, author_id: int) -> None:
        super().__init__()
        self.player: Player = None  # type: ignore
        self.author_id = author_id

    async def start(self, i: discord.Interaction) -> bool:
        in_vc = await self.check_in_vc(i)
        if not in_vc:
            return False

        assert isinstance(i.user, discord.Member) and i.user.voice and i.user.voice.channel
        if not self.check_player(i):
            await i.user.voice.channel.connect(cls=Player)
        self.player = i.guild.voice_client  # type: ignore
        return True

    async def check_in_vc(self, i: discord.Interaction) -> bool:
        assert isinstance(i.user, discord.Member)
        if not i.user.voice or not i.user.voice.channel:
            await i.response.send_message(
                "你必須先加入一個語音頻道",
                ephemeral=True,
            )
            return False
        return True

    async def interaction_check(self, i: discord.Interaction) -> bool:
        in_vc = await self.check_in_vc(i)
        return i.user.id == self.author_id and in_vc

    async def update(self, i: discord.Interaction) -> Any:
        self.add_items()
        try:
            await i.response.edit_message(
                embeds=[self.gen_queue_embed(), self.gen_playing_embed()], view=self
            )
        except discord.InteractionResponded:
            await i.edit_original_response(
                embeds=[self.gen_queue_embed(), self.gen_playing_embed()], view=self
            )

    def add_items(self) -> None:
        self.clear_items()
        self.add_item(AddSong(self.player))
        if self.player.queue.size >= 1:
            self.add_item(Next(self.player))
        if self.player.is_paused:
            self.add_item(Resume(self.player))
        if self.player.is_playing:
            if not self.player.is_paused:
                self.add_item(Pause(self.player))
            self.add_item(Stop(self.player))

    def gen_queue_embed(self) -> discord.Embed:
        embed = discord.Embed(title="待播清單 (前 5 首)")
        for track in self.player.queue.get_queue()[:5]:
            track: pomice.Track
            embed.add_field(
                name=f"{track.author} - {track.title}",
                value=str(track.uri),
                inline=False,
            )
        if not embed.fields:
            embed.description = "待播清單內目前沒有歌曲"
        return embed

    def gen_playing_embed(self) -> discord.Embed:
        embed = discord.Embed(title="目前播放")
        if not self.player.current:
            embed.description = "目前沒有正在播放的歌曲"
            return embed
        embed.add_field(
            name=f"{self.player.current.author} - {self.player.current.title}",
            value=str(self.player.current.uri),
            inline=False,
        )
        embed.set_image(url=self.player.current.thumbnail)
        return embed

    @staticmethod
    async def on_error(i: discord.Interaction, e: Exception, _) -> None:
        logger.error("Error in music player", exc_info=e)
        try:
            await i.response.send_message(f"錯誤: {e}", ephemeral=True)
        except discord.InteractionResponded:
            await i.followup.send(f"錯誤: {e}", ephemeral=True)

    @staticmethod
    def required(i: discord.Interaction, *, is_stop: bool = False) -> int:
        """Method which returns required votes based on amount of members in a channel."""
        player: Player = i.guild.voice_client  # type: ignore
        channel = i.client.get_channel(int(player.channel.id))
        if not isinstance(channel, discord.VoiceChannel):
            msg = "Channel not found"
            raise TypeError(msg)
        required = math.ceil((len(channel.members) - 1) / 2.5)

        if is_stop and len(channel.members) == 3:
            required = 2

        return required

    @staticmethod
    def check_player(i: discord.Interaction) -> bool:
        assert i.guild
        return i.guild.voice_client is not None

    @staticmethod
    def is_privileged(i: discord.Interaction) -> bool:
        """Check whether the user is an Admin or DJ."""
        if not isinstance(i.user, discord.Member):
            msg = "Member not found"
            raise RuntimeError(msg)
        return i.user.guild_permissions.kick_members


class VoteView(ui.View):
    def __init__(self, required: int, action: str) -> None:
        self.vote_set: set[int] = set()
        self.required = required
        self.action = action
        super().__init__()

    def _check_required(self) -> bool:
        return len(self.vote_set) >= self.required

    def gen_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="投票",
            description=f"是否贊成要 **{self.action}**?\n需要票數: **{self.required}**\n目前票數: **{len(self.vote_set)}**",
        )
        return embed

    async def update_embed(self, i: discord.Interaction) -> Any:
        await i.response.edit_message(embed=self.gen_embed())

    @ui.button(label="贊成", style=discord.ButtonStyle.green)
    async def vote(self, i: discord.Interaction, _) -> Any:
        self.vote_set.add(i.user.id)
        passed = self._check_required()
        await self.update_embed(i)
        if passed and i.message:
            await i.message.delete()


class Resume(ui.Button):
    def __init__(self, player: Player) -> None:
        self.player = player
        self.view: PlayerView
        super().__init__(style=discord.ButtonStyle.blurple, label="取消暫停")

    async def callback(self, i: discord.Interaction) -> Any:
        if not self.view.is_privileged(i):
            view = VoteView(self.view.required(i), "取消暫停")
            await i.response.send_message(
                content=" ".join([m.mention for m in self.player.channel.members]),
                embed=view.gen_embed(),
                view=view,
            )
            await view.wait()
        await self.player.set_pause(False)
        await self.view.update(i)


class Pause(ui.Button):
    def __init__(self, player: Player) -> None:
        self.player = player
        self.view: PlayerView
        super().__init__(style=discord.ButtonStyle.blurple, label="暫停")

    async def callback(self, i: discord.Interaction) -> Any:
        if not self.view.is_privileged(i):
            view = VoteView(self.view.required(i), "暫停")
            await i.response.send_message(
                content=" ".join([m.mention for m in self.player.channel.members]),
                embed=view.gen_embed(),
                view=view,
            )
            await view.wait()
        await self.player.set_pause(True)
        await self.view.update(i)


class Next(ui.Button):
    def __init__(self, player: Player) -> None:
        self.player = player
        self.view: PlayerView
        super().__init__(style=discord.ButtonStyle.blurple, label="下一首")

    async def callback(self, i: discord.Interaction) -> Any:
        if not self.view.is_privileged(i):
            view = VoteView(self.view.required(i), "下一首")
            await i.response.send_message(
                content=" ".join([m.mention for m in self.player.channel.members]),
                embed=view.gen_embed(),
                view=view,
            )
            await view.wait()
        await self.player.stop()
        await self.view.update(i)


class Stop(ui.Button):
    def __init__(self, player: Player) -> None:
        self.player = player
        self.view: PlayerView
        super().__init__(style=discord.ButtonStyle.red, label="停止播放")

    async def callback(self, i: discord.Interaction) -> Any:
        if not self.view.is_privileged(i):
            view = VoteView(self.view.required(i, is_stop=True), "停止播放")
            await i.response.send_message(
                content=" ".join([m.mention for m in self.player.channel.members]),
                embed=view.gen_embed(),
                view=view,
            )
            await view.wait()
        await self.player.destroy()


class SearchModal(ui.Modal):
    query = ui.TextInput(
        label="搜尋", placeholder="輸入歌曲關鍵字或網址", min_length=1, max_length=100
    )

    def __init__(self) -> None:
        super().__init__(title="新增歌曲")

    async def on_submit(self, i: discord.Interaction) -> Any:
        await i.response.defer()
        self.stop()


class SongSelector(ui.Select):
    def __init__(self, tracks: list[pomice.Track]) -> None:
        self.tracks = tracks
        options = [
            discord.SelectOption(label=track.title, value=str(i))
            for i, track in enumerate(tracks[:25])
        ]
        super().__init__(placeholder="選擇歌曲", options=options)
        self.view: "SongSelectView"
        self.track: pomice.Track

    async def callback(self, i: discord.Interaction) -> Any:
        await i.response.defer()
        self.view.track = self.tracks[int(self.values[0])]
        self.view.stop()


class SongSelectView(ui.View):
    def __init__(self, author_id: int, tracks: list[pomice.Track]) -> None:
        super().__init__()
        self.author_id = author_id
        self.add_item(SongSelector(tracks))
        self.track: pomice.Track | None = None

    async def interection_check(self, i: discord.Interaction) -> bool:
        return i.user.id == self.author_id


class AddSong(ui.Button):
    def __init__(self, player: Player) -> None:
        self.player = player
        self.view: PlayerView
        super().__init__(style=discord.ButtonStyle.blurple, label="新增歌曲")

    async def callback(self, i: discord.Interaction) -> Any:
        modal = SearchModal()
        await i.response.send_modal(modal)
        await modal.wait()
        if not modal.query:
            return

        results = await self.player.get_tracks(modal.query.value)
        if not results:
            return

        if isinstance(results, pomice.Playlist):
            for track in results.tracks:
                self.player.queue.put(track)
            await i.followup.send(f"{i.user.mention} 已新增歌曲 {results.name}")
        else:
            if len(results) == 1:
                track = results[0]
            else:
                view = SongSelectView(i.user.id, results)
                await i.followup.send(f"{i.user.mention} 請選擇歌曲", view=view, ephemeral=True)
                await view.wait()
                track = view.track
            if track:
                self.player.queue.put(track)
                await i.followup.send(f"{i.user.mention} 已新增歌曲 {track.title}")

        if not self.player.is_playing:
            await self.player.do_next()
        await self.view.update(i)


class PomiceCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

        self.pomice = pomice.NodePool()
        bot.loop.create_task(self.start_nodes())

    async def start_nodes(self) -> None:
        # Waiting for the bot to get ready before connecting to nodes.
        await self.bot.wait_until_ready()

        # You can pass in Spotify credentials to enable Spotify querying.
        # If you do not pass in valid Spotify credentials, Spotify querying will not work
        with contextlib.suppress(pomice.NodeCreationError):
            await self.pomice.create_node(
                bot=self.bot,
                host="127.0.0.1",
                port=7009,
                password=os.getenv("LAVALINK_PASSWORD"),  # type: ignore
                identifier="MAIN",
            )

    @commands.Cog.listener()
    async def on_pomice_track_end(self, player: Player, _, __) -> None:
        await player.do_next()

    @commands.Cog.listener()
    async def on_pomice_track_stuck(self, player: Player, _, __) -> None:
        await player.do_next()

    @commands.Cog.listener()
    async def on_pomice_track_exception(self, player: Player, _, __) -> None:
        await player.do_next()

    @app_commands.command(name="music", description="音樂")
    async def music(self, i: discord.Interaction) -> Any:
        view = PlayerView(i.user.id)
        success = await view.start(i)
        if not success:
            return
        view.add_items()
        await i.response.send_message(
            embeds=[view.gen_queue_embed(), view.gen_playing_embed()], view=view
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PomiceCog(bot))
