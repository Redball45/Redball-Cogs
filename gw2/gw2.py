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
import random
import time

try: # check if BeautifulSoup4 is installed
	from bs4 import BeautifulSoup
	soupAvailable = True
except:
	soupAvailable = False


class APIError(Exception):
	pass

class ShinyAPIError(Exception):
	pass

class APIKeyError(Exception):
	pass

class Gw2:
	"""This cog finds tp prices"""

	def __init__(self, bot):
		self.bot = bot
		self.keylist = dataIO.load_json("data/guildwars2/keys.json")
		self.session = aiohttp.ClientSession(loop=self.bot.loop)
		self.gemtrack = dataIO.load_json("data/gw2/gemtrack.json")
		
	def __unload(self):
		self.session.close()

	def save_gemtrack(self):
		dataIO.save_json("data/gw2/gemtrack.json", self.gemtrack)
	
	async def getGemPrice(self, numberOfGems : int = 400):
		try:
			endpoint = "commerce/exchange/coins?quantity=10000000"
			gemsresult = await self.call_api(endpoint)
		except APIKeyError as e:
			await self.bot.say(e)
			return 0
		
		gemCost = gemsresult['coins_per_gem']*numberOfGems
		return gemCost

	@commands.command(pass_context=True)
	async def trackgems(self, ctx, gold : int):
		"""This requests to be notified when the cost of 400 gems drops below a specified price (in gold - ex: trackgems 120)"""
		user = ctx.message.author
		color = self.getColor(user)
		price = gold * 10000
		
		self.gemtrack[user.id] = { "user_id": user.id, "price": price }
		self.save_gemtrack()
		
		await self.bot.say("{0.mention}, you'll be notified when the price of 400 gems drops below {1}".format(user, self.gold_to_coins(price)))

	# tracks gemprices and notifies people
	async def _gemprice_tracker(self):
		while self is self.bot.get_cog("Gw2"):
			gemCost = await self.getGemPrice()			
			doCleanup = False
			
			if gemCost != 0:
				for user_id, data in self.gemtrack.items():
					if gemCost < data["price"]:
						user = await self.bot.get_user_info(user_id)
						await self.bot.send_message(user, "Hey, {0.mention}! You asked to be notified when 400 gems were cheaper than {1}. Guess what? They're now only {2}!".format(user, self.gold_to_coins(data["price"]), self.gold_to_coins(gemCost)))
						self.gemtrack[user_id]["price"] = 0
						doCleanup = True;
			
				if doCleanup:
					keys = [k for k, v in self.gemtrack.items() if v["price"] == 0]
					for x in keys:
						del self.gemtrack[x]
					self.save_gemtrack()
			
			await asyncio.sleep(300)

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
	async def sab(self, ctx, *, charactername : str):
		"""This displays unlocked SAB items for the character specified
		Requires an API key with characters and progression"""
		user = ctx.message.author
		scopes = ["characters", "progression"]
		color = self.getColor(user)
		charactername = charactername.replace(" ", "%20")
		try:
			self._check_scopes_(user, scopes)
			key = self.keylist[user.id]["key"]
			endpoint = "characters/" +  charactername + "/sab/?access_token={0}".format(key)
			results = await self.call_api(endpoint)
			self.bot.say("No API errors")
		except APIKeyError as e:
			await self.bot.say(e)
			return
		except APIError as e:
			await self.bot.say("{0.mention}, API has responded with the following error: "
								"`{1}`".format(user, e))
			return
		#chainsticksunlock = 
		#data = discord.Embed(description='SAB Character Info', colour =color)
		#data.add_field(name=)
		
	@commands.command(pass_context=True)
	async def quaggan(self, ctx, *, quaggan_name : str = 'random'):
		"""This displays a quaggan"""
		user = ctx.message.author
		color = self.getColor(user)
		endpoint = 'quaggans'
		base_quaggan = 'https://static.staticwars.com/quaggans/'
		try:
			l_quaggans = await self.call_api(endpoint)
			if quaggan_name == 'random':
				quaggan_name = random.choice(l_quaggans)
				URL_quaggan = base_quaggan + quaggan_name + '.jpg'
				await self.bot.say(URL_quaggan)
			elif quaggan_name == 'list':
				data = discord.Embed(title='Available quaggans')
				data.add_field(name="List of quaggans", value=', '.join(l_quaggans))
				try:
					await self.bot.say(embed=data)
				except discord.HTTPException:
					await self.bot.say("Issue embedding data into discord - EC4")	
			elif quaggan_name in l_quaggans:
				URL_quaggan = base_quaggan + quaggan_name + '.jpg'
				await self.bot.say(URL_quaggan)
			else:
				await self.bot.say("I couldn't find the requested quaggan. List of all available quaggans:")
				data = discord.Embed(title='Available quaggans')
				data.add_field(name="List of quaggans", value=', '.join(l_quaggans))
				try:
					await self.bot.say(embed=data)
				except discord.HTTPException:
					await self.bot.say("Issue embedding data into discord - EC5")				
		except APIError as e:
			await self.bot.say("{0.mention}, API returned the following error:  "
							"`{1}`".format(user, e))
			return

	@commands.command(pass_context=True)
	async def gemprice(self, ctx, numberOfGems : int = 400):
		"""This lists current gold/gem prices"""
		user = ctx.message.author
		color = self.getColor(user)

		gemCost = await self.getGemPrice(numberOfGems)
		
		# If this is zero then the API is down (OR GEMS ARE FREE!!! OMG \o/)
		if gemCost == 0:
			return

		# Display data
		data = discord.Embed(title="Gem / Gold price", colour=color)
		data.add_field(name=str(numberOfGems) + " Gems",value=self.gold_to_coins(gemCost))

		try:
			await self.bot.say(embed=data)
		except discord.HTTPException:
			await self.bot.say("Issue embedding data into discord - EC3")

	@commands.command(pass_context=True)
	async def baglevel(self, ctx):
		"""This computes the best level for opening champion bags"""
		user = ctx.message.author
		color = self.getColor(user)
		
		d_gains = {}
		global_coefs = {"wood": 19*0.949/37,
				"metal": (6*1.53 + 19*0.578)/37,
				"leather": 6*2.26/37,
				"cloth": 6*2.26/37}
		d_IDs = {"wood": [19723, 19726, 19727, 19724, 19722, 19725],
			"metal": [19697, 19699, 19702, 19700, 19701],
			"leather": [19719, 19728, 19730, 19731, 19729, 19732],
			"cloth": [19718, 19739, 19741, 19743, 19748, 19745]}
		l_IDs =  [str(item) for sublist in d_IDs.values() for item in sublist]
		max_tier = {"wood": 6, "metal": 5, "leather": 6, "cloth": 6}
		d_bounds = {"wood":{1: {"min":1, "max":20},
				2: {"min":16, "max":33},
				3: {"min":31, "max":48},
				4: {"min":46, "max":63},
				5: {"min":59, "max":80},},
			"metal": {1: {"min": 1, "max": 23},
				2: {"min": 19, "max": 53},
				3: {"min": 49, "max": 62},
				4: {"min": 63, "max": 80},},
			"leather": {1: {"min": 1, "max": 18},
				2: {"min": 16, "max": 33},
				3: {"min": 31, "max": 48},
				4: {"min": 46, "max": 63},
				5: {"min": 61, "max": 80},},
			"cloth": {1: {"min": 1, "max": 20},
				2: {"min": 16, "max": 33},
				3: {"min": 31, "max": 48},
				4: {"min": 44, "max": 63},
				5: {"min": 58, "max": 80},},}
		l_mats = ["wood", "metal", "leather", "cloth"]
		TP_prices = {mat:{} for mat in l_mats}
		try:
			endpoint = "commerce/prices?ids=" + ','.join(l_IDs)
			l_prices = await self.call_api(endpoint)
		except APIKeyError as e:
			await self.bot.say(e)
			return
		except ShinyAPIError as e:
			await self.bot.say("{0.mention}, API has responded with the following error: "
					   "`{1}`".format(user, e))
			return
		d_prices = {elem["id"]: elem for elem in l_prices}
		for mat in l_mats:
			for i, ID in enumerate(d_IDs[mat]):
				mat_price = d_prices[ID]["sells"]["unit_price"]/float(100)
				TP_prices[mat][i+1] = mat_price
		for lvl in range(1, 81):
			gain = 0
			for mat in l_mats:
				r_tier = range(1, max_tier[mat] + 1)
				nb = 0
				coef = {elem: 0 for elem in r_tier}
				for tier in r_tier[:-1]:
					try:
						lb = d_bounds[mat][tier]
						if lb["min"] <= lvl <= lb["max"]:
							nb += 1
							coef[tier] += 0.9
							coef[tier + 1] += 0.1
					except KeyError:
						pass
				for tier in r_tier:
					mat_price = float(TP_prices[mat][tier])
					temp = coef[tier] * mat_price / nb
					gain += global_coefs[mat] * temp
			d_gains[lvl] = gain
		max_profit = max(d_gains.values())
		profit_levels = [lv for lv in range(1, 81) if d_gains[lv] == max_profit]


		# Display data
		data = discord.Embed(title="Best character levels to open champion bags", colour=color)
		data.add_field(name="Best levels",value=', '.join([str(elem) for elem in profit_levels]))
		data.add_field(name="Estimated profit",value=self.gold_to_coins(int(100*max_profit)))

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

	def _check_scopes_(self, user, scopes):
		if user.id not in self.keylist:
			raise APIKeyError(
				"No API key associated with {0.mention}".format(user))
		if scopes:
			missing = []
			for scope in scopes:
				if scope not in self.keylist[user.id]["permissions"]:
					missing.append(scope)
			if missing:
				missing = ", ".join(missing)
				raise APIKeyError(
					"{0.mention}, missing the following scopes to use this command: `{1}`".format(user, missing))
	

def check_keyfolder():
	if not os.path.exists("data/guildwars2"):
		print("Creating data/guildwars2")
		os.makedirs("data/guildwars2")

def check_folders():
	if not os.path.exists("data/gw2"):
		print("Creating data/gw2")
		os.makedirs("data/gw2")

def check_files():
	files = {
		"gemtrack.json": {}
	}

	for filename, value in files.items():
		if not os.path.isfile("data/gw2/{}".format(filename)):
			print("Creating empty {}".format(filename))
			dataIO.save_json("data/gw2/{}".format(filename), value)

def check_keyfiles():
	files = {
		"keys.json": {}
	}

	for filename, value in files.items():
		if not os.path.isfile("data/gw2/{}".format(filename)):
			print("Creating empty {}".format(filename))
			dataIO.save_json("data/gw2/{}".format(filename), value)


def setup(bot):
	check_folders()
	check_files()
	check_keyfolder()
	check_keyfiles()
	n = Gw2(bot)
	loop = asyncio.get_event_loop()
	loop.create_task(n._gemprice_tracker())
	if soupAvailable:
		bot.add_cog(n)
	else:
		raise RuntimeError("You need to run `pip3 install beautifulsoup4`")
