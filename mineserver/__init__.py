from .mineserver import MineServer


def setup(bot):
	n = MineServer(bot)
	bot.add_cog(n)
