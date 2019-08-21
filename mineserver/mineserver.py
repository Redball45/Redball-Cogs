import asyncio
import discord
from redbot.core import commands
from redbot.core import Config
from async_mcrcon import MinecraftClient

BaseCog = getattr(commands, "Cog", object)


async def setupcheck(ctx):
    """Because the help formatter uses this check outside the arkserver cog, to access the cog settings we
    need to get them separately here"""
    del ctx
    from redbot.core import Config
    settings = Config.get_conf(cog_instance=None, identifier=3931293439, force_registration=False,
                               cog_name="mineserver")
    return await settings.SetupDone()


async def minerolecheck(ctx):
    """Because the help formatter uses this check outside the arkserver cog, to access the cog settings we need
     to get them separately here"""
    from redbot.core import Config
    settings = Config.get_conf(cog_instance=None, identifier=54252452, force_registration=False,
                               cog_name="mineserver")
    role = discord.utils.get(ctx.guild.roles, id=(await settings.Role()))
    return role in ctx.author.roles


class ArkManagerException(Exception):
    pass


class MineServer(BaseCog):
    """Ark Server commands"""
    def __init__(self, bot):
        self.bot = bot
        self.settings = Config.get_conf(self, 54252452)
        self.settings.register_global(
            SetupDone=False,
            RCONPort=None,
            RCONPassword=None
        )

    async def rconcall(self, command):
        async with MinecraftClient('localhost', self.settings.RCONPort(), self.settings.RCONPassword) as mc:
            output = await mc.send(command)
            return output

    @commands.command()
    @commands.is_owner()
    async def minesetup(self, ctx):
        """Interactive setup process. Please complete this setup in DM with the bot."""
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

    @commands.group()
    @commands.check(setupcheck)
    @commands.check(minerolecheck)
    async def minecraft(self, ctx):
        """Commands related to the MinecraftServer"""

    @minecraft.command()
    async def save(self, ctx):
        await ctx.send(self.rconcall("save-all"))

    @commands.command(name="minerole")
    @commands.is_owner()
    async def minerole(self, ctx, role: discord.Role):
        """Sets a privileged role that has access to additional commands, privileged users can
        start, stop, restart, update, and change the active instance. """
        await self.settings.Role.set(role.id)
        await ctx.send("Role set to {.mention}".format(role))
