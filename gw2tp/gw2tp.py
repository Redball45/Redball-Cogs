import discord
from discord.ext import commands
from .utils import checks
from cogs.utils.dataIO import dataIO, fileIO
from __main__ import send_cmd_help


import json
import os
import asyncio
import aiohttp
import datetime

try: # check if BeautifulSoup4 is installed
	from bs4 import BeautifulSoup
	soupAvailable = True
except:
	soupAvailable = False

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
	async def tpdata(self, ctx, tpbuyid: str):
		"""This finds the current buy price of an item
		Doesn't require any keys/scopes"""
		user = ctx.message.author
		try:
			commerce = 'commerce/prices/'
			endpoint = commerce + tpbuyid
			results = await self.call_api(endpoint)
		except APIKeyError as e:
			await self.bot.say(e)
			return
		except APIError as e:
			await self.bot.say("{0.mention}, API has responded with the following error: "
							   "`{1}`".format(user, e))
			return
		buyprice = results["buys"]["unit_price"]
		sellprice = results ["sells"]["unit_price"]
		buyprice = self.gold_to_coins(buyprice)
		sellprice = self.gold_to_coins(sellprice)
		data = discord.Embed(description=None)
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

	def gold_to_coins(self, money):
		gold, remainder = divmod(money, 10000)
		silver, copper = divmod(remainder, 100)
		if not gold:
			if not silver:
				return "{0} copper".format(copper)
			else:
				return "{0} silver and {1} copper".format(silver, copper)
		else:
			return "{0} gold, {1} silver and {2} copper".format(gold, silver, copper)


def check_folders():
	if not os.path.exists("data/guildwars2"):
		print("Creating data/guildwars2")
		os.makedirs("data/guildwars2")


def check_files():
	files = {
		"gamedata.json": {},
		"settings.json": {"ENABLED": False},
		"language.json": {},
		"keys.json": {},
		"build.json": {"id": None}  # Yay legacy support
	}

	for filename, value in files.items():
		if not os.path.isfile("data/guildwars2/{}".format(filename)):
			print("Creating empty {}".format(filename))
			dataIO.save_json("data/guildwars2/{}".format(filename), value)


def setup(bot):
	if soupAvailable:
		bot.add_cog(Gw2tp(bot))
	else:
		raise RuntimeError("You need to run `pip3 install beautifulsoup4`")
	check_folders()
	check_files()