import asyncio
import logging
import os
import random
import re
import typing

import discord
import wavelink
from discord import app_commands, ui
from discord.ext import commands
from dotenv import load_dotenv
from wavelink.ext import spotify

from dev.model import BaseModal, BaseView, BotModel, DefaultEmbed, ErrorEmbed

load_dotenv()


class MusicView(BaseView):
    def __init__(self, player: wavelink.Player) -> None:
        super().__init__()

        self.player = player
        self.add_item(Previous(not player.queue.history))
        if player.is_paused():
            self.add_item(Resume(not player.is_playing()))
        else:
            self.add_item(Pause(not player.is_playing()))
        self.add_item(Next(not player.queue))
        self.add_item(Stop(not player.is_playing()))
        self.add_item(ClearQueue(not player.queue))
        self.add_item(Loop(not player.is_playing()))
        self.add_item(Shuffle(not player.queue))
        self.add_item(Disconnect())
        self.add_item(AddSong())
        self.add_item(AutoPlay())


class Resume(ui.Button):
    def __init__(self, disabled: bool):
        super().__init__(
            style=discord.ButtonStyle.blurple,
            row=1,
            emoji="<:play:1021592463552557086>",
            disabled=disabled,
        )
        self.view: MusicView

    async def callback(self, i: discord.Interaction) -> typing.Any:
        await self.view.player.resume()


class Pause(ui.Button):
    def __init__(self, disabled: bool):
        super().__init__(
            style=discord.ButtonStyle.blurple,
            row=1,
            emoji="<:pause:1021592461665116201>",
            disabled=disabled,
        )
        self.view: MusicView

    async def callback(self, i: discord.Interaction) -> typing.Any:
        await self.view.player.pause()
        await return_music_embed(i, self.view.player)


class Stop(ui.Button):
    def __init__(self, disabled: bool):
        super().__init__(
            style=discord.ButtonStyle.red,
            row=3,
            disabled=disabled,
            emoji="<:stop:1021592456225112075>",
        )
        self.view: MusicView

    async def callback(self, i: discord.Interaction) -> typing.Any:
        self.view.player.queue.clear()
        await self.view.player.stop()
        await return_music_embed(i, self.view.player)


class Next(ui.Button):
    def __init__(self, disabled: bool):
        super().__init__(row=1, disabled=disabled, emoji="<:right:982588993122238524>")
        self.view: MusicView

    async def callback(self, i: discord.Interaction) -> typing.Any:
        await self.view.player.resume()
        await self.view.player.stop()


class Previous(ui.Button):
    def __init__(self, disabled: bool):
        super().__init__(row=1, disabled=disabled, emoji="<:left:982588994778972171>")
        self.view: MusicView

    async def callback(self, i: discord.Interaction) -> typing.Any:
        current = self.view.player.current
        assert current is not None

        self.view.player.queue.put_at_front(current)
        self.view.player.queue.put_at_front(self.view.player.queue.history[-1])
        await self.view.player.stop()


class Loop(ui.Button):
    def __init__(self, disabled: bool):
        super().__init__(
            style=discord.ButtonStyle.green,
            row=2,
            disabled=disabled,
            emoji="<:repeat_song:1021592454618689627>",
        )
        self.view: MusicView

    async def callback(self, i: discord.Interaction) -> typing.Any:
        self.view.player.queue.loop = not self.view.player.queue.loop
        await return_music_embed(i, self.view.player)


class Shuffle(ui.Button):
    def __init__(self, disabled: bool):
        super().__init__(
            style=discord.ButtonStyle.green,
            row=2,
            disabled=disabled,
            emoji="<:shuffle:1021592452693508148>",
        )
        self.view: MusicView

    async def callback(self, i: discord.Interaction) -> typing.Any:
        queue = list(self.view.player.queue)
        random.shuffle(queue)
        self.view.player.queue.clear()
        self.view.player.queue.extend(queue)
        await return_music_embed(i, self.view.player)


class ClearQueue(ui.Button):
    def __init__(self, disabled: bool):
        super().__init__(row=2, disabled=disabled, emoji="<:clear:1021592450516647966>")
        self.view: MusicView

    async def callback(self, i: discord.Interaction) -> typing.Any:
        self.view.player.queue.clear()
        await return_music_embed(i, self.view.player)


class Disconnect(ui.Button):
    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.red,
            row=3,
            emoji="<:disconnect:1021592448541130762>",
        )
        self.view: MusicView

    async def callback(self, i: discord.Interaction) -> typing.Any:
        await i.response.defer()
        await self.view.player.disconnect()
        await i.delete_original_response()


