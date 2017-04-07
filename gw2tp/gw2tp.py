import discord
from discord.ext import commands

try: # check if BeautifulSoup4 is installed
	from bs4 import BeautifulSoup
	soupAvailable = True
except:
	soupAvailable = False
import aiohttp
...


class APIError(Exception):
	pass


class APIKeyError(Exception):
	pass

class Gw2tp:
	"""This cog finds tp prices"""

	def __init__(self, bot):
		self.bot = bot
		self.session = aiohttp.ClientSession(loop=self.bot.loop)

	@commands.command(pass_context=True)
	async def tp(self, ctx, tpbuyid: str):
		"""This finds the current buy price of an item
		Doesn't require any keys/scopes"""
		user = ctx.message.author
		try:
			commerce = 'commerce/prices/'
			endpoint = commerce + tpbuyid
			result = await self.call_api(endpoint)
		except APIKeyError as e:
			await self.bot.say(e)
			return
		except APIError as e:
			await self.bot.say("{0.mention}, API has responded with the following error: "
							   "`{1}`".format(user, e))
			return
		buyprice = results["unit_price"]
		sellprice = results ["unit_price"]
		color = self.getColor(user)
		data = discord.Embed(description=None, colour=color)
		data.add_field(name="Buy price", value=buyprice)
		data.add_field(name="Sell price", value=sellprice)

		try:
			await self.bot.say(embed=data)
		except discord.HTTPException:
			await self.bot.say("Need permission to embed links")



	async def call_api(self, endpoint):
		apiserv = 'https://api.guildwars2.com/v2/'
		url = apiserv + endpoint
		async with self.session.get(url) as r:
			results = await r.json()
		if "error" in results:
			raise APIError("The API is dead!")
		if "text" in results:
			raise APIError(results["text"])
		return results



def setup(bot):
	if soupAvailable:
		bot.add_cog(Gw2tp(bot))
	else:
		raise RuntimeError("You need to run `pip3 install beautifulsoup4`")