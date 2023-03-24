import random

from discord import Attachment, File, Interaction, Member, Message, Role, app_commands
from discord.app_commands import Choice
from discord.ext import commands
from discord.ui import Button

import utility.draw as draw
from debug import DefaultView
from utility.utils import default_embed, error_embed, log


class OtherCMDCog(commands.Cog, name="other"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
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
        self.bot.tree.remove_command(
            self.quote_ctx_menu.name, type=self.quote_ctx_menu.type
        )
        self.bot.tree.remove_command(
            self.hao_se_o_ctx_menu.name, type=self.hao_se_o_ctx_menu.type
        )
        self.bot.tree.remove_command(
            self.mark_fbi_ctx_menu.name, type=self.mark_fbi_ctx_menu.type
        )

    async def hao_se_o_context_menu(self, i: Interaction, message: Message):
        c = await i.client.db.cursor()
        await i.response.send_message("已新增", ephemeral=True)
        emojis = [
            "<:1_:1062180387922645082>",
            "<:2_:1062180392246980638>",
            "<:3_:1062180394906177678>",
        ]
        for e in emojis:
            await message.add_reaction(e)
        await c.execute(
            "INSERT INTO hao_se_o (user_id, count) VALUES(?, ?) ON CONFLICT (user_id) DO UPDATE SET count = count + 1 WHERE user_id = ?",
            (message.author.id, 1, message.author.id),
        )
        await i.client.db.commit()

    async def mark_fbi_message(self, i: Interaction, message: Message):
        await i.response.send_message("標記成功", ephemeral=True)
        await message.reply(f"⚠️ {i.user.mention} 已將此訊息標記為危險訊息，將自動通報至 FBI")

    @app_commands.command(name="bypass", description="繞過 Discord 的圖片禁令限制")
    @app_commands.rename(image="圖片")
    @app_commands.describe(image="要上傳的圖片")
    async def bypass(self, i: Interaction, image: Attachment):
        await i.response.send_message(image.url)

    @app_commands.command(name="haose", description="好色喔")
    @app_commands.rename(user="使用者", leaderboard="排行榜")
    @app_commands.choices(leaderboard=[Choice(name="查看排行榜", value=1)])
    async def hao_se_o(self, i: Interaction, user: Member = None, leaderboard: int = 0):
        c = await i.client.db.cursor()
        if leaderboard == 1:
            await c.execute("SELECT user_id, count FROM hao_se_o ORDER BY count DESC")
            data = await c.fetchall()
            embed = default_embed("好色喔排行榜前15名")
            desc = ""
            for index, tpl in enumerate(data[:15]):
                user = i.guild.get_member(tpl[0]) or await i.guild.fetch_member(tpl[0])
                desc += f"{index+1}. {user.mention} - {tpl[1]}次\n"
            embed.description = desc
            await i.response.send_message(embed=embed)
        else:
            user = user or i.user
            await c.execute("SELECT count FROM hao_se_o WHERE user_id = ?", (user.id,))
            count = await c.fetchone()
            if count is None:
                await i.response.send_message(
                    embed=error_embed().set_author(
                        name="這個人沒有色色過", icon_url=user.display_avatar.url
                    ),
                    ephemeral=True,
                )
            else:
                await i.response.send_message(
                    embed=default_embed(message=f"{count[0]}次").set_author(
                        name="好色喔", icon_url=user.display_avatar.url
                    )
                )

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        if message.author == self.bot.user:
            return
        if "機率" in message.content:
            value = random.randint(1, 100)
            await message.reply(f"{value}%")
        if "好色喔" in message.content:
            c = await self.bot.db.cursor()
            emojis = [
                "<:__1:1062180387922645082>",
                "<:__2:1062180392246980638>",
                "<:__3:1062180394906177678>",
            ]
            for e in emojis:
                await message.add_reaction(e)
            await c.execute(
                "INSERT INTO hao_se_o (user_id, count) VALUES(?, ?) ON CONFLICT (user_id) DO UPDATE SET count = count + 1 WHERE user_id = ?",
                (message.author.id, 1, message.author.id),
            )
            await self.bot.db.commit()

    @app_commands.command(name="ping", description="查看機器人目前延遲")
    async def ping(self, interaction: Interaction):
        await interaction.response.send_message(
            "🏓 Pong! {0}s".format(round(self.bot.latency, 1))
        )

    @app_commands.command(name="cute", description="讓申鶴說某個人很可愛")
    @app_commands.rename(person="某個人")
    async def cute(self, interaction: Interaction, person: str):
        await interaction.response.send_message(f"{person}真可愛~❤")

    @app_commands.command(name="flash", description="防放閃機制")
    async def flash(self, interaction: Interaction):
        await interaction.response.send_message(
            "https://media.discordapp.net/attachments/823440627127287839/960177992942891038/IMG_9555.jpg"
        )

    @app_commands.command(name="randomnumber", description="讓申鶴從兩個數字間挑一個隨機的給你")
    @app_commands.rename(num_one="數字一", num_two="數字二")
    async def number(self, interaction: Interaction, num_one: int, num_two: int):
        value = random.randint(int(num_one), int(num_two))
        await interaction.response.send_message(str(value))

    @app_commands.command(name="marry", description="結婚 💞")
    @app_commands.rename(person_one="攻", person_two="受")
    async def marry(self, interaction: Interaction, person_one: str, person_two: str):
        await interaction.response.send_message(f"{person_one} ❤ {person_two}")

    @commands.command(aliases=["q"])
    async def quote(self, ctx: commands.Context):
        log(True, False, "Quote", ctx.author.id)
        await ctx.message.delete()
        msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
        await self.send_quote_embed(msg.author, msg)

    @app_commands.command(name="pickrandom", description="從指令使用者所在的語音台中隨機挑選一個人")
    async def pickrandom(self, i: Interaction):
        v = i.user.voice.channel
        r = random.choice(v.members)
        await i.response.send_message(r.mention)

    @app_commands.command(name="total-members", description="查看目前群組總人數")
    async def members(self, i: Interaction):
        g = i.user.guild
        await i.response.send_message(
            embed=default_embed("群組總人數", f"目前共 {len(g.members)} 人")
        )

    async def quote_context_menu(self, i: Interaction, msg: Message) -> None:
        log(True, False, "Quote", i.user.id)
        await i.response.send_message(
            embed=default_embed().set_author(
                name="語錄擷取成功", icon_url=i.user.display_avatar.url
            ),
            ephemeral=True,
        )
        await self.send_quote_embed(msg.author, msg)

    @app_commands.command(name="rolemembers", description="查看一個身份組內的所有成員")
    @app_commands.rename(role="身份組")
    @app_commands.describe(role="請選擇要查看的身份組")
    async def role_members(self, i: Interaction, role: Role):
        memberStr = ""
        count = 1
        for member in role.members:
            memberStr += f"{count}. {member.mention}\n"
            count += 1
        await i.response.send_message(
            embed=default_embed(f"{role.name} ({len(role.members)})", memberStr)
        )

    @app_commands.command(name="avatar", description="查看一個用戶的頭像(並且偷偷下載)")
    @app_commands.rename(member="使用者")
    async def avatar(self, i: Interaction, member: Member):
        embed = default_embed(member)
        view = DefaultView()
        view.add_item(Button(label="下載頭像", url=member.avatar.url))
        embed.set_image(url=member.avatar)
        await i.response.send_message(embed=embed, view=view)

    @app_commands.command(name="cp", description="湊CP, 並查看兩人契合度")
    @app_commands.rename(person_one="攻", person_two="受", random_type="契合度計算方式")
    @app_commands.choices(
        random_type=[
            Choice(name="天命既定", value="seed"),
            Choice(name="隨機", value="random"),
        ]
    )
    async def slash_cp(
        self, i: Interaction, person_one: Member, person_two: Member, random_type: str
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
        embed = default_embed(
            cp_name, f"{'天命既定' if random_type == 'seed' else '隨機'}契合度: {num}%"
        )
        embed.set_image(url="attachment://ship.jpeg")

        await i.followup.send(
            content=f"{person_one.mention} ❤ {person_two.mention}",
            embed=embed,
            file=File(fp, filename="ship.jpeg"),
        )

    async def send_quote_embed(self, member: Member, msg: Message):
        embed = default_embed(
            message=msg.content,
        )
        embed.add_field(name="原訊息", value=f"[點我]({msg.jump_url})", inline=False)
        embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
        embed.set_footer(text=msg.created_at.strftime("%Y-%m-%d %H:%M:%S"))

        if msg.attachments:
            embed.set_image(url=msg.attachments[0].url)

        if msg.reference:
            ref = await msg.channel.fetch_message(msg.reference.message_id)
            embed.add_field(
                name="回覆給...", value=f"[{ref.author}]({ref.jump_url})", inline=False
            )

        channel = self.bot.get_channel(1061883645591310427)
        await channel.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(OtherCMDCog(bot))
