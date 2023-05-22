from collections import defaultdict
from datetime import timedelta
from typing import DefaultDict

import discord
from discord.ext import commands


class NoSpam(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot: commands.Bot = bot
        self.user_messages: DefaultDict[int, DefaultDict[str, list[int]]] = defaultdict(
            lambda: defaultdict(list)
        )

        self.guild_id = 1061877505067327528
        self.owner_id = 410036441129943050
        self.guild: discord.Guild
        self.owner: discord.User

        # max number of messages to track per user
        self.max_messages = 3
        # if the user sends the same message in this many channels, they will be timed out
        self.max_channels = 3
        # how long to timeout the user for
        self.timeout_length = timedelta(minutes=15)

    async def cog_load(self):
        self.bot.loop.create_task(self.get_guild())

    async def get_guild(self):
        await self.bot.wait_until_ready()
        guild = self.bot.get_guild(self.guild_id)
        if guild is None:
            raise ValueError("Guild not found")
        self.guild = guild

        owner = self.bot.get_user(self.owner_id)
        if owner is None:
            raise ValueError("Owner not found")
        self.owner = owner

    async def check_messages(self, user_id: int) -> None:
        # Get all messages sent by the user
        messages = self.user_messages[user_id]

        # Check if the user has sent the same message in at least 3 different channels
        for content, channels in messages.items():
            if len(channels) >= self.max_channels:
                # Get the member object for the user
                member = self.guild.get_member(user_id)
                if member is None:
                    continue

                # Timeout the user for sending scam links
                await member.timeout(self.timeout_length, reason="Sending scam links")

                # Get the URLs of the channels where the user sent the message
                channel_urls: list[str] = []
                for channel_id in channels:
                    channel = self.bot.get_channel(channel_id)
                    if not isinstance(channel, discord.TextChannel):
                        continue

                    channel_urls.append(channel.jump_url)

                    # Delete the user's message from the channel
                    await channel.purge(
                        check=lambda m: m.author.id == user_id and m.content == content
                    )

                # Send a message to the owner with details about the spam
                urls = "\n".join(channel_urls)
                embed = discord.Embed(title="Spam detected")
                embed.description = f"""
                Message: {content}
                Channels:
                {urls}
                """
                embed.set_author(
                    name=member.display_name, icon_url=member.display_avatar.url
                )
                embed.set_footer(text=f"ID: {member.id}")
                await self.owner.send(embed=embed)

    @commands.Cog.listener("on_message")
    async def track_message(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is None:
            return

        user_id = message.author.id
        channel_id = message.channel.id
        messages = self.user_messages[user_id]
        channels = messages[message.content]
        channels.append(channel_id)

        # Remove the message from the list if it's too old
        if len(messages) > self.max_messages:
            messages.pop(list(messages.keys())[0])

        await self.check_messages(user_id)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(NoSpam(bot))
