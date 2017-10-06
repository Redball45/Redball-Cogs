import discord
from discord.ext import commands
from redbot.core import Config

import asyncio
import os

class Welcome:
	"""Welcomes members to the server. Taken from irdumbs welcome cog https://github.com/irdumbs/Dumb-Cogs/blob/master/welcome/welcome.py, rewritten for Red-DiscordBot V3"""

	def __init__(self, bot):
		self.bot = bot
		self.settings = Config.get_conf(self, 21931)
		default_guild = {
			"GREETING": "Welcome {0.name} to {1.name}!",
			"ON": False,
			"CHANNEL": None,
			"WHISPER": False,
			"ROLE": None,
			"LOGCHANNEL": None,
			"GUILDMASTER": None,
			"GUILDNAME": None
			}
		default_user = {
			"WELCOMED": False,
			"IGN": None
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
			#send current settings to user
			greeting = await self.settings.guild(ctx.guild).GREETING()
			channel = await self.get_welcome_channel(ctx.guild)
			toggle = await self.settings.guild(ctx.guild).ON()
			whisper = await self.settings.guild(ctx.guild).WHISPER()
			role = await self.settings.guild(ctx.guild).ROLE()
			logchannel = await self.settings.guild(ctx.guild).LOGCHANNEL()
			msg = "```"
			msg += "GREETING: {}\n".format(greeting)
			msg += "CHANNEL: #{}\n".format(channel)
			msg += "ON: {}\n".format(toggle)
			msg += "WHISPER: {}\n".format(whisper)
			msg += "ROLE: {}\n".format(role)
			msg += "LOGCHANNEL: {}\n".format(logchannel)
			msg += "```"
			await ctx.send(msg)

	@welcomeset.command()
	@commands.is_owner()
	async def testwelcome(self, ctx):
		"""Sends a test welcome message, user that used the command is the one welcomed"""
		user = ctx.author
		try:
			await self.on_join(user)
		except Exception as e:
			await ctx.send(e)

	@welcomeset.command()
	@commands.is_owner()
	async def resetwelcome(self, ctx):
		"""Resets WELCOMED, useful for testing"""
		msg = await self.settings.user(ctx.author).WELCOMED()
		await ctx.send(msg)
		await self.settings.user(ctx.author).WELCOMED.set(False)
		msg = await self.settings.user(ctx.author).WELCOMED()
		await ctx.send(msg)
		

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
		"""Turns on/off welcoming new users to the server via whisper"""
		await self.settings.guild(ctx.guild).WHISPER.set(on_off)
		if await self.settings.guild(ctx.guild).WHISPER():
			await ctx.send("I will now whisper the greeting message to users.")
		else:
			await ctx.send("I will send an introduction message to the specified channel instead of whispering.")


	@welcomeset.command()
	async def role(self, ctx, role: discord.Role=None):
		"""Sets the role to give users once they link their GW2 account"""
		if role == None:
			await self.bot.send_cmd_help(ctx)
			return
		await self.settings.guild(ctx.guild).ROLE.set(role.name)
		await ctx.send("Users that join this server will be given the {0.name} role once they link their GW2 account.".format(role))

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
	async def logchannel(self, ctx, channel : discord.TextChannel):
		"""Sets the channel to send the logs of new users"""
		server = ctx.message.guild
		if channel is None:
			await self.bot.send_cmd_help(ctx)
		if not server.get_member(self.bot.user.id
								 ).permissions_in(channel).send_messages:
			await ctx.send("I do not have permissions to send "
							   "messages to {0.mention}".format(channel))
			return
		await self.settings.guild(ctx.guild).LOGCHANNEL.set(channel.id)
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

	@commands.command()
	async def tktregister(self, ctx, *, message):
		"""Ties your GW2 account name to your discord account, e.g !tktregister Redball.7236"""
		if await self.verify_gw2(ctx.message):
			await ctx.send("Verified!")
		else:
			await ctx.send("Sorry, I couldn't match you to the roster, please check the account name you entered e.g Redball.7236 and try again")

	@commands.group()
	@commands.guild_only()
	@commands.has_any_role('Knight Templar', 'Inquisitor', 'Admin')
	async def tktcheck(self, ctx, user: discord.Member):
		"""Checks the account name of the specified, you can mention them or use their discriminator"""
		username = await self.settings.user(user).IGN()
		if username:
			await ctx.send(username)
		else:
			await ctx.send("You haven't set a username, use !tktregister (account name) to do so.")
		if await self.verify_gw2:
			await ctx.send("This user is in the guild.")
		else:
			await ctx.send("This user is no longer in the guild.")

	@commands.group()
	@commands.guild_only()
	@commands.check(permcheck)
	async def welcomeguild(self, ctx):
		"""Sets welcome module settings"""
		if ctx.invoked_subcommand is None:
			await self.bot.send_cmd_help(ctx)
			name = await self.settings.guild(ctx.guild).GUILDNAME()
			leader = await self.settings.guild(ctx.guild).GUILDMASTER()
			msg = '```'
			msg += "NAME: {}\n".format(name)
			msg += "LEADER: #{}\n".format(leader)
			msg += "```"
			await ctx.send(msg)

	@welcomeguild.command()
	async def leader(self, ctx, user: discord.Member):
		await self.settings.guild(ctx.guild).GUILDMASTER.set(user.id)
		await ctx.send("Guild Master set to UID {0}".format(user.id))

	@welcomeguild.command()
	async def guildname(self, ctx, *, guild_name: str):
		"""Sets the guild name - MUST MATCH INGAME"""
		await self.settings.guild(ctx.guild).GUILDNAME.set(guild_name)
		await ctx.send("Guild Name set to {0}".format(guild_name))

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

	async def getmembers(self, guild):
		scopes = ["guilds"]
		guild_name = await self.settings.guild(guild).GUILDNAME()
		try:
			GW2 = self.bot.get_cog("GuildWars2")
		except Exception as e:
			print('GW2 cog might not be loaded?')
			print(e)
		endpoint_id = "guild/search?name=" + guild_name.replace(' ', '%20')
		try:
			guild_id = await GW2.call_api(endpoint_id)
			guild_id = guild_id[0]
			endpoint = "guild/{}/members".format(guild_id)
			gmid = await self.settings.guild(guild).GUILDMASTER()
			gm = await self.bot.get_user_info(gmid)
			results = await GW2.call_api(endpoint, gm, scopes)
			return results
		except Exception as e:
			print(e)
			return None     	

	async def verify_gw2(self, message):
		memberlist = await self.getmembers(message.guild)
		if memberlist == None:
			return False
		for member in memberlist:
			if member["name"] in message.content:
				await self.settings.user(message.author).IGN.set(member["name"])
				return True
		return False

	async def on_intro(self, message):
		if message.guild == None:
			return
		if message.author.bot == True:
			return
		if not await self.settings.guild(message.guild).ON():
			return
		welcomechannel = await self.settings.guild(message.guild).CHANNEL()		
		if message.channel.id != welcomechannel:
			return
		if await self.settings.user(message.author).WELCOMED():
			return
		gmid = await self.settings.guild(message.guild).GUILDMASTER()
		guild_name = await self.settings.guild(message.guild).GUILDNAME()
		if gmid == None or guild_name == None:
			print('Please setup the Guild Master and Guild Name to use welcome functions')
			return
		welcomechan = self.bot.get_channel(welcomechannel)
		chid = await self.settings.guild(message.guild).LOGCHANNEL()
		channel = self.bot.get_channel(chid)
		if not await self.verify_gw2(message):
			reply = await welcomechan.send("Sorry, I couldn't match you to the roster, please check the account name you entered e.g Redball.7236 and try again")
			await asyncio.sleep(30)
			try:
				await reply.delete()
			except:
				pass
			return
		rolename = await self.settings.guild(message.guild).ROLE()
		try:
			role = discord.utils.get(message.guild.roles, name=rolename)
			await message.author.add_roles(role, reason="Welcome cog check passed")
			if channel != None:
				await channel.send("{0.name} has been given the {1.name} role.".format(message.author, role))
		except:
			if channel != None:
				await channel.send("Something went wrong when I tried to give {0.name} the {1.name} role :(".format(message.author, role))
		await self.settings.user(message.author).WELCOMED.set(True)
		reply = await welcomechan.send("Verified!")
		await asyncio.sleep(30)
		try:
			await reply.delete()
			await message.delete()
		except:
			pass
		return

