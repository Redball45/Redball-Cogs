import discord
from discord.ext import commands
from redbot.core import Config

import asyncio
from datetime import datetime





class poll:
	"""Modification of original Red-Discord Bot poll to use config so that longer polls can be run and data is not lost after reload/restart."""

	def __init__(self, bot):
		self.settings = Config.get_conf(self, 21931)
		default_channel = {
			"ACTIVE": False,
			"QUESTION": '',
			"ANSWERS": {},
			"DATETIME": ''
			}
		self.settings.register_channel(**default_channel)


	@commands.command(no_pm=True)
	async def startpoll(self, ctx, *text):
		"""Starts a poll"""
	if await self.settings.channel(ctx.channel).ACTIVE()
		await ctx.send("Poll already ongoing in this channel")
		return
	check = " ".join(text).lower()
	if '@everyone' in check or '@here' in check:
		await ctx.send("Nice try.")
		return
	msg = [ans.strip() for ans in text.split(";")]
	if len(msg) < 2:
		await ctx.send("Not a valid poll.")
		return
	question = msg[0]
	msg.remove(question)
	await self.settings.channel(ctx.channel).QUESTION.set(question)
	answers = {}
	count = 1
	for answer in msg:
		answers[count] = {"ANSWER": answer, "VOTES" : 0}
		count += 1
	await self.settings.channel(ctx.channel).ANSWERS.set(answers)
	await self.settings.channel(ctx.channel).ACTIVE.set(True)
	now = datetime.utcnow()
	await self.settings.channel(ctx.channel).DATETIME.set(now)
	message = "**POLL STARTED!**\n\n{}\n\n".format(question)
	for id, data in answers.items():
		message += "{}. *{}*\n".format(id, data["ANSWER"])
	msg += "\nType the number to vote!"
	await ctx.send(message)



	@commands.command(no_pm=True)
	async def stoppoll(self, ctx)
	if not await self.settings.channel(ctx.channel).ACTIVE()
		await ctx.send("No poll ongoing in this channel")
		return
	starttime = await self.settings.channel(ctx.channel).DATETIME()
	answers = await self.settings.channel(ctx.channel).ANSWERS()
	already_voted = []
	async for message in ctx.channel.history(after=starttime):
		content = message.content
		try:
			i = int(message.content)
			if i in answers.keys():
				if message.author.id not in already_voted:
					data = answers[i]
					data["VOTES"] += 1
					answers[i] = data
					already_voted.append(message.author.id)
		except ValueError:
			pass
	msg = "**POLL ENDED!**\n\n{}\n\n".format(self.question)
	for data in answers.values():
		msg += "*{}* - {} votes\n".format(data["ANSWER"], str(data["VOTES"]))
	await self.settings.channel(ctx.channel).ACTIVE.set(False)
	await ctx.send(msg)
