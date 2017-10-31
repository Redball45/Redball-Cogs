from .poll import poll


def setup(bot):
	n = poll(bot)
	bot.add_cog(n)
	bot.add_listener(n.check_poll_votes, "on_message")
