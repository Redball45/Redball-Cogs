import asyncio
import glob

import discord
from redbot.core import commands
from redbot.core import Config
from .async_mcrcon import MinecraftClient

BaseCog = getattr(commands, "Cog", object)


async def setupcheck(ctx):
    """Because the help formatter uses this check outside the cog to determine whether to show you can see this command,
     and our checks access the cog config, we need to access the cog settings separately here"""
    del ctx
    from redbot.core import Config
    settings = Config.get_conf(cog_instance=None, identifier=54252452, force_registration=False,
                               cog_name="MineServer")
    return await settings.SetupDone()


async def minerolecheck(ctx):
    """Because the help formatter uses this check outside the cog to determine whether to show you can see this command,
     and our checks access the cog config, we need to access the cog settings separately here"""
    from redbot.core import Config
    settings = Config.get_conf(cog_instance=None, identifier=54252452, force_registration=False,
                               cog_name="MineServer")
    role = discord.utils.get(ctx.guild.roles, id=(await settings.Role()))
    return role in ctx.author.roles


class MineServer(BaseCog):
    """Minecraft server commands"""

    def __init__(self, bot):
        self.bot = bot
        self.settings = Config.get_conf(self, 54252452)
        self.settings.register_global(
            SetupDone=False,
            RCONPort=None,
            RCONPassword=None,
            LineNumber=1,
            Channel=None,
            LogFile=None,
            ChatEnabled=False
        )

    """Async RCON call using MrReacher's rcon implementation. Destination is hardcoded to localhost so this cog will 
    only function when present on the same machine as the server. If used on the same machine you can safely block
    external access to this port on your firewall."""

    async def rconcall(self, command):
        port = await self.settings.RCONPort()
        password = await self.settings.RCONPassword()
        try:
            async with MinecraftClient('localhost', port, password) as mc:
                output = await mc.send(command)
                return output
        except OSError as e:
            output = "Error when communicating with minecraft server: {0}".format(e)
            return output

    @commands.command()
    @commands.is_owner()
    async def minesetup(self, ctx):
        """Interactive setup process. Please complete this setup in DM with the bot to protect your RCON password."""

        def wait_check(message):
            return message.author == ctx.author and message.channel == ctx.channel

        try:
            await ctx.send("This setup process will set required options for this cog to function. For each question,"
                           "you should respond with desired setting.")
            await ctx.send("First, please respond with the RCON Port for the minecraft server.'.")
            answer = await self.bot.wait_for("message", check=wait_check, timeout=30)
            rcon_port = answer.content
            await ctx.send("Next, please respond with the RCON password for the server.")
            answer = await self.bot.wait_for("message", check=wait_check, timeout=30)
            rcon_pass = answer.content
        except asyncio.TimeoutError:
            return await ctx.send("You didn't reply in time, setup cancelled.")
        await self.settings.RCONPort.set(rcon_port)
        await self.settings.RCONPassword.set(rcon_pass)
        await self.settings.SetupDone.set(True)
        await ctx.send("Setup complete. If you need to change any of these settings, simply re-run this setup command.")

    @commands.group(aliases=["mc"])
    @commands.check(setupcheck)
    async def minecraft(self, ctx):
        """Commands related to remote management of a minecraft server."""

    @minecraft.command()
    @commands.check(minerolecheck)
    async def save(self, ctx):
        """Saves the world state to disk."""
        output = await self.rconcall("save-all")
        await ctx.send(output)

    @minecraft.command()
    async def list(self, ctx):
        """Returns a list of the players currently in the server."""
        output = await self.rconcall("list")
        await ctx.send(output)

    @minecraft.command()
    async def mods(self, ctx):
        """Returns a list of the mods currently in the server."""
        output = "```"
        for file in glob.glob("/home/minecraft/rebound/mods/*.jar"):
            filename = file.replace("/home/minecraft/rebound/mods/", "")
            filename = filename.replace(".jar", "")
            output = output + filename + "\n"
        output += "```"
        await ctx.send(output)

    @minecraft.command()
    @commands.check(minerolecheck)
    async def stop(self, ctx):
        """Stops the server gracefully, saving before shutdown."""

        def waitcheck(wait_react, wait_user):
            return wait_user == ctx.author and str(wait_react.emoji) == '✅' or wait_user == ctx.author and \
                   str(wait_react.emoji) == '❎'

        if await self.emptycheck():
            output = await self.rconcall("stop")
            return await ctx.send(output)
        message = await ctx.send("Players are currently in the server, shutdown anyway?")
        await message.add_reaction("✅")
        await message.add_reaction("❎")
        try:
            reaction, user = await self.bot.wait_for("reaction_add", check=waitcheck, timeout=30.0)
        except asyncio.TimeoutError:
            await message.clear_reactions()
            await message.edit(content="You took too long... shut down cancelled.")
            return
        if str(reaction.emoji) == '✅':
            output = await self.rconcall("stop")
        else:
            output = "Okay, shut down cancelled."
        await message.clear_reactions()
        await ctx.send(output)

    @minecraft.command()
    @commands.check(minerolecheck)
    async def whitelist(self, ctx, toggle: str = "info"):
        """Enables and disables the whitelist. Use whitelist on to enable and whitelist off to disable."""
        if toggle.lower() == "off":
            output = await self.rconcall("whitelist off")
            await ctx.send(output)
        elif toggle.lower() == "on":
            output = await self.rconcall("whitelist on")
            await ctx.send(output)
        else:
            await ctx.send("To enable the whitelist, use {0}minecraft whitelist on, and to disable use {0}minecraft"
                           "whitelist off.".format(ctx.prefix))

    @minecraft.command(aliases=["wca"])
    @commands.check(minerolecheck)
    async def whitelistadd(self, ctx, username: str):
        """Adds a user to the whitelist. They must be in the server."""
        command = "whitelist add " + username
        output = await self.rconcall(command)
        await ctx.send(output)

    @minecraft.command(aliases=["chat"])
    @commands.check(minerolecheck)
    async def say(self, ctx, *, message: str):
        """Sends a message that can be read by players in-game."""
        nick = ctx.author.display_name
        command = "say " + nick + ": " + message
        await self.rconcall(command)
        await ctx.message.add_reaction("✅")

    @commands.command(name="minerole")
    @commands.is_owner()
    async def minerole(self, ctx, role: discord.Role):
        """Sets a privileged role that has access to additional commands, privileged users can
        stop the server, save the world state and enable/disable the whitelist. """
        await self.settings.Role.set(role.id)
        await ctx.send("Role set to {.mention}".format(role))

    async def emptycheck(self):
        output = await self.rconcall("list")
        pccheck = output.split(":")
        if 'There are 0 ' in pccheck[0]:
            return True
        elif 'Error when communicating with minecraft server' in pccheck[0]:
            return True
        else:
            return False

    @minecraft.command(name="channel")
    async def channel(self, ctx, channel: discord.TextChannel):
        """Sets the channel that in-game chat is sent to. Set to None to disable."""
        if not ctx.guild.me.permissions_in(channel).send_messages:
            return await ctx.send("I do not have permissions to send messages to {.mention}".format(channel))
        await self.settings.Channel.set(channel.id)
        await ctx.send("Channel set to {.mention}".format(channel))

    @minecraft.command(name="logfile")
    async def logfile(self, ctx, *, filepath: str):
        """Sets the path to the log file that chat messages will be read from. This should be the latest.log file
        located within your minecraft/logs server directory."""
        await self.settings.LogFile.set(filepath)
        await ctx.send("File path set to {0}".format(filepath))

    @minecraft.command()
    @commands.is_owner()
    async def chatenabled(self, ctx, toggle: str = "info"):
        """Toggles whether chat is read from log files and outputted to discord. A channel and log file location must
        be set for this to work."""
        toggle_status = await self.settings.ChatEnabled()  # retrieves current status of toggle from settings file
        if toggle.lower() == "off":
            await self.settings.ChatEnabled.set(False)
            await ctx.send("I will no longer output chat from the server to discord..")
        elif toggle.lower() == "on":
            await self.settings.ChatEnabled.set(True)
            await ctx.send("I will output chat from the server to discord. A channel and log file location must be"
                           "set for this to work.")
        else:
            if toggle_status:
                await ctx.send("Chat output to discord is currently disabled.")
            else:
                await ctx.send("Chat output to discord is currently enabled.")

    @minecraft.command()
    @commands.is_owner()
    async def rlm(self, ctx):
        """Debug command, returns the current line number"""
        line = await self.settings.LineNumber()
        await ctx.send(line)

    async def readlogloop(self):
        """Reads from the minecraft log file and prints chat to a channel"""
        # Hardcoded values that should be changed to settings
        while self is self.bot.get_cog("MineServer"):
            await asyncio.sleep(5)
            while await self.settings.ChatEnabled():
                await asyncio.sleep(2)
                channel = self.bot.get_channel(await self.settings.Channel())
                file = await self.settings.LogFile()
                if channel is not None and file is not None:
                    if not await self.emptycheck():
                        with open(file, "r") as f:
                            data = f.readlines()
                            if await self.settings.LineNumber() > len(data):
                                await self.settings.LineNumber.set(1)
                            elif await self.settings.LineNumber() == len(data):
                                pass
                            else:
                                line = data[await self.settings.LineNumber()]
                                if "[Async Chat Thread - #4/INFO]: " in line:
                                    await channel.send(line.split("]:")[1])
                                await self.settings.LineNumber.set(await self.settings.LineNumber() + 1)
