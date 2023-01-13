from discord.ext import commands

from utility.utils import default_embed

class VoteCog(commands.Cog):
    def __init__(self, bot):
        self.bot: commands.Bot = bot
    
    @commands.has_any_role("學生管理員", "猜猜我是誰")
    @commands.command(name="vote")
    async def vote(self, ctx: commands.Context):
        vote_dict = {}
        
        message = await ctx.send("正在翻閱歷史訊息...")
        async for message in ctx.channel.history(limit=100):
            if '✅' in [str(reaction.emoji) for reaction in message.reactions]:
                vote_dict[message.id] = message.reactions[0].count - 1
        
        top_5 = sorted(vote_dict.items(), key=lambda x: x[1], reverse=True)[:5]
        
        await message.delete()
        
        for i, (message_id, votes) in enumerate(top_5, start=1):
            message = await ctx.channel.fetch_message(message_id)
            embed = default_embed(f"#{i}", message.content)
            embed.set_footer(text=f"第一階段獲得{votes}票")
            if message.attachments:
                embed.set_image(url=message.attachments[0].url)
            await ctx.send(embed=embed)
        
        embed = default_embed("第二輪投票", "請從上方選擇一個你最喜歡的群組名稱/圖片")
        message = await ctx.send(embed=embed)
        for i in range(5):
            await message.add_reaction(f"{i + 1}\N{combining enclosing keycap}")
        
        
async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(VoteCog(bot))
