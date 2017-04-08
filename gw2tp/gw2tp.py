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

class ShinyAPIError(Exception):
	pass

class APIKeyError(Exception):
	pass

class Gw2tp:
	"""This cog finds tp prices"""

	def __init__(self, bot):
		self.bot = bot
		self.session = aiohttp.ClientSession(loop=self.bot.loop)

	@commands.command(pass_context=True)
	async def tpdata(self, ctx, *, tpitemname: str):
		"""This finds the current buy and sell prices of an item
		If multiple matches are found, displays the first"""
		user = ctx.message.author
		tpitemname = tpitemname.replace(" ", "%20")
		color = self.getColor(user)
		try:
			shiniesendpoint = tpitemname
			shiniesresults = await self.call_shiniesapi(shiniesendpoint)
			itemnameresult = shiniesresults[0]["name"]
			tpbuyid = shiniesresults[0]["item_id"]
			commerce = 'commerce/prices/'
			endpoint = commerce + tpbuyid
			results = await self.call_api(endpoint)
		except APIKeyError as e:
			await self.bot.say(e)
			return
		except ShinyAPIError as e:
			await self.bot.say("{0.mention}, API has responded with the following error: "
							   "`{1}`".format(user, e))
			return
		except APIError as e:
			data = discord.Embed(description='I was unable to match that to an item on the TP , listing all - use !tpid (id) to select one', colour=color)
			#For each item returned, add to the data table
			counter = 0
			for name in shiniesresults:
				if counter < 10:
					data.add_field(name=name['name'], value=name['item_id'])
					counter += 1	
			try:
				await self.bot.say(embed=data)
				if counter > 9:
					await self.bot.say("More than 10 entries, try to refine your search")
			except discord.HTTPException:
				await self.bot.say("Issue embedding data into discord - EC1")
			return
		buyprice = results["buys"]["unit_price"]
		sellprice = results ["sells"]["unit_price"]			
		if buyprice != 0:
			buyprice = self.gold_to_coins(buyprice)
		if sellprice != 0:
			sellprice = self.gold_to_coins(sellprice)
		if buyprice == 0:
			buyprice = 'No buy orders'
		if sellprice == 0:
			sellprice = 'No sell orders'				
		data = discord.Embed(title=itemnameresult, description='Not the item you wanted? Try !tplist (name) instead', colour=color)
		data.add_field(name="Buy price", value=buyprice)
		data.add_field(name="Sell price", value=sellprice)

		try:
			await self.bot.say(embed=data)
		except discord.HTTPException:
			await self.bot.say("Issue embedding data into discord - EC2")

	@commands.command(pass_context=True)
	async def tpid(self, ctx, *, tpdataid: str):
		"""This finds the current buy and sell prices of an item
		If multiple matches are found, displays the first"""
		user = ctx.message.author
		color = self.getColor(user)
		try:
			commerce = 'commerce/prices/'
			endpoint = commerce + tpdataid
			results = await self.call_api(endpoint)
			items = 'items/'
			endpoint = items + tpdataid
			itemsresult = await self.call_api(endpoint)
			itemnameresult = itemsresult["name"]	
		except APIKeyError as e:
			await self.bot.say(e)
			return
		except APIError as e:
			await self.bot.say("{0.mention}, This item isn't on the TP "
							   "`{1}`".format(user, e))
			return
		buyprice = results["buys"]["unit_price"]
		sellprice = results ["sells"]["unit_price"]
		if buyprice != 0:
			buyprice = self.gold_to_coins(buyprice)
		if sellprice != 0:
			sellprice = self.gold_to_coins(sellprice)
		if buyprice == 0:
			buyprice = 'No buy orders'
		if sellprice == 0:
			sellprice = 'No sell orders'
		data = discord.Embed(title=itemnameresult, colour=color)
		data.add_field(name="Buy price", value=buyprice)
		data.add_field(name="Sell price", value=sellprice)

		try:
			await self.bot.say(embed=data)
		except discord.HTTPException:
			await self.bot.say("Iss")

	@commands.command(pass_context=True)
	async def tplist(self, ctx, *, tpitemname: str):
		"""This lists the ids and names of all matching items to the entered name"""
		user = ctx.message.author
		color = self.getColor(user)
		tpitemname = tpitemname.replace(" ", "%20")
		try:
			shiniesendpoint = tpitemname
			shiniesresults = await self.call_shiniesapi(shiniesendpoint)
		except APIKeyError as e:
			await self.bot.say(e)
			return
		except ShinyAPIError as e:
			await self.bot.say("{0.mention}, API has responded with the following error: "
							   "`{1}`".format(user, e))
			return
		data = discord.Embed(description='Matching IDs, use !tpid (id) to see prices for a specific item', colour=color)
		#For each item returned, add to the data table
		counter = 0
		for name in shiniesresults:
			if counter < 10:
				data.add_field(name=name['name'], value=name['item_id'])
				counter += 1	
		try:
			await self.bot.say(embed=data)
			if counter > 9:
				await self.bot.say("More than 10 entries, try to refine your search")
		except discord.HTTPException:
			await self.bot.say("Issue embedding data into discord - EC3")

	@commands.command(pass_context=True)
	async def gemprice(self, ctx, numberOfGems : int = 400):
		"""This lists current gold/gem prices"""
		user = ctx.message.author
		try:
			endpoint = "commerce/exchange/coins?quantity=10000000"
			gemsresult = await self.call_api(endpoint)
		except APIKeyError as e:
			await self.bot.say(e)
			return
		except ShinyAPIError as e:
			await self.bot.say("{0.mention}, API has responded with the following error: "
							   "`{1}`".format(user, e))
			return

		gemCost = gemsresult['coins_per_gem']*numberOfGems

		# Display data
		data = discord.Embed(title="Gem / Gold price", colour=color)
		data.add_field(name=str(numberOfGems) + " Gems",value=self.gold_to_coins(gemCost))

		try:
			await self.bot.say(embed=data)
		except discord.HTTPException:
			await self.bot.say("Issue embedding data into discord - EC3")

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
	async def call_shiniesapi(self, shiniesendpoint):
		shinyapiserv = 'https://www.gw2shinies.com/api/json/idbyname/'
		url = shinyapiserv + shiniesendpoint
		async with self.session.get(url) as r:
			shiniesresults = await r.json()
		if shiniesresults is None:
			raise ShinyAPIError("Could not find an item by that name")
		if "error" in shiniesresults:
			raise ShinyAPIError("The API is dead!")
		if "text" in shiniesresults:
			raise ShinyAPIError(shiniesresults["text"])
		return shiniesresults	

	def gold_to_coins(self, money):
		gold, remainder = divmod(money, 10000)
		silver, copper = divmod(remainder, 100)
		if gold == 0:
			gold_string = ""
		else:
			gold_string = str(gold) + "g"
		if silver == 0:
			silver_string = ""
		else:
			silver_string = " " + str(silver) + "s"
		if copper == 0:
			copper_string = ""
		else:
			copper_string = " " + str(copper) + "c" 
		return gold_string + silver_string + copper_string

	def getColor(self, user):
		try:
			color = user.colour
		except:
			color = discord.Embed.Empty
		return color

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