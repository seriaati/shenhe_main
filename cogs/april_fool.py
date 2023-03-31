from datetime import datetime

import discord
from discord.ext import commands

nii_lang_dict = {
    "我": "窩",
    "不": "噗",
    "你": "尼",
    "吧": "叭",
    "來": "乃",
    "好": "毫",
    "幹": "尬",
    "嗎": "麼",
}


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
            await webhook.send(
                content=new_content,
                username=message.author.display_name,
                avatar_url=message.author.display_avatar.url,
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AprilFoolCog(bot))
