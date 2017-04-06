import discord
from discord.ext import commands

class Gw2tp:
    """My custom cog that does stuff!"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def tpprice(self):
        """This does stuff!"""

        #Your code will go here
        await self.bot.say("I can do definitelystuff!")

def setup(bot):
    bot.add_cog(Gw2tp(bot))
