import discord
from discord.ext import commands
from redbot.core import Config

import asyncio


class poll:
	"""Modification of original Red-Discord Bot poll to use config so that longer polls can be run and data is not lost after reload/restart."""

	def __init__(self, bot):
		self.bot = bot
		self.settings = Config.get_conf(self, 21931)
		default_channel = {
			"ACTIVE": False,
			"QUESTION": '',
			"ANSWERS": {},
			"MESSAGEID": 0,
			"KEYS": [],
			"RESPONDED": []
			}
		self.settings.register_channel(**default_channel)
		self.responded = []


	@commands.command(no_pm=True)
	@commands.has_permissions(manage_messages=True)
	async def startpoll(self, ctx, *text):
		"""Starts a poll"""
		if len(text) < 1:
			return await self.bot.send_cmd_help(ctx)
		if await self.settings.channel(ctx.channel).ACTIVE():
			await ctx.send("Poll already ongoing in this channel")
			return
		check = " ".join(text).lower()
		if '@everyone' in check or '@here' in check:
			await ctx.send("Nice try.")
			return
		text = " ".join(text)
		msg = [ans.strip() for ans in text.split(";")]
		if len(msg) < 2:
			await ctx.send("Not a valid poll.")
			return
		question = msg[0]
		msg.remove(question)
		await self.settings.channel(ctx.channel).QUESTION.set(question)
		answers = {}
		count = 1
		keys = []
		responded = []
		for answer in msg:
			answers[str(count)] = {"ANSWER": answer, "VOTES" : 0}
			keys.append(count)
			count += 1
		await self.settings.channel(ctx.channel).ANSWERS.set(answers)
		await self.settings.channel(ctx.channel).ACTIVE.set(True)
		await self.settings.channel(ctx.channel).MESSAGEID.set(ctx.message.id)
		await self.settings.channel(ctx.channel).KEYS.set(keys)
		await self.settings.channel(ctx.channel).RESPONDED.set(responded)
		message = "**POLL STARTED!**\n\n{}\n\n".format(question)
		for key in keys:
			key = str(key)
			message += "{}. *{}*\n".format(key, answers[key]["ANSWER"])
		msg += "\nType the number to vote!"
		await ctx.send(message)
		del answers

	@commands.command(no_pm=True)
	@commands.is_owner()
	async def resetpoll(self, ctx):
		await self.settings.channel(ctx.channel).ACTIVE.set(False)
		await ctx.send("Done")


	@commands.command(no_pm=True)	
	@commands.has_permissions(manage_messages=True)
	async def stoppoll(self, ctx):
		if not await self.settings.channel(ctx.channel).ACTIVE():
			await ctx.send("No poll ongoing in this channel")
			return
		start = await self.settings.channel(ctx.channel).MESSAGEID()
		startmessage = await ctx.channel.get_message(start)
		answers = await self.settings.channel(ctx.channel).ANSWERS()
		question = await self.settings.channel(ctx.channel).QUESTION()
		keys = await self.settings.channel(ctx.channel).KEYS()
		already_voted = []
		async for message in ctx.channel.history(after=startmessage):
			try:
				i = int(message.content)
				i = str(i)
				if i in answers.keys():
					if message.author.id not in already_voted:
						data = answers[i]
						data["VOTES"] += 1
						answers[i] = data
						already_voted.append(message.author.id)
			except ValueError:
				pass
		msg = "**POLL ENDED!**\n\n{}\n\n".format(question)
		for key in keys:
			key = str(key)
			msg += "*{}* - {} votes\n".format(answers[key]["ANSWER"], str(answers[key]["VOTES"]))
		await self.settings.channel(ctx.channel).ACTIVE.set(False)
		await ctx.send(msg)

	async def check_poll_votes(self, message):
		if message.author.id != self.bot.user.id:
			if message.channel:
				if await self.settings.channel(message.channel).ACTIVE():
					responded = await self.settings.channel(message.channel).RESPONDED()
					if message.author.id not in responded:
						keys = await self.settings.channel(message.channel).KEYS()
						try:
							i = int(message.content)
						except ValueError:
							return
						if i in keys:
							reply = await message.channel.send("Response recorded.")
							responded.append(message.author.id)
							await self.settings.channel(message.channel).RESPONDED.set(responded)
							await asyncio.sleep(15)
							try:
								await reply.delete()
							except:
								pass

