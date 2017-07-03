import discord
from discord.ext import commands
from .utils import checks
from __main__ import send_cmd_help
import os
import asyncio
from subprocess import PIPE, run

def out(command):
	"""This function runs a shell script and collects the terminal response"""
	result = run(command, stdout=PIPE, stderr=PIPE, universal_newlines=True, shell=True)
	return result.stdout

Updating = True

class arkserver:
	"""Ark Server commands"""

	def __init__(self, bot):
		self.bot = bot

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
		"""Toggles autoupdating - is not saved and will revert to on upon bot/cog restart"""
		if Updating == True:
			Updating = False
			await self.bot.say("Automatic updating is now disabled.")
		else:
			Updating = True
			await self.bot.say("Automatic server updating is now enabled.")

	@ark.command(pass_context=True, name="start")
	@checks.is_owner()
	async def ark_start(self):
		"""Starts the Ark Server"""
		output = out("arkmanager start")
		await self.bot.say("{0}".format(output))

	@ark.command(pass_context=True, name="status")
	async def ark_status(self):
		"""Checks the server status"""
		output = out("arkmanager status")
		await self.bot.say("{0}".format(output))

	@ark.command(pass_context=True, name="restart")
	async def ark_restart(self, ctx, delay : int = 60):
		"""Restarts the ARK Server - delay in seconds can be specified after restart, default 60 maximum 600"""
		CurrentUpdating = Updating
		Updating = False #this makes sure autoupdate does not activate while the server is already busy
		if delay > 600:
			delay = 600
		await self.bot.say("Restarting in {0} seconds...".format(delay))
		text = "This server will restart in " + str(delay) + " seconds for maintenance."
		output = out('arkmanager broadcast' + ' ' + '"' + text + '"')
		await asyncio.sleep(delay)
		output = out("arkmanager restart")
		await self.bot.say("{0}".format(output))
		Updating = CurrentUpdating #sets Updating back to the state it was before the command was run

	@ark.command(pass_context=True, name="update")
	async def ark_update(self, ctx, delay : int = 60):
		"""Stops the ARK Server, installs updates, then reboots"""
		CurrentUpdating = Updating
		Updating = False #this makes sure autoupdate does not activate while the server is already busy
		if delay > 600:
			delay = 600
		await self.bot.say("Restarting in {0} seconds...".format(delay))
		text = "This server will restart in " + str(delay) + " seconds for updates."
		output = out('arkmanager broadcast' + ' ' + '"' + text + '"')
		await asyncio.sleep(delay)
		output = out("arkmanager update --update-mods --backup")
		await self.bot.say("{0}".format(output))
		Updating = CurrentUpdating #sets Updating back to the state it was before the command was run

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

	@ark.command(pass_context=True)
	@checks.mod_or_permissions(manage_webhooks=True)
	async def broadcast(self, ctx, *, text):
		"""Sends a message ingame"""
		output = out('arkmanager broadcast' + ' ' + '"' + text + '"')

	async def update_checker(self):
		"""Checks for updates automatically every hour"""
		while self is self.bot.get_cog("arkserver"):
			channel = self.bot.get_channel("330795712067665923")
			adminchannel = self.bot.get_channel("331076958425186305")
			if Updating == True:
				output = out("arkmanager checkupdate")
				if 'Your server is up to date!' in output:
					await self.bot.send_message(adminchannel,"No updates found.")
					await asyncio.sleep(3600)
				else:
					newoutput = out("arkmanager update --update-mods --backup --ifempty")
					if 'players are still connected' in newoutput:
						await self.bot.send_message(channel,"An update is available but players are still connected, automatic update will not continue.".format(newoutput))
						await asyncio.sleep(3600)
					else:
						await self.bot.send_message(channel,"{0}".format(newoutput))
						await asyncio.sleep(3600)
			else:
				await self.bot.send_message(adminchannel,"Automatic updating is disabled, if the option is toggled on this might be because the server is already restarting or updating.")
				await asyncio.sleep(1800)


def setup(bot):
	n = arkserver(bot)
	loop = asyncio.get_event_loop()
	loop.create_task(n.update_checker())
	bot.add_cog(n)
