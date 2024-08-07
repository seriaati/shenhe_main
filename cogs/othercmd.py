import random

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button
from loguru import logger

from dev.model import BaseView, BotModel, DefaultEmbed, ErrorEmbed
from utility import draw


class OtherCMDCog(commands.Cog, name="other"):
    def __init__(self, bot) -> None:
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
        self.bot.tree.add_command(self.quote_ctx_menu)
        self.bot.tree.add_command(self.hao_se_o_ctx_menu)
        self.bot.tree.add_command(self.mark_fbi_ctx_menu)

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(self.quote_ctx_menu.name, type=self.quote_ctx_menu.type)
        self.bot.tree.remove_command(self.hao_se_o_ctx_menu.name, type=self.hao_se_o_ctx_menu.type)
        self.bot.tree.remove_command(self.mark_fbi_ctx_menu.name, type=self.mark_fbi_ctx_menu.type)

    async def quote_context_menu(self, i: discord.Interaction, message: discord.Message) -> None:
        logger.info(f"Quoting {message.author.id} in {message.channel.id} by {i.user.id}")
        await i.response.send_message(
            embed=DefaultEmbed("語錄擷取成功"),
            ephemeral=True,
        )
        assert isinstance(message.author, discord.Member)
        await self.send_quote_embed(message.author, message)

    async def hao_se_o_context_menu(self, i: discord.Interaction, message: discord.Message) -> None:
        await i.response.send_message("已新增", ephemeral=True)
        emojis = [
            "<:1_:1062180387922645082>",
            "<:2_:1062180392246980638>",
            "<:3_:1062180394906177678>",
        ]
        for e in emojis:
            await message.add_reaction(e)

    async def mark_fbi_message(self, i: discord.Interaction, message: discord.Message) -> None:
        await i.response.send_message("標記成功", ephemeral=True)
        await message.reply(f"⚠️ {i.user.mention} 已將此訊息標記為危險訊息,將自動通報至 FBI")

    async def send_quote_embed(self, member: discord.Member, msg: discord.Message) -> None:
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
            embed.add_field(name="回覆給...", value=f"[{ref.author}]({ref.jump_url})", inline=False)

        channel = self.bot.get_channel(1061883645591310427)
        assert isinstance(channel, discord.TextChannel)
        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
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
    async def ping(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(f"🏓 Pong! {round(self.bot.latency, 1)}s")

    @app_commands.command(name="cute", description="讓申鶴說某個人很可愛")
    @app_commands.rename(person="某個人")
    async def cute(self, interaction: discord.Interaction, person: str) -> None:
        await interaction.response.send_message(f"{person}真可愛~❤")

    @app_commands.command(name="flash", description="防放閃機制")
    async def flash(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            "https://media.discordapp.net/attachments/823440627127287839/960177992942891038/IMG_9555.jpg"
        )

    @app_commands.command(name="randomnumber", description="讓申鶴從兩個數字間挑一個隨機的給你")
    @app_commands.rename(num_one="數字一", num_two="數字二")
    async def number(self, interaction: discord.Interaction, num_one: int, num_two: int) -> None:
        value = random.randint(int(num_one), int(num_two))
        await interaction.response.send_message(str(value))

    @app_commands.command(name="marry", description="結婚 💞")
    @app_commands.rename(person_one="攻", person_two="受")
    async def marry(
        self, interaction: discord.Interaction, person_one: str, person_two: str
    ) -> None:
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
    async def members(self, i: discord.Interaction) -> None:
        assert i.guild
        await i.response.send_message(
            embed=DefaultEmbed("群組總人數", f"目前共 {len(i.guild.members)} 人")
        )

    @app_commands.command(name="rolemembers", description="查看一個身份組內的所有成員")
    @app_commands.rename(role="身份組")
    @app_commands.describe(role="請選擇要查看的身份組")
    async def role_members(self, i: discord.Interaction, role: discord.Role) -> None:
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
    async def avatar(self, i: discord.Interaction, member: discord.Member) -> None:
        embed = DefaultEmbed(member.display_name)
        view = BaseView()
        view.add_item(Button(label="下載頭像", url=member.display_avatar.url))
        embed.set_image(url=member.display_avatar.url)
        await i.response.send_message(embed=embed, view=view)

    @app_commands.command(name="banner", description="查看一個用戶的橫幅(並且偷偷下載)")
    @app_commands.rename(member="使用者")
    async def banners(self, i: discord.Interaction, member: discord.Member):
        user = await i.client.fetch_user(member.id)
        if not user.banner:
            embed = ErrorEmbed(f"{member.display_name} 沒有橫幅")
            return await i.response.send_message(embed=embed, ephemeral=True)

        embed = DefaultEmbed(member.display_name)
        view = BaseView()
        view.add_item(Button(label="下載橫幅", url=user.banner.url))
        embed.set_image(url=user.banner.url)
        await i.response.send_message(embed=embed, view=view)

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
    ) -> None:
        await i.response.defer()

        if random_type == "seed":
            random.seed(str(person_one.id) + str(person_two.id))
        num = random.randint(0, 100)
        if person_one.id == 509258675983220754 and person_two.id == 410036441129943050:
            num = 6900

        fp = await draw.draw_ship_image(
            person_one.display_avatar.url,
            person_two.display_avatar.url,
            num,
            self.bot.session,
        )
        fp.seek(0)

        cp_name = f"{person_one.display_name[:len(person_one.display_name) // 2]}{person_two.display_name[len(person_two.display_name) // 2:]}"
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
