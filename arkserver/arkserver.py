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

	@commands.command(pass_context=True)
	@checks.mod_or_permissions(manage_webhooks=True)
	async def checkupdate(self):
		"""Checks for ark updates"""
		output = out("arkmanager checkupdate")
		await self.bot.say("{0}".format(output))

	@commands.command(pass_context=True)
	@checks.mod_or_permissions(manage_webhooks=True)
	async def arkrestart(self):
		"""Restarts the ARK Server"""
		output = out("arkmanager restart")
		await self.bot.say("{0}".format(output))

	@commands.command(pass_context=True)
	@checks.mod_or_permissions(manage_webhooks=True)
	async def arkupdate(self):
		"""Stops the ARK Server, installs updates, then reboots"""
		output = out("arkmanager update --update-mods")
		await self.bot.say("{0}".format(output))

	@commands.command(pass_context=True)
	@checks.mod_or_permissions(manage_webhooks=True)
	async def broadcast(self, ctx, text):
		"""Sends a message ingame"""
		output = out("arkmanager broadcast" + " " + text)

def setup(bot):
	n = arkserver(bot)
	bot.add_cog(n)
