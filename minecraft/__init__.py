from .minecraft import minecraft
import asyncio


def setup(bot):
	n = minecraft(bot)
	loop = asyncio.get_event_loop()
	bot.add_cog(n)