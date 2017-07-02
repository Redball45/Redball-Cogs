import discord
from discord.ext import commands
from .utils import checks
from __main__ import send_cmd_help
import os
import asyncio
from subprocess import PIPE, run

def out(command):
	result = run(command, stdout=PIPE, stderr=PIPE, universal_newlines=True, shell=True)
	return result.stdout

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
		output = out("arkmanager stop --warn")
		await self.bot.say("{0}".format(output))

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
		if delay > 600:
			delay = 600
		await self.bot.say("Restarting in {0} seconds...".format(delay))
		text = "This server will restart in " + str(delay) + " seconds for maintenance."
		output = out('arkmanager broadcast' + ' ' + '"' + text + '"')
		await asyncio.sleep(delay)
		output = out("arkmanager restart")
		await self.bot.say("{0}".format(output))

	@ark.command(pass_context=True, name="update")
	async def ark_update(self, ctx, delay : int = 60):
		"""Stops the ARK Server, installs updates, then reboots"""
		if delay > 600:
			delay = 600
		await self.bot.say("Restarting in {0} seconds...".format(delay))
		text = "This server will restart in " + str(delay) + " seconds for updates."
		output = out('arkmanager broadcast' + ' ' + '"' + text + '"')
		await asyncio.sleep(delay)
		output = out("arkmanager update --update-mods --backup")
		await self.bot.say("{0}".format(output))

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

	@ark.command(pass_context=True, name="forceupdate")
	@checks.is_owner()
	async def ark_forceupdate(self):
		"""Updates without warning with the -force parameter"""
		output = out("arkmanager update --update-mods --backup --force")
		await self.bot.say("{0}".format(output))

	@ark.command(pass_context=True)
	@checks.mod_or_permissions(manage_webhooks=True)
	async def broadcast(self, ctx, *, text):
		"""Sends a message ingame"""
		output = out('arkmanager broadcast' + ' ' + '"' + text + '"')

def setup(bot):
	n = arkserver(bot)
	bot.add_cog(n)
