import asyncio
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
            RCONPassword=None
        )

    """Async RCON call using MrReacher's rcon implementation. Destination is hardcoded to localhost so this cog will 
    only function when present on the same machine as the server. If used on the same machine you can safely block
    external access to this port on your firewall."""
    async def rconcall(self, command):
        port = await self.settings.RCONPort()
        password = await self.settings.RCONPassword()
        async with MinecraftClient('localhost', port, password) as mc:
            output = await mc.send(command)
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
        else:
            return False
