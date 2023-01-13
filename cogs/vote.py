from discord.ext import commands
from discord import ui, Interaction

from utility.utils import default_embed

class VoteCog(commands.Cog):
    def __init__(self, bot):
        self.bot: commands.Bot = bot
        
    class VoteView(ui.View):
        def __init__(self):
            super().__init__()
            for i in range(5):
                self.add_item(VoteCog.VoteButton(f"{i + 1}\N{combining enclosing keycap}"))
        
            self.voted = []
    
    class VoteButton(ui.Button):
        def __init__(self, emoji: str):
            super().__init__(emoji=emoji, label="0")
            self.votes = 0
            self.voted = []
        
        async def callback(self, interaction: Interaction):
            if interaction.user.id in self.voted:
                self.votes -= 1
                self.label = str(self.votes)
                self.view.voted.remove(interaction.user.id)
                self.voted.remove(interaction.user.id)
                return await interaction.response.edit_message(view=self.view)
            
            if interaction.user.id in self.view.voted:
                await interaction.response.send_message("你已經投過票了", ephemeral=True)
            else:
                self.view.voted.append(interaction.user.id)
                self.votes += 1
                self.label = str(self.votes)
                await interaction.response.edit_message(view=self.view)
    
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
        message = await ctx.send(embed=embed, view=VoteCog.VoteView())
        
async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(VoteCog(bot))
