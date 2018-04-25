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
			SetupDone=False,
			ARKDataDirectory=None,
			ARKManagerConfigDirectory=None,
			ARKStorageDirectory=None,
			Channel=None,
			AdminChannel=None
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
	
	@commands.command()
	@commands.is_owner()
	async def arksetup(self, ctx):
		"""Interactive setup process"""
		def waitcheck(m):
			return m.author == ctx.author and m.channel == ctx.channel
		try:
			await ctx.send("This setup process will set required options for this cog to function. For each question, you should respond with desired setting.")
			await ctx.send("First, please repond with the location the ARK Dedicated Server is installed to. This should be the top level directory. For example, '/home/[your username]/ARK/'.")
			answer = await self.bot.wait_for('message', check=waitcheck, timeout=30)
			ARKDedi = answer.content
			await ctx.send("Next, please respond with the location arkmanager configuration files are located. Unless you changed this, the default is usually '/etc/arkmanager/'.")
			answer = await self.bot.wait_for('message', check=waitcheck, timeout=30)
			ARKManager = answer.content
			await ctx.send("Next, please repond with a location to store inactive character and world save files, used for the map swapping and character swap features.")
			answer = await self.bot.wait_for('message', check=waitcheck, timeout=30)
			ARKStorage = answer.content
			await ctx.send("You have chosen:\n{0} as the server installation location.\n{1} as the arkmanager configuration location.\n{2} as the additional storage location.\nReply 'Yes' to confirm these settings and complete setup.".format(ARKDedi, ARKManager, ARKStorage))
			answer = await self.bot.wait_for('message', check=waitcheck, timeout=30)
			if answer.content.lower() != 'yes':
				return await ctx.send("Okay, setup cancelled.")
		except asyncio.TimeoutError:
			return await ctx.send("You didn't reply in time, setup cancelled.")
		await self.settings.ARKDataDirectory.set(ARKDedi)
		await self.settings.ARKManagerConfigDirectory.set(ARKManager)
		await self.settings.ARKStorageDirectory.set(ARKStorage)
		await self.settings.SetupDone.set(True)
		await ctx.send("Setup complete. If you need to change any of these settings, simply re-run this setup command.")

	async def setupCheck(ctx):
		"""Because the help formatter uses this check outside the arkserver cog, to access the cog settings we need to get them seperately here"""
		from redbot.core import Config
		settings = Config.get_conf(None, 3931293439, False, 'arkserver')
		return await settings.SetupDone()

	@commands.command()
	@commands.is_owner()
	async def arksettings(self, ctx):
		"""Displays the current data settings and whether setup is complete"""
		ARKDedi = await self.settings.ARKDataDirectory()
		ARKManager = await self.settings.ARKManagerConfigDirectory()
		ARKStorage = await self.settings.ARKStorageDirectory()
		ARKChannel = await self.settings.Channel()
		ARKAdminChannel = await self.settings.AdminChannel()
		SetupDone = await self.settings.SetupDone()
		await ctx.send("{0} is the server installation location.\n{1} is the arkmanager configuration location.\n{2} is the "
			"additional storage location.\nSetup complete? {3}\nSelected channel ID {4}.\nSelected admin channel ID {5}.".format(ARKDedi, ARKManager, ARKStorage, SetupDone, ARKChannel, ARKAdminChannel))


	@commands.group()
	@commands.has_role('ARK')
	@commands.check(setupCheck)
	async def ark(self, ctx):
		"""Commands related to Ark Server Management"""
		if ctx.invoked_subcommand is None:
			return await ctx.send_help()

	@commands.group()
	@commands.is_owner()
	@commands.check(setupCheck)
	async def arkadmin(self, ctx):
		"""Commands related to Ark Server Administration"""
		if ctx.invoked_subcommand is None:
			return await ctx.send_help()

	@arkadmin.command()
	async def resetstatus(self, ctx):
		"""Resets bot and the update lock"""
		self.updating = False


	@commands.group()
	@commands.has_role('ARK')
	@commands.check(setupCheck)
	async def arkchar(self, ctx):
		"""Commands related to Ark Character Management"""
		if ctx.invoked_subcommand is None:
			return await ctx.send_help()

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
		if steamid:
			await ctx.send(steamid)
		else:
			await ctx.send("No steamid attached to this user.")

	@arkchar.command()
	async def list(self, ctx):
		"""Lists characters currently in storage"""
		steamid = await self.settings.user(ctx.author).steamid()
		if steamid == None:
			await ctx.send("You need to have your steam ID attached to your discord account by my owner before you can use this command.")
			return
		output = '```\nAvailable characters in storage:'
		directory = await self.settings.ARKStorageDirectory()
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
			ctx.send("You need to have your steam ID attached to your discord account by my owner before you can use this command.")
			return
		source = await self.settings.ARKDataDirectory() + 'ShooterGame/Saved/SavedArks/' + steamid + '.arkprofile'
		destination = await self.settings.ARKStorageDirectory() + steamid + savename + '.bak'
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
			ctx.send("You need to have your steam ID attached to your discord account by my owner before you can use this command.")
			return
		source = await self.settings.ARKStorageDirectory() + steamid + savename + '.bak'
		destination = await self.settings.ARKDataDirectory() + 'ShooterGame/Saved/SavedArks/' + steamid + '.arkprofile'
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
		

	@arkadmin.command()
	async def forcemap(self, ctx, minput : str = 'info'):
		"""Swaps the settings save file to a specific map."""
		if minput.lower() == 'ragnarok':
			desiredMap = 'Ragnarok'
		elif minput.lower() == 'island':
			desiredMap = 'TheIsland'
		elif minput.lower() == 'scorched':
			desiredMap = 'ScorchedEarth_P'
		elif minput.lower() == 'center':
			desiredMap = 'TheCenter'
		elif minput.lower() == 'aberration':
			desiredMap = 'Aberration_P'
		elif minput.lower() == 'crystalisles':
			desiredMap = 'CrystalIsles'
		else:
			await ctx.send("I don't recognize that map, available options are {0}.".format(availableMaps))
			return
		await self.settings.Map.set(desiredMap)
		await ctx.send("Done.")	

	@ark.command()
	async def map(self, ctx, minput : str = 'info'):
		"""Swaps the server over to the desired map. This works by renaming instance configuration files."""
		await ctx.channel.trigger_typing()
		availableMaps = await self.detectMaps()
		if minput == 'info':
			await ctx.send("This command can swap the map the server is running on to the desired map. Options available are {0}. (e.g +ark map ragnarok)".format(availableMaps))
			await ctx.send("Current map is {0}".format(await self.settings.Map()))
			return
		if self.updating == True: #don't change the map if the server is restarting or updating
			await ctx.send("I'm already carrying out a restart or update!")
			return
		if await self.emptycheck():
			await ctx.send("The map cannot be swapped while players are in the server.")
			return
		desiredMap = next((s for s in availableMaps if minput.lower() in s), None)
		if not desiredMap:
			await ctx.send("I don't recognize that map, available options are {0}.".format(availableMaps))
			return
		if await self.settings.Map() == desiredMap:
			await ctx.send("The server is already running this map!") 
			return
		message = await ctx.send("Map will be swapped to {0}, the server will need to be restarted to complete the change, react agree to confirm.".format(desiredMap))
		await message.add_reaction('✔')
		def waitcheck(react, user):
			return react.emoji == '✔' and user == ctx.author  
		try:
			react, user = await self.bot.wait_for('reaction_add', check=waitcheck, timeout=30.0)
		except asyncio.TimeoutError:
			await message.clear_reactions()
			await message.edit(content="You took too long..")
			return
		await message.clear_reactions()
		await ctx.channel.trigger_typing()
		output = await self.runcommand("arkmanager stop", ctx.channel, await self.settings.Verbose())
		activeSaveLocation = await self.settings.ARKDataDirectory() + 'ShooterGame/Saved/SavedArks/'
		inactiveLocation = await self.settings.ARKStorageDirectory()
		configLocation = await self.settings.ARKManagerConfigDirectory() + 'instances/'
		self.updating = True #prevents the bot from restarting or updating while this is happening
		try:
			confTarget = configLocation + 'main.cfg'
			confDestination = configLocation + await self.settings.Map() + '.cfg'
			target = activeSaveLocation + await self.settings.Map() + '.ark'
			destination = await self.settings.ARKStorageDirectory() + await self.settings.Map() + '.ark'
			os.rename(confTarget, confDestination)
			os.rename(target, destination)
		except FileNotFoundError as e:
			await ctx.send("An error occured {0} when trying to rename files. Manual intervention required.".format(e))
			self.updating = False
			return
		try:
			rConfTarget = configLocation + desiredMap + '.cfg'
			rConfDestination = configLocation + 'main.cfg'
			rTarget = await self.settings.ARKStorageDirectory() + desiredMap + '.ark'
			rDestination = activeSaveLocation + desiredMap + '.ark'
			os.rename(rConfTarget, rConfDestination)
			os.rename(rTarget, rDestination)
		except FileNotFoundError as e:
			await ctx.send("An error occured {0} when trying to rename files.".format(e))
			self.updating = False
			return
		await self.settings.Map.set(desiredMap)
		output = await self.runcommand("arkmanager start", ctx.channel, await self.settings.Verbose())
		await ctx.bot.change_presence(game=discord.Game(name="Restarting Server"),status=discord.Status.dnd)
		if self.successcheck(output):
			message = await ctx.send("Server is restarting...")
		else:
			try:
				await ctx.send("Something went wrong \U0001F44F. {0}".format(output))
				return
			except:
				await ctx.send("Something went wrong \U0001F44F")
				return
		status = ''
		while '\x1b[0;39m Server online:  \x1b[1;32m Yes \x1b[0;39m\n' not in status:
			await asyncio.sleep(15)
			status = await self.runcommand("arkmanager status")
		await message.edit(content="Map swapped to {0} and server is now running.".format(desiredMap))
		await ctx.bot.change_presence(game=discord.Game(name=None),status=discord.Status.online)
		self.updating = False

	async def detectMaps(self):
		"""Returns a list of available maps based on available instance files within the instance configuration directory."""
		directory = await self.settings.ARKManagerConfigDirectory() + 'instances/'
		availableMaps = []
		for file in os.listdir(directory):
			if file.endswith(".cfg") and file != 'main.cfg':
				file = file.replace('.cfg', "")
				availableMaps.append(file)
		current = await self.settings.Map()
		availableMaps.append(current)
		return availableMaps



	@ark.command()
	async def checkupdate(self, ctx):
		"""Just checks for ark updates - use +ark update to start update"""
		if await self.updatechecker(ctx.channel, await self.settings.Verbose()):
			await ctx.send("Updates are available!")
		else:
			await ctx.send("Your server is up to date!")

	@ark.command()
	async def checkmodupdate(self, ctx):
		"""Just checks for mod updates - use +ark update to start update"""
		if await self.checkmods(ctx.channel, await self.settings.Verbose()):
			await ctx.send("Updates to some mods are available.")
		else:
			await ctx.send("No mod updates found.")		

	@ark.command(name="stop")
	@commands.has_any_role('Admin', 'Moderator', 'Swole Cabbage')
	async def ark_stop(self, ctx):
		"""Stops the Ark Server"""
		await ctx.channel.trigger_typing()
		output = await self.runcommand("arkmanager stop", ctx.channel, await self.settings.Verbose())
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

	@arkadmin.command(name="dinowipe")
	async def arkadmin_dinowipe(self, ctx):
		"""Runs DestroyWildDinos."""
		output = await self.runcommand('arkmanager rconcmd "destroywilddinos"', ctx.channel, True)

	@arkadmin.command(name="autoupdate")
	async def arkadmin_autoupdate(self, ctx, toggle : str = 'info'):
		"""Toggles autoupdating"""
		togglestatus = await self.settings.AutoUpdate() #retrives current status of toggle from settings file
		if toggle.lower() == 'off':
			await self.settings.AutoUpdate.set(False)
			await ctx.send("Automatic updating is now disabled.")
		elif toggle.lower() == 'on':
			await self.settings.AutoUpdate.set(True)
			await ctx.send("Automatic server updating is now enabled. You may wish to select a channel for autoupdate messages to go to via {0}arkadmin channel.".format(ctx.prefix))
		else:
			if togglestatus == True:
				await ctx.send("Automatic updating is currently enabled. You may wish to select a channel for autoupdate messages to go to via {0}arkadmin channel.".format(ctx.prefix))
			elif togglestatus == False:
				await ctx.send("Automatic updating is currently disabled.")

	@arkadmin.command(name="channel")
	async def arkadmin_channel(self, ctx, channel: discord.TextChannel):
		if not ctx.guild.me.permissions_in(channel).send_messages:
			return await ctx.send("I do not have permissions to send messages to {.mention}".format(channel))
		await self.settings.Channel.set(channel.id)
		await ctx.send("Channel set to {.mention}".format(channel))
		await ctx.send("You may also want to setup an administration channel with {0}arkadmin adminchannel. This channel is used for full verbose autoupdater logs - it can be quite spammy but is useful for diagnostics.".format(ctx.prefix))

	@arkadmin.command(name="adminchannel")
	async def arkadmin_adminchannel(self, ctx, channel: discord.TextChannel):
		if not ctx.guild.me.permissions_in(channel).send_messages:
			return await ctx.send("I do not have permissions to send messages to {.mention}".format(channel))
		await self.settings.AdminChannel.set(channel.id)
		await ctx.send("Channel set to {.mention}".format(channel))

	@arkadmin.command(name="verbose")
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
		output = await self.runcommand("arkmanager start", ctx.channel, await self.settings.Verbose())
		if await self.settings.Verbose() == False:
			output = self.sanitizeoutput(output)
			await ctx.send(output)

	@ark.command(name="status")
	async def ark_status(self, ctx):
		"""Checks the server status"""
		await ctx.channel.trigger_typing()
		output = await self.runcommand("arkmanager status", ctx.channel, await self.settings.Verbose())
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
		"""Restarts the ARK Server with a specificed delay (in seconds)"""
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
			await ctx.send("I'm already carrying out a restart or update!")
		else:
			self.updating = True
			self.cancel = False
			await ctx.send("Restarting in {0} seconds.".format(delay))
			await ctx.bot.change_presence(game=discord.Game(name="Restarting Server"),status=discord.Status.dnd)
			command = 'arkmanager broadcast "Server will shutdown for a user-requested restart in ' + str(delay) + ' seconds."'
			alert = await self.runcommand(command, ctx.channel, False)
			await asyncio.sleep(delay)
			if self.cancel != True:
				message = await ctx.send("Server is restarting...")
				output = await self.runcommand("arkmanager restart", ctx.channel, await self.settings.Verbose())
				await ctx.bot.change_presence(game=discord.Game(name=None),status=discord.Status.online)
				self.updating = False
				if self.successcheck(output):
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
		"""Checks for updates, if found, downloads, then restarts the server"""
		def waitcheck(m):
			return m.author == ctx.author and m.channel == ctx.channel
		status = await self.updatechecker(ctx.channel, await self.settings.Verbose())
		modstatus = await self.checkmods(ctx.channel, await self.settings.Verbose())
		if status == True or modstatus == True:
			await ctx.send("Updates are available.")
			empty = await self.runcommand("arkmanager status", ctx.channel, False)
			offline = await self.offlinecheck()
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
				await ctx.send("I'm already carrying out a restart or update!")
			else:
				self.updating = True
				await ctx.bot.change_presence(game=discord.Game(name="Updating Server"),status=discord.Status.dnd)
				alert = await self.runcommand('arkmanager broadcast "Server will shutdown for updates in 60 seconds."', ctx.channel, False)
				await asyncio.sleep(60)
				message = await ctx.send("Server is updating...")
				output = await self.runcommand("arkmanager update --update-mods --backup", ctx.channel, await self.settings.Verbose())
				if self.successcheck(output):
					if offline:
						await self.bot.change_presence(game=discord.Game(name=None),status=discord.Status.online)
						self.updating = False
						return await message.edit(content="Server has been updated and is now online.")
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

	@arkadmin.command(name="save")
	async def ark_save(self, ctx):
		"""Saves the world state"""
		output = await self.runcommand("arkmanager saveworld", ctx.channel, True)

	@arkadmin.command(name="backup")
	async def ark_backup(self, ctx):
		"""Creates a backup of the save and config"""
		output = await self.runcommand("arkmanager backup", ctx.channel, True)

	@arkadmin.command(name="updatenow")
	async def ark_updatenow(self, ctx):
		"""Updates with no delay or checks"""
		output = await self.runcommand("arkmanager update --update-mods --backup", ctx.channel, True)

	@arkadmin.command(name="validate")
	async def ark_validate(self, ctx):
		"""Validates files with steamcmd"""
		output = await self.runcommand("arkmanager update --validate", ctx.channel, True)

	@arkadmin.command(name="forceupdate")
	async def ark_forceupdate(self, ctx):
		"""Updates with the -force parameter"""
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
		if await self.offlinecheck():
			return True
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
			if 'Update to' in line and 'complete' in line:
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
				currentmap = await self.settings.Map()
				output = await self.runcommand("arkmanager status")
				if '\x1b[0;39m Server online:  \x1b[1;32m Yes \x1b[0;39m\n' not in output:
					await self.bot.change_presence(game=discord.Game(name="Server is offline!"),status=discord.Status.dnd)
					await asyncio.sleep(30)
				else:
					for line in output:
						if 'Players:' in line and 'Active' not in line:
							players = line
						if 'Server Name' in line:
							version = '(' + line.split('(')[1]
					try:
						message = currentmap + ' ' + players + version
						await self.bot.change_presence(game=discord.Game(name=message), status=discord.Status.online)
					except:
						pass
					await asyncio.sleep(30)
			else:
				await asyncio.sleep(15)

	async def update_checker(self):
		"""Checks for updates automatically every hour"""
		while self is self.bot.get_cog("arkserver"):
			await asyncio.sleep(60)
			if await self.settings.AutoUpdate() == True: #proceed only if autoupdating is enabled
				if self.updating == False: #proceed only if the bot isn't already manually updating or restarting
					try:
						verbose =  await self.settings.Verbose()
						channel = self.bot.get_channel(await self.settings.Channel())
						adminchannel = self.bot.get_channel(await self.settings.AdminChannel())
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
								if channel is not None:
									message = await channel.send("Server is updating...")
								update = await self.runcommand("arkmanager update --update-mods --backup", adminchannel, True)
								if self.successcheck(update):
									status = ''
									while '\x1b[0;39m Server online:  \x1b[1;32m Yes \x1b[0;39m\n' not in status:
										await asyncio.sleep(15)
										status = await self.runcommand("arkmanager status")
									if channel is not None:
										await message.edit(content="Server has been updated and is now online.")
									await self.bot.change_presence(game=discord.Game(name=None),status=discord.Status.online)
									self.updating = False
								else:
									if channel is not None:
										await message.edit(content="Something went wrong during automatic update.")
									await self.bot.change_presence(game=discord.Game(name=None),status=discord.Status.online)
									self.updating = False
							else:
								print("Manual update or restart was triggered during 15 minute delay, automatic update has been cancelled")
						else:
							if channel is not None:
								message = await channel.send("Server is updating...")
							update = await self.runcommand("arkmanager update --update-mods --backup", adminchannel, True)
							if self.successcheck(update):									
								status = ''
								while '\x1b[0;39m Server online:  \x1b[1;32m Yes \x1b[0;39m\n' not in status:
									await asyncio.sleep(15)
									status = await self.runcommand("arkmanager status")
								if channel is not None:
									await message.edit(content="Server has been updated and is now online.")
								await self.bot.change_presence(game=discord.Game(name=None),status=discord.Status.online)
								self.updating = False
							else:
								if channel is not None:
									await message.edit(content="Something went wrong during automatic update")
								await self.bot.change_presence(game=discord.Game(name=None),status=discord.Status.online)
								self.updating = False
					else:
						await asyncio.sleep(3540)
				else:
					print("Server is already updating or restarting, auto-update cancelled")
					