class AddSong(ui.Button):
    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.blurple,
            row=3,
            emoji="<:add_song:1021592446477549598>",
        )
        self.view: MusicView

    async def callback(self, i: discord.Interaction) -> typing.Any:
        await i.response.send_modal(AddSongModal(self.view))


class AddSongModal(BaseModal):
    query = ui.TextInput(
        label="歌曲連結或關鍵字", placeholder="請輸入歌曲連結或關鍵字", min_length=1, max_length=2000
    )

    def __init__(self, music_view: MusicView):
        super().__init__(title="新增歌曲", custom_id="add_song_modal")
        self.music_view = music_view

    async def on_submit(self, i: discord.Interaction) -> typing.Any:
        view = self.music_view
        view.disable_items()
        await i.response.edit_message(view=view)
        player = view.player
        query = self.query.value

        regex = re.compile(
            r"^(?:http|ftp)s?://"
            r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|"
            r"localhost|"
            r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
            r"(?::\d+)?"
            r"(?:/?|[/?]\S+)$",
            re.IGNORECASE,
        )
        if re.match(regex, query):  # query is a url
            if decoded := spotify.decode_url(query):
                if decoded["type"] is spotify.SpotifySearchType.unusable:
                    embed = ErrorEmbed("無效的 Spotify 連結")
                    await i.followup.send(embed=embed, ephemeral=True)
                elif decoded["type"] in (
                    spotify.SpotifySearchType.playlist,
                    spotify.SpotifySearchType.album,
                ):
                    first_track = None
                    async for spotify_track in spotify.SpotifyTrack.iterator(
                        query=decoded["id"], type=decoded["type"]
                    ):
                        if not first_track:
                            first_track = spotify_track
                        player.queue.put(spotify_track)
                    if first_track is None:
                        return await i.followup.send(
                            embed=ErrorEmbed("無法在 Spotify 上找到該播放清單/專輯"), ephemeral=True
                        )

                    if not player.is_playing():
                        await player.play(first_track)
                    embed = DefaultEmbed("已新增 Spotify 播放清單/專輯")
                    embed.set_image(url=first_track.images[0])
                    await i.edit_original_response(embed=embed)
                else:
                    track_ = await spotify.SpotifyTrack.search(
                        query=decoded["id"], return_first=True
                    )
                    spotify_track: spotify.SpotifyTrack = track_  # type: ignore
                    await player.play(spotify_track)
                    embed = DefaultEmbed("已新增 Spotify 歌曲")
                    embed.set_image(url=spotify_track.images[0])
                    await i.edit_original_response(
                        embed=embed,
                        view=view,
                    )
            elif "youtu.be" in query or "youtube" in query:
                if "list" in query:
                    playlist_ = await wavelink.NodePool.get_node().get_playlist(
                        wavelink.YouTubePlaylist, query
                    )
                    playlist: wavelink.YouTubePlaylist = playlist_  # type: ignore
                    embed = DefaultEmbed("已新增 Youtube 播放清單")

                    if not player.is_playing():
                        await player.play(playlist.tracks[0])
                        for youtube_track in playlist.tracks[1:]:
                            player.queue.put(youtube_track)
                        if isinstance(playlist.tracks[0], wavelink.YouTubeTrack):
                            embed.set_image(url=playlist.tracks[0].thumb)
                    else:
                        for youtube_track in playlist.tracks:
                            player.queue.put(youtube_track)
                        if hasattr(playlist.tracks[0], "thumb"):
                            embed.set_image(url=player.queue[0].thumb)
                    await i.edit_original_response(embed=embed, view=view)
                else:
                    if pos := re.search("&t=", query):
                        query = query[: pos.start()]
                    youtube_track_ = await wavelink.YouTubeTrack.search(
                        query, return_first=True
                    )
                    youtube_track: wavelink.YouTubeTrack = youtube_track_  # type: ignore
                    if not player.is_playing():
                        await player.play(youtube_track)
                    else:
                        player.queue.put(youtube_track)
                    embed = DefaultEmbed("已新增 Youtube 歌曲").set_image(
                        url=youtube_track.thumb
                    )
                    await i.edit_original_response(
                        embed=embed,
                    )
        else:  # query is not an url
            tracks = await wavelink.YouTubeTrack.search(query)
            options = []
            for youtube_track in tracks[:25]:
                if youtube_track.uri is None:
                    continue
                options.append(
                    discord.SelectOption(
                        label=youtube_track.title,
                        description=youtube_track.author,
                        value=youtube_track.uri,
                    )
                )
            embed = DefaultEmbed(f"Youtube 關鍵字搜尋: {query}")
            view.clear_items()
            view.add_item(ChooseSongSelect(options))
            return await i.edit_original_response(embed=embed, view=view)

        await asyncio.sleep(1.5)
        await return_music_embed(i, player)

    async def on_error(self, i: discord.Interaction, error: Exception) -> None:
        return await super().on_error(i, error)

    async def on_timeout(self) -> None:
        return await super().on_timeout()


