import discord
from discord.ext import commands


class misc:
	"""Misc commands. Some of these commands are only meant to be used with specific discord servers."""

	def __init__(self, bot):
		self.bot = bot

	def _role_from_string(self, server, rolename, roles=None):
		if roles is None:
			roles = server.roles

		roles = [r for r in roles if r is not None]
		role = discord.utils.find(lambda r: r.name.lower() == rolename.lower(),
								  roles)
		try:
			print("Role {} found from rolename {}".format(
				role.name, rolename))
		except:
			print("Role not found for rolename {}".format(rolename))
		return role

	def tktcheck(ctx):
		return ctx.guild.id == 171970841100288000

	@commands.command()
	@commands.check(tktcheck)
	async def nsfw(self, ctx):
		"""Gives access to the TKT nsfw channel"""
		if '18+' in ctx.message.content:
			role = self._role_from_string(ctx.guild, 'nsfw')
			await ctx.author.add_roles(role, reason='Requested by User')
			await ctx.send('Done')
			return
		await self.bot.send_cmd_help(ctx)
	
	@commands.command()
	@commands.check(tktcheck)
	    async def praise(self, ctx):
		"""PRAISE THE ONE AND ONLY LICH QUEEN GENETTA! MAY SHE BLESS YOUR POOR SOUL!"""
		praises = []
		praises.append("ALL HAIL THE TRUE LICH QUEEN GENETTA!!")
		praises.append("We all are nothing but humble servants to you Lich Queen!!")
		praises.append("All praise the Lich Queen!")
		praises.append("PRAISE LICH QUEEN GENETTA! MAY SHE BLESS YOUR POOR SOUL!")
		praises.append("ALL PRAISE THE LICH QUEEN GENETTA!")
		await ctx.send(random.choice(praises))

