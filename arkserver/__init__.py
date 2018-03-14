from .arkserver import arkserver
import asyncio


def setup(bot):
	n = arkserver(bot)
	loop = asyncio.get_event_loop()
	loop.create_task(n.update_checker())
	loop.create_task(n.presence_manager())
	loop.create_task(n.integrity_checker())
	bot.add_cog(n)