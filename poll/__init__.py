from .misc import misc
import asyncio


def setup(bot):
	n = misc(bot)
	#loop = asyncio.get_event_loop()
	#loop.create_task(n.gandarafullcheck())
	bot.add_cog(n)
	bot.add_listener(n.check_poll_votes, "on_message")