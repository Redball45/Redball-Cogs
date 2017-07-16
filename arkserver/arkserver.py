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

class HTTPException(Exception):
	pass

class arkserver:
	"""Ark Server commands"""

	def __init__(self, bot):
		self.bot = bot
		self.settings = dataIO.load_json("data/arkserver/settings.json")
		self.updating = False
		self.channel = self.bot.get_channel("333605978560004097")
		self.adminchannel = self.bot.get_channel("331076958425186305")

	async def runcommand(self, command, channel, verbose):
		"""This function runs a command in the terminal and collects the response"""
		process = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE, shell=False)
		status = ""
		list_replacements = ["[1;32m ", "[1;31m", "[0;39m   ", "[0;39m ", "[0;39m", "8[J", "[68G[   [1;32m", "  ]", "\033"]
		try:
			while True:
				output = process.stdout.readline().decode() #read each line of terminal output
				if output == '' and process.poll() is not None:
					break
				if output: 
					if verbose == True:
						if len(output) > 1900:
							print("The console returned a string for this line that exceeds the discord character limit.")
						else:
							sani = output
							sani = sani.lstrip("7")
							for elem in list_replacements:
								sani = sani.replace(elem, "")
							try:
								await self.bot.send_message(channel,"{0}".format(sani))
							except discord.HTTPException as e:
								print("Error posting to discord {0}, {1}".format(e, sani))
					if 'Your server needs to be restarted in order to receive the latest update' in output:
						status = status + 'Update'
					if 'has been updated on the Steam workshop' in output:
						status = status + 'ModUpdate'
					if 'The server is now running, and should be up within 10 minutes' in output:
						status = status + 'Success'
						break
					if 'players are still connected' in output:
						status = status + 'PlayersConnected'
					if 'Players: 0' in output:
						status = status + 'EmptyTrue'
					if 'online:  Yes' in output:
						status = status + 'NotUpdating'
		except:
			print("Something went wrong... you should check the status of the server with +ark status.")
			print("Updating and restarting options will be locked for 3 minutes for safety.")
			self.updating = True
			await asyncio.sleep(180)
			self.updating = False
			if process.poll() is None:
				process.kill()
			return status
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
	async def resetstatus(self, ctx):
		"""Resets bot and self.updating status."""
		channel = ctx.message.channel
		self.updating = False
		await self.bot.change_presence(game=discord.Game(name=None),status=discord.Status.online)
		await self.bot.say("Status check confirmed an update is actually happening.")


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
		user = ctx.message.author
		channel = ctx.message.channel #gets channel from user message command
		message = ctx.message
		output = await self.runcommand("arkmanager status", channel, False)
		if minput == 'info':
			await self.bot.say("This command can swap the map the server is running on to the desired map. Options available are 'Ragnarok' 'Island' and 'Scorched'. (e.g +ark map ragnarok)")
			return
		if 'EmptyTrue' not in output:
			await self.bot.say("The map cannot be swapped while players are in the server.")
			await self.bot.add_reaction(message, <:youtried:336180558956593152>)
			return
		await asyncio.sleep(5) #just to make sure previous arkmanager command has time to finish
		if self.updating == True: #don't change the map if the server is restarting or updating
			await self.bot.say("I'm already carrying out a restart or update! :ban:")
			return
		if minput.lower() == 'ragnarok':
			desiredMap = 'Ragnarok'
		elif minput.lower() == 'island':
			desiredMap = 'TheIsland'
		elif minput.lower() == 'scorched':
			desiredMap = 'ScorchedEarth'
		else:
			await self.bot.say("I don't recognize that map, available options are Ragnarok, Island and Scorched.")
			return
		if self.settings["Map"] == desiredMap:
			await self.bot.say("The server is already running this map!") 
			await self.bot.add_reaction(message, ':youtried:')
			return
		await self.bot.say("Map will be swapped to {0}, the server will need to be restarted to complete the change, please confirm by typing Yes.".format(desiredMap))
		answer = await self.bot.wait_for_message(timeout=30, author=user)
		try:	
			if answer.content != "Yes":
				await self.bot.say("Okay, change cancelled.")
				return
		except:
			await self.bot.say("Okay, change cancelled.")
			return
		self.updating = True #prevents the bot from restarting or updating while this is happening
		if self.settings["Map"] == 'Ragnarok':
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
		await self.bot.change_presence(game=discord.Game(name="Restarting Server"),status=discord.Status.dnd)
		await self.bot.say("Server will be restarted in 60 seconds.")
		alert = await self.runcommand('arkmanager broadcast "Server will shutdown for a restart in 60 seconds."', channel, False)
		await asyncio.sleep(60)
		output = await self.runcommand("arkmanager restart", channel, self.settings["Verbose"])
		if 'Success' in output:
			await self.bot.say("Map changed and server has been restarted.")
		else:
			await self.bot.say("Something went wrong :clap:")
		await self.bot.change_presence(game=discord.Game(name=None),status=discord.Status.online)
		self.updating = False


	@ark.command(pass_context=True)
	async def checkupdate(self, ctx):
		"""Checks for ark updates - does not actually start the update"""
		channel = ctx.message.channel #gets channel from user message command
		output = await self.runcommand("arkmanager checkupdate", channel, True)

	@ark.command(pass_context=True)
	async def checkmodupdate(self, ctx):
		"""Checks for ark mod updates - does not actually start the update"""
		channel = ctx.message.channel
		output = await self.runcommand("arkmanager checkmodupdate", channel, True)

	@ark.command(pass_context=True, name="stop")
	@checks.is_owner()
	async def ark_stop(self, ctx):
		"""Stops the Ark Server"""
		channel = ctx.message.channel
		output = await self.runcommand("arkmanager stop", channel, True)

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

	@ark.command(pass_context=True, name="verbose")
	@checks.is_owner()
	async def ark_verbose(self, ctx, toggle : str = 'info'):
		"""Toggles command verbosity"""
		togglestatus = self.settings["Verbose"] #retrives current status of toggle from settings file
		if toggle.lower() == 'off':
			self.settings["Verbose"] = False
			await self.bot.say("I will not be verbose when executing commands.")
		elif toggle.lower() == 'on':
			self.settings["Verbose"] = True
			await self.bot.say("I will output all lines from the console when executing commands.")
		else:
			if togglestatus == True:
				await self.bot.say("I am currently outputting all lines from the console when executing commands.")
			elif togglestatus == False:
				await self.bot.say("I am currently not being verbose when executing commands.")
		dataIO.save_json('data/arkserver/settings.json', self.settings)

	@ark.command(pass_context=True, name="start")
	@checks.is_owner()
	async def ark_start(self, ctx):
		"""Starts the Ark Server"""
		channel = ctx.message.channel
		output = await self.runcommand("arkmanager start", channel, True)

	@ark.command(pass_context=True, name="status")
	async def ark_status(self, ctx):
		"""Checks the server status"""
		channel = ctx.message.channel
		output = await self.runcommand("arkmanager status", channel, True)

	@ark.command(pass_context=True, name="restart")
	async def ark_restart(self, ctx, delay : int = 300):
		"""Restarts the ARK Server with a user specificed delay (in seconds)"""
		if delay > 900:
			delay = 900
		if delay < 120:
			delay = 120
		user = ctx.message.author
		channel = ctx.message.channel
		empty = await self.runcommand("arkmanager status", channel, False)
		if 'EmptyTrue' not in empty:
			await self.bot.say("Players are currently in the server, restart anyway?")
			answer = await self.bot.wait_for_message(timeout=30, author=user)
			try:	
				if answer.content != "Yes":
					await self.bot.say("Okay, restart cancelled.")
					return
			except:
				await self.bot.say("Okay, restart cancelled.")
				return
		if self.updating == True:
			await self.bot.say("I'm already carrying out a restart or update! :ban:")
		else:
			self.updating = True
			await self.bot.say("Restarting in {0} seconds.".format(delay))
			await self.bot.change_presence(game=discord.Game(name="Restarting Server"),status=discord.Status.dnd)
			await asyncio.sleep(delay-60)
			alert = await self.runcommand('arkmanager broadcast "Server will shutdown for a user-requested restart in 60 seconds."', channel, False)
			await asyncio.sleep(60)
			output = await self.runcommand("arkmanager restart", channel, self.settings["Verbose"])
			await self.bot.change_presence(game=discord.Game(name=None),status=discord.Status.online)
			self.updating = False
			if 'Success' in output:
				await self.bot.say("Server has been restarted :ok_hand_g:")
			else:
				await self.bot.say("Something went wrong :clap:")

	@ark.command(pass_context=True, name="update")
	async def ark_update(self, ctx):
		"""Stops the ARK Server, installs updates, then reboots"""
		user = ctx.message.author
		channel = ctx.message.channel
		status = await self.runcommand("arkmanager checkupdate", channel, False)
		modstatus = await self.runcommand("arkmanager checkmodupdate", channel, False)
		if 'Update' in status or 'ModUpdate' in modstatus:
			await self.bot.say("Updates are available.")
			empty = await self.runcommand("arkmanager status", channel, False)
			if 'EmptyTrue' not in empty:
				await self.bot.say("Players are currently in the server, update anyway?")
				answer = await self.bot.wait_for_message(timeout=30, author=user)
				try:
					if answer.content != "Yes":
						await self.bot.say("Okay, update cancelled.")
						return
				except:
					await self.bot.say("Okay, update cancelled.")
					return
			await self.bot.say("Server will be restarted in 60 seconds.")
			if self.updating == True:
				await self.bot.say("I'm already carrying out a restart or update! :ban:")
			else:
				self.updating = True
				await self.bot.change_presence(game=discord.Game(name="Updating Server"),status=discord.Status.dnd)
				alert = await self.runcommand('arkmanager broadcast "Server will shutdown for updates in 60 seconds."', channel, False)
				await asyncio.sleep(60)
				output = await self.runcommand("arkmanager update --update-mods --backup", channel, self.settings["Verbose"])
				await self.bot.change_presence(game=discord.Game(name=None),status=discord.Status.online)
				self.updating = False
				if 'Success' in output:
					await self.bot.say("Updates were found and installed. :ok_hand_g:")
				else:
					await self.bot.say("Something went wrong :clap:")
		else:
			await self.bot.say("No updates found.")

	@ark.command(pass_context=True, name="save")
	@checks.is_owner()
	async def ark_save(self, ctx):
		"""Saves the world state"""
		channel = ctx.message.channel
		output = await self.runcommand("arkmanager saveworld", channel, True)

	@ark.command(pass_context=True, name="backup")
	@checks.is_owner()
	async def ark_backup(self, ctx):
		"""Creates a backup of the save and config files"""
		channel = ctx.message.channel
		output = await self.runcommand("arkmanager backup", channel, True)

	@ark.command(pass_context=True, name="updatenow")
	@checks.is_owner()
	async def ark_updatenow(self, ctx):
		"""Updates without warning"""
		channel = ctx.message.channel
		output = await self.runcommand("arkmanager update --update-mods --backup", channel, True)

	@ark.command(pass_context=True, name="validate")
	@checks.is_owner()
	async def ark_validate(self, ctx):
		"""Validates the server files with steamcmd"""
		user = ctx.message.author
		channel = ctx.message.channel
		await self.bot.say("Please note this can take a significant amount of time, please confirm you want to do this by replying Yes")
		answer = await self.bot.wait_for_message(timeout=30, author=user)
		if answer.content == "Yes":
			output = await self.runcommand("arkmanager update --validate", channel, True)
		else: 
			await self.bot.edit_message(message, "Okay, validation cancelled")
			return

	@ark.command(pass_context=True, name="vpsrestart")
	@checks.is_owner()
	async def ark_boxrestart(self, ctx):
		"""Restarts the VPS"""
		user = ctx.message.author
		channel = ctx.message.channel
		await self.bot.say("Please note this will restart the VPS and may take some time, please confirm you want to do this by replying Yes")
		answer = await self.bot.wait_for_message(timeout=30, author=user)
		if answer.content == "Yes":
			output = await self.runcommand("reboot", channel, False)
		else: 
			await self.bot.edit_message(message, "Okay, restart cancelled")
			return

	@ark.command(pass_context=True, name="forceupdate")
	@checks.is_owner()
	async def ark_forceupdate(self, ctx):
		"""Updates without warning with the -force parameter"""
		channel = ctx.message.channel
		output = self.runcommand("arkmanager update --update-mods --backup --force", channel, True)

	async def update_checker(self):
		"""Checks for updates automatically every hour"""
		while self is self.bot.get_cog("arkserver"):
			await asyncio.sleep(60)
			try:
				if self.settings["AutoUpdate"] == True: #proceed only if autoupdating is enabled
					if self.updating == False: #proceed only if the bot isn't already manually updating or restarting
						verbose = self.settings["Verbose"]
						status = await self.runcommand("arkmanager checkupdate", self.adminchannel, verbose)
						modstatus = await self.runcommand("arkmanager checkmodupdate", self.adminchannel, verbose)
						await self.bot.send_message(self.adminchannel,"Update check completed at {0}".format(datetime.utcnow()))
						if 'Update' in status or 'ModUpdate' in modstatus: #proceed with update if checkupdate tells us that an update is available
							empty = await self.runcommand("arkmanager status", self.adminchannel, False)
							if 'EmptyTrue' not in empty:
								#players detected in the server, queue update for in 15 minutes
								alert = await self.runcommand('arkmanager broadcast "Server will shutdown for updates in 15 minutes."', self.channel, False)
								await asyncio.sleep(300)
								alert = await self.runcommand('arkmanager broadcast "Server will shutdown for updates in 10 minutes."', self.channel, False)
								await asyncio.sleep(300)
								alert = await self.runcommand('arkmanager broadcast "Server will shutdown for updates in 5 minutes."', self.channel, False)
								await asyncio.sleep(240)
								alert = await self.runcommand('arkmanager broadcast "Server will shutdown for updates in 60 seconds."', self.channel, False)
								await asyncio.sleep(60)
								if self.updating == False:
									await self.bot.change_presence(game=discord.Game(name="Updating Server"),status=discord.Status.dnd)
									self.updating = True
									update = await self.runcommand("arkmanager update --update-mods --backup", self.adminchannel, True)
									if 'Success' in update:									
										await self.bot.send_message(self.channel,"Server has been updated :ok_hand_b:")
										await self.bot.change_presence(game=discord.Game(name=None),status=discord.Status.online)
										self.updating = False
										await asyncio.sleep(3540)
									else:
										await self.bot.send_message(self.channel,"Something went wrong during automatic update :clap:")
										await self.bot.change_presence(game=discord.Game(name=None),status=discord.Status.online)
										self.updating = False
										await asyncio.sleep(240)
								else:
									await self.bot.send_message(self.adminchannel,"Manual update or restart was triggered during 15 minute delay, automatic update has been cancelled")
									await asyncio.sleep(1800)
							else:
								update = await self.runcommand("arkmanager update --update-mods --backup", self.adminchannel, True)
								if 'Success' in update:									
									await self.bot.send_message(self.channel,"Server has been updated :ok_hand_b:")
									await self.bot.change_presence(game=discord.Game(name=None),status=discord.Status.online)
									self.updating = False
								else:
									await self.bot.send_message(self.channel,"Something went wrong during automatic update :clap:")
									await self.bot.change_presence(game=discord.Game(name=None),status=discord.Status.online)
									self.updating = False
								await asyncio.sleep(3540)
						else:
							await asyncio.sleep(3540)
					else:
						await self.bot.send_message(self.adminchannel,"Server is already updating or restarting, auto-update cancelled")
						await asyncio.sleep(3540)
			except Exception as e:
				print("Update checker encountered an exception {0}".format(e))
				await asyncio.sleep(240)

def check_folders():
	if not os.path.exists("data/arkserver"): #create folder for settings file
		print("Creating data/arkserver")
		os.makedirs("data/arkserver")

def check_files():
	files = {
		"settings.json": {"AutoUpdate": True, "Verbose" : True} #create settings file if it doesn't already exist
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
