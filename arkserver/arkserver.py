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
from queue import Queue, Empty  # python 3.x

ON_POSIX = 'posix' in sys.builtin_module_names
BaseCog = getattr(commands, "Cog", object)


class Arkserver(BaseCog):
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

    @staticmethod
    def enqueue_output(out, queue):
        """Queues output from Popen output"""
        for line in iter(out.readline, b''):
            queue.put(line)
        out.close()

    async def runcommand(self, command, channel=None, verbose=False, instance='default'):
        """This function runs a command in the terminal and uses a separate thread to collect the response
        so it isn't blocking"""
        if instance == 'default':
            instance = await self.settings.Instance()
        command = 'arkmanager ' + command + ' @' + instance
        process = Popen(shlex.split(command), stdout=PIPE, bufsize=1, close_fds=ON_POSIX, start_new_session=True)
        queue = Queue()
        thread = Thread(target=self.enqueue_output, args=(process.stdout, queue))
        thread.daemon = True
        thread.start()
        output = []
        list_replacements = ["[1;32m ", "[1;31m", "[0;39m   ", "[0;39m ", "[0;39m", "8[J", "[68G[   [1;32m",
                             "  ]", "\033"]
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
                print("Something went wrong... you should check the status of the server with +ark status. {0}".format(
                    exception))
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
        def wait_check(message):
            return message.author == ctx.author and message.channel == ctx.channel
        try:
            await ctx.send("This setup process will set required options for this cog to function. For each question,"
                           "you should respond with desired setting.")
            await ctx.send("First, please respond with the location arkmanager configuration files are located. Please "
                           "include the last '/' Unless you changed this, the default is usually '/etc/arkmanager/'.")
            answer = await self.bot.wait_for('message', check=wait_check, timeout=30)
            ark_manager = answer.content
            await ctx.send("Next, please respond with a location to store inactive character world save files, "
                           "used for the character swap features.")
            answer = await self.bot.wait_for('message', check=wait_check, timeout=30)
            ark_storage = answer.content
            await ctx.send("You have chosen:\n{0} as the arkmanager configuration location and \n{1} as the character"
                           "storage location.\nReply 'Yes' to confirm these settings and complete setup.".format(
                            ark_manager, ark_storage))
            answer = await self.bot.wait_for('message', check=wait_check, timeout=30)
            if answer.content.lower() != 'yes':
                return await ctx.send("Okay, setup cancelled.")
        except asyncio.TimeoutError:
            return await ctx.send("You didn't reply in time, setup cancelled.")
        await self.settings.ARKManagerConfigDirectory.set(ark_manager)
        await self.settings.ARKStorageDirectory.set(ark_storage)
        await self.settings.SetupDone.set(True)
        await ctx.send("Setup complete. If you need to change any of these settings, simply re-run this setup command.")
        await ctx.send("This cog makes use of three separate permission levels.\nAll users can see the status of the "
                       "server and make use of the character management system if enabled.\nPrivileged users can "
                       "start, stop, restart, update, and change the active instance.\n As the owner you have access"
                       "to additional commands to manage advanced settings that control cog functionality.\n"
                       "A discord role needs to be assigned if you wish to grant other users access to the privileged"
                       "commands, you can do this via +arkadmin role (mention the role directly).")
        await ctx.send("The default instance limit is 1. This is the maximum number of ARK Dedicated Server processes"
                       "that can be run at once with this cog. You can change this with arkadmin instancelimit (n) if"
                       "you desire but you should NOT set this to more than your server is capable of running.")

    @staticmethod
    async def setupcheck():
        """Because the help formatter uses this check outside the arkserver cog, to access the cog settings we
        need to get them separately here"""
        from redbot.core import Config
        settings = Config.get_conf(cog_instance=None, identifier=3931293439, force_registration=False,
                                   cog_name="arkserver")
        return await settings.SetupDone()

    @staticmethod
    async def arkrolecheck(ctx):
        """Because the help formatter uses this check outside the arkserver cog, to access the cog settings we need
         to get them separately here"""
        from redbot.core import Config
        settings = Config.get_conf(cog_instance=None, identifier=3931293439, force_registration=False,
                                   cog_name="arkserver")
        role = discord.utils.get(ctx.guild.roles, id=(await settings.Role()))
        return role in ctx.author.roles

    @staticmethod
    async def arkcharcheck():
        """Because the help formatter uses this check outside the arkserver cog, to access the cog settings we need
         to get them separately here"""
        from redbot.core import Config
        settings = Config.get_conf(cog_instance=None, identifier=3931293439, force_registration=False,
                                   cog_name="arkserver")
        return await settings.CharacterEnabled()

    @commands.command()
    @commands.is_owner()
    async def arksettings(self, ctx):
        """Displays the current data settings and whether setup is complete"""
        ark_limit = await self.settings.InstanceLimit()
        ark_manager = await self.settings.ARKManagerConfigDirectory()
        ark_storage = await self.settings.ARKStorageDirectory()
        ark_channel = await self.settings.Channel()
        ark_admin_channel = await self.settings.AdminChannel()
        setup_done = await self.settings.SetupDone()
        ark_role = await self.settings.Role()
        ark_char = await self.settings.CharacterEnabled()
        await ctx.send("{0} is the current instance limit.\n{1} is the arkmanager configuration location.\n{2} is the "
                       "additional storage location.\nSetup complete? {3}\nSelected channel ID {4}.\nSelected admin"
                       "channel ID {5}.\n Selected privileged role ID {6}.\nCharacter management enabled? {7}.".format(
                        ark_limit, ark_manager, ark_storage, setup_done, ark_channel, ark_admin_channel, ark_role,
                        ark_char))

    @commands.group()
    @commands.check(setupcheck)
    async def ark(self, ctx):
        """Commands related to the Ark Server"""

    @commands.group()
    @commands.is_owner()
    @commands.check(setupcheck)
    async def arkadmin(self, ctx):
        """Commands related to Ark Server Administration"""

    @commands.group()
    @commands.check(setupcheck)
    @commands.check(arkcharcheck)
    async def arkchar(self, ctx):
        """Commands related to Ark Character Management"""

    @arkchar.command()
    @commands.is_owner()
    async def setid(self, ctx, userobject: discord.Member, *, inputid):
        """Sets the steam identifier for the mentioned user, required to use any character commands.
        Enter a steamID64."""
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
            await ctx.send("You need to have your steam ID attached to your discord account by my owner before you "
                           "can use this command.")
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
        if not savename.isalpha():
            await ctx.send("Please only use alphabetic characters in the savename.")
            return
        steamid = await self.settings.user(ctx.author).steamid()
        if steamid:
            await ctx.send("You need to have your steam ID attached to your discord account by my owner before you can"
                           "use this command.")
            return
        instance = await self.settings.Instance()
        server_location = await self.get_server_location(instance)
        if not server_location:
            await ctx.send("Couldn't find the server location for the current instance.")
            return
        save_dir = await self.get_alt_save_directory()
        if not save_dir:
            await ctx.send("Couldn't find the save location for the current instance.")
            return
        source = server_location + '/ShooterGame/Saved/' + save_dir + '/' + steamid + '.arkprofile'
        destination = await self.settings.ARKStorageDirectory() + steamid + savename + '.bak'
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
            await ctx.send("An error occurred {0} when trying to rename files.".format(e))
            return
        await ctx.send("Stored your current character as {0}.".format(savename))

    async def ingamecheck(self, steamid):
        output = await self.runcommand('rconcmd "listplayers"')
        for line in output:
            if steamid in line:
                return True
        return False

    async def get_server_location(self, instance):
        server_location = None
        output = await self.runcommand('list-instances', instance=instance)
        for elem in output:
            if ('@' + instance) in elem:
                config, server_location = elem.split('=> ')
                server_location = server_location.replace('\n', '')
        return server_location

    async def get_alt_save_directory(self):
        save_dir = None
        config_file = await self.settings.ARKManagerConfigDirectory() + 'instances/' + await self.settings.Instance() +\
            '.cfg'
        with open(config_file, 'r') as f:
            for line in f:
                if line.startswith('ark_AltSaveDirectoryName'):
                    command, value = line.split('=')
                    save_dir = value.replace('"', '')
                    save_dir = save_dir.replace('\n', '')
        return save_dir

    @arkchar.command()
    async def retrieve(self, ctx, savename: str):
        """Retrieves the specified character"""
        if not savename.isalpha():
            await ctx.send("Please only use alphabetic characters in the savename.")
            return
        steamid = await self.settings.user(ctx.author).steamid()
        if steamid:
            await ctx.send("You need to have your steam ID attached to your discord account by my owner before you can"
                           "use this command.")
            return
        instance = await self.settings.Instance()
        server_location = await self.get_server_location(instance)
        if not server_location:
            await ctx.send("Couldn't find the server location for the current instance.")
            return
        save_dir = await self.get_alt_save_directory()
        if not save_dir:
            await ctx.send("Couldn't find the save location for the current instance.")
            return
        source = await self.settings.ARKStorageDirectory() + steamid + savename + '.bak'
        destination = server_location + '/ShooterGame/Saved/' + save_dir + '/' + steamid + '.arkprofile'
        if not os.path.isfile(source):
            await ctx.send("That character doesn't exist in storage.")
            return
        if os.path.isfile(destination):
            await ctx.send("You already have a character active, you need to store it first!")
            return
        await self.runcommand('rconcmd "listplayers"', ctx.channel)
        if await self.ingamecheck(steamid):
            await ctx.send("You need to leave the server before I can do this.")
            return
        try:
            os.rename(source, destination)
        except Exception as e:
            await ctx.send("An error occurred {0} when trying to rename files.".format(e))
            return
        await ctx.send("Character {0} is now active.".format(savename))

    @ark.command()
    @commands.check(arkrolecheck)
    async def instance(self, ctx, minput: str = 'info'):
        """Sets the instance that cog commands operate on. Use this command with no instance specified to see the
        current instance."""
        if minput == 'info':
            await ctx.send("Current instance is {0}".format(await self.settings.Instance()))
            return
        available_instances = await self.detect_instances()
        desired_instance = next((s for s in available_instances if minput.lower() in s.lower()), None)
        if not desired_instance:
            await ctx.send("I don't recognize that instance, available options are {0}.".format(available_instances))
            return
        await self.settings.Instance.set(desired_instance)
        await ctx.send("Set to {0}.".format(desired_instance))

    @ark.command(name="swap", aliases=["map"])
    @commands.check(arkrolecheck)
    async def swap(self, ctx, minput: str = 'info'):
        """Swaps an active instance to another instance. This works by stopping a running instance and starting a
         different one."""
        async with ctx.channel.typing():
            available_instances = await self.detect_instances()
            if minput == 'info':
                await ctx.send("This command can swap the instance the server is running on to the desired instance."
                               "Options available are {0}. (e.g +ark swap ragnarok)".format(available_instances))
                await ctx.send("Current instance is {0}".format(await self.settings.Instance()))
                return
            if self.updating:  # don't change the instance if the server is restarting or updating
                await ctx.send("I'm already carrying out a restart or update!")
                return
            if await self.playercheck():
                await ctx.send("The instance cannot be swapped while players are in the server.")
                return
            desired_instance = next((s for s in available_instances if minput.lower() in s.lower()), None)
            if not desired_instance:
                await ctx.send("I don't recognize that instance, available options are {0}.".format(
                    available_instances))
                return
            if await self.settings.Instance() == desired_instance:
                await ctx.send("The server is already running this instance!")
                return
            message = await ctx.send("Instance will be swapped to {0}, the server will need to be restarted to complete"
                                     "the change, react agree to confirm.".format(desired_instance))
            await message.add_reaction('✔')

            def waitcheck(wait_react, wait_user):
                return wait_react.emoji == '✔' and wait_user == ctx.author

            try:
                await self.bot.wait_for('reaction_add', check=waitcheck, timeout=30.0)
            except asyncio.TimeoutError:
                await message.clear_reactions()
                await message.edit(content="You took too long..")
                return

            await message.clear_reactions()
            if await self.offlinecheck():
                await ctx.send("The instance the cog is currently using isn't online, this must be an active instance."
                               "Otherwise you could just start the instance you want with +ark start (instance name).")
                return
            if not await self.offlinecheck(instance=desired_instance):
                await ctx.send("The instance you have selected to swap to is already running!")
                return
            self.updating = True
            await self.runcommand("stop", ctx.channel, await self.settings.Verbose())
            self.active_instances = self.active_instances - 1
            # All done, now we can start the new instance.
            await self.settings.Instance.set(desired_instance)
            verbose = await self.settings.Verbose()
            await self.runcommand(command="start", channel=ctx.channel, verbose=verbose)
            self.active_instances = self.active_instances + 1
            self.updating = False

    async def detect_instances(self):
        """Returns a list of available Instances based on available instance files within the instance configuration
        directory."""
        directory = await self.settings.ARKManagerConfigDirectory() + 'instances/'
        available_instances = []
        for file in os.listdir(directory):
            if file.endswith(".cfg"):
                file = file.replace('.cfg', "")
                available_instances.append(file)
        return available_instances

    @ark.command()
    @commands.check(arkrolecheck)
    async def checkupdate(self, ctx):
        """Just checks for ark updates - use +ark update to start update"""
        if await self.updatechecker(ctx.channel, await self.settings.Verbose()):
            await ctx.send("Updates are available!")
        else:
            await ctx.send("Your server is up to date!")

    @ark.command()
    @commands.check(arkrolecheck)
    async def checkmodupdate(self, ctx):
        """Just checks for mod updates - use +ark update to start update"""
        if await self.checkmods(ctx.channel, await self.settings.Verbose()):
            await ctx.send("Updates to some mods are available.")
        else:
            await ctx.send("No mod updates found.")

    @ark.command(name="stop")
    @commands.check(arkrolecheck)
    async def ark_stop(self, ctx, minput: str = 'default'):
        """Stops the Ark Server"""
        async with ctx.channel.typing():
            if minput != 'default':
                available_instances = await self.detect_instances()
                desired_instance = next((s for s in available_instances if minput.lower() in s.lower()), None)
                if not desired_instance:
                    await ctx.send("I don't recognize that instance, available options are {0}.".format(
                        available_instances))
                    return
            else:
                desired_instance = minput
            output = await self.runcommand("stop", ctx.channel, await self.settings.Verbose(),
                                           desired_instance)
            if not await self.settings.Verbose():
                output = self.sanitizeoutput(output)
                await ctx.send(output)
            self.active_instances = self.active_instances - 1

    @ark.command(name="players")
    async def ark_players(self, ctx):
        """Lists players currently in the server."""
        output = await self.runcommand('rconcmd "listplayers"', ctx.channel, False)
        players = "```Players ingame:"
        for line in output:
            if '.' in line:
                slot, name, steamid = line.split(' ', 2)
                players += "\n" + name.rstrip(',')
        players += "```"
        await ctx.send(players)

    @arkadmin.command(name="dinowipe")
    async def arkadmin_dinowipe(self, ctx):
        """Runs DestroyWildDinos."""
        await self.runcommand('rconcmd "destroywilddinos"', ctx.channel, True)

    @arkadmin.command(name="autoupdate")
    async def arkadmin_autoupdate(self, ctx, toggle: str = 'info'):
        """Toggles autoupdating"""
        toggle_status = await self.settings.AutoUpdate()  # retrieves current status of toggle from settings file
        if toggle.lower() == 'off':
            await self.settings.AutoUpdate.set(False)
            await ctx.send("Automatic updating is now disabled.")
        elif toggle.lower() == 'on':
            await self.settings.AutoUpdate.set(True)
            await ctx.send("Automatic server updating is now enabled. You may wish to select a channel for autoupdate"
                           "messages to go to via {0}arkadmin channel.".format(ctx.prefix))
        else:
            if toggle_status:
                await ctx.send("Automatic updating is currently enabled. You may wish to select a channel for"
                               "autoupdate messages to go to via {0}arkadmin channel.".format(ctx.prefix))
            else:
                await ctx.send("Automatic updating is currently disabled.")

    @arkadmin.command(name="channel")
    async def arkadmin_channel(self, ctx, channel: discord.TextChannel):
        if not ctx.guild.me.permissions_in(channel).send_messages:
            return await ctx.send("I do not have permissions to send messages to {.mention}".format(channel))
        await self.settings.Channel.set(channel.id)
        await ctx.send("Channel set to {.mention}".format(channel))
        await ctx.send("You may also want to setup an administration channel with {0}arkadmin adminchannel. This"
                       "channel is used for full verbose autoupdater logs - it can be quite spammy but is useful for"
                       "diagnostics.".format(ctx.prefix))

    @arkadmin.command(name="role")
    async def arkadmin_role(self, ctx, role: discord.Role):
        await self.settings.Role.set(role.id)
        await ctx.send("Role set to {.mention}".format(role))

    @arkadmin.command(name="instancelimit")
    async def arkadmin_instancelimit(self, ctx, instance_limit: str = 'info'):
        try:
            instance_limit = int(instance_limit)
            await self.settings.InstanceLimit.set(instance_limit)
        except ValueError:
            return await ctx.send("Not a valid number.")
        await ctx.send("Instance limit set to {0}".format(instance_limit))

    @arkadmin.command(name="adminchannel")
    async def arkadmin_adminchannel(self, ctx, channel: discord.TextChannel):
        if not ctx.guild.me.permissions_in(channel).send_messages:
            return await ctx.send("I do not have permissions to send messages to {.mention}".format(channel))
        await self.settings.AdminChannel.set(channel.id)
        await ctx.send("Channel set to {.mention}".format(channel))

    @arkadmin.command(name="charmanagement")
    async def arkadmin_charactermanagement(self, ctx, toggle: str = 'info'):
        """Enables or disables the ability for users to store and retrieve character files belonging to them in the
         storage directory."""
        toggle_status = await self.settings.CharacterEnabled()
        if toggle.lower() == 'off':
            await self.settings.CharacterEnabled.set(False)
            await ctx.send("Character management has been disabled.")
        elif toggle.lower() == 'on':
            await self.settings.CharacterEnabled.set(True)
            await ctx.send("Character management has been enabled. Each user that wishes to use this feature needs to"
                           "have a SteamID assigned to their discord profile by my owner to ensure they can only "
                           "modify their own character save files.")
        else:
            if toggle_status:
                await ctx.send("Character management is currently enabled.")
            else:
                await ctx.send("Character management is currently disabled.")

    @arkadmin.command(name="verbose")
    async def ark_verbose(self, ctx, toggle: str = 'info'):
        """Toggles command verbosity"""
        toggle_status = await self.settings.Verbose()  # retrieves current status of toggle from settings file
        if toggle.lower() == 'off':
            await self.settings.Verbose.set(False)
            await ctx.send("I will not be verbose when executing commands.")
        elif toggle.lower() == 'on':
            await self.settings.Verbose.set(True)
            await ctx.send("I will output all lines from the console when executing commands.")
        else:
            if toggle_status:
                await ctx.send("I am currently outputting all lines from the console when executing commands.")
            else:
                await ctx.send("I am currently not being verbose when executing commands.")

    @ark.command(name="start")
    @commands.check(arkrolecheck)
    async def ark_start(self, ctx, minput: str = 'default'):
        """Starts the Ark Server"""
        if self.active_instances >= await self.settings.InstanceLimit():
            await ctx.send("Instance limit has been reached, please stop another instance first. If you think this is"
                           "incorrect, use [p]ark instancecheck.")
            return
        async with ctx.channel.typing():
            if minput != 'default':
                available_instances = await self.detect_instances()
                desired_instance = next((s for s in available_instances if minput.lower() in s.lower()), None)
                if not desired_instance:
                    await ctx.send("I don't recognize that instance, available options are {0}.".format(
                        available_instances))
                    return
            else:
                desired_instance = minput
            output = await self.runcommand("start", ctx.channel, await self.settings.Verbose(),
                                           desired_instance)
            if not await self.settings.Verbose():
                output = self.sanitizeoutput(output)
                await ctx.send(output)
            self.active_instances = self.active_instances + 1

    @ark.command(name="instancecheck")
    @commands.check(arkrolecheck)
    async def ark_instancecheck(self, ctx):
        """Resets self.active_instances in case it has become desynced from reality"""
        await self.discover_instances()
        await ctx.send("Detected {0} instances.".format(self.active_instances))

    @ark.command(name="status")
    async def ark_status(self, ctx, instance: str = 'default'):
        """Checks the server status"""
        async with ctx.channel.typing():
            verbose = await self.settings.Verbose()
            output = await self.runcommand("status", instance=instance, channel=ctx.channel, verbose=verbose)
            if not verbose:
                output = self.sanitizeoutput(output)
                await ctx.send(output)

    @ark.command(name="cancel")
    @commands.check(arkrolecheck)
    async def ark_cancel(self, ctx):
        """Cancels a pending restart"""
        self.cancel = True
        await ctx.send("Restart cancelled.")

    @ark.command(name="restart")
    @commands.check(arkrolecheck)
    async def ark_restart(self, ctx, delay: int = 60):
        """Restarts the ARK Server with a specified delay (in seconds)"""
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
        await self.runcommand("status", ctx.channel, False)
        if await self.playercheck():
            await ctx.send("Players are currently in the server, restart anyway?")
            answer = await self.bot.wait_for('message', check=waitcheck)
            try:
                if answer.content.lower() != "yes":
                    await ctx.send("Okay, restart cancelled.")
                    return
            except asyncio.TimeoutError:
                await ctx.send("Okay, restart cancelled.")
                return
        if self.updating:
            await ctx.send("I'm already carrying out a restart or update!")
        else:
            self.updating = True
            self.cancel = False
            await ctx.send("Restarting in {0} seconds.".format(delay))
            await ctx.bot.change_presence(activity=discord.Game(name="Restarting Server"), status=discord.Status.dnd)
            command = 'broadcast "Server will shutdown for a user-requested restart in '\
                      + str(delay) + ' seconds."'
            await self.runcommand(command, ctx.channel, False)
            await asyncio.sleep(delay)
            if not self.cancel:
                message = await ctx.send("Server is restarting...")
                output = await self.runcommand("restart", ctx.channel, await self.settings.Verbose())
                self.updating = False
                if self.successcheck(output):
                    status = ''
                    while '\x1b[0;39m Server online:  \x1b[1;32m Yes \x1b[0;39m\n' not in status:
                        await asyncio.sleep(15)
                        status = await self.runcommand("status")
                    await message.edit(content="Server is up.")
                    self.updating = False
                else:
                    try:
                        await ctx.send("Something went wrong \U0001F44F. {0}".format(output))
                    except discord.DiscordException:
                        print("Something went wrong \U0001F44F. {0}".format(output))
                    self.updating = False
            else:
                self.cancel = False
                await self.runcommand('broadcast "Restart was cancelled by user request."', ctx.channel,
                                      False)
                self.updating = False
                # restart was cancelled

    @ark.command(name="update")
    @commands.check(arkrolecheck)
    async def ark_update(self, ctx):
        """Checks for updates, if found, downloads, then restarts the server"""
        def waitcheck(m):
            return m.author == ctx.author and m.channel == ctx.channel
        status = await self.updatechecker(ctx.channel, await self.settings.Verbose())
        modstatus = await self.checkmods(ctx.channel, await self.settings.Verbose())
        if status or modstatus:
            await ctx.send("Updates are available.")
            offline = await self.offlinecheck()
            if await self.playercheck():
                await ctx.send("Players are currently in the server, update anyway?")
                answer = await self.bot.wait_for('message', check=waitcheck)
                try:
                    if answer.content.lower() != "yes":
                        await ctx.send("Okay, restart cancelled.")
                        return
                except asyncio.TimeoutError:
                    await ctx.send("Okay, restart cancelled.")
                    return
            await ctx.send("Server will be restarted in 60 seconds.")
            if self.updating:
                await ctx.send("I'm already carrying out a restart or update!")
            else:
                self.updating = True
                await ctx.bot.change_presence(activity=discord.Game(name="Updating Server"), status=discord.Status.dnd)
                await self.runcommand('broadcast "Server will shutdown for updates in 60 seconds."',
                                      ctx.channel, False)
                await asyncio.sleep(60)
                message = await ctx.send("Server is updating...")
                verbose = await self.settings.Verbose()
                output = await self.runcommand(command="update --update-mods --backup", channel=ctx.channel,
                                               verbose=verbose, instance='all')
                if self.successcheck(output):
                    if offline:
                        self.updating = False
                        return await message.edit(content="Server has been updated and is now online.")
                    status = ''
                    while '\x1b[0;39m Server online:  \x1b[1;32m Yes \x1b[0;39m\n' not in status:
                        await asyncio.sleep(15)
                        status = await self.runcommand("status")
                    await message.edit(content="Server has been updated and is now online.")
                    self.updating = False
                else:
                    try:
                        await ctx.send("Something went wrong \U0001F44F. {0}".format(output))
                    except discord.DiscordException:
                        print("Something went wrong \U0001F44F. {0}".format(output))
                    self.updating = False
        else:
            await ctx.send("No updates found.")

    @arkadmin.command(name="save")
    async def ark_save(self, ctx, minput: str = 'default'):
        """Saves the world state"""
        async with ctx.channel.typing():
            output = await self.runcommand(command="save", channel=ctx.channel,
                                           verbose=await self.settings.Verbose(), instance=minput)
            if not await self.settings.Verbose():
                await ctx.send(output)

    @arkadmin.command(name="backup")
    async def ark_backup(self, ctx, minput: str = 'default'):
        """Creates a backup of the save and config for the current instance. Use 'all' to backup all instances."""
        async with ctx.channel.typing():
            output = await self.runcommand(command="backup", channel=ctx.channel,
                                           verbose=await self.settings.Verbose(), instance=minput)
            if not await self.settings.Verbose():
                await ctx.send(output)

    @arkadmin.command(name="updatenow")
    async def ark_updatenow(self, ctx):
        """Updates with no delay or checks"""
        await self.runcommand("update --update-mods --backup", ctx.channel, True)

    @arkadmin.command(name="validate")
    async def ark_validate(self, ctx):
        """Validates files with steamcmd"""
        await self.runcommand("update --validate", ctx.channel, True)

    @arkadmin.command(name="forceupdate")
    async def ark_forceupdate(self, ctx):
        """Updates with the -force parameter"""
        await self.runcommand("update --update-mods --backup --force", ctx.channel, True)

    async def checkmods(self, channel=None, verbose=False):
        output = await self.runcommand("checkmodupdate", channel, verbose)
        for line in output:
            if 'has been updated on the Steam workshop' in line:
                return True
        return False

    async def updatechecker(self, channel=None, verbose=False):
        output = await self.runcommand("checkupdate", channel, verbose)
        if 'Your server is up to date!\n' in output:
            return False
        else:
            return True

    async def playercheck(self, channel=None, verbose=False):
        """Returns True if players are present in the server."""
        if await self.offlinecheck():
            return False
        output = await self.runcommand("status", channel, verbose)
        for line in output:
            if 'Players: 0' in line:
                return False
        return True

    async def offlinecheck(self, instance='default'):
        """Returns True if the server is offline"""
        output = await self.runcommand("status", instance=instance)
        if '\x1b[0;39m Server online:  \x1b[1;32m Yes \x1b[0;39m\n' in output and\
                '\x1b[0;39m Server running:  \x1b[1;32m Yes \x1b[0;39m\n' in output:
            return False
        else:
            return True

    @staticmethod
    def successcheck(output):
        for line in output:
            if 'The server is now running, and should be up within 10 minutes' in line:
                return True
            if 'Update to' in line and 'complete' in line:
                return True
        return False

    @staticmethod
    def sanitizeoutput(output):
        list_replacements = ["[1;32m ", "7", "[1;31m", "[0;39m   ", "[0;39m ", "[0;39m", "8[J", "[68G[   [1;32m",
                             "  ]", "\033"]
        message = "```"
        for elem in output:
            for item in list_replacements:
                elem = elem.replace(item, "")
            message += elem
        message += "```"
        return message

    async def discover_instances(self):
        self.active_instances = 0
        instance_list = []
        for instance in await self.detect_instances():
            if not await self.offlinecheck(instance=instance):
                self.active_instances = self.active_instances + 1
                instance_list.append(instance)
        if self.active_instances > await self.settings.InstanceLimit():
            print('Warning: More instances are currently running than the instance limit!')
            adminchannel = self.bot.get_channel(await self.settings.AdminChannel())
            if adminchannel is not None:
                await adminchannel.send('Warning: More instances are currently running than the instance limit!')
        return instance_list

    async def presence_manager(self):
        """Reports status of the currently active instance using discord status"""
        while self is self.bot.get_cog("arkserver"):
            if not self.updating:
                currentinstance = await self.settings.Instance()
                try:
                    output = await self.runcommand("status", instance=currentinstance)
                    if '\x1b[0;39m Server online:  \x1b[1;32m Yes \x1b[0;39m\n' not in output:
                        message = currentinstance + ': Offline'
                        await self.bot.change_presence(activity=discord.Game(name=message), status=discord.Status.dnd)
                    else:
                        players, version = None, None
                        for line in output:
                            if 'Players:' in line and 'Active' not in line:
                                players = line
                            if 'Server Name' in line:
                                version = '(' + line.split('(')[1]
                        try:
                            message = currentinstance + ' ' + players + version
                            await self.bot.change_presence(activity=discord.Game(name=message),
                                                           status=discord.Status.online)
                        except discord.DiscordException:
                            pass
                    await asyncio.sleep(30)
                except Exception as e:
                    print("Error in presence_manager: {0}".format(e))
                    await asyncio.sleep(30)
            else:
                await asyncio.sleep(15)

    async def notify_updates(self, instance):
        if await self.playercheck(instance):
            await self.runcommand('broadcast "Server will shutdown for updates in approximately'
                                  ' 15 minutes."', await self.settings.Channel(), False)
            await asyncio.sleep(300)
            await self.runcommand('broadcast "Server will shutdown for updates in approximately'
                                  ' 10 minutes."', await self.settings.Channel(), False)
            await asyncio.sleep(300)
            await self.runcommand('broadcast "Server will shutdown for updates in approximately'
                                  ' 5 minutes."', await self.settings.Channel(), False)
            await asyncio.sleep(240)
            await self.runcommand('broadcast "Server will shutdown for updates in approximately'
                                  ' 60 seconds."', await self.settings.Channel(), False)
            await asyncio.sleep(60)

    async def update_checker(self):
        """Checks for updates automatically every hour"""
        while self is self.bot.get_cog("arkserver"):
            await asyncio.sleep(60)
            if await self.settings.AutoUpdate():  # proceed only if autoupdating is enabled
                if not self.updating:  # proceed only if the bot isn't already manually updating or restarting
                    status = await self.updatechecker()
                    modstatus = await self.checkmods()
                    adminchannel = self.bot.get_channel(await self.settings.AdminChannel())
                    channel = self.bot.get_channel(await self.settings.Channel())
                    print("Update check completed at {0}".format(datetime.utcnow()))
                    if status or modstatus:  # proceed with update if checkupdate tells us that an update is available
                        instance_list = await self.discover_instances()
                        self.updating = True
                        await self.bot.change_presence(activity=discord.Game(name="Updating Server"),
                                                       status=discord.Status.dnd)
                        if not instance_list:
                            update = await self.runcommand(command="update --update-mods --backup",
                                                           channel=adminchannel, verbose=await self.settings.Verbose(),
                                                           instance='all')
                            if not await self.settings.Verbose():
                                if adminchannel is not None:
                                    await adminchannel.send(update)
                        else:
                            await asyncio.gather(*[self.notify_updates(instance) for instance in instance_list])
                            await self.update_server()
                        await self.bot.change_presence(activity=discord.Game(name="Servers Launching..."),
                                                       status=discord.Status.idle)
                        if channel is not None:
                            await channel.send("Servers have been updated and should be up within 10 minutes.")
                        await asyncio.sleep(300)
                        self.updating = False
                    else:
                        await asyncio.sleep(3540)
                else:
                    print("Server is already updating or restarting, auto-update cancelled")

    async def update_server(self):
        channel = self.bot.get_channel(await self.settings.Channel())
        adminchannel = self.bot.get_channel(await self.settings.AdminChannel())
        if channel is not None:
            await channel.send("Servers are restarting for updates.")
        update = await self.runcommand(command="update --update-mods --backup", channel=adminchannel,
                                       verbose=await self.settings.Verbose(), instance="all")
        if not await self.settings.Verbose():
            if adminchannel is not None:
                await adminchannel.send(update)
