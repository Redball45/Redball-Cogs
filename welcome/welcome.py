import discord
from discord.ext import commands
from redbot.core import Config

import asyncio
import os

default_greeting = "Welcome {0.name} to {1.name}!"
default_settings = {"GREETING": [default_greeting], "ON": False,
					"CHANNEL": None, "WHISPER": False}

class Welcome:
	"""Welcomes members to the server. Taken from irdumbs welcome cog https://github.com/irdumbs/Dumb-Cogs/blob/master/welcome/welcome.py, rewritten for Red-DiscordBot V3"""

	def __init__(self, bot):
		self.bot = bot
		self.settings = Config.get_conf(self, 21931)
		default_guild = {
			"GREETING": [default_greeting],
			"ON": False,
			"CHANNEL": None,
			"WHISPER": False
			}
		default_user = {
			"WELCOMED": False
		}
		self.settings.register_guild(**default_guild)
		self.settings.register_user(**default_user)

	def permcheck(ctx):
		return ctx.message.author.id == 77910702664200192 or ctx.message.author.id == 158543628648710144 and ctx.message.guild.id == 171970841100288000

	@commands.group()
	@commands.guild_only()
	@commands.check(permcheck)
	async def welcomeset(self, ctx):
		"""Sets welcome module settings"""
		if ctx.invoked_subcommand is None:
			await self.bot.send_cmd_help(ctx)
			greeting = await self.settings.guild(ctx.guild).GREETING()
			channel = await self.get_welcome_channel(ctx.guild)
			toggle = await self.settings.guild(ctx.guild).ON()
			whisper = await self.settings.guild(ctx.guild).WHISPER()
			msg = "```"
			msg += "GREETING: {}\n".format(greeting)
			msg += "CHANNEL: #{}\n".format(channel)
			msg += "ON: {}\n".format(toggle)
			msg += "WHISPER: {}\n".format(whisper)
			msg += "```"
			await ctx.send(msg)

	@welcomeset.command()
	async def testwelcome(self, ctx):
		"""Sends a test welcome message"""
		user = ctx.author
		try:
			await self.on_join(user)
		except Exception as e:
			await ctx.send(e)

	@welcomeset.command()
	async def toggle(self, ctx, on_off: bool):
		"""Turns on/off welcoming new users to the server"""
		await self.settings.guild(ctx.guild).ON.set(on_off)
		if await self.settings.guild(ctx.guild).ON():
			await ctx.send("I will now welcome new users to the server.")
		else:
			await ctx.send("I will no longer welcome new users.")

	@welcomeset.command()
	async def whisper(self, ctx, on_off: bool):
		"""Turns on/off welcoming new users to the server"""
		await self.settings.guild(ctx.guild).WHISPER.set(on_off)
		if await self.settings.guild(ctx.guild).WHISPER():
			await ctx.send("I will now whisper the greeting message to users.")
		else:
			await ctx.send("I will send an introduction message to the specified channel instead of whispering.")

	@welcomeset.command()
	async def channel(self, ctx, channel : discord.TextChannel):
		"""Sets the channel to send the welcome message"""
		server = ctx.message.guild
		if channel is None:
			await self.bot.send_cmd_help(ctx)
		if not server.get_member(self.bot.user.id
								 ).permissions_in(channel).send_messages:
			await ctx.send("I do not have permissions to send "
							   "messages to {0.mention}".format(channel))
			return
		await self.settings.guild(ctx.guild).CHANNEL.set(channel.id)
		channel = await self.get_welcome_channel(server)
		await ctx.send("I will now send welcome "
									"messages to {0.mention}".format(channel))


	@welcomeset.command()
	async def message(self, ctx, *, format_msg):
		"""Adds a welcome message for this server
		{0} is user
		{1} is server
		Default is set to:
			Welcome {0.name} to {1.name}!
		Example formats:
			{0.mention}.. What are you doing here?
			{1.name} has a new member! {0.name}#{0.discriminator} - {0.id}
			Someone new joined! Who is it?! D: IS HE HERE TO HURT US?!"""
		server = ctx.message.guild
		await self.settings.guild(ctx.guild).GREETING.set(format_msg)
		await ctx.send("Welcome message set for the server.")

	async def get_welcome_channel(self, server):
		try:
			chanid = await self.settings.guild(server).CHANNEL()
			channel = self.bot.get_channel(chanid)
			return channel
		except Exception as e:
			print("The error is {0}".format(e))
			return None

	async def speak_permissions(self, server):
		channel = await self.get_welcome_channel(server)
		if channel is None:
			return False
		return server.get_member(self.bot.user.id).permissions_in(channel).send_messages

	async def on_join(self, member):
		server = member.guild
		if not await self.settings.guild(server).ON():
			return
		if member.guild is None:
			return
		msg = await self.settings.guild(server).GREETING()
		whisper = await self.settings.guild(server).WHISPER()
		if whisper:
			try:
				await member.send(msg.format(member, server))
			except:
				print("welcome.py: unable to whisper {}. Probably "
					  "doesn't want to be PM'd".format(member))
		channel = await self.get_welcome_channel(server)
		if channel is None:
			print('welcome.py: Channel not found. It was most '
						'likely deleted. User joined: {}'.format(member.name))
			return
		if whisper:
			return
		if not await self.speak_permissions(server):
			print("Permissions Error. User that joined: "
				  "{0.name}".format(member))
			print("Bot doesn't have permissions to send messages to "
				  "{0.name}'s #{1.name} channel".format(server, channel))
			return
		await channel.send(msg.format(member, server))

	async def on_intro(self, message):
		if message.channel != 344634206170644480:
			return
		if await self.settings.user(message.author).WELCOMED():
			return
		else:
			channel = self.bot.get_channel(295213438962106389)
			await channel.send("@here, {0.name} just introduced themselves in <#296657796110483457>!".format(message.author))
			await self.settings.user(message.author).WELCOMED.set(True):

