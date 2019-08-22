from .mineserver import MineServer
import asyncio


def setup(bot):
	n = MineServer(bot)
	loop = asyncio.get_event_loop()
	loop.create_task(n.readlogloop())
	bot.add_cog(n)
