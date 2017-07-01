import discord
from discord.ext import commands
from .utils import checks
from __main__ import send_cmd_help
import os
import asyncio


class arkserver:
	"""Ark Server commands"""

	def __init__(self, bot):
		self.bot = bot

	@commands.command(pass_context=True)
	@checks.mod_or_permissions(manage_webhooks=True)
	async def restart(self):
		"""Restarts the ARK Server"""
		await os.system("arkmanager restart")
		await self.bot.say("Server restarted.")


def setup(bot):
	n = misc(bot)
	bot.add_cog(n)