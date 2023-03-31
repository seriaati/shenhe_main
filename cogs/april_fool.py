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
    "在": "再",
    "是": "肆",
    "啊": "阿",
    "啦": "辣",
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
        now = datetime.now()
        if (
            now.month == 4 and now.day == 1
        ) or message.channel.id == 1091296420486729758:
            await message.delete()

            webhook = await message.channel.webhooks()
            if not webhook:
                webhook = await message.channel.create_webhook(name="April Fool")
            else:
                webhook = webhook[0]

            new_content = message.content
            for k, v in nii_lang_dict.items():
                new_content = new_content.replace(k, v)

            num = randint(1, 100)
            if num <= 10:
                new_content += "ww"

            # reaplce all emoji strings with "?"
            guild_emoji_strings = [f"<:{a.name}:{a.id}>" for a in message.guild.emojis]
            if not any(a in new_content for a in guild_emoji_strings):
                new_content = re.sub(r"<:\w+:\d+>", choice(kokomi_emojis), new_content)
                new_content = re.sub(r"<a:\w+:\d+>", choice(kokomi_emojis), new_content)

            if message.reference:
                new_content = f"[↰]({message.reference.jump_url}){message.reference.resolved.content}\n\n{new_content}"
            await webhook.send(
                content=new_content,
                username=message.author.display_name,
                avatar_url=message.author.display_avatar.url,
                files=[await a.to_file() for a in message.attachments],
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AprilFoolCog(bot))