class ChooseSongSelect(ui.Select):
    def __init__(self, options: list[discord.SelectOption]):
        super().__init__(placeholder="選擇想播放的歌曲", options=options)
        self.view: MusicView

    async def callback(self, i: discord.Interaction) -> typing.Any:
        self.view.disable_items()
        player = self.view.player

        track = await wavelink.YouTubeTrack.search(self.values[0], return_first=True)
        if not player.is_playing():
            await player.play(track)
        else:
            player.queue.put(track)

        embed = DefaultEmbed(track.title)
        embed.set_author(name="已新增 Youtube 歌曲")
        embed.set_image(url=track.thumb)
        await i.response.edit_message(embed=embed, view=self.view)
        await asyncio.sleep(1.5)
        await return_music_embed(i, player)


class AutoPlay(ui.Button):
    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.primary,
            emoji="<:auto_play_off:1100374478283866153>",
            row=3,
        )
        self.view: MusicView

    async def calllback(self, i: discord.Interaction) -> typing.Any:
        self.view.player.autoplay = not self.view.player.autoplay
        await return_music_embed(i, self.view.player)


async def get_player_embed(player: wavelink.Player) -> discord.Embed:
    embed = DefaultEmbed()
    current = player.current
    if current is None:
        embed.title = "目前沒有正在播放的歌曲"
        embed.description = "點按下方的按鈕來新增歌曲"
    else:
        embed.title = current.title
        description = f"<:song_author:1021667652718055475> 歌手: {current.author}\n<:song_link:1021667672225763419> 連結: {current.uri}\n"
        embed.description = description
        if isinstance(current, wavelink.YouTubeTrack):
            embed.set_thumbnail(url=current.thumb)
        elif isinstance(current, spotify.SpotifyTrack):
            embed.set_thumbnail(url=current.images[0])
    return embed


def get_queue_embed(queue: wavelink.BaseQueue) -> discord.Embed:
    embed = DefaultEmbed()
    if queue.is_empty:
        embed.title = "空的待播放清單"
        embed.description = "點按下方的按鈕來新增歌曲"
    else:
        desc = ""
        for index, song in enumerate(list(queue)[:10]):
            desc += f"{index+1}. {song.title}\n"
        embed.title = "播放清單(前10首)"
        embed.description = desc
    return embed


def get_player_status_embed(player: wavelink.Player) -> discord.Embed:
    embed = DefaultEmbed()
    embed.add_field(
        name="播放狀態", value="暫停中" if player.is_paused() else "正在播放", inline=False
    )
    embed.add_field(
        name="循環模式", value="開啟" if player.queue.loop else "關閉", inline=False
    )
    embed.add_field(name="自動播放", value="開啟" if player.autoplay else "關閉", inline=False)
    return embed


async def return_music_embed(i: discord.Interaction, player: wavelink.Player) -> None:
    player_embed = await get_player_embed(player)
    queue_embed = get_queue_embed(player.queue + player.auto_queue)
    status_embed = get_player_status_embed(player)
    view = MusicView(player)
    embeds = (player_embed, queue_embed, status_embed)

    try:
        await i.response.edit_message(embeds=embeds, view=view)
    except discord.InteractionResponded:
        await i.edit_original_response(embeds=embeds, view=view)
    view.message = await i.original_response()


class MusicCog(commands.Cog, name="music"):
    def __init__(self, bot):
        super().__init__()
        self.bot: BotModel = bot

    async def cog_load(self) -> None:
        self.bot.loop.create_task(self.connect_node())

    async def connect_node(self):
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

        await asyncio.sleep(300)
        if not player.is_playing():
            await player.disconnect()

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, node: wavelink.Node) -> None:
        logging.info(f"Node {node.id} is ready.")

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
        await return_music_embed(i, player)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MusicCog(bot))
