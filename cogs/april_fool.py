import re
from datetime import datetime
from random import choice, randint

import discord
from discord.ext import commands

nii_lang_dict = {
    "我": "窩",
    "不": "噗",
    "你": "尼",
    "吧": "叭",
    "來": "乃",
    "好": "豪",
    "幹": "尬",
    "嗎": "麼",
    "了": "勒",
    "媽": "麻",
    "是": "肆",
    "啊": "阿",
    "啦": "辣",
    "死": "鼠",
    "很": "粉",
    "沒": "迷",
    "怎": "腫",
    "的": "躂",
    "平": "大",
    "flat": "boing boing",
    "牆": "大肉包",
    "小": "大",
}

kokomi_emojis = (
    "<:kokoStare:1061964170117001226>",
    "<:kokoSugoi:1091307049746444298>",
    "<:kokoTea:1091307053475188736>",
    "<:kokoGrumpy:1091307055656226899>",
    "<:kokoBeg:1091307059158450197>",
    "<:kokoFacepalm:1091307062438395984>",
    "<:kokoFlap:1091307064397139998>",
    "<:kokoHide:1091307068138459136>",
    "<:kokoLove:1091307071523262494>",
    "<:kokoTeehee:1091307073960153148>",
    "<:kokoPeek:1091307077110071326>",
    "<:kokoPeep:1091307080826224670>",
    "<:kokoSip:1091307083095359509>",
    "<:kokoAmazed:1091307086299807774>",
    "<:kokoPikachu:1091307090066292758>",
    "<:kokoAyaya:1091307092524150804>",
    "<:kokoBless:1091307095883776040>",
    "<:kokoHurts:1091307099541229609>",
    "<:kokoCry:1091307101692887070>",
    "<:kokoFork:1091307105237094410>",
    "<:kokoHi:1091307108684800000>",
)


class AprilFoolCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        if message.channel.id in (
            1091299347213324348,
            1061946990927290370,
            1091400450449875145,
        ):
            return

        now = datetime.now()
        if (
            now.month == 4
            and now.day == 1
            and any(word in message.content for word in nii_lang_dict)
        ):
            await message.delete()

            webhook = await message.channel.webhooks()
            if not webhook:
                webhook = await message.channel.create_webhook(name="April Fool")
            else:
                webhook = webhook[0]

            content = message.content
            for k, v in nii_lang_dict.items():
                content = content.replace(k, v)

            num = randint(1, 100)
            if num <= 5:
                ww_num = randint(1, 4)
                content += "w" * ww_num

            # reaplce all emoji strings with "?"
            guild_emoji_strings = [
                f"<{'a' if a.animated else ''}:{a.name}:{a.id}>"
                for a in message.guild.emojis
            ]
            if not any(a in content for a in guild_emoji_strings):
                content = re.sub(r"<:\w+:\d+>", choice(kokomi_emojis), content)
                content = re.sub(r"<a:\w+:\d+>", choice(kokomi_emojis), content)

            if message.reference:
                ref = message.reference.resolved
                if ref.author.bot:
                    real_author = discord.utils.get(
                        message.guild.members,
                        display_name=ref.author.name,
                    )
                else:
                    real_author = ref.author
                role = [r for r in real_author.roles if "神之眼" in r.name]
                if not role:
                    color = 0xFFFFFF
                else:
                    role = role[0]
                    color = role.color

                mention = real_author.mention

                embed = discord.Embed(
                    color=color,
                    description=f"{ref.content}\n\n[跳至該訊息]({ref.jump_url})",
                    timestamp=message.created_at,
                )
                embed.set_author(
                    name=real_author.display_name,
                    icon_url=real_author.display_avatar.url,
                )

                if ref.attachments:
                    embed.set_thumbnail(url=ref.attachments[0].url)
                content = f"{content} {mention}"

            await webhook.send(
                content=content,
                username=message.author.display_name,
                avatar_url=message.author.display_avatar.url,
                files=[
                    await a.to_file(spoiler=a.is_spoiler()) for a in message.attachments
                ],
                embed=embed if message.reference else None,
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AprilFoolCog(bot))
