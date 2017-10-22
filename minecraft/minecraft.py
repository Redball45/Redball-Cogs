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
		self.session = pyscreen.get_session_with_name('minecraft')


	
	@commands.group()
	@commands.is_owner()
	async def mc(self, ctx):
		"""Commands related to Minecraft Server Management"""
		if ctx.invoked_subcommand is None:
			await self.bot.send_cmd_help(ctx)

	@mc.command()
	async def start(self, ctx):
		"""Starts the minecraft server"""
		if not self.session:
			self.session = pyscreen.ScreenSession('minecraft')
			self.session.send_command('bash /home/ark/minecraft/craftbukkit.sh', True)
			return await ctx.send("Server started.")
		await ctx.send("Server already running.")

	@mc.command()
	async def stop(self, ctx):
		"""Stops the server and screen session"""
		if self.session:
			self.session.send_command('stop', False)
			await asyncio.sleep(10)
			#self.session.kill()
			return await ctx.send("Server stopped.")
		await ctx.send("No active session.")


	@mc.command()
	async def allsessions(self, ctx):
		"""Print all active screen sessions"""
		sessions = pyscreen.get_all_sessions()
		await ctx.send(sessions)
		



