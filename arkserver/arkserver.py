import discord
from discord.ext import commands
from .utils import checks
from __main__ import send_cmd_help
from cogs.utils.dataIO import dataIO, fileIO

import json
import os
import asyncio
import subprocess

#def out(command):
	"""This function runs a shell script and collects the terminal response"""
#	result = run(command, stdout=PIPE, stderr=PIPE, universal_newlines=True, shell=True)
#	return result.stdout

def out(command, tochannel):
	result = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	for line in iter(p.stdout.readline,''):
		await self.bot.send_message(tochannel,"{0}".format(line))


class arkserver:
	"""Ark Server commands"""

	def __init__(self, bot):
		self.bot = bot
		self.settings = dataIO.load_json("data/arkserver/settings.json")

	@commands.group(pass_context=True)
	@checks.mod_or_permissions(manage_webhooks=True)
	async def ark(self, ctx):
		"""Commands related to Ark Server Management"""
		if ctx.invoked_subcommand is None:
			await self.bot.send_cmd_help(ctx)

	@ark.command(pass_context=True)
	async def checkupdate(self):
		"""Checks for ark updates - does not actually start the update"""
		output = out("arkmanager checkupdate")
		await self.bot.say("{0}".format(output))

	@ark.command(pass_context=True, name="stop")
	@checks.is_owner()
	async def ark_stop(self):
		"""Stops the Ark Server"""
		output = out("arkmanager stop")
		await self.bot.say("{0}".format(output))

	@ark.command(pass_context=True, name="toggle")
	@checks.is_owner()
	async def ark_toggle(self):
		"""Toggles autoupdating"""
		if self.settings["AutoUpdate"] == True:
			self.settings["AutoUpdate"] = False
			await self.bot.say("Automatic updating is now disabled.")
		else:
			self.settings["AutoUpdate"] = True
			await self.bot.say("Automatic server updating is now enabled.")
		dataIO.save_json('data/arkserver/settings.json', self.settings)

	@ark.command(pass_context=True, name="start")
	@checks.is_owner()
	async def ark_start(self):
		"""Starts the Ark Server"""
		output = out("arkmanager start")
		await self.bot.say("{0}".format(output))

	@ark.command(pass_context=True, name="status")
	async def ark_status(self):
		"""Checks the server status"""
		output = out("arkmanager status", ctx.message.channel)
		await self.bot.say("{0}".format(output))

	@ark.command(pass_context=True, name="restart")
	async def ark_restart(self, ctx, delay : int = 60):
		"""Restarts the ARK Server - delay in seconds can be specified after restart, default 60 maximum 600"""
		CurrentUpdating = self.settings["AutoUpdate"]
		self.settings["AutoUpdate"] = False #this makes sure autoupdate does not activate while the server is already busy
		if delay > 600:
			delay = 600
		await self.bot.say("Restarting in {0} seconds...".format(delay))
		text = "This server will restart in " + str(delay) + " seconds for maintenance."
		output = out('arkmanager broadcast' + ' ' + '"' + text + '"')
		await asyncio.sleep(delay)
		output = out("arkmanager restart")
		await self.bot.say("{0}".format(output))
		self.settings["AutoUpdate"] = CurrentUpdating #sets Updating back to the state it was before the command was run

	@ark.command(pass_context=True, name="update")
	async def ark_update(self, ctx, delay : int = 60):
		"""Stops the ARK Server, installs updates, then reboots"""
		CurrentUpdating = self.settings["AutoUpdate"]
		self.settings["AutoUpdate"] = False #this makes sure autoupdate does not activate while the server is already busy
		if delay > 600:
			delay = 600
		await self.bot.say("Restarting in {0} seconds...".format(delay))
		text = "This server will restart in " + str(delay) + " seconds for updates."
		output = out('arkmanager broadcast' + ' ' + '"' + text + '"')
		await asyncio.sleep(delay)
		output = out("arkmanager update --update-mods --backup")
		await self.bot.say("{0}".format(output))
		self.settings["AutoUpdate"] = CurrentUpdating #sets Updating back to the state it was before the command was run

	@ark.command(pass_context=True, name="save")
	async def ark_save(self):
		"""Saves the world state"""
		output = out("arkmanager saveworld")
		await self.bot.say("{0}".format(output))

	@ark.command(pass_context=True, name="backup")
	async def ark_backup(self):
		"""Creates a backup of the save and config files"""
		output = out("arkmanager backup")
		await self.bot.say("{0}".format(output))

	@ark.command(pass_context=True, name="updatenow")
	@checks.is_owner()
	async def ark_updatenow(self):
		"""Updates without warning"""
		output = out("arkmanager update --update-mods --backup")
		await self.bot.say("{0}".format(output))

	@ark.command(pass_context=True, name="validate")
	@checks.is_owner()
	async def ark_validate(self):
		"""Validates the server files with steamcmd"""
		await self.bot.say("Please note this can take a significant amount of time, please confirm you want to do this by replying Yes")
		answer = await self.bot.wait_for_message(timeout=30, author=user)
		if answer.content == "Yes":
			output = out("arkmanager update --validate")
			await self.bot.say("{0}".format(output))
		else: 
			await self.bot.edit_message(message, "Okay, validation cancelled")
			return

	@ark.command(pass_context=True, name="forceupdate")
	@checks.is_owner()
	async def ark_forceupdate(self):
		"""Updates without warning with the -force parameter"""
		output = out("arkmanager update --update-mods --backup --force --ifempty")
		await self.bot.say("{0}".format(output))

	async def update_checker(self):
		"""Checks for updates automatically every hour"""
		while self is self.bot.get_cog("arkserver"):
			channel = self.bot.get_channel("330795712067665923")
			adminchannel = self.bot.get_channel("331076958425186305")
			if self.settings["AutoUpdate"] == True:
				output = out("arkmanager checkupdate", channel)
				if 'Your server is up to date!' in output:
					await self.bot.send_message(adminchannel,"No updates found.")
					await asyncio.sleep(3600)
				else:
					newoutput = out("arkmanager update --update-mods --backup --ifempty", adminchannel)
					if 'players are still connected' in newoutput:
						await self.bot.send_message(channel,"An update is available but players are still connected, automatic update will not continue.".format(newoutput))
						await asyncio.sleep(3600)
					else:
						await self.bot.send_message(channel,"{0}".format(newoutput))
						await asyncio.sleep(3600)
			else:
				await self.bot.send_message(adminchannel,"Automatic updating is disabled, if the option is toggled on this might be because the server is already restarting or updating.")
				await asyncio.sleep(1800)

def check_folders():
	if not os.path.exists("data/arkserver"):
		print("Creating data/arkserver")
		os.makedirs("data/arkserver")

def check_files():
	files = {
		"settings.json": {"AutoUpdate": True}
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
