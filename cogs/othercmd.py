import io
import logging
import random
import re
import zipfile
from typing import Dict, List, Optional, Union
from uuid import uuid4

import discord
from discord import Embed, app_commands
from discord.ext import commands
from discord.ui import Button

import utility.draw as draw
from dev.model import BaseView, BotModel, DefaultEmbed, ErrorEmbed, Inter
from utility.paginator import GeneralPaginator
from utility.utils import divide_chunks


async def send_no_image_found(i: discord.Interaction):
    embed = ErrorEmbed("此訊息內沒有任何圖片", "請確認訊息內是否有圖片或是圖片網址")
    embed.set_footer(text="如果這是誤判，請聯絡小雪")
    await i.edit_original_response(embed=embed)


def convert_twitter_to_direct_url(url: str) -> str:
    if "twitter" in url and "fxtwitter" not in url:
        url = url.replace("twitter", "fxtwitter")

    image_extensions = ("png", "jpg", "jpeg", "gif", "webp")
    if any(ext in url for ext in image_extensions):
        return url
    return url + ".jpg"


def convert_phixiv_to_direct_url(url: str) -> Optional[str]:
    if "pixiv" in url and "phixiv" not in url:
        url = url.replace("pixiv", "phixiv")

    id_pattern = re.compile(r"/(\d+)$")
    match = id_pattern.search(url)
    if not match:
        return None

    artwork_id = match.group(1)
    url = f"https://www.phixiv.net/d/{artwork_id}"
    return url


