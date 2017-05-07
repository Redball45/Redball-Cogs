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
import urllib
import re

try: # check if BeautifulSoup4 is installed
	from bs4 import BeautifulSoup
	soupAvailable = True
except:
	soupAvailable = False


DEFAULT_HEADERS = {'User-Agent': "A GW2 Discord bot",
'Accept': 'application/json'}

class APIError(Exception):
	pass

class ShinyAPIError(Exception):
	pass

class APIKeyError(Exception):
	pass

class Guildwars2:
	"""This cog finds tp prices"""

	def __init__(self, bot):
		self.bot = bot
		self.keylist = dataIO.load_json("data/guildwars2/keys.json")
		self.session = aiohttp.ClientSession(loop=self.bot.loop)
		self.gemtrack = dataIO.load_json("data/guildwars2/gemtrack.json")
		self.build = dataIO.load_json("data/guildwars2/build.json")
		self.gamedata = dataIO.load_json("data/guildwars2/gamedata.json")
		self.settings = dataIO.load_json("data/guildwars2/settings.json")
		self.language = dataIO.load_json("data/guildwars2/language.json")
		self.containers = dataIO.load_json("data/guildwars2/containers.json")
		
	def __unload(self):
		self.session.close()

	@commands.group(pass_context=True)
	async def key(self, ctx):
		"""Commands related to API keys"""
		if ctx.invoked_subcommand is None:
			await send_cmd_help(ctx)
			return

	@key.command(pass_context=True)
	async def add(self, ctx, key):
		"""Adds your key and associates it with your discord account"""
		server = ctx.message.server
		channel = ctx.message.channel
		user = ctx.message.author
		has_permissions = channel.permissions_for(server.me).manage_messages
		if has_permissions:
			await self.bot.delete_message(ctx.message)
			output = "Your message was removed for privacy"
		else:
			output = "I would've removed your message as well, but I don't have the neccesary permissions..."
		if user.id in self.keylist:
			await self.bot.say("{0.mention}, you're already on the list, "
							   "remove your key first if you wish to change it. {1}".format(user, output))
			return
		endpoint = "tokeninfo?access_token={0}".format(key)
		try:
			results = await self.call_api(endpoint)
		except APIError as e:
			await self.bot.say("{0.mention}, {1}. {2}".format(user, e, output))
			return
		endpoint = "account/?access_token={0}".format(key)
		try:
			acc = await self.call_api(endpoint)
		except APIError as e:
			await self.bot.say("{0.mention}, API has responded with the following error: "
							   "`{1}`".format(user, e))
			return
		name = results["name"]
		if not name:
			name = None  # Else embed fails
		self.keylist[user.id] = {
			"key": key, "account_name": acc["name"], "name": name, "permissions": results["permissions"]}
		await self.bot.say("{0.mention}, your api key was verified and "
						   "added to the list. {1}".format(user, output))
		self.save_keys()

	@key.command(pass_context=True)
	async def remove(self, ctx):
		"""Removes your key from the list"""
		user = ctx.message.author
		if user.id in self.keylist:
			self.keylist.pop(user.id)
			self.save_keys()
			await self.bot.say("{0.mention}, sucessfuly removed your key. "
							   "You may input a new one.".format(user))
		else:
			await self.bot.say("{0.mention}, no API key associated with your account".format(user))

	@key.command(hidden=True)
	@checks.is_owner()
	async def clear(self):
		"""Purges the key list"""
		self.keylist = {}
		self.save_keys()
		await self.bot.say("Key list is now empty.")

	@key.command(name='list', hidden=True)
	@checks.is_owner()
	async def _list(self):
		"""Lists all keys and users"""
		if not self.keylist:
			await self.bot.say("Keylist is empty!")
		else:
			msg = await self.bot.say("Calculating...")
			readablekeys = {}
			for key, value in self.keylist.items():
				user = await self.bot.get_user_info(key)
				name = user.name
				readablekeys[name] = value
			await self.bot.edit_message(msg,
										"```{0}```".format(json.dumps(readablekeys, indent=2)))

	@key.command(pass_context=True)
	async def info(self, ctx):
		"""Information about your api key
		Requires a key
		"""
		user = ctx.message.author
		scopes = []
		try:
			self._check_scopes_(user, scopes)
			key = self.keylist[user.id]["key"]
			endpoint = "account/?access_token={0}".format(key)
			results = await self.call_api(endpoint)
		except APIKeyError as e:
			await self.bot.say(e)
			return
		except APIError as e:
			await self.bot.say("{0.mention}, API has responded with the following error: "
							   "`{1}`".format(user, e))
			return
		accountname = results["name"]
		keyname = self.keylist[user.id]["name"]
		permissions = self.keylist[user.id]["permissions"]
		permissions = ', '.join(permissions)
		color = self.getColor(user)
		data = discord.Embed(description=None, colour=color)
		if keyname:
			data.add_field(name="Key name", value=keyname)
		data.add_field(name="Permissions", value=permissions)
		data.set_author(name=accountname)
		try:
			await self.bot.say(embed=data)
		except discord.HTTPException:
			await self.bot.say("Need permission to embed links")

	@commands.command(pass_context=True)
	async def langset(self, ctx, lang):
		"""Set the language parameter and store it into settings file"""
		server = ctx.message.server

		if server is None:
			await self.bot.say("That command is not available in DMs.")

		else:
			languages = ["en", "de", "es", "fr", "ko", "zh"]
			if lang in languages:
				await self.bot.say("Language for this server set to {0}.".format(lang))
				self.language[server.id] = {"language": lang}
				dataIO.save_json('data/guildwars2/language.json', self.language)
			else:
				await self.bot.say("ERROR: Please use one of the following parameters: en, de, es, fr, ko, zh")

	@commands.command(pass_context=True)
	async def account(self, ctx):
		"""Information about your account
		Requires a key with account scope
		"""
		user = ctx.message.author
		scopes = ["account"]
		try:
			self._check_scopes_(user, scopes)
			key = self.keylist[user.id]["key"]
			endpoint = "account/?access_token={0}".format(key)
			results = await self.call_api(endpoint)
		except APIKeyError as e:
			await self.bot.say(e)
			return
		except APIError as e:
			await self.bot.say("{0.mention}, API has responded with the following error: "
							   "`{1}`".format(user, e))
			return
		accountname = self.keylist[user.id]["account_name"]
		created = results["created"].split("T", 1)[0]
		hascommander = "Yes" if results["commander"] else "No"
		color = self.getColor(user)
		data = discord.Embed(description=None, colour=color)
		data.add_field(name="Created account on", value=created)
		data.add_field(name="Has commander tag", value=hascommander, inline=False)
		if "fractal_level" in results:
			fractallevel = results["fractal_level"]
			data.add_field(name="Fractal level", value=fractallevel)
		if "wvw_rank" in results:
			wvwrank = results["wvw_rank"]
			data.add_field(name="WvW rank", value=wvwrank)
		if "pvp" in self.keylist[user.id]["permissions"]:
			endpoint = "pvp/stats?access_token={0}".format(key)
			try:
				pvp = await self.call_api(endpoint)
			except APIError as e:
				await self.bot.say("{0.mention}, API has responded with the following error: "
								   "`{1}`".format(user, e))
				return
			pvprank = pvp["pvp_rank"] + pvp["pvp_rank_rollovers"]
			data.add_field(name="PVP rank", value=pvprank)
		data.set_author(name=accountname)
		try:
			await self.bot.say(embed=data)
		except discord.HTTPException:
			await self.bot.say("Need permission to embed links")

	@commands.command(pass_context=True)
	async def li(self, ctx):
		"""Shows how many Legendary Insights you have
		Requires a key with inventories and characters scope
		"""
		user = ctx.message.author
		scopes = ["inventories", "characters"]
		msg = await self.bot.say("Getting legendary insights, this might take a while...")
		try:
			self._check_scopes_(user, scopes)
			key = self.keylist[user.id]["key"]
			endpoint_bank = "account/bank?access_token={0}".format(key)
			endpoint_shared = "account/inventory?access_token={0}".format(key)
			endpoint_char = "characters?access_token={0}".format(key)
			bank = await self.call_api(endpoint_bank)
			shared = await self.call_api(endpoint_shared)
			characters = await self.call_api(endpoint_char)
		except APIKeyError as e:
			await self.bot.say(e)
			return
		except APIError as e:
			await self.bot.say("{0.mention}, API has responded with the following error: "
							   "`{1}`".format(user, e))
			return

		bank = [item["count"] for item in bank if item != None and item["id"] == 77302]
		shared = [item["count"] for item in shared if item != None and item["id"] == 77302]
		li = sum(bank) + sum(shared)

		for character in characters:
			endpoint = "characters/{0}?access_token={1}".format(character, key)
			try:
				char = await self.call_api(endpoint)
			except APIError as e:
				await self.bot.say("{0.mention}, API has responded with the following error: "
								   "`{1}`".format(user, e))
				return
			bags = [bag for bag in char["bags"] if bag != None]
			for bag in bags:
				inv = [item["count"] for item in bag["inventory"] if item != None and item["id"] == 77302]
				li += sum(inv)
		await self.bot.edit_message(msg, "{0.mention}, you have {1} legendary insights".format(user, li))

	@commands.group(pass_context=True)
	async def character(self, ctx):
		"""Character related commands
		Requires key with characters scope
		"""
		if ctx.invoked_subcommand is None:
			await send_cmd_help(ctx)

	@character.command(name="info", pass_context=True)
	async def _info(self, ctx, *, character: str):
		"""Info about the given character
		You must be the owner of given character.
		Requires a key with characters scope
		"""
		scopes = ["characters"]
		user = ctx.message.author
		character = character.title()
		character.replace(" ", "%20")
		try:
			self._check_scopes_(user, scopes)
			key = self.keylist[user.id]["key"]
			endpoint = "characters/{0}?access_token={1}".format(character, key)
			results = await self.call_api(endpoint)
		except APIKeyError as e:
			await self.bot.say(e)
			return
		except APIError as e:
			await self.bot.say("{0.mention}, API has responded with the following error: "
							   "`{1}`".format(user, e))
			return
		accountname = self.keylist[user.id]["account_name"]
		age = self.get_age(results["age"])
		created = results["created"].split("T", 1)[0]
		deaths = results["deaths"]
		deathsperhour = round(deaths / (results["age"] / 3600), 1)
		if "title" in results:
			title = await self._get_title_(results["title"], ctx)
		else:
			title = None
		gender = results["gender"]
		profession = results["profession"]
		race = results["race"]
		guild = results["guild"]
		color = self.gamedata["professions"][profession.lower()]["color"]
		color = int(color, 0)
		icon = self.gamedata["professions"][profession.lower()]["icon"]
		data = discord.Embed(description=title, colour=color)
		data.set_thumbnail(url=icon)
		data.add_field(name="Created at", value=created)
		data.add_field(name="Played for", value=age)
		if guild is not None:
			guild = await self._get_guild_(results["guild"])
			gname = guild["name"]
			gtag = guild["tag"]
			data.add_field(name="Guild", value="[{0}] {1}".format(gtag, gname))
		data.add_field(name="Deaths", value=deaths)
		data.add_field(name="Deaths per hour", value=str(deathsperhour))
		data.set_author(name=character)
		data.set_footer(text="A {0} {1} {2}".format(
			gender.lower(), race.lower(), profession.lower()))
		try:
			await self.bot.say(embed=data)
		except discord.HTTPException:
			await self.bot.say("Need permission to embed links")

	@character.command(name="list", pass_context=True)
	async def _list_(self, ctx):
		"""Lists all your characters
		Requires a key with characters scope
		"""
		user = ctx.message.author
		scopes = ["characters"]
		try:
			self._check_scopes_(user, scopes)
			key = self.keylist[user.id]["key"]
			endpoint = "characters/?access_token={0}".format(key)
			results = await self.call_api(endpoint)
		except APIKeyError as e:
			await self.bot.say(e)
			return
		except APIError as e:
			await self.bot.say("{0.mention}, API has responded with the following error: "
							   "`{1}`".format(user, e))
			return
		output = "{0.mention}, your characters: ```"
		for x in results:
			output += "\n" + x
		output += "```"
		await self.bot.say(output.format(user))

	@character.command(pass_context=True)
	async def gear(self, ctx, *, character: str):
		"""Displays the gear of given character
		You must be the owner of given character.
		Requires a key with characters scope
		"""
		user = ctx.message.author
		scopes = ["characters"]
		character = character.title()
		character.replace(" ", "%20")
		try:
			self._check_scopes_(user, scopes)
			key = self.keylist[user.id]["key"]
			endpoint = "characters/{0}?access_token={1}".format(character, key)
			results = await self.call_api(endpoint)
		except APIKeyError as e:
			await self.bot.say(e)
			return
		except APIError as e:
			await self.bot.say("{0.mention}, invalid character name".format(user))
			return
		eq = results["equipment"]
		gear = {}
		pieces = ["Helm", "Shoulders", "Coat", "Gloves", "Leggings", "Boots", "Ring1", "Ring2", "Amulet",
				  "Accessory1", "Accessory2", "Backpack", "WeaponA1", "WeaponA2", "WeaponB1", "WeaponB2"]
		for piece in pieces:
			gear[piece] = {"id": None, "upgrades": None, "infusions": None,
						   "statname": None}
		for item in eq:
			for piece in pieces:
				if item["slot"] == piece:
					gear[piece]["id"] = item["id"]
					if "upgrades" in item:
						gear[piece]["upgrades"] = item["upgrades"]
					if "infusions" in item:
						gear[piece]["infusions"] = item["infusions"]
					if "stats" in item:
						gear[piece]["statname"] = item["stats"]["id"]
					else:
						gear[piece]["statname"] = await self._getstats_(gear[piece]["id"])
		profession = results["profession"]
		level = results["level"]
		color = self.gamedata["professions"][profession.lower()]["color"]
		icon = self.gamedata["professions"][profession.lower()]["icon"]
		color = int(color, 0)
		data = discord.Embed(description="Gear", colour=color)
		for piece in pieces:
			if gear[piece]["id"] is not None:
				statname = await self._getstatname_(gear[piece]["statname"], ctx)
				itemname = await self._get_item_name_(gear[piece]["id"], ctx)
				if gear[piece]["upgrades"]:
					upgrade = await self._get_item_name_(gear[piece]["upgrades"], ctx)
				if gear[piece]["infusions"]:
					infusion = await self._get_item_name_(gear[piece]["infusions"], ctx)
				if gear[piece]["upgrades"] and not gear[piece]["infusions"]:
					msg = "{0} {1} with {2}".format(
						statname, itemname, upgrade)
				elif gear[piece]["upgrades"] and gear[piece]["infusions"]:
					msg = "{0} {1} with {2} and {3}".format(
						statname, itemname, upgrade, infusion)
				elif gear[piece]["infusions"] and not gear[piece]["upgrades"]:
					msg = "{0} {1} with {2}".format(
						statname, itemname, infusion)
				elif not gear[piece]["upgrades"] and not gear[piece]["infusions"]:
					msg = "{0} {1}".format(statname, itemname)
				data.add_field(name=piece, value=msg, inline=False)
		data.set_author(name=character)
		data.set_footer(text="A level {0} {1} ".format(
			level, profession.lower()), icon_url=icon)
		try:
			await self.bot.say(embed=data)
		except discord.HTTPException:
			await self.bot.say("Need permission to embed links")

	@commands.group(pass_context=True)
	async def wallet(self, ctx):
		"""Wallet related commands.
		Require a key with the scope wallet
		"""
		if ctx.invoked_subcommand is None:
			await send_cmd_help(ctx)

	@wallet.command(pass_context=True)
	async def currencies(self, ctx):
		"""Returns a list of all currencies"""
		user = ctx.message.author
		try:
			endpoint = "currencies?ids=all"
			results = await self.call_api(endpoint)
		except APIError as e:
			await self.bot.say("{0.mention}, API has responded with the following error: "
							   "`{1}`".format(user, e))
			return
		currlist = [currency["name"] for currency in results]
		output = "Available currencies are: ```"
		output += ", ".join(currlist) + "```"
		await self.bot.say(output)

	@wallet.command(pass_context=True)
	async def currency(self, ctx, *, currency: str):
		"""Info about a currency. See [p]wallet currencies for list"""
		user = ctx.message.author
		try:
			endpoint = "currencies?ids=all"
			results = await self.call_api(endpoint)
		except APIError as e:
			await self.bot.say("{0.mention}, API has responded with the following error: "
							   "`{1}`".format(user, e))
			return
		if currency.lower() == "gold":
			currency = "coin"
		cid = None
		for curr in results:
			if curr["name"].lower() == currency.lower():
				cid = curr["id"]
				desc = curr["description"]
				icon = curr["icon"]
		if not cid:
			await self.bot.say("Invalid currency. See `[p]wallet currencies`")
			return
		color = self.getColor(user)
		data = discord.Embed(description="Currency", colour=color)
		scopes = ["wallet"]
		try:
			self._check_scopes_(user, scopes)
			key = self.keylist[user.id]["key"]
			endpoint = "account/wallet?access_token={0}".format(key)
			wallet = await self.call_api(endpoint)
			for item in wallet:
				if item["id"] == 1 and cid == 1:
					count = self.gold_to_coins(item["value"])
				elif item["id"] == cid:
					count = item["value"]
			data.add_field(name="Count", value=count, inline=False)
		except:
			pass
		data.set_thumbnail(url=icon)
		data.add_field(name="Description", value=desc, inline=False)
		data.set_author(name=currency.title())
		try:
			await self.bot.say(embed=data)
		except discord.HTTPException:
			await self.bot.say("Need permission to embed links")

	@wallet.command(pass_context=True)
	async def show(self, ctx):
		"""Shows most important currencies in your wallet
		Requires key with scope wallet
		"""
		user = ctx.message.author
		scopes = ["wallet"]
		try:
			self._check_scopes_(user, scopes)
			key = self.keylist[user.id]["key"]
			endpoint = "account/wallet?access_token={0}".format(key)
			results = await self.call_api(endpoint)
		except APIKeyError as e:
			await self.bot.say(e)
			return
		except APIError as e:
			await self.bot.say("{0.mention}, API has responded with the following error: "
							   "`{1}`".format(user, e))
			return
		wallet = [{"count": 0, "id": 1, "name": "Gold"},
				  {"count": 0, "id": 4, "name": "Gems"},
				  {"count": 0, "id": 2, "name": "Karma"},
				  {"count": 0, "id": 3, "name": "Laurels"},
				  {"count": 0, "id": 18, "name": "Transmutation Charges"},
				  {"count": 0, "id": 23, "name": "Spirit Shards"},
				  {"count": 0, "id": 32, "name": "Unbound Magic"},
				  {"count": 0, "id": 15, "name": "Badges of Honor"},
				  {"count": 0, "id": 16, "name": "Guild Commendations"}]
		for x in wallet:
			for curr in results:
				if curr["id"] == x["id"]:
					x["count"] = curr["value"]
		accountname = self.keylist[user.id]["account_name"]
		color = self.getColor(user)
		data = discord.Embed(description="Wallet", colour=color)
		for x in wallet:
			if x["name"] == "Gold":
				x["count"] = self.gold_to_coins(x["count"])
				data.add_field(name=x["name"], value=x["count"], inline=False)
			elif x["name"] == "Gems":
				data.add_field(name=x["name"], value=x["count"], inline=False)
			else:
				data.add_field(name=x["name"], value=x["count"])
		data.set_author(name=accountname)
		try:
			await self.bot.say(embed=data)
		except discord.HTTPException:
			await self.bot.say("Need permission to embed links")

	@wallet.command(pass_context=True)
	async def tokens(self, ctx):
		"""Shows instance-specific currencies
		Requires key with scope wallet
		"""
		user = ctx.message.author
		scopes = ["wallet"]
		try:
			self._check_scopes_(user, scopes)
			key = self.keylist[user.id]["key"]
			endpoint = "account/wallet?access_token={0}".format(key)
			results = await self.call_api(endpoint)
		except APIKeyError as e:
			await self.bot.say(e)
			return
		except APIError as e:
			await self.bot.say("{0.mention}, API has responded with the following error: "
							   "`{1}`".format(user, e))
			return
		wallet = [{"count": 0, "id": 5, "name": "Ascalonian Tears"},
				  {"count": 0, "id": 6, "name": "Shards of Zhaitan"},
				  {"count": 0, "id": 9, "name": "Seals of Beetletun"},
				  {"count": 0, "id": 10, "name": "Manifestos of the Moletariate"},
				  {"count": 0, "id": 11, "name": "Deadly Blooms"},
				  {"count": 0, "id": 12, "name": "Symbols of Koda"},
				  {"count": 0, "id": 13, "name": "Flame Legion Charr Carvings"},
				  {"count": 0, "id": 14, "name": "Knowledge Crystals"},
				  {"count": 0, "id": 7, "name": "Fractal relics"},
				  {"count": 0, "id": 24, "name": "Pristine Fractal Relics"},
				  {"count": 0, "id": 28, "name": "Magnetite Shards"}]
		for x in wallet:
			for curr in results:
				if curr["id"] == x["id"]:
					x["count"] = curr["value"]
		accountname = self.keylist[user.id]["account_name"]
		color = self.getColor(user)
		data = discord.Embed(description="Tokens", colour=color)
		for x in wallet:
			if x["name"] == "Magnetite Shards":
				data.add_field(name=x["name"], value=x["count"], inline=False)
			else:
				data.add_field(name=x["name"], value=x["count"])
		data.set_author(name=accountname)
		try:
			await self.bot.say(embed=data)
		except discord.HTTPException:
			await self.bot.say("Need permission to embed links")

	@wallet.command(pass_context=True)
	async def maps(self, ctx):
		"""Shows map-specific currencies
		Requires key with scope wallet
		"""
		user = ctx.message.author
		scopes = ["wallet"]
		try:
			self._check_scopes_(user, scopes)
			key = self.keylist[user.id]["key"]
			endpoint = "account/wallet?access_token={0}".format(key)
			results = await self.call_api(endpoint)
		except APIKeyError as e:
			await self.bot.say(e)
			return
		except APIError as e:
			await self.bot.say("{0.mention}, API has responded with the following error: "
							   "`{1}`".format(user, e))
			return
		wallet = [{"count": 0, "id": 25, "name": "Geodes"},
				  {"count": 0, "id": 27, "name": "Bandit Crests"},
				  {"count": 0, "id": 19, "name": "Airship Parts"},
				  {"count": 0, "id": 22, "name": "Lumps of Aurillium"},
				  {"count": 0, "id": 20, "name": "Ley Line Crystals"},
				  {"count": 0, "id": 32, "name": "Unbound Magic"}]
		for x in wallet:
			for curr in results:
				if curr["id"] == x["id"]:
					x["count"] = curr["value"]
		accountname = self.keylist[user.id]["account_name"]
		color = self.getColor(user)
		data = discord.Embed(description="Tokens", colour=color)
		for x in wallet:
			data.add_field(name=x["name"], value=x["count"])
		data.set_author(name=accountname)
		try:
			await self.bot.say(embed=data)
		except discord.HTTPException:
			await self.bot.say("Need permission to embed links")

	@commands.group(pass_context=True)
	async def guild(self, ctx):
		"""Guild related commands.
		Require a key with the scope guild
		"""
		if ctx.invoked_subcommand is None:
			await send_cmd_help(ctx)

	@guild.command(pass_context=True, name="info")
	async def __info(self, ctx, *, guild: str):
		"""Information about general guild stats
		Enter guilds name
		Requires a key with guilds scope
		"""
		user = ctx.message.author
		color = self.getColor(user)
		guild = guild.replace(' ', '%20')
		scopes = ["guilds"]
		try:
			self._check_scopes_(user, scopes)
			key = self.keylist[user.id]["key"]
			endpoint_id = "guild/search?name={0}".format(guild)
			guild_id = await self.call_api(endpoint_id)
			guild_id = str(guild_id).strip("['")
			guild_id = str(guild_id).strip("']")
			endpoint = "guild/{1}?access_token={0}".format(key, guild_id)
			results = await self.call_api(endpoint)
		except APIKeyError as e:
			await self.bot.say(e)
			return
		except APIError as e:
			await self.bot.say("{0.mention}, API has responded with the following error: "
							   "`{1}`".format(user, e))
			return
		level = results["level"]
		name = results["name"]
		tag = results["tag"]
		member_cap = results["member_capacity"]
		motd = results["motd"]
		influence = results["influence"]
		aetherium = results["aetherium"]
		resonance = results["resonance"]
		favor = results["favor"]
		member_count = results["member_count"]
		data = discord.Embed(
			description='General Info about your guild', colour=color)
		data.set_author(name=name + " [" + tag + "]")
		data.add_field(name='Influence', value=influence, inline=True)
		data.add_field(name='Aetherium', value=aetherium, inline=True)
		data.add_field(name='Resonance', value=resonance, inline=True)
		data.add_field(name='Favor', value=favor, inline=True)
		data.add_field(name='Members', value=str(
			member_count) + "/" + str(member_cap), inline=True)
		data.add_field(name='Message of the day:', value=motd, inline=False)
		data.set_footer(text='A level {0} guild'.format(level))

		try:
			await self.bot.say(embed=data)
		except discord.HTTPException:
			await self.bot.say("Need permission to embed links")

	@guild.command(name="id", pass_context=True)
	async def _id(self, ctx, *, guild: str):
		"""Get ID of given guild's name
		Doesn't require any keys/scopes"""
		user = ctx.message.author
		guild = guild.replace(' ', '%20')
		try:
			endpoint = "guild/search?name={0}".format(guild)
			result = await self.call_api(endpoint)
		except APIKeyError as e:
			await self.bot.say(e)
			return
		except APIError as e:
			await self.bot.say("{0.mention}, API has responded with the following error: "
							   "`{1}`".format(user, e))
			return
		guild = guild.replace('%20', ' ')
		result = str(result).strip("['")
		result = str(result).strip("']")

		await self.bot.say('ID of the guild {0} is: {1}'.format(guild, result))

	@guild.command(pass_context=True)
	async def members(self, ctx, *, guild: str):
		"""Get list of all members and their ranks
		Requires key with guilds scope and also Guild Leader permissions ingame"""
		user = ctx.message.author
		color = self.getColor(user)
		guild = guild.replace(' ', '%20')
		scopes = ["guilds"]
		try:
			self._check_scopes_(user, scopes)
			key = self.keylist[user.id]["key"]
			endpoint_id = "guild/search?name={0}".format(guild)
			guild_id = await self.call_api(endpoint_id)
			guild_id = str(guild_id).strip("['")
			guild_id = str(guild_id).strip("']")
			endpoint = "guild/{1}/members?access_token={0}".format(
				key, guild_id)
			endpoint_ranks = "guild/{1}/ranks?access_token={0}".format(
				key, guild_id)
			ranks = await self.call_api(endpoint_ranks)
			results = await self.call_api(endpoint)
		except APIKeyError as e:
			await self.bot.say(e)
			return
		except APIError as e:
			await self.bot.say("{0.mention}, API has responded with the following error: "
							   "`{1}`".format(user, e))
			return

		guild = guild.replace('%20', ' ')
		data = discord.Embed(description='Members of {0}'.format(
			guild.title()), colour=color)
		data.set_author(name=guild.title())
		counter = 0
		order_id = 1
		# For each order the rank has, go through each member and add it with
		# the current order increment to the embed
		for order in ranks:
			for member in results:
				# Filter invited members
				if member['rank'] != "invited":
					member_rank = member['rank']
					# associate order from /ranks with rank from /members
					for rank in ranks:
						if member_rank == rank['id']:
							# await self.bot.say('DEBUG: ' + member['name'] + '
							# has rank ' + member_rank + ' and rank has order '
							# + str(rank['order']))
							if rank['order'] == order_id:
								if counter < 20:
									data.add_field(
										name=member['name'], value=member['rank'])
									counter += 1
			order_id += 1
		try:
			await self.bot.say(embed=data)
		except discord.HTTPException:
			await self.bot.say("Need permission to embed links")

	@guild.command(pass_context=True)
	async def treasury(self, ctx, *, guild: str):
		"""Get list of current and needed items for upgrades
				Requires key with guilds scope and also Guild Leader permissions ingame"""
		user = ctx.message.author
		color = self.getColor(user)
		guild = guild.replace(' ', '%20')
		language = self.getlanguage(ctx)

		scopes = ["guilds"]
		try:
			self._check_scopes_(user, scopes)
			key = self.keylist[user.id]["key"]
			endpoint_id = "guild/search?name={0}".format(guild)
			guild_id = await self.call_api(endpoint_id)
			guild_id = str(guild_id).strip("['")
			guild_id = str(guild_id).strip("']")
			endpoint = "guild/{1}/treasury?access_token={0}".format(
				key, guild_id)
			treasury = await self.call_api(endpoint)
		except APIKeyError as e:
			await self.bot.say(e)
			return
		except APIError as e:
			await self.bot.say("{0.mention}, API has responded with the following error: "
							   "`{1}`".format(user, e))
			return

		guild = guild.replace('%20', ' ')

		data = discord.Embed(description='Treasury contents of {0}'.format(
			guild.title()), colour=color)
		data.set_author(name=guild.title())

		counter = 0
		item_counter = 0
		amount = 0
		item_id = ""

		# Collect listed items
		for item in treasury:
			item_id += str(item["item_id"]) + ","

		endpoint_items = "items?ids={0}&lang={1}".format(str(item_id),language)

		# Call API once for all items
		try:
			itemlist = await self.call_api(endpoint_items)
		except APIError as e:
			await self.bot.say("{0.mention}, API has responded with the following error: "
							   "`{1}`".format(user, e))
			return

		# Collect amounts
		if treasury:
			for item in treasury:
				if counter < 20:
					current = item["count"]
					item_name = itemlist[item_counter]["name"]
					needed = item["needed_by"]

					for need in needed:
						amount = amount + need["count"]

					if amount != current:
						data.add_field(name=item_name, value=str(current)+"/"+str(amount), inline=True)
						counter += 1
					amount = 0
					item_counter += 1
		else:
			await self.bot.say("Treasury is empty!")

		try:
			await self.bot.say(embed=data)
		except discord.HTTPException:
			await self.bot.say("Need permission to embed links")

	@commands.group(pass_context=True)
	async def pvp(self, ctx):
		"""PvP related commands.
		Require a key with the scope pvp
		"""
		if ctx.invoked_subcommand is None:
			await send_cmd_help(ctx)

	@pvp.command(pass_context=True)
	async def stats(self, ctx):
		"""Information about your general pvp stats
		Requires a key with pvp scope
		"""
		user = ctx.message.author
		scopes = ["pvp"]
		try:
			self._check_scopes_(user, scopes)
			key = self.keylist[user.id]["key"]
			endpoint = "pvp/stats?access_token={0}".format(key)
			results = await self.call_api(endpoint)
		except APIKeyError as e:
			await self.bot.say(e)
			return
		except APIError as e:
			await self.bot.say("{0.mention}, API has responded with the following error: "
							   "`{1}`".format(user, e))
			return
		accountname = self.keylist[user.id]["account_name"]
		pvprank = results["pvp_rank"] + results["pvp_rank_rollovers"]
		totalgamesplayed = sum(results["aggregate"].values())
		totalwins = results["aggregate"]["wins"] + results["aggregate"]["byes"]
		if totalgamesplayed != 0:
			totalwinratio = int((totalwins / totalgamesplayed) * 100)
		else:
			totalwinratio = 0
		rankedgamesplayed = sum(results["ladders"]["ranked"].values())
		rankedwins = results["ladders"]["ranked"]["wins"] + \
			results["ladders"]["ranked"]["byes"]
		if rankedgamesplayed != 0:
			rankedwinratio = int((rankedwins / rankedgamesplayed) * 100)
		else:
			rankedwinratio = 0

		rank_id = results["pvp_rank"] // 10 + 1
		endpoint_ranks = "pvp/ranks/{0}".format(rank_id)
		try:
			rank = await self.call_api(endpoint_ranks)
		except APIError as e:
			await self.bot.say("{0.mention}, API has responded with the following error: "
							   "`{1}`".format(user, e))
			return
		rank_icon = rank["icon"]
		color = self.getColor(user)
		data = discord.Embed(description=None, colour=color)
		data.add_field(name="Rank", value=pvprank, inline=False)
		data.add_field(name="Total games played", value=totalgamesplayed)
		data.add_field(name="Total wins", value=totalwins)
		data.add_field(name="Total winratio",
					   value="{}%".format(totalwinratio))
		data.add_field(name="Ranked games played", value=rankedgamesplayed)
		data.add_field(name="Ranked wins", value=rankedwins)
		data.add_field(name="Ranked winratio",
					   value="{}%".format(rankedwinratio))
		data.set_author(name=accountname)
		data.set_thumbnail(url=rank_icon)
		try:
			await self.bot.say(embed=data)
		except discord.HTTPException:
			await self.bot.say("Need permission to embed links")

	@pvp.command(pass_context=True)
	async def professions(self, ctx, *, profession: str=None):
		"""Information about your pvp profession stats.
		If no profession is given, defaults to general profession stats.
		Example: !pvp professions elementalist
		"""
		user = ctx.message.author
		professionsformat = {}
		scopes = ["pvp"]
		try:
			self._check_scopes_(user, scopes)
			key = self.keylist[user.id]["key"]
			endpoint = "pvp/stats?access_token={0}".format(key)
			results = await self.call_api(endpoint)
		except APIKeyError as e:
			await self.bot.say(e)
			return
		except APIError as e:
			await self.bot.say("{0.mention}, API has responded with the following error: "
							   "`{1}`".format(user, e))
			return
		accountname = self.keylist[user.id]["account_name"]
		professions = self.gamedata["professions"].keys()
		if not profession:
			for profession in professions:
				if profession in results["professions"]:
					wins = results["professions"][profession]["wins"] + \
						results["professions"][profession]["byes"]
					total = sum(results["professions"][profession].values())
					winratio = int((wins / total) * 100)
					professionsformat[profession] = {
						"wins": wins, "total": total, "winratio": winratio}
			mostplayed = max(professionsformat,
							 key=lambda i: professionsformat[i]['total'])
			icon = self.gamedata["professions"][mostplayed]["icon"]
			mostplayedgames = professionsformat[mostplayed]["total"]
			highestwinrate = max(
				professionsformat, key=lambda i: professionsformat[i]["winratio"])
			highestwinrategames = professionsformat[highestwinrate]["winratio"]
			leastplayed = min(professionsformat,
							  key=lambda i: professionsformat[i]["total"])
			leastplayedgames = professionsformat[leastplayed]["total"]
			lowestestwinrate = min(
				professionsformat, key=lambda i: professionsformat[i]["winratio"])
			lowestwinrategames = professionsformat[lowestestwinrate]["winratio"]
			color = self.getColor(user)
			data = discord.Embed(description="Professions", colour=color)
			data.set_thumbnail(url=icon)
			data.add_field(name="Most played profession", value="{0}, with {1}".format(
				mostplayed.capitalize(), mostplayedgames))
			data.add_field(name="Highest winrate profession", value="{0}, with {1}%".format(
				highestwinrate.capitalize(), highestwinrategames))
			data.add_field(name="Least played profession", value="{0}, with {1}".format(
				leastplayed.capitalize(), leastplayedgames))
			data.add_field(name="Lowest winrate profession", value="{0}, with {1}%".format(
				lowestestwinrate.capitalize(), lowestwinrategames))
			data.set_author(name=accountname)
			try:
				await self.bot.say(embed=data)
			except discord.HTTPException:
				await self.bot.say("Need permission to embed links")
		elif profession.lower() not in self.gamedata["professions"]:
			await self.bot.say("Invalid profession")
		elif profession.lower() not in results["professions"]:
			await self.bot.say("You haven't played that profession!")
		else:
			prof = profession.lower()
			wins = results["professions"][prof]["wins"] + \
				results["professions"][prof]["byes"]
			total = sum(results["professions"][prof].values())
			winratio = int((wins / total) * 100)
			color = self.gamedata["professions"][prof]["color"]
			color = int(color, 0)
			data = discord.Embed(
				description="Stats for {0}".format(prof), colour=color)
			data.set_thumbnail(url=self.gamedata["professions"][prof]["icon"])
			data.add_field(name="Total games played",
						   value="{0}".format(total))
			data.add_field(name="Wins", value="{0}".format(wins))
			data.add_field(name="Winratio",
						   value="{0}%".format(winratio))
			data.set_author(name=accountname)
			try:
				await self.bot.say(embed=data)
			except discord.HTTPException:
				await self.bot.say("Need permission to embed links")

	@commands.command(pass_context=True)
	async def bosses(self, ctx):
		"""Lists all the bosses you killed this week
		Requires a key with progression scope
		"""
		user = ctx.message.author
		scopes = ["progression"]
		try:
			self._check_scopes_(user, scopes)
			key = self.keylist[user.id]["key"]
			endpoint = "account/raids/?access_token={0}".format(key)
			results = await self.call_api(endpoint)
		except APIKeyError as e:
			await self.bot.say(e)
			return
		except APIError as e:
			await self.bot.say("{0.mention}, API has responded with the following error: "
							   "`{1}`".format(user, e))
			return
		else:
			newbosslist = list(
				set(list(self.gamedata["bosses"])) ^ set(results))
			if not newbosslist:
				await self.bot.say("Congratulations {0.mention}, "
								   "you've cleared everything. Here's a gold star: "
								   ":star:".format(user))
			else:
				formattedlist = []
				output = "{0.mention}, you haven't killed the following bosses this week: ```"
				newbosslist.sort(
					key=lambda val: self.gamedata["bosses"][val]["order"])
				for boss in newbosslist:
					formattedlist.append(self.gamedata["bosses"][boss]["name"])
				for x in formattedlist:
					output += "\n" + x
				output += "```"
				await self.bot.say(output.format(user))

	@commands.group(pass_context=True)
	async def wvw(self, ctx):
		"""Commands related to wvw"""
		if ctx.invoked_subcommand is None:
			await send_cmd_help(ctx)

	@wvw.command(pass_context=True)
	async def worlds(self, ctx):
		"""List all worlds
		"""
		user = ctx.message.author
		try:
			endpoint = "worlds?ids=all"
			results = await self.call_api(endpoint)
		except APIError as e:
			await self.bot.say("{0.mention}, API has responded with the following error: "
							   "`{1}`".format(user, e))
			return
		output = "Available worlds are: ```"
		for world in results:
			output += world["name"] + ", "
		output += "```"
		await self.bot.say(output)

	@wvw.command(pass_context=True, name="info")
	async def worldinfo(self, ctx, *, world: str=None):
		"""Info about a world. If none is provided, defaults to account's world
		"""
		user = ctx.message.author
		if not world and user.id in self.keylist:
			try:
				key = self.keylist[user.id]["key"]
				endpoint = "account/?access_token={0}".format(key)
				results = await self.call_api(endpoint)
				wid = results["world"]
			except APIError as e:
				await self.bot.say("{0.mention}, API has responded with the following error: "
								   "`{1}`".format(user, e))
				return
		else:
			wid = await self.getworldid(world)
		if not wid:
			await self.bot.say("Invalid world name")
			return
		try:
			endpoint = "wvw/matches?world={0}".format(wid)
			results = await self.call_api(endpoint)
			endpoint_ = "worlds?id={0}".format(wid)
			worldinfo = await self.call_api(endpoint_)
			worldname = worldinfo["name"]
			population = worldinfo["population"]
		except APIError as e:
			await self.bot.say("{0.mention}, API has responded with the following error: "
							   "`{1}`".format(user, e))
			return
		worldcolor = ""
		for key, value in results["all_worlds"].items():
			if wid in value:
				worldcolor = key
		if not worldcolor:
			await self.bot.say("Could not resolve world's color")
			return
		if worldcolor == "red":
			color = discord.Colour.red()
		elif worldcolor == "green":
			color = discord.Colour.green()
		else:
			color = discord.Colour.blue()
		score = results["scores"][worldcolor]
		ppt = 0
		victoryp = results["victory_points"][worldcolor]
		for m in results["maps"]:
			for objective in m["objectives"]:
				if objective["owner"].lower() == worldcolor:
					ppt += objective["points_tick"]
		if population == "VeryHigh":
			population = "Very high"
		kills = results["kills"][worldcolor]
		deaths = results["deaths"][worldcolor]
		kd = round((kills / deaths), 2)
		data = discord.Embed(description="Performance", colour=color)
		data.add_field(name="Score", value=score)
		data.add_field(name="Points per tick", value=ppt)
		data.add_field(name="Victory Points", value=victoryp)
		data.add_field(name="K/D ratio", value=str(kd), inline=False)
		data.add_field(name="Population", value=population, inline=False)
		data.set_author(name=worldname)
		try:
			await self.bot.say(embed=data)
		except discord.HTTPException:
			await self.bot.say("Need permission to embed links")

	@checks.mod_or_permissions(manage_webhooks=True)
	@commands.command(pass_context=True)
	async def search(self, ctx, *, item):
		"""Find items on your account!"""
		user = ctx.message.author
		scopes = ["inventories", "characters"]
		key = self.keylist[user.id]["key"]
		try:
			self._check_scopes_(user, scopes)
			headers = self.construct_headers(key)
			endpoint_bank = "account/bank"
			endpoint_shared = "account/inventory"
			endpoint_char = "characters?page=0"
			endpoint_material = "account/materials"
			bank = await self.call_api(endpoint_bank, headers)
			shared = await self.call_api(endpoint_shared, headers)
			material = await self.call_api(endpoint_material, headers)
			characters = await self.call_api(endpoint_char, headers)
			await self.bot.say("Debugging - Initial API Call OK")
		except APIKeyError as e:
			await self.bot.say(e)
			return
		except APIError as e:
			await self.bot.say("{0.mention}, API has responded with the following error: "
							   "`{1}`".format(user, e))
			return
		shiniesendpoint = item.replace(" ", "%20")
		shiniesresults = await self.call_shiniesapi(shiniesendpoint)
		number = len(shiniesresults)
		if not number:
			await self.bot.say("Your search gave me no results, sorry. Check for typos.")
			return
		if number > 20:
			await self.bot.say("Your search gave me {0} item results. Please be more specific".format(number))
			return
		items = []
		msg = "Which one of these interests you? Type it's number```"
		for name in shiniesresults:
			items.append(name)
		if number != 1:
			for c, m in enumerate(items):
				msg += "\n{}: {}".format(c, m["name"])
			msg += "```"
			message = await self.bot.say(msg)
			answer = await self.bot.wait_for_message(timeout=120, author=user)
			try:
				num = int(answer.content)
				choice = items[num]
				choiceid = shiniesresults[num]["item_id"]
			except:
				await self.bot.edit_message(message, "That's not a number in the list")
				return
			try:
				await self.bot.delete_message(answer)
			except:
				pass
		else:
			message = await self.bot.say("Searching far and wide...")
			choice = items[0]
			choiceid = shiniesresults[0]["item_id"]
		output = ""
		await self.bot.edit_message(message, "Searching far and wide...")
		results = {"bank" : 0, "shared" : 0, "material" : 0, "characters" : {}}
		bankresults = [item["count"] for item in bank if item != None and item["id"] == choiceid]
		results["bank"] = sum(bankresults)
		sharedresults = [item["count"] for item in shared if item != None and item["id"] == choiceid]
		results["shared"] = sum(sharedresults)
		materialresults = [item["count"] for item in material if item != None and item["id"] == choiceid]
		results["material"] = sum(materialresults)
		for character in characters:
			results["characters"][character["name"]] = 0
			bags = [bag for bag in character["bags"] if bag != None]
			for bag in bags:
				inv = [item["count"] for item in bag["inventory"] if item != None and item["id"] == choiceid]
				results["characters"][character["name"]] += sum(inv)
		if results["bank"]:
			output += "BANK: Found {0}\n".format(results["bank"])
		if results["material"]:
			output += "MATERIAL STORAGE: Found {0}\n".format(results["material"])
		if results["shared"]:
			output += "SHARED: Found {0}\n".format(results["shared"])
		if results["characters"]:
			for char, value in results["characters"].items():
				if value:
					output += "{0}: Found {1}\n".format(char.upper(), value)
		if not output:
			await self.bot.edit_message(message, "Sorry, nothing found")
		else:
			await self.bot.edit_message(message, "```" + output + "```")

	@commands.command(pass_context=True)
	async def gw2wiki(self, ctx, *search):
		"""Search the guild wars 2 wiki
		Returns the first result, will not always be accurate.
		"""
		if not soupAvailable:
			await self.bot.say("BeautifulSoup needs to be installed "
							   "for this command to work.")
			return
		search = "+".join(search)
		wiki = "http://wiki.guildwars2.com/"
		search = search.replace(" ", "+")
		user = ctx.message.author
		url = wiki + \
			"index.php?title=Special%3ASearch&profile=default&fulltext=Search&search={0}".format(
				search)
		async with self.session.get(url) as r:
			results = await r.text()
			soup = BeautifulSoup(results, 'html.parser')
		try:
			div = soup.find("div", {"class": "mw-search-result-heading"})
			a = div.find('a')
			link = a['href']
			await self.bot.say("{0.mention}: {1}{2}".format(user, wiki, link))
		except:
			await self.bot.say("{0.mention}, no results found".format(user))

	@commands.command(pass_context=True)
	async def daily(self, ctx, pve_pvp_wvw_fractals):
		"""Returns current GW2 dailies for pve, pvp, wvw or fractals"""
		valid_dailies = ["pvp", "wvw", "pve", "fractals"]
		user = ctx.message.author
		search = pve_pvp_wvw_fractals.lower()
		try:
			endpoint = "achievements/daily"
			results = await self.call_api(endpoint)
		except APIError as e:
			await self.bot.say("{0.mention}, API has responded with the following error: "
							   "`{1}`".format(user, e))
			return
		search = pve_pvp_wvw_fractals.lower()
		if search in valid_dailies:
			data = results[search]
		else:
			await self.bot.say("Invalid type of daily")
			return
		dailies = []
		for x in data:
			if x["level"]["max"] == 80:
				dailies.append(str(x["id"]))
		dailies = ",".join(dailies)
		try:
			endpoint = "achievements?ids={0}".format(dailies)
			results = await self.call_api(endpoint)
		except APIError as e:
			await self.bot.say("{0.mention}, API has responded with the following error: "
							   "`{1}`".format(user, e))
			return
		output = "{0} dailes for today are: ```".format(search.capitalize())
		for x in results:
			output += "\n" + x["name"]
		output += "```"
		await self.bot.say(output)

	@commands.group(pass_context=True, no_pm=True)
	@checks.admin_or_permissions(manage_server=True)
	async def gamebuild(self, ctx):
		"""Commands related to setting up a new game build notifier"""
		server = ctx.message.server
		if server.id not in self.settings:
			self.settings[server.id] = {"ON": False, "CHANNEL": None}
			self.settings[server.id]["CHANNEL"] = server.default_channel.id
			dataIO.save_json('data/guildwars2/settings.json', self.settings)
		if ctx.invoked_subcommand is None:
			await send_cmd_help(ctx)

	@gamebuild.command(pass_context=True)
	async def channel(self, ctx, channel: discord.Channel=None):
		"""Sets the channel to send the update announcement
		If channel isn't specified, the server's default channel will be used"""
		server = ctx.message.server
		if channel is None:
			channel = ctx.message.server.default_channel
		if not server.get_member(self.bot.user.id
								 ).permissions_in(channel).send_messages:
			await self.bot.say("I do not have permissions to send "
							   "messages to {0.mention}".format(channel))
			return
		self.settings[server.id]["CHANNEL"] = channel.id
		dataIO.save_json('data/guildwars2/settings.json', self.settings)
		channel = self.get_announcement_channel(server)
		await self.bot.send_message(channel, "I will now send build announcement "
									"messages to {0.mention}".format(channel))

	@checks.mod_or_permissions(administrator=True)
	@gamebuild.command(pass_context=True)
	async def toggle(self, ctx, on_off: bool = None):
		"""Toggles checking for new builds"""
		server = ctx.message.server
		if on_off is not None:
			self.settings[server.id]["ON"] = on_off
		if self.settings[server.id]["ON"]:
			await self.bot.say("I will notify you on this server about new builds")
			if not self.settings["ENABLED"]:
				await self.bot.say("Build checking is globally disabled though. "
								   "Owner has to enable it using `[p]gamebuild globaltoggle on`")
		else:
			await self.bot.say("I will not send "
							   "notifications about new builds")
		dataIO.save_json('data/guildwars2/settings.json', self.settings)

	@checks.is_owner()
	@gamebuild.command()
	async def globaltoggle(self, on_off: bool = None):
		"""Toggles checking for new builds, globally.
		Note that in order to receive notifications you to
		set up notification channel and enable it per server using
		[p]gamebuild toggle
		Off by default.
		"""
		if on_off is not None:
			self.settings["ENABLED"] = on_off
		if self.settings["ENABLED"]:
			await self.update_build()
			await self.bot.say("Build checking is enabled. "
							   "You still need to enable it per server.")
		else:
			await self.bot.say("Build checking is globally disabled")
		dataIO.save_json('data/guildwars2/settings.json', self.settings)

	@commands.group(pass_context=True)
	async def tp(self, ctx):
		"""Commands related to tradingpost
		Requires no additional scopes"""
		if ctx.invoked_subcommand is None:
			await send_cmd_help(ctx)

	@tp.command(pass_context=True)
	async def current(self, ctx, buys_sells):
		"""Show current selling/buying transactions
		invoke with sells or buys"""
		user = ctx.message.author
		color = self.getColor(user)
		state = buys_sells.lower()
		scopes = ["tradingpost"]
		if state == "buys" or state == "sells":
			try:
				self._check_scopes_(user, scopes)
				key = self.keylist[user.id]["key"]
				accountname = self.keylist[user.id]["account_name"]
				endpoint = "commerce/transactions/current/{1}?access_token={0}".format(key, state)
				results = await self.call_api(endpoint)
			except APIKeyError as e:
				await self.bot.say(e)
				return
			except APIError as e:
				await self.bot.say("{0.mention}, API has responded with the following error: "
								   "`{1}`".format(user, e))
				return
		else:
			await self.bot.say("{0.mention}, Please us either 'sells' or 'buys' as parameter".format(user))
			return

		data = discord.Embed(description='Current ' + state, colour=color)
		data.set_author(name='Transaction overview of {0}'.format(accountname))
		data.set_thumbnail(
			url="https://wiki.guildwars2.com/images/thumb/d/df/Black-Lion-Logo.png/300px-Black-Lion-Logo.png")
		data.set_footer(text="Black Lion Trading Company")

		results = results[:20] # Only display 20 most recent transactions
		item_id = ""
		dup_item = {}
		# Collect listed items
		for result in results:
			item_id += str(result["item_id"]) + ","
			if result["item_id"] not in dup_item:
				dup_item[result["item_id"]] = len(dup_item)
		# Get information about all items, doesn't matter if string ends with ,
		endpoint_items = "items?ids={0}".format(str(item_id))
		endpoint_listing = "commerce/listings?ids={0}".format(str(item_id))
		# Call API once for all items
		try:
			itemlist = await self.call_api(endpoint_items)
			listings = await self.call_api(endpoint_listing)
		except APIError as e:
			await self.bot.say("{0.mention}, API has responded with the following error: "
							   "`{1}`".format(user, e))
			return
		for result in results:
			# Store data about transaction
			index = dup_item[result["item_id"]]
			quantity = result["quantity"]
			price = result["price"]
			item_name = itemlist[index]["name"]
			offers = listings[index][state]
			max_price = offers[0]["unit_price"]
			data.add_field(name=item_name, value=str(quantity) + " x " + self.gold_to_coins(price)
				+ " | Max. offer: " + self.gold_to_coins(max_price), inline=False)
		try:
			await self.bot.say(embed=data)
		except discord.HTTPException:
			await self.bot.say("Need permission to embed links")


	def save_gemtrack(self):
		dataIO.save_json("data/guildwars2/gemtrack.json", self.gemtrack)
	
	async def getGemPrice(self, numberOfGems : int = 400):
		try:
			endpoint = "commerce/exchange/coins?quantity=10000000"
			gemsresult = await self.call_api(endpoint)
		except APIKeyError as e:
			await self.bot.say(e)
			return 0
		
		gemCost = gemsresult['coins_per_gem']*numberOfGems
		return gemCost
  
	@commands.group(pass_context=True)
	async def gem(self, ctx):
		"""Gem - Gold transfer related commands"""
		if ctx.invoked_subcommand is None:
			await send_cmd_help(ctx)
	  
	@gem.command(pass_context=True)
	async def track(self, ctx, gold : int):
		"""This requests to be notified when the cost of 400 gems drops below a specified price (in gold - ex: trackgems 120)"""
		user = ctx.message.author
		color = self.getColor(user)
		price = gold * 10000
		
		self.gemtrack[user.id] = { "user_id": user.id, "price": price }
		self.save_gemtrack()
		
		await self.bot.say("{0.mention}, you'll be notified when the price of 400 gems drops below {1}".format(user, self.gold_to_coins(price)))

	# tracks gemprices and notifies people
	async def _gemprice_tracker(self):
		while self is self.bot.get_cog("Guildwars2"):
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

	@tp.command(pass_context=True)
	async def data(self, ctx, *, tpitemname: str):
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
			data = discord.Embed(description='I was unable to match that to an item on the TP , listing all - use !tp id (id) to select one', colour=color)
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

	@tp.command(pass_context=True)
	async def id(self, ctx, *, tpdataid: str):
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

	@tp.command(pass_context=True)
	async def list(self, ctx, *, tpitemname: str):
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
		except APIKeyError as e:
			await self.bot.say(e)
			return
		except APIError as e:
			await self.bot.say("{0.mention}, API has responded with the following error: "
								"`{1}`".format(user, e))
			return

		data = discord.Embed(title='SAB Character Info', colour =color)
		for elem in results["unlocks"]:
			data.add_field(name=elem["name"].replace('_', ' ').title(), value="Unlocked")
		for elem in results["songs"]:
			data.add_field(name=elem["name"].replace('_', ' ').title(), value="Unlocked")
		try:
			await self.bot.say(embed=data)
		except discord.HTTPException:
			await self.bot.say("Need permission to embed links")

	@commands.command(pass_context=True)
	async def cats(self, ctx):
		"""This displays unlocked home instance cats for your account
		Requires an API key with characters and progression"""
		user = ctx.message.author
		scopes = ["progression"]
		color = self.getColor(user)
		try:
			self._check_scopes_(user, scopes)
			key = self.keylist[user.id]["key"]
			endpoint = "account/home/cats/?access_token={0}".format(key)
			results = await self.call_api(endpoint)
		except APIKeyError as e:
			await self.bot.say(e)
			return
		except APIError as e:
			await self.bot.say("{0.mention}, API has responded with the following error: "
								"`{1}`".format(user, e))
			return
		else:
			listofcats = []
			for cat in results:
				id = cat["id"]
				hint = cat["hint"]
				listofcats.append(hint)			
			catslist = list(
				set(list(self.gamedata["cats"])) ^ set(listofcats))
			if not catslist:
				await self.bot.say("Congratulations {0.mention}, "
									"you've collected all the cats. Here's a gold star: "
									":star:".format(user))
			else:
				formattedlist = []
				output = "{0.mention}, you haven't collected the following cats yet: ```"
				catslist.sort(
					key=lambda val: self.gamedata["cats"][val]["order"])
				for cat in catslist:
					formattedlist.append(self.gamedata["cats"][cat]["name"])
				for x in formattedlist:
					output += "\n" + x
				output += "```"
				await self.bot.say(output.format(user))

	@commands.group(pass_context=True)
	async def container(self, ctx):
		"""Command used to find out what's the most expensive item inside a container"""
		if ctx.invoked_subcommand is None:
			await send_cmd_help(ctx)
			return
	
	@container.command(hidden=True, pass_context=True, name="add")
	@checks.mod_or_permissions(manage_webhooks=True)
	async def containeradd(self, ctx, *, input_data: str):
		"""Add a container data. Format is !container add name;data (data in JSON format)"""
		try:
			name, data = input_data.split(';',1)
		except IndexError:
			await self.bot.say("Plz format as !container add name;data (data in JSON format)")
			return
		try:
			self.containers[name] = json.loads(data)
		except ValueError:
			await self.bot.say("Error in reading the JSON format")
			return
		self.save_containers()
		await self.bot.say("Data added")
	
	@container.command(hidden=True, pass_context=True, name="del")
	@checks.mod_or_permissions(manage_webhooks=True)
	async def containerdelete(self, ctx, *, input_data: str):
		"""Remove a container data. Format is !container del name"""
		try:
			del self.containers[input_data]
		except KeyError:
			await self.bot.say("Couldn't find the required container")
			return
		self.save_containers()
		await self.bot.say("Data removed")
	
	@container.command(hidden=True, pass_context=True, name="list")
	@checks.mod_or_permissions(manage_webhooks=True)
	async def containerlist(self, ctx, *, input_data: str=""):
		"""List container data.
		List either all container names (without argument) or a specific container (with the name as argument)"""
		if input_data == "":
			await self.bot.say(', '.join(self.containers.keys()))
			return
		else:
			try:
				await self.bot.say(json.dumps(self.containers[input_data]))
			except KeyError:
				await self.bot.say("Couldn't find the required container")
				return
	
	@container.command(pass_context=True, name="check")
	async def containercheck(self, ctx, *, input_name: str):
		"""Gets the prices of a container's contents and give the most expensive ones.
		container check [Container name] (copy-paste from in-game chat), also works without []"""
		Aikan_ID = 180491225839697920
		user = ctx.message.author
		color = self.getColor(user)
		# Remove the [] around the copied name
		clean_name = input_name.strip('[]')
		# Make sure it's a single item 
		if clean_name[0] in [str(i) for i in range(10)]:
			await self.bot.say("Please copy the name of a single box. You don't want me to handle plurals, do you?")
			return
		try:
			# Hope the container is in the database
			l_contents = self.containers[clean_name]
		except KeyError:
			# Report and ban
			await self.bot.say("Couldn't find said item in the container database."
					   + " Your bullying has been reported to Aikan, who will take appropriate measures")
			Aikan = await self.bot.get_user_info(Aikan_ID)
			await self.bot.send_message(Aikan, "Issue with container " + input_name)
			return 
		# Add prices to l_contents, result is l_tot
		# The items will look like {'sell_price': -, 'buy_price': -, u'name': -, u'id': -}
		base_URL = "commerce/prices?ids="
		comma_IDs = ','.join([elem["id"] for elem in l_contents])
		endpoint = base_URL + comma_IDs
		data_prices = await self.call_api(endpoint)
		l_prices = {str(elem["id"]): elem for elem in data_prices}
		l_tot = []
		for elem in l_contents:
			try:
				p = l_prices[elem["id"]]
				d = dict.copy(elem)
				d["sell_price"] = p["sells"]["unit_price"]
				d["buy_price"] = p["buys"]["unit_price"]
				l_tot.append(d)
			except KeyError:
				# Happens if the content is account bound
				pass
		# Sort l_tot in various ways to get best items 
		data = discord.Embed(title='Most expensive items')
		best_item = sorted(l_tot, key=lambda elem:elem["sell_price"])[-1]
		data.add_field(name="Best sell price", 
				value="{0} at {1}".format(best_item["name"], self.gold_to_coins(best_item["sell_price"])),
				  inline=False)
		best_item =  sorted(l_tot, key=lambda elem:elem["buy_price"])[-1]
		data.add_field(name="Best buy price", 
				value="{0} at {1}".format(best_item["name"], self.gold_to_coins(best_item["buy_price"])),
				  inline=False)
		try:
			await self.bot.say(embed=data)
		except discord.HTTPException:
			await self.bot.say("Issue embedding data into discord - EC5")	

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
	async def UBM(self, ctx, MC_price_str : str = "0"):
		"""This displays which way of converting unbound magic to gold is the most profitable.
		It takes as an optional argument the value the user gives to mystic coins (in copper), defaults to 0"""
		user = ctx.message.author
		color = self.getColor(user)
		# The result will be the coin return per that amount of UBM
		UBM_UNIT = 1000
		# Mystic coin data. Required because they're not sellable on TP
		MC_ID = "19675"
		MC_price = self.coins_to_gold(MC_price_str)
		# Container prices
		packet_price_coin = 5000
		packet_price_magic = 250
		bundle_price_coin_1 = 10000
		bundle_price_magic_1 = 500
		bundle_price_coin_2 = 4000
		bundle_price_magic_2 = 1250
		# Data agglomerated from various sources. "Item_ID": "number of such items obtained" 
		# in ["samples"]["container"] tries
		d_data = {
			"bundle": {
				"70957": 33, "72315": 28, "24330": 88, "24277": 700,
				"24335": 126, "75654": 16, "24315": 96, "24310": 96,
				"24358": 810, "24351": 490, "24357": 780, "24370": 24,
				"76491": 31, "37897": 810, "68942": 102, "19721": 310,
				"24320": 204, "70842": 84, "24325": 110, "24300": 630,
				"74988": 16, "24305": 106, "72504": 23, "68063": 64,
				"19675": 58, "24289": 760, "76179": 19, "24283": 730,
				"24295": 780, "48884": 950},
			"packet": {
				"19719": 330, "19718": 260, "19739": 590, "19731": 620,
				"19730": 1010, "19732": 465, "19697": 290, "19698": 250,
				"19699": 1300, "19748": 240, "19700": 670, "19701": 155,
				"19702": 670, "19703": 250, "19741": 1090, "19743": 870,
				"19745": 95, "46736": 43, "46739": 47, "46738": 42,
				"19728": 810, "19729": 580, "19726": 860, "19727": 920,
				"19724": 890, "19725": 285, "19722": 640, "19723": 300,
				"46741": 44},
			"samples": {"packet": 1720, "bundle": 1595}}
		# Build the price list
		URL = "commerce/prices?ids="
		l_IDs = list(d_data["packet"].keys()) + list(d_data["bundle"].keys())
		# For now, the API doesn't take non-sellable IDs into account when using ?ids=
		# It's still safer to explicitely remove that ID
		l_IDs.remove("19675")
		endpoint = URL + ','.join(l_IDs)
		prices_data = await self.call_api(endpoint)
		d_prices = {str(elem["id"]): int(0.85 * elem["sells"]["unit_price"])
					for elem in prices_data}
		d_prices[MC_ID] = MC_price
		# Get raw content of containers
		numerator = sum([d_prices[elem] * d_data["packet"][elem]
						 for elem in  d_data["packet"].keys()])
		packet_content = int(numerator/float(d_data["samples"]["packet"]))

		numerator = sum([d_prices[elem] * d_data["bundle"][elem]
						 for elem in  d_data["bundle"].keys()])
		bundle_content = int(numerator/float(d_data["samples"]["bundle"]))
		# Compute net returns
		return_per_packet = (packet_content - packet_price_coin)
		return_per_bunch_p = int(return_per_packet * float(UBM_UNIT) / packet_price_magic)
		return_per_bundle_1 = (bundle_content - bundle_price_coin_1)
		return_per_bunch_b_1 = int(return_per_bundle_1 * float(UBM_UNIT) / bundle_price_magic_1)
		return_per_bundle_2 = (bundle_content - bundle_price_coin_2)
		return_per_bunch_b_2 = int(return_per_bundle_2 * float(UBM_UNIT) / bundle_price_magic_2)
		# Display said returns
		r1 = "{1} per {0} unbound magic".format(UBM_UNIT, self.gold_to_coins(return_per_bunch_p))
		r2 = "{1} per {0} unbound magic".format(UBM_UNIT, self.gold_to_coins(return_per_bunch_b_1))
		r3 = "{1} per {0} unbound magic".format(UBM_UNIT, self.gold_to_coins(return_per_bunch_b_2))
		data = discord.Embed(title="Unbound magic conversion returns using Magic-Warped...")
		data.add_field(name="Packets", value=r1, inline=False)
		data.add_field(name="Bundles", value=r2, inline=False)
		data.add_field(name="Bundles (Ember Bay)", value=r3, inline=False)
		try:
			await self.bot.say(embed=data)
		except discord.HTTPException:
			await self.bot.say("Issue embedding data into discord - EC5")		

	@gem.command(pass_context=True)
	async def price(self, ctx, numberOfGems : int = 400):
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

	async def call_api(self, endpoint, headers=DEFAULT_HEADERS):
		apiserv = 'https://api.guildwars2.com/v2/'
		url = apiserv + endpoint
		async with self.session.get(url, headers=headers) as r:
			results = await r.json()
		if "error" in results:
			raise APIError("The API is dead! Endpoint: {0}".format(endpoint))
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

	async def _gamebuild_checker(self):
		while self is self.bot.get_cog("Guildwars2"):
			if self.settings["ENABLED"]:
				if await self.update_build():
					channels = self.get_channels()
					if channels:
						for channel in channels:
							await self.bot.send_message(self.bot.get_channel(channel),
														"@here Guild Wars 2 has just updated! New build: "
														"`{0}`".format(self.build["id"]))
					else:
						print ("A new build was found, but no channels to notify were found. Maybe error?")
			await asyncio.sleep(60)

	def getlanguage(self, ctx):
		server = ctx.message.server

		with open('data/guildwars2/language.json') as langfile:
			data = json.load(langfile)
		# Direct messages to bot defaults to english
		if server is None:
			language = "en"
		else:
			# Default value if no language set
			if server.id in data:
				language = data[server.id]["language"]
			else:
				language = "en"
		return language

	async def getworldid(self, world):
		if world is None:
			return None
		try:
			endpoint = "worlds?ids=all"
			results = await self.call_api(endpoint)
		except APIError:
			return None
		for w in results:
			if w["name"].lower() == world.lower():
				return w["id"]
		return None

	async def _get_guild_(self, gid):
		endpoint = "guild/{0}".format(gid)
		try:
			results = await self.call_api(endpoint)
		except APIError:
			return None
		return results

	async def _get_title_(self, tid, ctx):
		language = self.getlanguage(ctx)
		endpoint = "titles/{0}?lang={1}".format(tid,language)
		try:
			results = await self.call_api(endpoint)
		except APIError:
			return None
		title = results["name"]
		return title

	def get_age(self, age):
		hours, remainder = divmod(int(age), 3600)
		minutes, seconds = divmod(remainder, 60)
		days, hours = divmod(hours, 24)
		if days:
			fmt = '{d} days, {h} hours, {m} minutes, and {s} seconds'
		else:
			fmt = '{h} hours, {m} minutes, and {s} seconds'

		return fmt.format(d=days, h=hours, m=minutes, s=seconds)

	async def _get_item_name_(self, items, ctx):
		language = self.getlanguage(ctx)
		name = []
		if isinstance(items, int):
			endpoint = "items/{0}?lang={1}".format(items, language)
			try:
				results = await self.call_api(endpoint)
			except APIError:
				return None
			name.append(results["name"])
		else:
			for x in items:
				endpoint = "items/{0}?lang={1}".format(x, language)
				try:
					results = await self.call_api(endpoint)
				except APIError:
					return None
				name.append(results["name"])
		name = ", ".join(name)
		return name

	async def _getstats_(self, item):
		endpoint = "items/{0}".format(item)
		try:
			results = await self.call_api(endpoint)
		except APIError:
			return None
		name = results["details"]["infix_upgrade"]["id"]
		return name

	async def _getstatname_(self, item, ctx):
		language = self.getlanguage(ctx)
		endpoint = "itemstats/{0}?lang={1}".format(item, language)
		try:
			results = await self.call_api(endpoint)
		except APIError:
			return None
		name = results["name"]
		return name

	def get_channels(self):
		try:
			channels = []
			for server in self.settings:
				if not server == "ENABLED": #Ugly I know
					if self.settings[server]["ON"]:
						channels.append(self.settings[server]["CHANNEL"])
			return channels
		except:
			return None

	def get_announcement_channel(self, server):
		try:
			return server.get_channel(self.settings[server.id]["CHANNEL"])
		except:
			return None

	async def update_build(self):
		endpoint = "build"
		try:
			results = await self.call_api(endpoint)
		except APIError:
			return False
		build = results["id"]
		if not self.build["id"] == build:
			self.build["id"] = build
			dataIO.save_json('data/guildwars2/build.json', self.build)
			return True
		else:
			return False

	def construct_headers(self, key):
		headers = {"Authorization": "Bearer {0}".format(key)}
		headers.update(DEFAULT_HEADERS)
		return headers

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
	
	def coins_to_gold(self, input_string):
		# Convert a gold string into a gold int
		# You can use , or spaces as million/thousand/unit separators and g, s and c (lower-case)
		# "1,234g 56s 78c" -> 12345678
		# "1g 3c" -> 10003
		# "1 234 567" -> 1234567
		current_string = input_string.replace(",", "").replace(" ", "")
		l_separators = [
			{"symbol": "g", "value": 100**2},
			{"symbol": "s", "value": 100**1},
			{"symbol": "c", "value": 100**0}]
		total = 0
		for elem in l_separators:
			if elem["symbol"] in current_string:
				amount, current_string = current_string.split(elem["symbol"])
				total += int(amount) * elem["value"]
		if current_string != "":
			total += int(current_string)
		return total

	def getColor(self, user):
		try:
			color = user.colour
		except:
			color = discord.Embed.Empty
		return color

	def _check_scopes_(self, user, scopes):
		if user.id not in self.keylist:
			raise APIKeyError(
				"No API key associated with {0.mention}, add one with [p]key add (key)".format(user))
		if scopes:
			missing = []
			for scope in scopes:
				if scope not in self.keylist[user.id]["permissions"]:
					missing.append(scope)
			if missing:
				missing = ", ".join(missing)
				raise APIKeyError(
					"{0.mention}, missing the following scopes to use this command: `{1}`".format(user, missing))

	def save_keys(self):
		dataIO.save_json('data/guildwars2/keys.json', self.keylist)
	
	def save_containers(self):
		dataIO.save_json('data/guildwars2/containers.json', self.containers)

def check_folders():
	if not os.path.exists("data/guildwars2"):
		print("Creating data/guildwars2")
		os.makedirs("data/guildwars2")

def check_files():
	files = {
		"gemtrack.json": {},
		"gamedata.json": {},
		"settings.json": {"ENABLED": False},
		"language.json": {},
		"build.json": {"id": None},  # Yay legacy support
		"keys.json": {},
		"containers.json": {},
		"keys.json": {}
	}

	for filename, value in files.items():
		if not os.path.isfile("data/guildwars2/{}".format(filename)):
			print("Creating empty {}".format(filename))
			dataIO.save_json("data/guildwars2/{}".format(filename), value)


def setup(bot):
	check_folders()
	check_files()
	n = Guildwars2(bot)
	loop = asyncio.get_event_loop()
	loop.create_task(n._gemprice_tracker())
	loop.create_task(n._gamebuild_checker())
	if soupAvailable:
		bot.add_cog(n)
	else:
		raise RuntimeError("You need to run `pip3 install beautifulsoup4`")
