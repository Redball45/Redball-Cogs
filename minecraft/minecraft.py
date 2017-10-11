import discord
from discord.ext import commands

from os import system





class HTTPException(Exception):
	pass

class minecraft:
	"""Minecraft Server commands"""



	def __init__(self, bot):
		self.bot = bot

	
	@commands.group()
	@commands.is_owner()
	async def mc(self, ctx):
		"""Commands related to Minecraft Server Management"""
		if ctx.invoked_subcommand is None:
			await self.bot.send_cmd_help(ctx)

	@mc.command()
	async def start(self, ctx):
		"""Starts the minecraft server"""
		shell_command = 'screen bash ' + '/home/ark/minecraft/craftbukkit.sh'
		system(full_command)


