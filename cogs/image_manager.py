import io
import re
import zipfile
from typing import Dict, List, Optional, Union
from uuid import uuid4

import discord
from discord import app_commands
from discord.ext import commands

from dev.model import BotModel, DefaultEmbed, ErrorEmbed
from utility.paginator import GeneralPaginator

url_pattern = re.compile(
    r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
)


def post_url_to_image_url(url: str) -> str:
    url = re.sub(r"\?.*", "", url)  # remove query string
    if "twitter" in url and "fxtwitter" not in url:
        url = url.replace("twitter", "fxtwitter")
        image_extensions = ("png", "jpg", "jpeg", "gif", "webp")
        if any(ext in url for ext in image_extensions):
            return url
        return url + ".png"
    elif "pixiv" in url and "phixiv" not in url:
        url = url.replace("pixiv", "phixiv")
        id_pattern = re.compile(r"/(\d+)$")
        match = id_pattern.search(url)
        if not match:
            return url

        artwork_id = match.group(1)
        url = f"https://www.phixiv.net/d/{artwork_id}"
        return url
    else:
        return url


async def send_no_image_found(i: discord.Interaction):
    embed = ErrorEmbed("此訊息內沒有任何圖片", "請確認訊息內是否有圖片或是圖片網址")
    embed.set_footer(text="如果這是誤判，請聯絡小雪")
    await i.edit_original_response(embed=embed)


def get_image_embeds(
    user: Union[discord.Member, discord.User],
    images: List[str],
    title: str,
    jump_url: Optional[str] = None,
) -> List[discord.Embed]:
    embeds: List[discord.Embed] = []
    for image_url in images:
        image_url = post_url_to_image_url(image_url)
        embed = DefaultEmbed(title, image_url)
        assert embed.description
        if jump_url:
            embed.description += f"\n\n[點我回到訊息]({jump_url})"
        embed.set_author(name=user.display_name, icon_url=user.display_avatar.url)
        embed.set_image(url=image_url)
        embed.set_footer(text=f"共 {len(images)} 張圖片")
        embeds.append(embed)
    return embeds


class DownloadImage(discord.ui.Button):
    def __init__(self):
        super().__init__(label="下載所有圖片", style=discord.ButtonStyle.primary)

    async def callback(self, inter: discord.Interaction):
        i: Inter = inter  # type: ignore
        embed = DefaultEmbed("下載圖片中", "請稍後...")
        await i.response.send_message(embed=embed, ephemeral=True)

        urls: List[str] = await i.client.pool.fetchval(
            "SELECT image_urls FROM save_image WHERE user_id = $1", i.user.id
        )
        if not urls:
            embed = ErrorEmbed("沒有圖片可以下載")
            return await i.edit_original_response(embed=embed)

        fps: Dict[str, io.BytesIO] = {}
        for url in urls:
            url = post_url_to_image_url(url)
            artwork_id = url.split("/")[-1] + ".jpg"
            fp = io.BytesIO()
            async with i.client.session.get(url) as resp:
                fp.write(await resp.read())
            fps[artwork_id] = fp

        zip_file = io.BytesIO()
        with zipfile.ZipFile(zip_file, "w") as zip:
            num = 1
            for filename, fp in fps.items():
                fp.seek(0)
                zip.writestr(filename, fp.getvalue())
                num += 1

        zip_file.seek(0)

        embed = DefaultEmbed("圖片下載成功")
        embed.description = f"共 {len(fps)} 張圖片"
        embed.set_footer(text="資料庫內的圖片皆已刪除")
        file_ = discord.File(zip_file, filename=f"{uuid4()}.zip")
        await i.edit_original_response(attachments=[file_], embed=embed)

        await i.client.pool.execute(
            "DELETE FROM save_image WHERE user_id = $1", i.user.id
        )


class ImageManager(commands.Cog):
    def __init__(self, bot):
        self.bot: BotModel = bot

    async def cog_load(self):
        self.save_iamge_ctx_menu = app_commands.ContextMenu(
            name="儲存圖片", callback=self.save_image
        )
        self.bot.tree.add_command(self.save_iamge_ctx_menu)

    async def cog_unload(self):
        self.bot.tree.remove_command(
            self.save_iamge_ctx_menu.name, type=self.save_iamge_ctx_menu.type
        )

    async def save_image(self, i: discord.Interaction, message: discord.Message):
        await i.response.defer(ephemeral=True)

        if not url_pattern.search(message.content) and not message.attachments:
            return await send_no_image_found(i)

        db_urls: List[str] = []
        websites = ("twitter", "fxtwitter", "phixiv", "pixiv")
        image_extensions = ("png", "jpg", "jpeg", "gif", "webp")
        if any(website in message.content for website in websites) or any(
            ext in message.content for ext in image_extensions
        ):
            urls = url_pattern.findall(message.content)
            if not urls:
                return await send_no_image_found(i)
            db_urls.extend(urls)

        if message.attachments:
            for attachment in message.attachments:
                if attachment.content_type and "image" in attachment.content_type:
                    db_urls.append(attachment.url)

        if not db_urls:
            return await send_no_image_found(i)

        new_urls = db_urls.copy()
        original = await self.bot.pool.fetchval(
            "SELECT image_urls FROM save_image WHERE user_id = $1", i.user.id
        )
        if original is not None:
            new_urls.extend(original)

        await self.bot.pool.execute(
            "INSERT INTO save_image (image_urls, user_id) VALUES ($1, $2) ON CONFLICT (user_id) DO UPDATE SET image_urls = $1",
            new_urls,
            i.user.id,
        )

        embeds = get_image_embeds(i.user, db_urls, "圖片儲存成功", message.jump_url)
        for embed in embeds:
            embed.set_footer(text=f"資料庫內目前共有 {len(new_urls)} 張圖片")
        await GeneralPaginator(i, embeds).start(edit=True)

    @app_commands.command(name="image-manager", description="圖片管理器")
    async def image_manager(self, i: discord.Interaction):
        await i.response.defer(ephemeral=True)
        images_ = await self.bot.pool.fetchval(
            "SELECT image_urls FROM save_image WHERE user_id = $1", i.user.id
        )

        if not images_:
            return await i.edit_original_response(
                embed=ErrorEmbed(
                    "你目前沒有儲存任何圖片",
                    """
                    以下是可以儲存的圖片來源：
                    1. 本身帶有圖片附件的訊息
                    2. 本身帶有圖片網址的訊息
                    3. Twitter 貼文的訊息
                    4. Pixiv 繪圖的訊息
                    """,
                )
            )
        images: List[str] = images_  # type: ignore
        embeds = get_image_embeds(i.user, images, "圖片管理器")

        await GeneralPaginator(i, embeds, [DownloadImage()]).start(edit=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ImageManager(bot))
