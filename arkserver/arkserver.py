import discord
from discord.ext import commands
from .utils import checks
from __main__ import send_cmd_help
from discord.ext.commands.cooldowns import BucketType
from cogs.utils.dataIO import dataIO, fileIO
from datetime import datetime

import json
import os
import asyncio
import subprocess
import shlex


class arkserver:
	"""Ark Server commands"""

	def __init__(self, bot):
		self.bot = bot
		self.settings = dataIO.load_json("data/arkserver/settings.json")
		self.updating = False

	async def runcommand(self, command, channel, verbose):
		"""This function runs a command in the terminal and collects the response"""
		process = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE, shell=False)
		status = "False"
		list_replacements = ["[1;32m ", "[0;39m   ", "[0;39m ", "[0;39m", "8[J", "[68G[   [1;32m", "  ]", "\033"]
		while True:
			output = process.stdout.readline().decode() #read each line of terminal output
			if output == '' and process.poll() is not None:
				if command != 'arkmanager restart --warn':
					break
			if output: 
				if verbose == True:
					sani = output
					sani = sani.lstrip("7")
					for elem in list_replacements:
						sani = sani.replace(elem, "")
					await self.bot.send_message(channel,"{0}".format(sani))
				if 'Your server needs to be restarted in order to receive the latest update' in output:
					status = "True"
				if 'The server is now running, and should be up within 10 minutes' in output:
					break
				if 'players are still connected' in output:
					status = "PlayersConnected"
				if 'Players: 0' in output:
					status = "EmptyTrue"
		if process.poll() is None:
			process.kill()
		return status


	@commands.group(pass_context=True)
	@checks.mod_or_permissions(manage_webhooks=True)
	async def ark(self, ctx):
		"""Commands related to Ark Server Management"""
		if ctx.invoked_subcommand is None:
			await self.bot.send_cmd_help(ctx)

	@ark.command(pass_context=True, hidden=True)
	@checks.is_owner()
	async def forcemap(self, ctx, minput : str = 'info'):
		"""Swaps the settings save file to a specific map."""
		if minput.lower() == 'ragnarok':
			desiredMap = 'Ragnarok'
		elif minput.lower() == 'island':
			desiredMap = 'TheIsland'
		elif minput.lower() == 'scorched':
			desiredMap = 'ScorchedEarth'
		else:
			await self.bot.say("I don't recognize that map, available options are Ragnarok, Island and Scorched")
			return
		self.settings["Map"] = desiredMap
		dataIO.save_json('data/arkserver/settings.json', self.settings)

	@ark.command(pass_context=True)
	async def map(self, ctx, minput : str = 'info'):
		"""Swaps the server over to the desired map."""
		channel = ctx.message.channel #gets channel from user message command
		output = await self.runcommand("arkmanager status", channel, False)
		if minput == 'info':
			await self.bot.say("This command can swap the map the server is running on to the desired map. Options available are 'Ragnarok' 'Island' and 'Scorched'. (e.g +ark map ragnarok)")
			return
		if output != 'EmptyTrue':
			await self.bot.say("The map cannot be swapped while players are in the server.")
			return
		await asyncio.sleep(5) #just to make sure previous arkmanager command has time to finish
		if self.updating == True: #don't change the map if the server is restarting or updating
			await self.bot.say("I'm already carrying out a restart or update!")
			return
		if minput.lower() == 'ragnarok':
			desiredMap = 'Ragnarok'
		elif minput.lower() == 'island':
			desiredMap = 'TheIsland'
		elif minput.lower() == 'scorched':
			desiredMap = 'ScorchedEarth'
		else:
			await self.bot.say("I don't recognize that map, available options are Ragnarok, Island and Scorched")
			return
		if self.settings["Map"] == desiredMap:
			await self.bot.say("The server is already running this map!") 
			return
		elif self.settings["Map"] == 'Ragnarok':
			output = await self.runcommand("mv /etc/arkmanager/arkmanager.cfg /etc/arkmanager/rag.cfg", channel, False)
		elif self.settings["Map"] == 'TheIsland':
			output = await self.runcommand("mv /etc/arkmanager/arkmanager.cfg /etc/arkmanager/island.cfg", channel, False)
		elif self.settings["Map"] == 'ScorchedEarth':
			output = await self.runcommand("mv /etc/arkmanager/arkmanager.cfg /etc/arkmanager/scorched.cfg", channel, False)
		if desiredMap == 'Ragnarok':
			output = await self.runcommand("mv /etc/arkmanager/rag.cfg /etc/arkmanager/arkmanager.cfg", channel, False)
		elif desiredMap == 'TheIsland':
			output = await self.runcommand("mv /etc/arkmanager/island.cfg /etc/arkmanager/arkmanager.cfg", channel, False)
		elif desiredMap == 'ScorchedEarth':
			output = await self.runcommand("mv /etc/arkmanager/scorched.cfg /etc/arkmanager/arkmanager.cfg", channel, False)
		self.settings["Map"] = desiredMap
		dataIO.save_json('data/arkserver/settings.json', self.settings)
		self.updating = True #prevents the bot from restarting or updatinng while this is happening
		await self.bot.change_presence(game=discord.Game(name="Restarting Server"),status=discord.Status.dnd)
		output = await self.runcommand("arkmanager restart", channel, True)
		await asyncio.sleep(15)
		await self.bot.change_presence(game=discord.Game(name=None),status=discord.Status.online)
		self.updating = False


	@ark.command(pass_context=True)
	async def checkupdate(self, ctx, verbose : bool = True):
		"""Checks for ark updates - does not actually start the update"""
		channel = ctx.message.channel #gets channel from user message command
		output = await self.runcommand("arkmanager checkupdate", channel, verbose)

	@ark.command(pass_context=True)
	async def checkmodupdate(self, ctx, verbose : bool = True):
		"""Checks for ark mod updates - does not actually start the update"""
		channel = ctx.message.channel
		output = await self.runcommand("arkmanager checkmodupdate", channel, verbose)

	@ark.command(pass_context=True, name="stop")
	@checks.is_owner()
	async def ark_stop(self, ctx, verbose : bool = True):
		"""Stops the Ark Server"""
		channel = ctx.message.channel
		output = await self.runcommand("arkmanager stop", channel, verbose)

	@ark.command(pass_context=True, name="toggle")
	@checks.is_owner()
	async def ark_toggle(self, ctx, toggle : str = 'info'):
		"""Toggles autoupdating"""
		togglestatus = self.settings["AutoUpdate"] #retrives current status of toggle from settings file
		if toggle.lower() == 'off':
			self.settings["AutoUpdate"] = False
			await self.bot.say("Automatic updating is now disabled.")
		elif toggle.lower() == 'on':
			self.settings["AutoUpdate"] = True
			await self.bot.say("Automatic server updating is now enabled.")
		else:
			if togglestatus == True:
				await self.bot.say("Automatic updating is currently enabled.")
			elif togglestatus == False:
				await self.bot.say("Automatic updating is currently disabled.")
		dataIO.save_json('data/arkserver/settings.json', self.settings)

	@ark.command(pass_context=True, name="start")
	@checks.is_owner()
	async def ark_start(self, ctx, verbose : bool = True):
		"""Starts the Ark Server"""
		channel = ctx.message.channel
		output = await self.runcommand("arkmanager start", channel, verbose)

	@ark.command(pass_context=True, name="status")
	async def ark_status(self, ctx, verbose : bool = True):
		"""Checks the server status"""
		channel = ctx.message.channel
		output = await self.runcommand("arkmanager status", channel, verbose)

	@ark.command(pass_context=True, name="restart")
	async def ark_restart(self, ctx, verbose : bool = True):
		"""Restarts the ARK Server with a 60 second delay"""
		if self.updating == True:
			await self.bot.say("I'm already carrying out a restart or update!")
		else:
			self.updating = True
			await self.bot.change_presence(game=discord.Game(name="Restarting Server"),status=discord.Status.dnd)
			channel = ctx.message.channel
			output = await self.runcommand("arkmanager restart --warn", channel, verbose)
			await asyncio.sleep(30)
			await self.bot.change_presence(game=discord.Game(name=None),status=discord.Status.online)
			self.updating = False

	@ark.command(pass_context=True, name="update")
	async def ark_update(self, ctx, verbose : bool = True):
		"""Stops the ARK Server, installs updates, then reboots"""
		if self.updating == True:
			await self.bot.say("I'm already carrying out a restart or update!")
		else:
			self.updating = True
			await self.bot.change_presence(game=discord.Game(name="Updating Server"),status=discord.Status.dnd)
			channel = ctx.message.channel
			output = await self.runcommand("arkmanager update --update-mods --backup --warn", channel, verbose)
			await asyncio.sleep(30)
			await self.bot.change_presence(game=discord.Game(name=None),status=discord.Status.online)
			self.updating = False

	@ark.command(pass_context=True, name="save")
	@checks.is_owner()
	async def ark_save(self, ctx, verbose : bool = True):
		"""Saves the world state"""
		channel = ctx.message.channel
		output = await self.runcommand("arkmanager saveworld", channel, verbose)

	@ark.command(pass_context=True, name="backup")
	@checks.is_owner()
	async def ark_backup(self, ctx, verbose : bool = True):
		"""Creates a backup of the save and config files"""
		channel = ctx.message.channel
		output = await self.runcommand("arkmanager backup", channel, verbose)

	@ark.command(pass_context=True, name="updatenow")
	@checks.is_owner()
	async def ark_updatenow(self, ctx, verbose : bool = True):
		"""Updates without warning"""
		channel = ctx.message.channel
		output = await self.runcommand("arkmanager update --update-mods --backup", channel, verbose)

	@ark.command(pass_context=True, name="validate")
	@checks.is_owner()
	async def ark_validate(self, ctx, verbose : bool = True):
		"""Validates the server files with steamcmd"""
		user = ctx.message.author
		channel = ctx.message.channel
		await self.bot.say("Please note this can take a significant amount of time, please confirm you want to do this by replying Yes")
		answer = await self.bot.wait_for_message(timeout=30, author=user)
		if answer.content == "Yes":
			output = await self.runcommand("arkmanager update --validate", channel, verbose)
		else: 
			await self.bot.edit_message(message, "Okay, validation cancelled")
			return

	@ark.command(pass_context=True, name="vpsrestart")
	@checks.is_owner()
	async def ark_boxrestart(self, ctx, verbose : bool = True):
		"""Restarts the VPS"""
		user = ctx.message.author
		channel = ctx.message.channel
		await self.bot.say("Please note this will restart the VPS and may take some time, please confirm you want to do this by replying Yes")
		answer = await self.bot.wait_for_message(timeout=30, author=user)
		if answer.content == "Yes":
			output = await self.runcommand("reboot", channel, verbose)
		else: 
			await self.bot.edit_message(message, "Okay, restart cancelled")
			return

	@ark.command(pass_context=True, name="forceupdate")
	@checks.is_owner()
	async def ark_forceupdate(self, ctx, verbose : bool = True):
		"""Updates without warning with the -force parameter"""
		channel = ctx.message.channel
		output = self.runcommand("arkmanager update --update-mods --backup --force", channel, verbose)

	async def update_checker(self):
		"""Checks for updates automatically every hour"""
		while self is self.bot.get_cog("arkserver"):
			channel = self.bot.get_channel("330795712067665923")
			adminchannel = self.bot.get_channel("331076958425186305")
			await asyncio.sleep(60)
			if self.settings["AutoUpdate"] == True: #proceed only if autoupdating is enabled
				if self.updating == False: #proceed only if the bot isn't already manually updating or restarting
					verbose = False
					status = await self.runcommand("arkmanager checkupdate", adminchannel, verbose)
					await self.bot.send_message(adminchannel,"Update check completed at {0}".format(datetime.utcnow()))
					if status == "True": #proceed with update if checkupdate tells us that an update is available
						await asyncio.sleep(5) #small delay to make sure previous command has cleaned up properly
						await self.bot.change_presence(game=discord.Game(name="Updating Server"),status=discord.Status.dnd)
						self.updating = True #this stops a manually update from being triggered by a user
						verbose = True
						newoutput = await self.runcommand("arkmanager update --update-mods --backup --ifempty", adminchannel)
						if status == "PlayersConnected":
							await self.bot.send_message(channel,"An update is available but players are still connected, automatic update will not continue.".format(newoutput))
							await asyncio.sleep(15)
							await self.bot.change_presence(game=discord.Game(name=None),status=discord.Status.online)
							self.updating = False #update was cancelled so remove the lock on updating/restarting
							await asyncio.sleep(3540)
						else:
							await self.bot.send_message(channel,"Server has been updated.")
							await asyncio.sleep(15)
							await self.bot.change_presence(game=discord.Game(name=None),status=discord.Status.online)
							self.updating = False #update was completed so remove the lock on updating/restarting
							await asyncio.sleep(3540)
					else:
						await asyncio.sleep(3540)
				else:
					await self.bot.send_message(adminchannel,"Server is already updating or restarting, auto-update cancelled")
					await asyncio.sleep(3540)

def check_folders():
	if not os.path.exists("data/arkserver"): #create folder for settings file
		print("Creating data/arkserver")
		os.makedirs("data/arkserver")

def check_files():
	files = {
		"settings.json": {"AutoUpdate": True} #create settings file if it doesn't already exist
	}

	for filename, value in files.items():
		if not os.path.isfile("data/arkserver/{}".format(filename)):
			print("Creating empty {}".format(filename))
			dataIO.save_json("data/arkserver/{}".format(filename), value)

def setup(bot):
	check_folders()
	check_files()
	n = arkserver(bot)
	loop = asyncio.get_event_loop()
	loop.create_task(n.update_checker())
	bot.add_cog(n)