class OtherCMDCog(commands.Cog, name="other"):
    def __init__(self, bot):
        self.bot: BotModel = bot
        self.quote_ctx_menu = app_commands.ContextMenu(
            name="語錄", callback=self.quote_context_menu
        )
        self.hao_se_o_ctx_menu = app_commands.ContextMenu(
            name="好色喔", callback=self.hao_se_o_context_menu
        )
        self.mark_fbi_ctx_menu = app_commands.ContextMenu(
            name="標記危險訊息", callback=self.mark_fbi_message
        )
        self.save_iamge_ctx_menu = app_commands.ContextMenu(
            name="儲存圖片", callback=self.save_image
        )
        self.bot.tree.add_command(self.quote_ctx_menu)
        self.bot.tree.add_command(self.hao_se_o_ctx_menu)
        self.bot.tree.add_command(self.mark_fbi_ctx_menu)
        self.bot.tree.add_command(self.save_iamge_ctx_menu)

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(
            self.quote_ctx_menu.name, type=self.quote_ctx_menu.type
        )
        self.bot.tree.remove_command(
            self.hao_se_o_ctx_menu.name, type=self.hao_se_o_ctx_menu.type
        )
        self.bot.tree.remove_command(
            self.mark_fbi_ctx_menu.name, type=self.mark_fbi_ctx_menu.type
        )
        self.bot.tree.remove_command(
            self.save_iamge_ctx_menu.name, type=self.save_iamge_ctx_menu.type
        )

    async def quote_context_menu(
        self, i: discord.Interaction, message: discord.Message
    ) -> None:
        logging.info(
            f"Quoting {message.author.id} in {message.channel.id} by {i.user.id}"
        )
        await i.response.send_message(
            embed=DefaultEmbed("語錄擷取成功"),
            ephemeral=True,
        )
        assert isinstance(message.author, discord.Member)
        await self.send_quote_embed(message.author, message)

    async def hao_se_o_context_menu(
        self, i: discord.Interaction, message: discord.Message
    ):
        await i.response.send_message("已新增", ephemeral=True)
        emojis = [
            "<:1_:1062180387922645082>",
            "<:2_:1062180392246980638>",
            "<:3_:1062180394906177678>",
        ]
        for e in emojis:
            await message.add_reaction(e)

    async def mark_fbi_message(self, i: discord.Interaction, message: discord.Message):
        await i.response.send_message("標記成功", ephemeral=True)
        await message.reply(f"⚠️ {i.user.mention} 已將此訊息標記為危險訊息，將自動通報至 FBI")

    async def save_image(self, i: discord.Interaction, message: discord.Message):
        await i.response.defer(ephemeral=True)

        url_pattern = re.compile(
            r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
        )
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

        embeds = self.get_image_embeds(i.user, db_urls, "圖片儲存成功")
        await GeneralPaginator(i, embeds).start(edit=True)

    async def send_quote_embed(self, member: discord.Member, msg: discord.Message):
        embed = DefaultEmbed(
            description=msg.content,
        )
        embed.add_field(name="原訊息", value=f"[點我]({msg.jump_url})", inline=False)
        embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
        embed.set_footer(text=msg.created_at.strftime("%Y-%m-%d %H:%M:%S"))

        if msg.attachments:
            embed.set_image(url=msg.attachments[0].url)

        if msg.reference and msg.reference.message_id:
            ref = await msg.channel.fetch_message(msg.reference.message_id)
            embed.add_field(
                name="回覆給...", value=f"[{ref.author}]({ref.jump_url})", inline=False
            )

        channel = self.bot.get_channel(1061883645591310427)
        assert isinstance(channel, discord.TextChannel)
        await channel.send(embed=embed)

    class DownloadImage(discord.ui.Button):
        def __init__(self):
            super().__init__(label="下載所有圖片", style=discord.ButtonStyle.primary)

        async def callback(self, inter: discord.Interaction):
            i: Inter = inter  # type: ignore
            embed = DefaultEmbed("下載圖片中", "請稍後...")
            await i.response.send_message(embed=embed, ephemeral=True)

            urls_ = await i.client.pool.fetchval(
                "SELECT image_urls FROM save_image WHERE user_id = $1", i.user.id
            )
            urls: List[str] = urls_  # type: ignore
            if not urls:
                embed = ErrorEmbed("沒有圖片可以下載")
                return await i.edit_original_response(embed=embed)

            fps: Dict[str, io.BytesIO] = {}
            for url in urls:
                clean_url = re.sub(r"\?.*", "", url)
                if "twitter" in clean_url:
                    clean_url = convert_twitter_to_direct_url(clean_url)
                elif "phixiv" in clean_url or "pixiv" in clean_url:
                    clean_url = convert_phixiv_to_direct_url(clean_url)
                    if clean_url is None:
                        continue

                artwork_id = clean_url.split("/")[-1] + ".jpg"
                fp = io.BytesIO()
                logging.info(f"Downloading {clean_url}")
                async with i.client.session.get(clean_url) as resp:
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
        embeds = self.get_image_embeds(i.user, images, "圖片管理器")

        await GeneralPaginator(i, embeds, [self.DownloadImage()]).start(edit=True)

    def get_image_embeds(
        self, user: Union[discord.Member, discord.User], images: List[str], title: str
    ) -> List[Embed]:
        embeds: List[Embed] = []
        for image in images:
            image = re.sub(r"\?.*", "", image)
            if "twitter" in image:
                image = convert_twitter_to_direct_url(image)
            elif "phixiv" in image or "pixiv" in image:
                image = convert_phixiv_to_direct_url(image)
                if image is None:
                    continue

            embed = DefaultEmbed(title, image)
            embed.set_author(name=user.display_name, icon_url=user.display_avatar.url)
            embed.set_image(url=image)
            embed.set_footer(text=f"共 {len(images)} 張圖片")
            embeds.append(embed)
        return embeds

    @app_commands.command(name="bypass", description="繞過 Discord 的圖片禁令限制")
    @app_commands.rename(image="圖片")
    @app_commands.describe(image="要上傳的圖片")
    async def bypass(self, i: discord.Interaction, image: discord.Attachment):
        await i.response.send_message(image.url)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author == self.bot.user:
            return
        if "機率" in message.content:
            value = random.randint(1, 100)
            await message.reply(f"{value}%")
        if "好色喔" in message.content:
            emojis = [
                "<:__1:1062180387922645082>",
                "<:__2:1062180392246980638>",
                "<:__3:1062180394906177678>",
            ]
            for e in emojis:
                await message.add_reaction(e)

    @app_commands.command(name="ping", description="查看機器人目前延遲")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "🏓 Pong! {0}s".format(round(self.bot.latency, 1))
        )

    @app_commands.command(name="cute", description="讓申鶴說某個人很可愛")
    @app_commands.rename(person="某個人")
    async def cute(self, interaction: discord.Interaction, person: str):
        await interaction.response.send_message(f"{person}真可愛~❤")

    @app_commands.command(name="flash", description="防放閃機制")
    async def flash(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "https://media.discordapp.net/attachments/823440627127287839/960177992942891038/IMG_9555.jpg"
        )

    @app_commands.command(name="randomnumber", description="讓申鶴從兩個數字間挑一個隨機的給你")
    @app_commands.rename(num_one="數字一", num_two="數字二")
    async def number(
        self, interaction: discord.Interaction, num_one: int, num_two: int
    ):
        value = random.randint(int(num_one), int(num_two))
        await interaction.response.send_message(str(value))

    @app_commands.command(name="marry", description="結婚 💞")
    @app_commands.rename(person_one="攻", person_two="受")
    async def marry(
        self, interaction: discord.Interaction, person_one: str, person_two: str
    ):
        await interaction.response.send_message(f"{person_one} ❤ {person_two}")

    @app_commands.command(name="pickrandom", description="從指令使用者所在的語音台中隨機挑選一個人")
    async def pickrandom(self, i: discord.Interaction):
        assert isinstance(i.user, discord.Member)
        if not i.user.voice:
            return await i.response.send_message(embed=ErrorEmbed("你不在一個語音台中!"))
        v = i.user.voice.channel
        assert isinstance(v, discord.VoiceChannel)
        r = random.choice(v.members)
        await i.response.send_message(r.mention)

    @app_commands.guild_only()
    @app_commands.command(name="total-members", description="查看目前群組總人數")
    async def members(self, i: discord.Interaction):
        assert i.guild
        await i.response.send_message(
            embed=DefaultEmbed("群組總人數", f"目前共 {len(i.guild.members)} 人")
        )

    @app_commands.command(name="rolemembers", description="查看一個身份組內的所有成員")
    @app_commands.rename(role="身份組")
    @app_commands.describe(role="請選擇要查看的身份組")
    async def role_members(self, i: discord.Interaction, role: discord.Role):
        member_str = ""
        count = 1
        for member in role.members:
            member_str += f"{count}. {member.mention}\n"
            count += 1
        await i.response.send_message(
            embed=DefaultEmbed(f"{role.name} ({len(role.members)})", member_str)
        )

    @app_commands.command(name="avatar", description="查看一個用戶的頭像(並且偷偷下載)")
    @app_commands.rename(member="使用者")
    async def avatar(self, i: discord.Interaction, member: discord.Member):
        embed = DefaultEmbed(str(member))
        view = BaseView()
        view.add_item(Button(label="下載頭像", url=member.display_avatar.url))
        embed.set_image(url=member.avatar)
        await i.response.send_message(embed=embed, view=view)

    @app_commands.guild_only()
    @app_commands.command(name="popular-thread", description="查看目前最熱門的討論串")
    async def popular_thread(self, i: discord.Interaction):
        assert i.guild
        assert i.guild.icon

        threads = i.guild.threads
        threads = sorted(threads, key=lambda x: x.message_count, reverse=True)

        embeds: List[discord.Embed] = []
        div_threads = list(divide_chunks(threads, 10))
        for div in div_threads:
            embed = DefaultEmbed("最熱門的討論串")
            embed.set_author(name=i.guild.name, icon_url=i.guild.icon.url)
            for thread in div:
                value = f"訊息數量: {thread.message_count}"
                if thread.owner:
                    value += f"\n創建者: {thread.owner.mention}"
                embed.add_field(name=thread.name, value=value, inline=False)
            embeds.append(embed)

        await GeneralPaginator(i, embeds).start()

    @app_commands.command(name="cp", description="湊CP, 並查看兩人契合度")
    @app_commands.rename(person_one="攻", person_two="受", random_type="契合度計算方式")
    @app_commands.choices(
        random_type=[
            app_commands.Choice(name="天命既定", value="seed"),
            app_commands.Choice(name="隨機", value="random"),
        ]
    )
    async def slash_cp(
        self,
        i: discord.Interaction,
        person_one: discord.Member,
        person_two: discord.Member,
        random_type: str,
    ):
        await i.response.defer()

        if random_type == "seed":
            random.seed(str(person_one.id) + str(person_two.id))
        num = random.randint(0, 100)

        fp = await draw.draw_ship_image(
            person_one.display_avatar.url,
            person_two.display_avatar.url,
            num,
            self.bot.session,
        )
        fp.seek(0)

        cp_name = f"{person_one.display_name[:len(person_one.display_name)//2]}{person_two.display_name[len(person_two.display_name)//2:]}"
        embed = DefaultEmbed(
            cp_name, f"{'天命既定' if random_type == 'seed' else '隨機'}契合度: {num}%"
        )
        embed.set_image(url="attachment://ship.jpeg")

        await i.followup.send(
            content=f"{person_one.mention} ❤ {person_two.mention}",
            embed=embed,
            file=discord.File(fp, filename="ship.jpeg"),
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(OtherCMDCog(bot))
