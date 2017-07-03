import discord
from discord.ext import commands
from .utils import checks
from __main__ import send_cmd_help
from cogs.utils.dataIO import dataIO, fileIO

import json
import os
import asyncio
import subprocess
import shlex

#def out(command):
#"""This function runs a shell script and collects the terminal response"""
#	result = run(command, stdout=PIPE, stderr=PIPE, universal_newlines=True, shell=True)
#	return result.stdout



class arkserver:
	"""Ark Server commands"""

	def __init__(self, bot):
		self.bot = bot
		self.settings = dataIO.load_json("data/arkserver/settings.json")

	async def runcommand(self, command, channel):
		process = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE)
		while True:
			output = process.stdout.readline().decode()
			if output == '' and process.poll() is not None:
				break
			if output: 
				await self.bot.send_message(channel,"{0}".format(output))
		rc = process.poll()
		return rc

	@commands.group(pass_context=True)
	@checks.mod_or_permissions(manage_webhooks=True)
	async def ark(self, ctx):
		"""Commands related to Ark Server Management"""
		if ctx.invoked_subcommand is None:
			await self.bot.send_cmd_help(ctx)

	@ark.command(pass_context=True)
	async def checkupdate(self, ctx):
		"""Checks for ark updates - does not actually start the update"""
		channel = ctx.message.channel
		output = await self.runcommand("arkmanager checkupdate", channel)

	@ark.command(pass_context=True)
	async def checkmodupdate(self, ctx):
		"""Checks for ark mod updates - does not actually start the update"""
		channel = ctx.message.channel
		output = await self.runcommand("arkmanager checkmodupdate", channel)

	@ark.command(pass_context=True, name="stop")
	@checks.is_owner()
	async def ark_stop(self, ctx):
		"""Stops the Ark Server"""
		channel = ctx.message.channel
		output = await self.runcommand("arkmanager stop", channel)

	@ark.command(pass_context=True, name="toggle")
	@checks.is_owner()
	async def ark_toggle(self, ctx, toggle : str = 'info'):
		"""Toggles autoupdating"""
		togglestatus = self.settings["AutoUpdate"]
		if toggle == 'info':
			if togglestatus = True:
				await self.bot.say("Automatic updating is currently enabled.")
			elif togglestatus = False:
				await self.bot.say("Automatic updating is currently disabled.")
		if toggle.lower() == 'off':
			self.settings["AutoUpdate"] = False
			await self.bot.say("Automatic updating is now disabled.")
		elif toggle.lower() == 'on':
			self.settings["AutoUpdate"] = True
			await self.bot.say("Automatic server updating is now enabled.")
		dataIO.save_json('data/arkserver/settings.json', self.settings)

	@ark.command(pass_context=True, name="start")
	@checks.is_owner()
	async def ark_start(self, ctx):
		"""Starts the Ark Server"""
		channel = ctx.message.channel
		output = await self.runcommand("arkmanager start", channel)

	@ark.command(pass_context=True, name="status")
	async def ark_status(self, ctx):
		"""Checks the server status"""
		channel = ctx.message.channel
		output = await self.runcommand("arkmanager status", channel)

	@ark.command(pass_context=True, name="restart")
	async def ark_restart(self, ctx):
		"""Restarts the ARK Server with a 60 second delay"""
		CurrentUpdating = self.settings["AutoUpdate"]
		channel = ctx.message.channel
		self.settings["AutoUpdate"] = False #this makes sure autoupdate does not activate while the server is already busy
		await self.bot.say("Restarting in 60 seconds...")
		await asyncio.sleep(60)
		output = await self.runcommand("arkmanager restart --warn", channel)
		self.settings["AutoUpdate"] = CurrentUpdating #sets Updating back to the state it was before the command was run

	@ark.command(pass_context=True, name="update")
	async def ark_update(self, ctx):
		"""Stops the ARK Server, installs updates, then reboots"""
		CurrentUpdating = self.settings["AutoUpdate"]
		channel = ctx.message.channel
		self.settings["AutoUpdate"] = False #this makes sure autoupdate does not activate while the server is already busy
		await self.bot.say("Restarting in 60 seconds...")
		await asyncio.sleep(60)
		output = await self.runcommand("arkmanager update --update-mods --backup --warn", channel)
		self.settings["AutoUpdate"] = CurrentUpdating #sets Updating back to the state it was before the command was run

	@ark.command(pass_context=True, name="save")
	async def ark_save(self, ctx):
		"""Saves the world state"""
		channel = ctx.message.channel
		output = await self.runcommand("arkmanager saveworld", channel)

	@ark.command(pass_context=True, name="backup")
	async def ark_backup(self, ctx):
		"""Creates a backup of the save and config files"""
		output = await self.runcommand("arkmanager backup", channel)

	@ark.command(pass_context=True, name="updatenow")
	@checks.is_owner()
	async def ark_updatenow(self, ctx):
		"""Updates without warning"""
		channel = ctx.message.channel
		output = await self.runcommand("arkmanager update --update-mods --backup", channel)

	@ark.command(pass_context=True, name="validate")
	@checks.is_owner()
	async def ark_validate(self, ctx):
		"""Validates the server files with steamcmd"""
		channel = ctx.message.channel
		await self.bot.say("Please note this can take a significant amount of time, please confirm you want to do this by replying Yes")
		answer = await self.bot.wait_for_message(timeout=30, author=user)
		if answer.content == "Yes":
			output = await self.runcommand("arkmanager update --validate", channel)
		else: 
			await self.bot.edit_message(message, "Okay, validation cancelled")
			return

	@ark.command(pass_context=True, name="forceupdate")
	@checks.is_owner()
	async def ark_forceupdate(self, ctx):
		"""Updates without warning with the -force parameter"""
		channel = ctx.message.channel
		output = self.runcommand("arkmanager update --update-mods --backup --force", channel)

	async def update_checker(self):
		"""Checks for updates automatically every hour"""
		while self is self.bot.get_cog("arkserver"):
			channel = self.bot.get_channel("330795712067665923")
			adminchannel = self.bot.get_channel("331076958425186305")
			if self.settings["AutoUpdate"] == True:
				output = await self.runcommand("arkmanager checkupdate", adminchannel)
				if 'Your server is up to date!' in output:
					await self.bot.send_message(adminchannel,"No updates found.")
					await asyncio.sleep(3600)
				else:
					newoutput = await self.runcommand("arkmanager update --update-mods --backup --ifempty", adminchannel)
					if 'players are still connected' in newoutput:
						await self.bot.send_message(channel,"An update is available but players are still connected, automatic update will not continue.".format(newoutput))
						await asyncio.sleep(3600)
					else:
						await self.bot.send_message(channel,"Server has been updated.")
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
