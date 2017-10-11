import discord
from discord.ext import commands

from os import system

import asyncio
import pyscreen





class HTTPException(Exception):
	pass

class minecraft:
	"""Minecraft Server commands"""



	def __init__(self, bot):
		self.bot = bot
		self.running = False
		self.session = None

	
	@commands.group()
	@commands.is_owner()
	async def mc(self, ctx):
		"""Commands related to Minecraft Server Management"""
		if ctx.invoked_subcommand is None:
			await self.bot.send_cmd_help(ctx)

	@mc.command()
	async def start(self, ctx):
		"""Starts the minecraft server"""
		if not self.running:
			self.session = pyscreen.ScreenSession('minecraft')
			self.session.send_command('bash /home/ark/minecraft/craftbukkit.sh')
			self.running = True
			await ctx.send("Server started.")
			return
		await ctx.send("Server already running.")

	@mc.command()
	async def stop(self, ctx):
		"""Stops the screen session"""
		if self.running:
			command = 'screen -S minecraft -p 0 -X stuff "`printf "stop\r"`";'
			system(command)
			await asyncio.sleep(10)
			command = 'screen -S minecraft -X quit'
			system(command)
			self.running = False
			return await ctx.send("Server stopped.")
		await ctx.send("Server isn't running.")




