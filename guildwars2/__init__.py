import datetime
import json
import logging
import logging.handlers
import os
import discord

import aiohttp
from .account import AccountMixin
from .achievements import AchievementsMixin
from .api import ApiMixin
from .characters import CharactersMixin
from .commerce import CommerceMixin
from .daily import DailyMixin
from .database import DatabaseMixin
from .events import EventsMixin
from .guild import GuildMixin
from .guildmanage import GuildManageMixin
from .key import KeyMixin
from .misc import MiscMixin
from .notifiers import NotiifiersMixin
from .pvp import PvpMixin
from .wallet import WalletMixin
from .wvw import WvwMixin
from .exceptions import APIKeyError, APIError, APIInvalidKey, APIInactiveError
from .mongo import MongoController
from .extras import ExtrasMixin

with open("cogs/CogManager/cogs/guildwars2/dbconfig.json", encoding="utf-8", mode="r") as f:
    data = json.load(f)
    DB_HOST = data["DATABASE"]["host"]
    DB_PORT = data["DATABASE"]["port"]
    DB_CREDENTIALS = data["DATABASE"]["credentials"]


class GuildWars2(AccountMixin, AchievementsMixin, ApiMixin, CharactersMixin, CommerceMixin,
                 DailyMixin, DatabaseMixin, EventsMixin, GuildMixin, GuildManageMixin, KeyMixin,
                 MiscMixin, NotiifiersMixin, PvpMixin, WalletMixin, WvwMixin, ExtrasMixin):
    """Guild Wars 2 commands"""

    def __init__(self, bot):
        self.bot = bot
        self.bot.database = MongoController(DB_HOST, DB_PORT, DB_CREDENTIALS)
        self.db = self.bot.database.db.gw2
        with open(
                "cogs/CogManager/cogs/guildwars2/gamedata.json", encoding="utf-8",
                mode="r") as f:
            self.gamedata = json.load(f)
        with open(
                "cogs/CogManager/cogs/guildwars2/containers.json", encoding="utf-8",
                mode="r") as f:
            self.containers = json.load(f)
        self.session = aiohttp.ClientSession(loop=self.bot.loop)
        self.boss_schedule = self.generate_schedule()
        self.embed_color = 0xc12d2b
        self.log = logging.getLogger(__name__)
        self.tasks = []
        self.waiting_for = []
        self.bot.available = True

    def __unload(self):
        for task in self.tasks:
            task.cancel()
        self.tasks = []
        self.session.close()

    async def error_handler(self, ctx, exc):
        user = ctx.author
        if isinstance(exc, APIKeyError):
            await ctx.send(exc)
            return
        if isinstance(exc, APIInactiveError):
            await ctx.send("{.mention}, the API is currently down. "
                           "Try again later.".format(user))
            return
        if isinstance(exc, APIInvalidKey):
            await ctx.send("{.mention}, your API key is invalid! Remove your "
                           "key and add a new one".format(user))
            return
        if isinstance(exc, APIError):
            await ctx.send(
                "{.mention}, API has responded with the following error: "
                "`{}`".format(user, exc))
            return

    def can_embed_links(self, ctx):
        if not isinstance(ctx.channel, discord.abc.GuildChannel):
            return True
        return ctx.channel.permissions_for(ctx.me).embed_links

def setup_logging():
    if not os.path.exists("logs"):
        os.makedirs("logs")
    if not os.path.isfile("logs/guildwars2.log"):
        with open("logs/guildwars2.log", 'a'):
            os.utime("logs/guildwars2.log", None)
    formatter = logging.Formatter(
        '%(asctime)s:%(levelname)s:%(name)s: %(message)s')
    logging.getLogger("discord").setLevel(logging.INFO)
    logging.getLogger("discord.http").setLevel(logging.WARNING)
    logger = logging.getLogger("")
    logger.setLevel(logging.INFO)
    file_hdlr = logging.handlers.RotatingFileHandler(
        filename="logs/guildwars2.log",
        maxBytes=10 * 1024 * 1024,
        encoding="utf-8",
        backupCount=5)
    file_hdlr.setFormatter(formatter)
    stderr_hdlr = logging.StreamHandler()
    stderr_hdlr.setFormatter(formatter)
    stderr_hdlr.setLevel(logging.ERROR)
    logger.addHandler(file_hdlr)
    logger.addHandler(stderr_hdlr)

def setup(bot):
    setup_logging()
    cog = GuildWars2(bot)
    loop = bot.loop
    bot.database = MongoController(DB_HOST, DB_PORT, DB_CREDENTIALS)
    loop.create_task(
        bot.database.setup_cog(cog, {
            "cache": {
                "day": datetime.datetime.utcnow().weekday(),
                "news": [],
                "build": 0,
                "dailies": {},
                "arcdps": 0
            }
        }))
    tasks = (cog.game_update_checker, cog.daily_checker, cog.news_checker,
            cog.gem_tracker, cog.world_population_checker, cog.guild_synchronizer,
            cog.boss_notifier, cog.forced_account_names, cog.arcdps_checker)
    for task in tasks:
        cog.tasks.append(loop.create_task(task()))
    bot.add_cog(cog)
