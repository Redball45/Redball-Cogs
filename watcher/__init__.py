from .watcher import Watcher
import asyncio


def setup(bot):
	n = Watcher(bot)
	loop = asyncio.get_event_loop()
	loop.create_task(n.ticket_watch())
	bot.add_cog(n)
