import random
import re

from discord import ButtonStyle, Interaction, Member, Message, utils
from discord.ext import commands
from discord.ui import Button, button

from apps.flow import register_flow_account, remove_flow_account
from debug import DefaultView
from utility.utils import default_embed, error_embed, log


class WelcomeCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot: commands.Bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        if message.author.id == self.bot.user.id:
            return

        guild = self.bot.get_guild(self.bot.guild_id)
        uid_channel = utils.get(guild.channels, name="uid台")
        if message.channel.id == uid_channel.id:
            uid = re.findall(r"\d+", message.content)
            if len(uid) == 0:
                return
            uid = uid[0]
            if len(uid) != 9:
                return await message.channel.send(
                    content=message.author.mention,
                    embed=error_embed().set_author(
                        name="UID 長度需為9位數", icon_url=message.author.avatar
                    ),
                )
            if uid[0] != "9":
                return await message.channel.send(
                    content=message.author.mention,
                    embed=error_embed().set_author(
                        name="你不是台港澳服玩家", icon_url=message.author.avatar
                    ),
                )
            await self.bot.db.execute(
                "INSERT INTO genshin_accounts (user_id, uid) VALUES (?, ?) ON CONFLICT (user_id) DO UPDATE SET uid = ? WHERE user_id =?",
                (message.author.id, uid, uid, message.author.id),
            )
            await self.bot.db.commit()
            await message.channel.send(
                content=message.author.mention,
                embed=default_embed(message=uid).set_author(
                    name="UID 設置成功", icon_url=message.author.avatar
                ),
            )
            traveler = utils.get(guild.roles, name="旅行者")
            await message.author.add_roles(traveler)

    @commands.Cog.listener()
    async def on_member_remove(self, member: Member):
        if member.guild.id != self.bot.guild_id:
            return
        log(True, False, "On Member Remove", member.id)
        await remove_flow_account(member.id, self.bot.db)

    @commands.Cog.listener()
    async def on_member_update(self, before: Member, after: Member):
        if before.guild.id != self.bot.guild_id:
            return
        if self.bot.debug_toggle:
            return

        traveler = utils.get(before.guild.roles, name="旅行者")
        if traveler not in before.roles and traveler in after.roles:
            await register_flow_account(after.id, self.bot.db)
            public = self.bot.get_channel(916951131022843964)
            view = WelcomeCog.Welcome(after)
            welcome_strs = [
                "祝你保底不歪十連雙黃",
                "祝你10連全武器 <:ehe:956180671620055050> <:ehe:956180671620055050>",
                "希望你喜歡並享受這裡充滿歡笑和||變態||的氣氛",
                "我們群中都是喜歡玩原神的||大課長||玩家!",
                "歡迎你成為我們的一份子||(扣上鐵鏈)||",
                "刻晴賽高!",
                "要好好跟大家相處唷~",
                "你也是偽裝成萌新的大佬嗎?",
                "七七喜歡你~",
            ]
            welcome_str = random.choice(welcome_strs)
            embed = default_embed(
                f"歡迎 {after.name} !", f"歡迎來到緣神有你(๑•̀ω•́)ノ\n {welcome_str}"
            )
            embed.set_thumbnail(url=after.avatar)
            await public.send(content=after.mention, embed=embed, view=view)

    class Welcome(DefaultView):
        def __init__(self, member: Member):
            self.member = member
            super().__init__(timeout=None)

        @button(label="歡迎~", style=ButtonStyle.blurple, custom_id="welcome_button")
        async def welcome(self, i: Interaction, button: Button):
            image_urls = [
                "https://media.discordapp.net/attachments/936772657536446535/978537906538954782/mhQ174-icc4ZdT1kSdw-dw.gif",
                "https://media.discordapp.net/attachments/630553822036623370/946061268828192829/don_genshin220223.gif",
                "https://media.discordapp.net/attachments/813430632347598882/821418716243427419/d6bf3d80f1151c55.gif",
                "https://media.discordapp.net/attachments/630553822036623370/811578439852228618/kq_genshin210217.gif",
                "https://media.discordapp.net/attachments/630553822036623370/810819929187155968/kq.gif",
                "https://media.discordapp.net/attachments/630553822036623370/865978275125264414/ayk_genshin210717.gif",
                "https://media.discordapp.net/attachments/630553822036623370/890615080381730836/kkm_genshin210923.gif",
                "https://media.discordapp.net/attachments/630553822036623370/840964488362590208/qq_genshin210509.gif",
                "https://media.discordapp.net/attachments/630553822036623370/920326390329516122/rid_genshin211214.gif",
                "https://media.discordapp.net/attachments/630553822036623370/866703863276240926/rdsg_genshin210719.gif",
            ]
            image_url = random.choice(image_urls)
            embed = default_embed(
                f"{self.member.name} 歡迎歡迎~", "<:penguin_hug:978250194779000892>"
            )
            embed.set_thumbnail(url=image_url)
            embed.set_author(name=i.user.name, icon_url=i.user.display_avatar.url)
            await i.response.send_message(embed=embed)

    class AcceptRules(DefaultView):
        def __init__(self):
            super().__init__(timeout=None)

        @button(label="同意以上規則", style=ButtonStyle.green, custom_id="accept_rule_button")
        async def accept_rules(self, i: Interaction, button: Button):
            uid_unlock = utils.get(i.guild.roles, name="uid_unlock")
            uid_channel = utils.get(i.guild.channels, name="uid台")
            if uid_unlock in i.user.roles:
                return await i.response.send_message(
                    embed=default_embed("您已同意過上述規則了", f"請至 {uid_channel} 輸入 UID"),
                    ephemeral=True,
                )

            await i.user.add_roles(uid_unlock)
            await i.response.send_message(
                embed=default_embed("✅ 您已同意上述規則", f"請至 {uid_channel.mention} 輸入你的 UID"),
                ephemeral=True,
            )

    @commands.is_owner()
    @commands.command(name="welcome")
    async def welcome(self, ctx: commands.Context):
        content = "旅行者們，歡迎來到「緣神有你」。\n在這裡你能收到提瓦特的二手消息, 還能找到志同道合的旅行者結伴同行。\n準備好踏上旅途了嗎? 出發前請先閱讀下方的「旅行者須知」。\n"
        rules = default_embed(
            "🔖 旅行者須知",
            "⚠️ 以下違規情形發生，將直接刪除貼文並禁言\n\n"
            "1. 張貼侵權事物的網址或載點\n"
            "2. 惡意引戰 / 惡意帶風向 / 仇恨言論或霸凌 / 煽動言論\n"
            "3. 交換 / 租借 / 買賣遊戲帳號、外掛\n"
            "4. 在色色台以外發表色情訊息 / 大尺度圖片 / 露點或者其他暴露圖 / \n使人感到不適的圖片或表情 / 以上相關連結\n"
            "5. 發送大量無意義言論洗版\n"
            "6. 討論政治相關內容\n"
            "7. 以暱稱惡搞或假冒管理員以及官方帳號 / 使用不雅的暱稱或簽名\n"
            "8. 推銷或發布垃圾訊息\n"
            "9. 私訊騷擾其他旅行者\n\n"
            "以上守則會隨著大家違規的創意和台主們的心情不定時更新, 感謝遵守規則的各位~\n",
        )
        view = WelcomeCog.AcceptRules()
        await ctx.send(content=content, embed=rules, view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WelcomeCog(bot))
