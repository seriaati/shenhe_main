from random import choice, randint

from debug import DefaultView
from discord import Interaction, Member, Message, Role, app_commands
from discord.app_commands import Choice
from discord.ext import commands
from discord.ui import Button
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
        self.bot.tree.add_command(self.quote_ctx_menu)
        self.bot.tree.add_command(self.hao_se_o_ctx_menu)

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(
            self.quote_ctx_menu.name, type=self.quote_ctx_menu.type
        )
        self.bot.tree.remove_command(
            self.hao_se_o_ctx_menu.name, type=self.hao_se_o_ctx_menu.type
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
    async def on_message(self, message):
        if message.author == self.bot.user:
            return
        if "機率" in message.content:
            value = randint(1, 100)
            await message.channel.send(f"{value}%")
        if "好色喔" in message.content:
            c = await self.bot.db.cursor()
            emojis = [
                "<:word_hao:1021424223199187025>",
                "<:word_se:1021424220976193646>",
                "<:word_o:1021424218337984545>",
            ]
            for e in emojis:
                await message.add_reaction(e)
            await c.execute(
                "INSERT INTO hao_se_o (user_id, count) VALUES(?, ?) ON CONFLICT (user_id) DO UPDATE SET count = count + 1 WHERE user_id = ?",
                (message.author.id, 1, message.author.id),
            )
            await self.bot.db.commit()

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.emoji.id == 1062180398077059132:  # QuoteTimeWakuWaku
            log(True, False, "Quote", payload.user_id)
            member = self.bot.get_user(payload.user_id)
            msg = await channel.fetch_message(payload.message_id)
            channel = self.bot.get_channel(payload.channel_id)
            emoji = self.bot.get_emoji(payload.emoji.id)
            await msg.remove_reaction(emoji, member)
            await channel.send(f"✅ 語錄擷取成功", delete_after=3)
            await self.send_quote_embed(member, msg)

    @app_commands.command(name="ping延遲", description="查看機器人目前延遲")
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

    @app_commands.command(name="randomnumber隨機數", description="讓申鶴從兩個數字間挑一個隨機的給你")
    @app_commands.rename(num_one="數字一", num_two="數字二")
    async def number(self, interaction: Interaction, num_one: int, num_two: int):
        value = randint(int(num_one), int(num_two))
        await interaction.response.send_message(str(value))

    @app_commands.command(name="marry結婚", description="結婚 💞")
    @app_commands.rename(person_one="攻", person_two="受")
    async def marry(self, interaction: Interaction, person_one: str, person_two: str):
        await interaction.response.send_message(f"{person_one} ❤ {person_two}")

    @commands.command(aliases=["q"])
    async def quote(self, ctx):
        log(True, False, "Quote", ctx.author.id)
        await ctx.message.delete()
        msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
        await self.send_quote_embed(ctx.author, msg)

    @app_commands.command(name="pickrandom")
    async def pickrandom(self, i: Interaction):
        v = i.user.voice.channel
        r = choice(v.members)
        await i.response.send_message(f"{r.display_name}#{r.discriminator}")

    @app_commands.command(name="members總人數", description="查看目前群組總人數")
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
        await self.send_quote_embed(i.user, msg)

    @app_commands.command(name="rolemembers身份組人數", description="查看一個身份組內的所有成員")
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

    @app_commands.command(name="avatar頭像", description="查看一個用戶的頭像(並且偷偷下載)")
    @app_commands.rename(member="使用者")
    async def avatar(self, i: Interaction, member: Member):
        embed = default_embed(member)
        view = DefaultView()
        view.add_item(Button(label="下載頭像", url=member.avatar.url))
        embed.set_image(url=member.avatar)
        await i.response.send_message(embed=embed, view=view)

    async def send_quote_embed(self, member: Member, msg: Message):
        embed = default_embed(
            message=msg.content,
        )
        embed.add_field(name="原訊息", value=f"[點我]({msg.jump_url})")
        embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
        embed.set_footer(text=msg.created_at.strftime("%Y-%m-%d %H:%M:%S"))
        
        if msg.attachments:
            embed.set_image(url=msg.attachments[0].url)
        
        if msg.reference:
            ref = await msg.channel.fetch_message(msg.reference.message_id)
            embed.add_field(name="回覆給...", value=f"[{ref.author}]({ref.jump_url})")
        
        channel = self.bot.get_channel(1061883645591310427)
        message = await channel.send(embed=embed)
        emoji = self.bot.get_emoji(1062180398077059132)
        await message.add_reaction(emoji)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(OtherCMDCog(bot))
