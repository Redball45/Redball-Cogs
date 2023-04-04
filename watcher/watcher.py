import urllib.request

import asyncio
from redbot.core import commands
import webbrowser

BaseCog = getattr(commands, "Cog", object)


class Watcher(BaseCog):
    """Ark Server commands"""

    def __init__(self, bot):
        self.bot = bot

    async def ticket_watch(self):
        while self is self.bot.get_cog("Watcher"):
            channel = self.bot.get_channel(1058922005841334292)
            url = "https://www.fansale.co.uk/fansale/tickets/classical/final-fantasy-xiv/790111/16817717"
            text = "Unfortunately no suitable offers were found."
            webbrowser.open(url)
            # Search for the text on the website
            with urllib.request.urlopen(url) as response:
                html = response.read().decode("utf-8")
                if text in html:
                    await channel.send("Tickets may be available!")
                    await channel.send(f"{url}")
            await asyncio.sleep(600)
