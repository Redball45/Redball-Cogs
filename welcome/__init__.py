from .welcome import Welcome


def setup(bot):
	cog = Welcome(bot)
	bot.add_listener(cog.on_join, "on_member_join")
	bot.add_listener(cog.on_intro, "on_message")
	bot.add_cog(cog)
	