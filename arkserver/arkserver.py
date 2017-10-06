import discord
from discord.ext import commands
from redbot.core import Config
from datetime import datetime

import os
import sys
import asyncio
import glob
from subprocess import PIPE, Popen
from threading import Thread
import shlex


try:
	from Queue import Queue, Empty
except ImportError:
	from queue import Queue, Empty # python 3.x

ON_POSIX = 'posix' in sys.builtin_module_names

class HTTPException(Exception):
	pass

class arkserver:
	"""Ark Server commands"""



	def __init__(self, bot):
		self.bot = bot
		self.settings = Config.get_conf(self, 3931293439)
		self.updating = False
		self.cancel = False
		default_user = {
			"steamid": None
		}
		self.settings.register_global(
			Verbose=True,
			AutoUpdate=False,
			Map=None,
			Cache__map=None,
			Cache__players=None,
			Cache__version=None
		)
		self.settings.register_user(**default_user)


	def enqueue_output(self, out, queue):
		for line in iter(out.readline, b''):
			queue.put(line)
		out.close()

	async def runcommand(self, command, channel=None, verbose=False):
		"""This function runs a command in the terminal and uses a seperate thread to collect the response so it isn't blocking"""
		process = Popen(shlex.split(command), stdout=PIPE, bufsize=1, close_fds=ON_POSIX)
		q = Queue()
		t = Thread(target=self.enqueue_output, args=(process.stdout, q))
		t.daemon = True
		t.start()
		output = []
		list_replacements = ["[1;32m ", "[1;31m", "[0;39m   ", "[0;39m ", "[0;39m", "8[J", "[68G[   [1;32m", "  ]", "\033"]
		while True:
			try:
				try:
					readline = q.get_nowait().decode()
				except Empty:
					if t.isAlive() == False and q.empty() == True:
						break
					else:
						pass
				else: 
					if readline:
						if len(readline) > 1900:
							output.append("Line exceeded character limit.")
						else:
							output.append(readline)
						if verbose == True and channel != None:
							sani = readline.lstrip("7")
							for elem in list_replacements:
								sani = sani.replace(elem, "")
							try:
								await channel.send("{0}".format(sani))
							except Exception as e:
								print("Error posting to discord {0}, {1}".format(e, sani))
								pass

			except Exception as e:
				print("Something went wrong... you should check the status of the server with +ark status. {0}".format(e))
				print("Updating and restarting options will be locked for 3 minutes for safety.")
				self.updating = True
				await asyncio.sleep(180)
				self.updating = False
				if process.poll() is None:
					process.kill()
				return output
		return output
	
	@commands.group()
	@commands.has_role('ARK')
	async def ark(self, ctx):
		"""Commands related to Ark Server Management"""
		if ctx.invoked_subcommand is None:
			await self.bot.send_cmd_help(ctx)

	@ark.command()
	@commands.has_any_role('Admin', 'Moderator', 'Swole Cabbage')
	async def resetstatus(self, ctx):
		"""Resets bot and self.updating status."""
		self.updating = False
		currentmap = await self.settings.Cache.map()
		version = await self.settings.Cache.version()
		players = await self.settings.Cache.players()
		game = currentmap + ' ' + players + version
		await ctx.bot.change_presence(game=discord.Game(name=game),status=discord.Status.online)

	@commands.group()
	@commands.has_role('ARK')
	async def arkchar(self, ctx):
		"""Commands related to Ark Character Management"""
		if ctx.invoked_subcommand is None:
			await self.bot.send_cmd_help(ctx)

	@arkchar.command()
	@commands.is_owner()
	async def setid(self, ctx, userobject: discord.Member, *, inputid):
		"""Sets the steam identifier for the mentioned user, required to use any character commands"""
		if len(inputid) != 17:
			await ctx.send("That's not a valid steam ID.")
			return
		await self.settings.user(userobject).steamid.set(inputid)
		await ctx.send("Saved.")

	@arkchar.command()
	@commands.is_owner()
	async def showid(self, ctx, userobject: discord.Member):
		"""Shows the steam id of the mentioned user"""
		steamid = await self.settings.user(userobject).steamid()
		await ctx.send(steamid)

	@arkchar.command()
	async def list(self, ctx):
		"""Lists characters currently in storage"""
		steamid = await self.settings.user(ctx.author).steamid()
		if steamid == None:
			await ctx.send("You need to have your steam ID attached to your discord account by Redball before you can use this command.")
			return
		output = '```\nAvailable characters in storage:'
		directory = '/home/ark/ARK/ShooterGame/Saved/SavedArks/characters/'
		search = directory + steamid + '*'
		list_replacements = [steamid, directory, '.bak']
		for name in glob.glob(search):
			for elem in list_replacements:
				name = name.replace(elem, "")
			output += '\n' + name
		output += '```'
		await ctx.send(output)

	@arkchar.command()
	async def store(self, ctx, savename: str):
		"""Stores your current character to the specified name"""
		if len(savename) > 10:
			await ctx.send("Please use a name with 10 characters or less.")
			return
		if savename.isalpha() != True:
			await ctx.send("Please only use alphabetic characters in the savename.")
			return		
		steamid = await self.settings.user(ctx.author).steamid()
		if steamid == None:
			ctx.send("You need to have your steam ID attached to your discord account by Redball before you can use this command.")
			return
		source = '/home/ark/ARK/ShooterGame/Saved/SavedArks/' + steamid + '.arkprofile'
		destination = '/home/ark/ARK/ShooterGame/Saved/SavedArks/characters/' + steamid + savename + '.bak'
		if os.path.isfile(source) == False:
			await ctx.send("You don't have a character active at the moment.")
			return
		if os.path.isfile(destination) == True:
			await ctx.send("A file already exists with that name, please choose another.")
			return
		if await self.ingamecheck(steamid):
			await ctx.send("You need to leave the server before I can do this.")
			return
		try:
			os.rename(source, destination)
		except Exception as e:
			await ctx.send("An error occured {0} when trying to rename files.".format(e))
			return
		await ctx.send("Stored your current character as {0}.".format(savename))

	async def ingamecheck(self, steamid):
		output = await self.runcommand('arkmanager rconcmd "listplayers"')
		for line in output:
			if steamid in line:
				return True
		return False

	@arkchar.command()
	async def retrieve(self, ctx, savename: str):
		"""Retrieves the specificed character"""
		if savename.isalpha() != True:
			await ctx.send("Please only use alphabetic characters in the savename.")
			return		
		steamid = await self.settings.user(ctx.author).steamid()
		if steamid == None:
			ctx.send("You need to have your steam ID attached to your discord account by Redball before you can use this command.")
			return
		source = '/home/ark/ARK/ShooterGame/Saved/SavedArks/characters/' + steamid + savename + '.bak'
		destination = '/home/ark/ARK/ShooterGame/Saved/SavedArks/' + steamid + '.arkprofile'
		if os.path.isfile(source) == False:
			await ctx.send("That character doesn't exist in storage.")
			return
		if os.path.isfile(destination) == True:
			await ctx.send("You already have a character active, you need to store it first!")
			return
		output = await self.runcommand('arkmanager rconcmd "listplayers"', ctx.channel)
		if await self.ingamecheck(steamid):
			await ctx.send("You need to leave the server before I can do this.")
			return
		try:
			os.rename(source, destination)
		except Exception as e:
			await ctx.send("An error occured {0} when trying to rename files.".format(e))
			return
		await ctx.send("Character {0} is now active.".format(savename))
		

	@ark.command()
	@commands.is_owner()
	async def forcemap(self, ctx, minput : str = 'info'):
		"""Swaps the settings save file to a specific map."""
		if minput.lower() == 'ragnarok':
			desiredMap = 'Ragnarok'
		elif minput.lower() == 'island':
			desiredMap = 'TheIsland'
		elif minput.lower() == 'scorched':
			desiredMap = 'ScorchedEarth'
		elif minput.lower() == 'center':
			desiredMap = 'TheCenter'
		elif minput.lower() == 'aberration':
			desiredMap = 'Aberration'
		else:
			await ctx.send("I don't recognize that map, available options are Ragnarok, Island, Center, Aberration and Scorched")
			return
		await self.settings.Map.set(desiredMap)
		await ctx.send("Done.")	

	@ark.command()
	async def map(self, ctx, minput : str = 'info'):
		"""Swaps the server over to the desired map."""
		await ctx.channel.trigger_typing()
		if minput == 'info':
			await ctx.send("This command can swap the map the server is running on to the desired map. Options available are 'Ragnarok', 'Island', 'Center', 'Aberration' and 'Scorched'. (e.g +ark map ragnarok)")
			await ctx.send("Current map is {0}".format(await self.settings.Map()))
			return
		if self.updating == True: #don't change the map if the server is restarting or updating
			await ctx.send("I'm already carrying out a restart or update! <:banned:284492719202631680>")
			return
		if minput.lower() == 'ragnarok':
			desiredMap = 'Ragnarok'
		elif minput.lower() == 'island':
			desiredMap = 'TheIsland'
		elif minput.lower() == 'scorched':
			desiredMap = 'ScorchedEarth'
		elif minput.lower() == 'center':
			desiredMap = 'TheCenter'
		elif minput.lower() == 'aberration':
			desiredMap = 'Aberration'
		else:
			await ctx.send("I don't recognize that map, available options are Ragnarok, Island, Center and Scorched.")
			return
		if await self.settings.Map() == desiredMap:
			await ctx.send("The server is already running this map!") 
			await ctx.message.add_reaction(':youtried:336180558956593152')
			return
		if await self.emptycheck():
			await ctx.send("The map cannot be swapped while players are in the server.")
			await ctx.message.add_reaction(':youtried:336180558956593152')
			return
		message = await ctx.send("Map will be swapped to {0}, the server will need to be restarted to complete the change, react agree to confirm.".format(desiredMap))
		await message.add_reaction(':Agree:243888050441027585')
		def waitcheck(react, user):
			return react.emoji == self.bot.get_emoji(243888050441027585) and user == ctx.author  
		try:
			react, user = await self.bot.wait_for('reaction_add', check=waitcheck, timeout=30.0)
		except asyncio.TimeoutError:
			await message.clear_reactions()
			await message.edit(content="You took too long..")
			return
		await message.clear_reactions()
		await ctx.channel.trigger_typing()
		self.updating = True #prevents the bot from restarting or updating while this is happening
		try:
			if await self.settings.Map() == 'Ragnarok':
				os.rename('/etc/arkmanager/instances/main.cfg', '/etc/arkmanager/instances/rag.cfg')
			elif await self.settings.Map() == 'TheIsland':
				os.rename("/etc/arkmanager/instances/main.cfg", "/etc/arkmanager/instances/island.cfg")
			elif await self.settings.Map() == 'ScorchedEarth':
				os.rename("/etc/arkmanager/instances/main.cfg", "/etc/arkmanager/instances/scorched.cfg")
			elif await self.settings.Map() == 'TheCenter':
				os.rename("/etc/arkmanager/instances/main.cfg", "/etc/arkmanager/instances/center.cfg")
			elif await self.settings.Map() == 'Aberration':
				os.rename("/etc/arkmanager/instances/main.cfg", "/etc/arkmanager/instances/aberratiom.cfg")
		except FileNotFoundError as e:
			await ctx.send("An error occured {0} when trying to rename the current main.cfg")
			self.updating = False
			return
		try:
			if desiredMap == 'Ragnarok':
				os.rename("/etc/arkmanager/instances/rag.cfg", "/etc/arkmanager/instances/main.cfg")
			elif desiredMap == 'TheIsland':
				os.rename("/etc/arkmanager/instances/island.cfg", "/etc/arkmanager/instances/main.cfg")
			elif desiredMap == 'ScorchedEarth':
				os.rename("/etc/arkmanager/instances/scorched.cfg", "/etc/arkmanager/instances/main.cfg")
			elif desiredMap == 'TheCenter':
				os.rename("/etc/arkmanager/instances/center.cfg", "/etc/arkmanager/instances/main.cfg")
			elif desiredMap == 'Aberration':
				os.rename("/etc/arkmanager/instances/aberration.cfg", "/etc/arkmanager/instances/main.cfg")
		except FileNotFoundError as e:
			await ctx.send("An error occured {0} when trying to rename {1}.cfg to main.cfg".format(e, desiredMap))
			self.updating = False
			return
		await self.settings.Map.set(desiredMap)
		if await self.offlinecheck():
			await ctx.send("Server isn't running currently, I've swapped the map but the server still needs to be started.")
		else:
			output = await self.runcommand("arkmanager restart", ctx.channel, self.settings.Verbose())
		await ctx.bot.change_presence(game=discord.Game(name="Restarting Server"),status=discord.Status.dnd)
		if self.successcheck(output):
			await message.edit(content="Server is restarting...")
		else:
			try:
				await message.edit(content="Something went wrong \U0001F44F. {0}".format(output))
				self.updating = False
				return
			except:
				await message.edit(content="Something went wrong \U0001F44F")
				self.updating = False
				return
		status = ''
		while '\x1b[0;39m Server online:  \x1b[1;32m Yes \x1b[0;39m\n' not in status:
			await asyncio.sleep(15)
			status = await self.runcommand("arkmanager status")
		await message.edit(content="Map swapped to {0} and server is now running.".format(desiredMap))
		await ctx.bot.change_presence(game=discord.Game(name=None),status=discord.Status.online)
		self.updating = False

	@ark.command()
	async def checkupdate(self, ctx):
		"""Just checks for ark updates - use +ark update to start update"""
		if await self.updatechecker(ctx.channel, self.settings.Verbose()):
			await ctx.send("Updates are available!")
		else:
			await ctx.send("Your server is up to date!")

	@ark.command()
	async def checkmodupdate(self, ctx):
		"""Just checks for mod updates - use +ark update to start update"""
		if await self.checkmods(ctx.channel, self.settings.Verbose()):
			await ctx.send("Updates to some mods are available.")
		else:
			await ctx.send("No mod updates found.")		

	@ark.command(name="stop")
	@commands.has_any_role('Admin', 'Moderator', 'Swole Cabbage')
	async def ark_stop(self, ctx):
		"""Stops the Ark Server"""
		await ctx.channel.trigger_typing()
		output = await self.runcommand("arkmanager stop", ctx.channel, self.settings.Verbose())
		if await self.settings.Verbose() == False:
			output = self.sanitizeoutput(output)
			await ctx.send(output)

	@ark.command(name="players")
	async def ark_players(self, ctx):
		"""Lists players currently in the server."""
		output = await self.runcommand('arkmanager rconcmd "listplayers"', ctx.channel, False)
		players = "```Players ingame:"
		for line in output:
			if '.' in line:
				slot, name, steamid = line.split(' ',2)
				players += "\n" + name.rstrip(',')
		players += "```"
		await ctx.send(players)

	@ark.command(name="dinowipe")
	@commands.is_owner()
	async def ark_dinowipe(self, ctx):
		"""Runs DestroyWildDinos, useful for getting newly released creatures to spawn."""
		output = await self.runcommand('arkmanager rconcmd "destroywilddinos"', ctx.channel, True)

	@ark.command(name="autoupdate")
	@commands.is_owner()
	async def ark_autoupdate(self, ctx, toggle : str = 'info'):
		"""Toggles autoupdating"""
		togglestatus = await self.settings.AutoUpdate() #retrives current status of toggle from settings file
		if toggle.lower() == 'off':
			await self.settings.AutoUpdate.set(False)
			await ctx.send("Automatic updating is now disabled.")
		elif toggle.lower() == 'on':
			await self.settings.AutoUpdate.set(True)
			await ctx.send("Automatic server updating is now enabled.")
		else:
			if togglestatus == True:
				await ctx.send("Automatic updating is currently enabled.")
			elif togglestatus == False:
				await ctx.send("Automatic updating is currently disabled.")

	@ark.command(name="verbose")
	@commands.is_owner()
	async def ark_verbose(self, ctx, toggle : str = 'info'):
		"""Toggles command verbosity"""
		togglestatus = await self.settings.Verbose() #retrives current status of toggle from settings file
		if toggle.lower() == 'off':
			await self.settings.Verbose.set(False)
			await ctx.send("I will not be verbose when executing commands.")
		elif toggle.lower() == 'on':
			await self.settings.Verbose.set(True)
			await ctx.send("I will output all lines from the console when executing commands.")
		else:
			if togglestatus == True:
				await ctx.send("I am currently outputting all lines from the console when executing commands.")
			elif togglestatus == False:
				await ctx.send("I am currently not being verbose when executing commands.")

	@ark.command(name="start")
	@commands.has_any_role('Admin', 'Moderator', 'Swole Cabbage')
	async def ark_start(self, ctx):
		"""Starts the Ark Server"""
		await ctx.channel.trigger_typing()
		output = await self.runcommand("arkmanager start", ctx.channel, self.settings.Verbose())
		if await self.settings.Verbose() == False:
			output = self.sanitizeoutput(output)
			await ctx.send(output)

	@ark.command(name="status")
	async def ark_status(self, ctx):
		"""Checks the server status"""
		await ctx.channel.trigger_typing()
		output = await self.runcommand("arkmanager status", ctx.channel, self.settings.Verbose())
		if await self.settings.Verbose() == False:
			output = self.sanitizeoutput(output)
			await ctx.send(output)

	@ark.command(name="cancel")
	async def ark_cancel(self, ctx):
		"""Cancels a pending restart"""
		self.cancel = True
		await ctx.send("Restart cancelled.")

	@ark.command(name="restart")
	async def ark_restart(self, ctx, delay : int = 60):
		"""Restarts the ARK Server with a user specificed delay (in seconds)"""
		def waitcheck(m):
			return m.author == ctx.author and m.channel == ctx.channel
		try:
			int(delay)
		except ValueError:
			try:
				float(delay)
			except ValueError:
				await ctx.send("Delay entered must be a number!")
				return
		if delay > 900:
			delay = 900
		output = await self.runcommand("arkmanager status", ctx.channel, False)
		if await self.emptycheck():
			await ctx.send("Players are currently in the server, restart anyway?")
			answer = await self.bot.wait_for('message', check=waitcheck)
			try:	
				if answer.content.lower() != "yes":
					await ctx.send("Okay, restart cancelled.")
					return
			except:
				await ctx.send("Okay, restart cancelled.")
				return
		if self.updating == True:
			await ctx.send("I'm already carrying out a restart or update! <:banned:284492719202631680>")
		else:
			self.updating = True
			self.cancel = False
			await ctx.send("Restarting in {0} seconds.".format(delay))
			await ctx.bot.change_presence(game=discord.Game(name="Restarting Server"),status=discord.Status.dnd)
			command = 'arkmanager broadcast "Server will shutdown for a user-requested restart in ' + str(delay) + ' seconds."'
			alert = await self.runcommand(command, ctx.channel, False)
			await asyncio.sleep(delay)
			if self.cancel != True:
				output = await self.runcommand("arkmanager restart", ctx.channel, await self.settings.Verbose())
				await ctx.bot.change_presence(game=discord.Game(name=None),status=discord.Status.online)
				self.updating = False
				if self.successcheck(output):
					message = await channel.send("Server is restarting...")
					status = ''
					while '\x1b[0;39m Server online:  \x1b[1;32m Yes \x1b[0;39m\n' not in status:
						await asyncio.sleep(15)
						status = await self.runcommand("arkmanager status")
					await message.edit(content="Server is up.")
					await self.bot.change_presence(game=discord.Game(name=None),status=discord.Status.online)
					self.updating = False
				else:
					try:
						await ctx.send("Something went wrong \U0001F44F. {0}".format(output))
					except:
						await ctx.send("Something went wrong \U0001F44F")
					await ctx.bot.change_presence(game=discord.Game(name=None),status=discord.Status.online)
					self.updating = False
			else:
				self.cancel = False
				alert = await self.runcommand('arkmanager broadcast "Restart was cancelled by user request."', ctx.channel, False)
				await ctx.bot.change_presence(game=discord.Game(name=None),status=discord.Status.online)
				self.updating = False
				#restart was cancelled

	@ark.command(name="update")
	async def ark_update(self, ctx):
		"""Checks for updates and if any are found, downloads, then restarts the server"""
		def waitcheck(m):
			return m.author == ctx.author and m.channel == ctx.channel
		status = await self.updatechecker(ctx.channel, self.settings.Verbose())
		modstatus = await self.checkmods(ctx.channel, self.settings.Verbose())
		if status == True or modstatus == True:
			await ctx.send("Updates are available.")
			empty = await self.runcommand("arkmanager status", ctx.channel, False)
			if await self.emptycheck():
				await ctx.send("Players are currently in the server, update anyway?")
				answer = await self.bot.wait_for('message', check=waitcheck)
				try:	
					if answer.content.lower() != "yes":
						await ctx.send("Okay, restart cancelled.")
						return
				except:
					await ctx.send("Okay, restart cancelled.")
					return
			await ctx.send("Server will be restarted in 60 seconds.")
			if self.updating == True:
				await ctx.send("I'm already carrying out a restart or update! <:banned:284492719202631680>")
			else:
				self.updating = True
				await ctx.bot.change_presence(game=discord.Game(name="Updating Server"),status=discord.Status.dnd)
				alert = await self.runcommand('arkmanager broadcast "Server will shutdown for updates in 60 seconds."', ctx.channel, False)
				await asyncio.sleep(60)
				output = await self.runcommand("arkmanager update --update-mods --backup", ctx.channel, await self.settings.Verbose())
				if self.successcheck(output):
					message = await channel.send("Server is updating...")
					status = ''
					while '\x1b[0;39m Server online:  \x1b[1;32m Yes \x1b[0;39m\n' not in status:
						await asyncio.sleep(15)
						status = await self.runcommand("arkmanager status")
					await message.edit(content="Server has been updated and is now online.")
					await self.bot.change_presence(game=discord.Game(name=None),status=discord.Status.online)
					self.updating = False
				else:
					try:
						await ctx.send("Something went wrong \U0001F44F. {0}".format(output))
					except:
						await ctx.send("Something went wrong \U0001F44F")
					await ctx.bot.change_presence(game=discord.Game(name=None),status=discord.Status.online)
					self.updating = False
		else:
			await ctx.send("No updates found.")

	@ark.command(name="save")
	@commands.is_owner()
	async def ark_save(self, ctx):
		"""Saves the world state"""
		output = await self.runcommand("arkmanager saveworld", ctx.channel, True)

	@ark.command(name="backup")
	@commands.is_owner()
	async def ark_backup(self, ctx):
		"""Creates a backup of the save and config files"""
		output = await self.runcommand("arkmanager backup", ctx.channel, True)

	@ark.command(name="updatenow")
	@commands.is_owner()
	async def ark_updatenow(self, ctx):
		"""Updates withn no delay or empty checks"""
		output = await self.runcommand("arkmanager update --update-mods --backup", ctx.channel, True)

	@ark.command(name="validate")
	@commands.is_owner()
	async def ark_validate(self, ctx):
		"""Validates the server files with steamcmd"""
		output = await self.runcommand("arkmanager update --validate", ctx.channel, True)

	@ark.command(name="forceupdate")
	@commands.is_owner()
	async def ark_forceupdate(self, ctx):
		"""Updates without warning with the -force parameter"""
		output = self.runcommand("arkmanager update --update-mods --backup --force", ctx.channel, True)

	async def checkmods(self, channel=None, verbose=False):
		output = await self.runcommand("arkmanager checkmodupdate", channel, verbose)
		for line in output:
			if 'has been updated on the Steam workshop' in line:
				return True
		return False

	async def updatechecker(self, channel=None, verbose=False):
		output = await self.runcommand("arkmanager checkupdate", channel, verbose)
		if 'Your server is up to date!\n' in output:
			return False
		else:
			return True

	async def emptycheck(self, channel=None, verbose=False):
		output = await self.runcommand("arkmanager status", channel, verbose)
		for line in output:
			if 'Players: 0' in line:
				return False
		return True

	async def offlinecheck(self, channel=None, verbose=False):
		output = await self.runcommand("arkmanager status")
		if '\x1b[0;39m Server online:  \x1b[1;32m Yes \x1b[0;39m\n' in output:
			return False
		else:
			return True


	def successcheck(self, output):
		for line in output:
			if 'The server is now running, and should be up within 10 minutes' in line:
				return True
		return False

	def sanitizeoutput(self, output):
		list_replacements = ["[1;32m ", "7", "[1;31m", "[0;39m   ", "[0;39m ", "[0;39m", "8[J", "[68G[   [1;32m", "  ]", "\033"]
		message = "```"
		for elem in output:
			for item in list_replacements:
				elem = elem.replace(item, "")
			message += elem
		message += "```"
		return message

	async def presence_manager(self):
		"""Reports server status using discord status"""
		while self is self.bot.get_cog("arkserver"):
			if self.updating == False:
				difference = False
				currentmap = await self.settings.Map()
				if currentmap != await self.settings.Cache.map():
					difference = True
					await self.settings.Cache.map.set(currentmap)
				output = await self.runcommand("arkmanager status")
				if '\x1b[0;39m Server online:  \x1b[1;32m Yes \x1b[0;39m\n' not in output:
					await self.bot.change_presence(game=discord.Game(name="Server is offline!"),status=discord.Status.dnd)
					if await self.settings.Cache.map() != 'Offline':
						await self.settings.Cache.map.set('Offline')
					await asyncio.sleep(30)
				else:
					for line in output:
						if 'Players:' in line and 'Active' not in line:
							players = line
						if 'Server Name' in line:
							version = '(' + line.split('(')[1]
					if players != await self.settings.Cache.players():
						difference = True
						await self.settings.Cache.players.set(players)
					if version != await self.settings.Cache.version():
						difference = True
						await self.settings.Cache.version.set(version)
					if difference:
						message = currentmap + ' ' + players + version
						await self.bot.change_presence(game=discord.Game(name=message), status=discord.Status.online)
					await asyncio.sleep(30)
			await asyncio.sleep(15)

	async def update_checker(self):
		"""Checks for updates automatically every hour"""
		while self is self.bot.get_cog("arkserver"):
			await asyncio.sleep(60)
			if await self.settings.AutoUpdate() == True: #proceed only if autoupdating is enabled
				if self.updating == False: #proceed only if the bot isn't already manually updating or restarting
					try:
						verbose =  await self.settings.Verbose()
						adminchannel = self.bot.get_channel(331076958425186305)
						channel = self.bot.get_channel(333605978560004097)
						status = await self.updatechecker()
						modstatus = await self.checkmods()
						print("Update check completed at {0}".format(datetime.utcnow()))
					except Exception as e:
						print("checkupdate commands encountered an exception {0}".format(e))
						await asyncio.sleep(240)
						status = ''
					if status == True or modstatus == True: #proceed with update if checkupdate tells us that an update is available
						if await self.emptycheck():
							#players detected in the server, queue update for in 15 minutes
							alert = await self.runcommand('arkmanager broadcast "Server will shutdown for updates in 15 minutes."', channel, False)
							await asyncio.sleep(300)
							alert = await self.runcommand('arkmanager broadcast "Server will shutdown for updates in 10 minutes."', channel, False)
							await asyncio.sleep(300)
							alert = await self.runcommand('arkmanager broadcast "Server will shutdown for updates in 5 minutes."', channel, False)
							await asyncio.sleep(240)
							alert = await self.runcommand('arkmanager broadcast "Server will shutdown for updates in 60 seconds."', channel, False)
							await asyncio.sleep(60)
							if self.updating == False:
								await self.bot.change_presence(game=discord.Game(name="Updating Server"),status=discord.Status.dnd)
								self.updating = True
								update = await self.runcommand("arkmanager update --update-mods --backup", adminchannel, True)
								if self.successcheck(update):									
									message = await channel.send("Server is updating...")
									status = ''
									while '\x1b[0;39m Server online:  \x1b[1;32m Yes \x1b[0;39m\n' not in status:
										await asyncio.sleep(15)
										status = await self.runcommand("arkmanager status")
									await message.edit(content="Server has been updated and is now online.")
									await self.bot.change_presence(game=discord.Game(name=None),status=discord.Status.online)
									self.updating = False
								else:
									await channel.send("Something went wrong during automatic update")
									await self.bot.change_presence(game=discord.Game(name=None),status=discord.Status.online)
									self.updating = False
							else:
								print("Manual update or restart was triggered during 15 minute delay, automatic update has been cancelled")
						else:
							update = await self.runcommand("arkmanager update --update-mods --backup", adminchannel, True)
							if self.successcheck(update):									
								message = await channel.send("Server is updating...")
								status = ''
								while '\x1b[0;39m Server online:  \x1b[1;32m Yes \x1b[0;39m\n' not in status:
									await asyncio.sleep(15)
									status = await self.runcommand("arkmanager status")
								await message.edit(content="Server has been updated and is now online.")
								await self.bot.change_presence(game=discord.Game(name=None),status=discord.Status.online)
								self.updating = False
							else:
								await channel.send("Something went wrong during automatic update")
								await self.bot.change_presence(game=discord.Game(name=None),status=discord.Status.online)
								self.updating = False
					else:
						await asyncio.sleep(3540)
				else:
					print("Server is already updating or restarting, auto-update cancelled")
					
