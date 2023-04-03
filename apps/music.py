import asyncio
import random
import re
import typing

import discord
import wavelink
from discord import ui
from wavelink.ext import spotify

from dev.model import BaseView, DefaultEmbed, ErrorEmbed


def music_deco(func):
    async def inner_function(*args, **kwargs):
        item_self = args[0]
        interaction = args[1]
        await func(*args, **kwargs)
        await return_music_embed(interaction, item_self.view.player)

    return inner_function


class MusicView(BaseView):
    def __init__(self, player: wavelink.Player) -> None:
        super().__init__()
        self.player = player
        self.add_item(Prev(len(player.queue.history) < 2))
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


class Resume(ui.Button):
    def __init__(self, disabled: bool):
        super().__init__(
            style=discord.ButtonStyle.blurple,
            row=1,
            emoji="<:play:1021592463552557086>",
            disabled=disabled,
        )
        self.view: MusicView

    @music_deco
    async def callback(self, i: discord.Interaction) -> typing.Any:
        await i.response.defer()
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

    @music_deco
    async def callback(self, i: discord.Interaction) -> typing.Any:
        await i.response.defer()
        await self.view.player.pause()


class Stop(ui.Button):
    def __init__(self, disabled: bool):
        super().__init__(
            style=discord.ButtonStyle.red,
            row=3,
            disabled=disabled,
            emoji="<:stop:1021592456225112075>",
        )
        self.view: MusicView

    @music_deco
    async def callback(self, i: discord.Interaction) -> typing.Any:
        await i.response.defer()
        self.view.player.queue.clear()
        await self.view.player.stop()


class Next(ui.Button):
    def __init__(self, disabled: bool):
        super().__init__(row=1, disabled=disabled, emoji="<:right:982588993122238524>")
        self.view: MusicView

    async def callback(self, i: discord.Interaction) -> typing.Any:
        await self.view.player.stop()
        self.view.disable_items()
        await i.response.edit_message(view=self.view)

        await asyncio.sleep(2)
        await return_music_embed(i, self.view.player)


class Prev(ui.Button):
    def __init__(self, disabled: bool):
        super().__init__(row=1, disabled=disabled, emoji="<:left:982588994778972171>")
        self.view: MusicView

    async def callback(self, i: discord.Interaction) -> typing.Any:
        self.view.disable_items()
        await i.response.edit_message(view=self.view)

        current = self.view.player.track
        self.view.player.queue.put_at_front(current)
        i.client.prev = True
        await self.view.player.stop()
        await asyncio.sleep(2)
        i.client.prev = False
        await return_music_embed(i, self.view.player)


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

    @music_deco
    async def callback(self, i: discord.Interaction) -> typing.Any:
        await i.response.defer()
        queue = list(self.view.player.queue)
        random.shuffle(queue)
        self.view.player.queue.clear()
        self.view.player.queue.extend(queue)


class ClearQueue(ui.Button):
    def __init__(self, disabled: bool):
        super().__init__(row=2, disabled=disabled, emoji="<:clear:1021592450516647966>")
        self.view: MusicView

    @music_deco
    async def callback(self, i: discord.Interaction) -> typing.Any:
        await i.response.defer()
        self.view.player.queue.clear()


class Disconnect(ui.Button):
    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.red,
            row=3,
            emoji="<:disconnect:1021592448541130762>",
        )

    async def callback(self, i: discord.Interaction) -> typing.Any:
        self.view: MusicView
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


class AddSongModal(ui.Modal):
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
        if re.match(regex, query) is not None:  # query is a url
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

        embed = DefaultEmbed()
        embed.set_author(name="已新增 Youtube 歌曲", icon_url=i.user.display_avatar.url)
        embed.set_image(url=track.thumb)
        await i.response.edit_message(embed=embed, view=self.view)
        await asyncio.sleep(1.5)
        await return_music_embed(i, player)


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


async def get_queue_embed(queue: wavelink.Queue, loop: bool) -> discord.Embed:
    embed = DefaultEmbed()
    if queue.is_empty:
        embed.title = "空的待播放清單"
        embed.description = "點按下方的按鈕來新增歌曲"
    elif loop:
        embed.title = "循環模式開啟中"
    else:
        desc = ""
        for index, song in enumerate(list(queue)[:10]):
            desc += f"{index+1}. {song.title}\n"
        embed.title = "播放清單(前10首)"
        embed.description = desc
    return embed


async def return_music_embed(i: discord.Interaction, player: wavelink.Player) -> None:
    player_embed = await get_player_embed(player)
    queue_embed = await get_queue_embed(player.queue, player.queue.loop)
    view = MusicView(player)

    try:
        await i.response.edit_message(embeds=[player_embed, queue_embed], view=view)
    except discord.InteractionResponded:
        await i.edit_original_response(embeds=[player_embed, queue_embed], view=view)
    view.message = await i.original_response()
