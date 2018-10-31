#pylint: disable=W,C,R


from datetime import datetime
import os
import sys
import asyncio
import glob
from subprocess import PIPE, Popen
from threading import Thread
import shlex

import discord
from redbot.core import commands
from redbot.core import Config


try:
	from Queue import Queue, Empty
except ImportError:
	from queue import Queue, Empty # python 3.x

ON_POSIX = 'posix' in sys.builtin_module_names

BaseCog = getattr(commands, "Cog", object)

class arkserver(BaseCog):
	"""Ark Server commands"""



	def __init__(self, bot):
		self.bot = bot
		self.settings = Config.get_conf(self, 3931293439)
		self.updating = False
		self.cancel = False
		self.active_instances = 0
		default_user = {
			"steamid": None
		}
		self.settings.register_global(
			Verbose=True,
			AutoUpdate=False,
			Instance=None,
			SetupDone=False,
			CharacterEnabled=False,
			ARKManagerConfigDirectory=None,
			ARKStorageDirectory=None,
			Channel=None,
			AdminChannel=None,
			Role=None,
			InstanceLimit=1
		)
		self.settings.register_user(**default_user)


	def enqueue_output(self, out, queue):
		"""Queues output from Popen output"""
		for line in iter(out.readline, b''):
			queue.put(line)
		out.close()

	async def runcommand(self, command, channel=None, verbose=False, instance='default'):
		"""This function runs a command in the terminal and uses a seperate thread to collect the response so it isn't blocking"""
		if instance == 'default':
			instance = await self.settings.Instance()
		command = command + ' @' + instance
		process = Popen(shlex.split(command), stdout=PIPE, bufsize=1, close_fds=ON_POSIX, start_new_session=True)
		queue = Queue()
		thread = Thread(target=self.enqueue_output, args=(process.stdout, queue))
		thread.daemon = True
		thread.start()
		output = []
		list_replacements = ["[1;32m ", "[1;31m", "[0;39m   ", "[0;39m ", "[0;39m", "8[J", "[68G[   [1;32m", "  ]", "\033"]
		while True:
			try:
				try:
					readline = queue.get_nowait().decode()
				except Empty:
					if thread.isAlive() is False and queue.empty() is True:
						break
					else:
						pass
				else:
					if readline:
						if len(readline) > 1900:
							output.append("Line exceeded character limit.")
						else:
							output.append(readline)
						if verbose and channel is not None:
							sani = readline.lstrip("7")
							for elem in list_replacements:
								sani = sani.replace(elem, "")
							try:
								await channel.send("{0}".format(sani))
							except Exception as exception:
								print("Error posting to discord {0}, {1}".format(exception, sani))

			except Exception as exception:
				print("Something went wrong... you should check the status of the server with +ark status. {0}".format(exception))
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
		def waitcheck(message):
			return message.author == ctx.author and message.channel == ctx.channel
		try:
			await ctx.send("This setup process will set required options for this cog to function. For each question, you should respond with desired setting.")
			await ctx.send("First, please respond with the location arkmanager configuration files are located. Please include the last '/' Unless you changed this, the default is usually '/etc/arkmanager/'.")
			answer = await self.bot.wait_for('message', check=waitcheck, timeout=30)
			ark_manager = answer.content
			await ctx.send("Next, please repond with a location to store inactive character world save files, used for the character swap features.")
			answer = await self.bot.wait_for('message', check=waitcheck, timeout=30)
			ark_storage = answer.content
			await ctx.send("You have chosen:\n{0} as the arkmanager configuration location and \n{1} as the character storage location.\nReply 'Yes' to confirm these settings and complete setup.".format(ark_manager, ark_storage))
			answer = await self.bot.wait_for('message', check=waitcheck, timeout=30)
			if answer.content.lower() != 'yes':
				return await ctx.send("Okay, setup cancelled.")
		except asyncio.TimeoutError:
			return await ctx.send("You didn't reply in time, setup cancelled.")
		await self.settings.ARKManagerConfigDirectory.set(ark_manager)
		await self.settings.ARKStorageDirectory.set(ark_storage)
		await self.settings.SetupDone.set(True)
		await ctx.send("Setup complete. If you need to change any of these settings, simply re-run this setup command.")
		await ctx.send("This cog makes use of three seperate permission levels.\nAll users can see the status of the server and make use of the character management system if enabled.\nPriviledged users can "
				"start, stop, restart, update, and change the active instance.\n As the owner you have access to additional commands to manage advanced settings that control cog functionality.\n"
				"A discord role needs to be assigned if you wish to grant other users access to the priviledged commands, you can do this via +arkadmin role (mention the role directly).")
		await ctx.send("The default instance limit is 1. This is the maximum number of ARK Dedicated Server processes that can be run at once with this cog. You can change this with arkadmin instancelimit (n) if you desire but you should NOT set this to more than your server is capable of running.")

	async def setupCheck(ctx):
		"""Because the help formatter uses this check outside the arkserver cog, to access the cog settings we need to get them seperately here"""
		from redbot.core import Config
		settings = Config.get_conf(None, 3931293439, False, 'arkserver')
		return await settings.SetupDone()

	async def arkRoleCheck(ctx):
		"""Because the help formatter uses this check outside the arkserver cog, to access the cog settings we need to get them seperately here"""
		from redbot.core import Config
		settings = Config.get_conf(None, 3931293439, False, 'arkserver')
		role = discord.utils.get(ctx.guild.roles, id=(await settings.Role()))
		return role in ctx.author.roles

	async def arkCharCheck(ctx):
		"""Because the help formatter uses this check outside the arkserver cog, to access the cog settings we need to get them seperately here"""
		from redbot.core import Config
		settings = Config.get_conf(None, 3931293439, False, 'arkserver')
		return await settings.CharacterEnabled()

	@commands.command()
	@commands.is_owner()
	async def arksettings(self, ctx):
		"""Displays the current data settings and whether setup is complete"""
		ARKLimit = await self.settings.InstanceLimit()
		ARKManager = await self.settings.ARKManagerConfigDirectory()
		ARKStorage = await self.settings.ARKStorageDirectory()
		ARKChannel = await self.settings.Channel()
		ARKAdminChannel = await self.settings.AdminChannel()
		SetupDone = await self.settings.SetupDone()
		ARKRole = await self.settings.Role()
		ARKChar = await self.settings.CharacterEnabled()
		await ctx.send("{0} is the current instance limit.\n{1} is the arkmanager configuration location.\n{2} is the "
			"additional storage location.\nSetup complete? {3}\nSelected channel ID {4}.\nSelected admin channel ID {5}.\nSelected priviledged role ID {6}.\nCharacter management enabled? {7}.".format(ARKLimit, ARKManager, ARKStorage, SetupDone, ARKChannel, ARKAdminChannel, ARKRole, ARKChar))


	@commands.group()
	@commands.check(setupCheck)
	async def ark(self, ctx):
		"""Commands related to the Ark Server"""

	@commands.group()
	@commands.is_owner()
	@commands.check(setupCheck)
	async def arkadmin(self, ctx):
		"""Commands related to Ark Server Administration"""

	@commands.group()
	@commands.check(setupCheck)
	@commands.check(arkCharCheck)
	async def arkchar(self, ctx):
		"""Commands related to Ark Character Management"""


	@arkchar.command()
	@commands.is_owner()
	async def setid(self, ctx, userobject: discord.Member, *, inputid):
		"""Sets the steam identifier for the mentioned user, required to use any character commands. Enter a steamID64."""
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
		if steamid is None:
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
		instance = await self.settings.Instance()
		serverLocation = await self.getServerLocation(instance)
		if not serverLocation:
			await ctx.send("Couldn't find the server location for the current instance.")
			return
		saveDir = await self.getAltSaveDirectory()
		if not saveDir:
			await ctx.send("Couldn't find the save location for the current instance.")
			return
		source = serverLocation + '/ShooterGame/Saved/' + saveDir + '/' + steamid + '.arkprofile'
		await ctx.send(source)
		destination = await self.settings.ARKStorageDirectory() + steamid + savename + '.bak'
		await ctx.send(destination)
		if os.path.isfile(source) is False:
			await ctx.send("You don't have a character active at the moment.")
			return
		if os.path.isfile(destination) is True:
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

	async def getServerLocation(self, instance):
		serverLocation = None
		output = await self.runcommand('arkmanager list-instances', instance=instance)
		for elem in output:
			if ('@' + instance) in elem:
				config, serverLocation = elem.split('=> ')
				serverLocation = serverLocation.replace('\n','')
		return serverLocation

	async def getAltSaveDirectory(self):
		saveDir = None
		configFile = await self.settings.ARKManagerConfigDirectory() + 'instances/' + await self.settings.Instance() + '.cfg'
		with open(configFile, 'r') as f:
			for line in f:
				if line.startswith('ark_AltSaveDirectoryName'):
					command, value = line.split('=')
					saveDir = value.replace('"', '')
					saveDir = saveDir.replace('\n', '')
		return saveDir

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
		instance = await self.settings.Instance()
		serverLocation = await self.getServerLocation(instance)
		if not serverLocation:
			await ctx.send("Couldn't find the server location for the current instance.")
			return
		saveDir = await self.getAltSaveDirectory()
		if not saveDir:
			await ctx.send("Couldn't find the save location for the current instance.")
			return
		source = await self.settings.ARKStorageDirectory() + steamid + savename + '.bak'
		destination = serverLocation + '/ShooterGame/Saved/' + saveDir + '/' + steamid + '.arkprofile'
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
	@commands.check(arkRoleCheck)
	async def instance(self, ctx, minput : str = 'info'):
		"""Sets the instance that cog commands operate on. Use this command with no instance specified to see the current instance."""
		if minput == 'info':
			await ctx.send("Current instance is {0}".format(await self.settings.Instance()))
			return
		availableInstances = await self.detectInstances()
		desiredInstance = next((s for s in availableInstances if minput.lower() in s.lower()), None)
		if not desiredInstance:
			await ctx.send("I don't recognize that instance, available options are {0}.".format(availableInstances))
			return
		await self.settings.Instance.set(desiredInstance)
		await ctx.send("Set to {0}.".format(desiredInstance))	

	@ark.command(name="swap", aliases=["map"])
	@commands.check(arkRoleCheck)
	async def swap(self, ctx, minput : str = 'info'):
		"""Swaps an active instance to another instance. This works by stopping a running instance and starting a different one."""
		await ctx.channel.trigger_typing()
		availableInstances = await self.detectInstances()
		if minput == 'info':
			await ctx.send("This command can swap the instance the server is running on to the desired instance. Options available are {0}. (e.g +ark swap ragnarok)".format(availableInstances))
			await ctx.send("Current instance is {0}".format(await self.settings.Instance()))
			return
		if self.updating == True: #don't change the instance if the server is restarting or updating
			await ctx.send("I'm already carrying out a restart or update!")
			return
		if await self.playercheck():
			await ctx.send("The instance cannot be swapped while players are in the server.")
			return
		desiredInstance = next((s for s in availableInstances if minput.lower() in s.lower()), None)
		if not desiredInstance:
			await ctx.send("I don't recognize that instance, available options are {0}.".format(availableInstances))
			return
		if await self.settings.Instance() == desiredInstance:
			await ctx.send("The server is already running this instance!") 
			return
		message = await ctx.send("Instance will be swapped to {0}, the server will need to be restarted to complete the change, react agree to confirm.".format(desiredInstance))
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
		if await self.offlinecheck():
			await ctx.send("The instance the cog is currently using isn't online, this must be an active instance. Otherwise you could just start the instance you want with +ark start (instance name).")
			return
		if not await self.offlinecheck(instance=desiredInstance):
			await ctx.send("The instance you have selected to swap to is already running!")
			return
		self.updating = True
		output = await self.runcommand("arkmanager stop", ctx.channel, await self.settings.Verbose())
		self.active_instances = self.active_instances - 1
		#All done, now we can start the new instance.
		await self.settings.Instance.set(desiredInstance)
		verbose = await self.settings.Verbose()
		output = await self.runcommand(command="arkmanager start", channel=ctx.channel, verbose=verbose)
		self.active_instances = self.active_instances + 1
		self.updating = False


	async def detectInstances(self):
		"""Returns a list of available Instances based on available instance files within the instance configuration directory."""
		directory = await self.settings.ARKManagerConfigDirectory() + 'instances/'
		availableInstances = []
		for file in os.listdir(directory):
			if file.endswith(".cfg"):
				file = file.replace('.cfg', "")
				availableInstances.append(file)
		return availableInstances

	@ark.command()
	@commands.check(arkRoleCheck)
	async def checkupdate(self, ctx):
		"""Just checks for ark updates - use +ark update to start update"""
		if await self.updatechecker(ctx.channel, await self.settings.Verbose()):
			await ctx.send("Updates are available!")
		else:
			await ctx.send("Your server is up to date!")

	@ark.command()
	@commands.check(arkRoleCheck)
	async def checkmodupdate(self, ctx):
		"""Just checks for mod updates - use +ark update to start update"""
		if await self.checkmods(ctx.channel, await self.settings.Verbose()):
			await ctx.send("Updates to some mods are available.")
		else:
			await ctx.send("No mod updates found.")		

	@ark.command(name="stop")
	@commands.check(arkRoleCheck)
	async def ark_stop(self, ctx):
		"""Stops the Ark Server"""
		await ctx.channel.trigger_typing()
		output = await self.runcommand("arkmanager stop", ctx.channel, await self.settings.Verbose())
		if await self.settings.Verbose() == False:
			output = self.sanitizeoutput(output)
			await ctx.send(output)
		self.active_instances = self.active_instances - 1

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

	@arkadmin.command(name="role")
	async def arkadmin_role(self, ctx, role: discord.Role):
		await self.settings.Role.set(role.id)
		await ctx.send("Role set to {.mention}".format(role))

	@arkadmin.command(name="instancelimit")
	async def arkadmin_instancelimit(self, ctx, instanceLimit: str = 'info'):
		try:
			instanceLimit = int(instanceLimit)
			await self.settings.InstanceLimit.set(instanceLimit)
		except:
			return await ctx.send("Not a valid number.")
		await ctx.send("Instance limit set to {0}".format(instanceLimit))

	@arkadmin.command(name="adminchannel")
	async def arkadmin_adminchannel(self, ctx, channel: discord.TextChannel):
		if not ctx.guild.me.permissions_in(channel).send_messages:
			return await ctx.send("I do not have permissions to send messages to {.mention}".format(channel))
		await self.settings.AdminChannel.set(channel.id)
		await ctx.send("Channel set to {.mention}".format(channel))

	@arkadmin.command(name="charmanagement")
	async def arkadmin_charactermanagement(self, ctx, toggle : str = 'info'):
		"""Enables or disables the ability for users to store and retrieve character files belonging to them in the storage directory.""" 
		togglestatus = await self.settings.CharacterEnabled() #retrives current status of toggle from settings file
		if toggle.lower() == 'off':
			await self.settings.CharacterEnabled.set(False)
			await ctx.send("Character management has been disabled.")
		elif toggle.lower() == 'on':
			await self.settings.CharacterEnabled.set(True)
			await ctx.send("Character management has been enabled. Each user that wishes to use this feature needs to have a SteamID assigned to their discord profile by my owner to ensure they can only "
				"modify their own character save files.")
		else:
			if togglestatus == True:
				await ctx.send("Character management is currently enabled.")
			elif togglestatus == False:
				await ctx.send("Character management is currently disabled.")

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
	@commands.check(arkRoleCheck)
	async def ark_start(self, ctx):
		"""Starts the Ark Server"""
		if self.active_instances >= await self.settings.InstanceLimit():
			await ctx.send("Instance limit has been reached, please stop another instance first.")
			return
		await ctx.channel.trigger_typing()
		output = await self.runcommand("arkmanager start", ctx.channel, await self.settings.Verbose())
		if await self.settings.Verbose() == False:
			output = self.sanitizeoutput(output)
			await ctx.send(output)
		self.active_instances = self.active_instances + 1

	@ark.command(name="status")
	async def ark_status(self, ctx, instance: str = 'default'):
		"""Checks the server status"""
		await ctx.channel.trigger_typing()
		verbose = await self.settings.Verbose()
		output = await self.runcommand("arkmanager status", instance=instance, channel=ctx.channel, verbose=verbose)
		if verbose == False:
			output = self.sanitizeoutput(output)
			await ctx.send(output)

	@ark.command(name="cancel")
	@commands.check(arkRoleCheck)
	async def ark_cancel(self, ctx):
		"""Cancels a pending restart"""
		self.cancel = True
		await ctx.send("Restart cancelled.")

	@ark.command(name="restart")
	@commands.check(arkRoleCheck)
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
		if await self.playercheck():
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
			await ctx.bot.change_presence(activity=discord.Game(name="Restarting Server"),status=discord.Status.dnd)
			command = 'arkmanager broadcast "Server will shutdown for a user-requested restart in ' + str(delay) + ' seconds."'
			alert = await self.runcommand(command, ctx.channel, False)
			await asyncio.sleep(delay)
			if self.cancel != True:
				message = await ctx.send("Server is restarting...")
				output = await self.runcommand("arkmanager restart", ctx.channel, await self.settings.Verbose())
				await ctx.bot.change_presence(activity=discord.Game(name=None),status=discord.Status.online)
				self.updating = False
				if self.successcheck(output):
					status = ''
					while '\x1b[0;39m Server online:  \x1b[1;32m Yes \x1b[0;39m\n' not in status:
						await asyncio.sleep(15)
						status = await self.runcommand("arkmanager status")
					await message.edit(content="Server is up.")
					await self.bot.change_presence(activity=discord.Game(name=None),status=discord.Status.online)
					self.updating = False
				else:
					try:
						await ctx.send("Something went wrong \U0001F44F. {0}".format(output))
					except:
						await ctx.send("Something went wrong \U0001F44F")
					await ctx.bot.change_presence(activity=discord.Game(name=None),status=discord.Status.online)
					self.updating = False
			else:
				self.cancel = False
				alert = await self.runcommand('arkmanager broadcast "Restart was cancelled by user request."', ctx.channel, False)
				await ctx.bot.change_presence(activity=discord.Game(name=None),status=discord.Status.online)
				self.updating = False
				#restart was cancelled

	@ark.command(name="update")
	@commands.check(arkRoleCheck)
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
			if await self.playercheck():
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
				await ctx.bot.change_presence(activity=discord.Game(name="Updating Server"),status=discord.Status.dnd)
				alert = await self.runcommand('arkmanager broadcast "Server will shutdown for updates in 60 seconds."', ctx.channel, False)
				await asyncio.sleep(60)
				message = await ctx.send("Server is updating...")
				verbose = await self.settings.Verbose()
				output = await self.runcommand(command="arkmanager update --update-mods --backup", channel=ctx.channel, verbose=verbose, instance='all')
				if self.successcheck(output):
					if offline:
						await self.bot.change_presence(activity=discord.Game(name=None),status=discord.Status.online)
						self.updating = False
						return await message.edit(content="Server has been updated and is now online.")
					status = ''
					while '\x1b[0;39m Server online:  \x1b[1;32m Yes \x1b[0;39m\n' not in status:
						await asyncio.sleep(15)
						status = await self.runcommand("arkmanager status")
					await message.edit(content="Server has been updated and is now online.")
					await self.bot.change_presence(activity=discord.Game(name=None),status=discord.Status.online)
					self.updating = False
				else:
					try:
						await ctx.send("Something went wrong \U0001F44F. {0}".format(output))
					except:
						await ctx.send("Something went wrong \U0001F44F")
					await ctx.bot.change_presence(activity=discord.Game(name=None),status=discord.Status.online)
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
		output = await self.runcommand(command="arkmanager backup", channel=ctx.channel, verbose=True, instance='all')

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

	async def playercheck(self, channel=None, verbose=False):
		"""Returns True if players are present in the server."""
		if await self.offlinecheck():
			return False
		output = await self.runcommand("arkmanager status", channel, verbose)
		for line in output:
			if 'Players: 0' in line:
				return False
		return True

	async def offlinecheck(self, channel=None, verbose=False, instance='default'):
		"""Returns True if the server is offline"""
		output = await self.runcommand("arkmanager status", instance=instance)
		if '\x1b[0;39m Server online:  \x1b[1;32m Yes \x1b[0;39m\n' in output and '\x1b[0;39m Server running:  \x1b[1;32m Yes \x1b[0;39m\n' in output:
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

	async def discover_instances(self):
		for instance in await self.detectInstances():
			if not await self.offlinecheck(instance=instance):
				self.active_instances = self.active_instances + 1
		if self.active_instances > await self.settings.InstanceLimit():
			print('Warning: More instances are currently running than the instance limit!')
			adminchannel = self.bot.get_channel(await self.settings.AdminChannel())
			if adminchannel is not None:
				await adminchannel.send('Warning: More instances are currently running than the instance limit!')


	async def presence_manager(self):
		"""Reports status of the currently active instance using discord status"""
		while self is self.bot.get_cog("arkserver"):
			if self.updating == False:
				currentinstance = await self.settings.Instance()
				try:
					output = await self.runcommand("arkmanager status", instance=currentinstance)
					if '\x1b[0;39m Server online:  \x1b[1;32m Yes \x1b[0;39m\n' not in output:
						await self.bot.change_presence(activity=discord.Game(name="Server is offline!"),status=discord.Status.dnd)
						await asyncio.sleep(30)
					else:
						for line in output:
							if 'Players:' in line and 'Active' not in line:
								players = line
							if 'Server Name' in line:
								version = '(' + line.split('(')[1]
						try:
							message = currentinstance + ' ' + players + version
							await self.bot.change_presence(activity=discord.Game(name=message), status=discord.Status.online)
						except:
							pass
						await asyncio.sleep(30)
				except Exception as e:
					print("Error in presence_manager: {0}".format(e))
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
						if await self.playercheck():
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
								await self.bot.change_presence(activity=discord.Game(name="Updating Server"),status=discord.Status.dnd)
								self.updating = True
								if channel is not None:
									message = await channel.send("Server is updating...")
								update = await self.runcommand(command="arkmanager update --update-mods --backup", channel=adminchannel, verbose=True, instance='all')
								if self.successcheck(update):
									status = ''
									while '\x1b[0;39m Server online:  \x1b[1;32m Yes \x1b[0;39m\n' not in status:
										await asyncio.sleep(15)
										status = await self.runcommand("arkmanager status")
									if channel is not None:
										await message.edit(content="Server has been updated and is now online.")
									await self.bot.change_presence(activity=discord.Game(name=None),status=discord.Status.online)
									self.updating = False
								else:
									if channel is not None:
										await message.edit(content="Something went wrong during automatic update.")
									await self.bot.change_presence(activity=discord.Game(name=None),status=discord.Status.online)
									self.updating = False
							else:
								print("Manual update or restart was triggered during 15 minute delay, automatic update has been cancelled")
						else:
							if channel is not None:
								message = await channel.send("Server is updating...")
							update = await self.runcommand(command="arkmanager update --update-mods --backup", channel=adminchannel, verbose=True, instance='all')
							if self.successcheck(update):									
								status = ''
								while '\x1b[0;39m Server online:  \x1b[1;32m Yes \x1b[0;39m\n' not in status:
									await asyncio.sleep(15)
									status = await self.runcommand("arkmanager status")
								if channel is not None:
									await message.edit(content="Server has been updated and is now online.")
								await self.bot.change_presence(activity=discord.Game(name=None),status=discord.Status.online)
								self.updating = False
							else:
								if channel is not None:
									await message.edit(content="Something went wrong during automatic update")
								await self.bot.change_presence(activity=discord.Game(name=None),status=discord.Status.online)
								self.updating = False
					else:
						await asyncio.sleep(3540)
				else:
					print("Server is already updating or restarting, auto-update cancelled")
					
