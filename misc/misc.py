import discord
from discord.ext import commands

import asyncio
import os
import os.path
import sys
import aiohttp
import copy
import glob
from typing import List
import subprocess
from threading import Thread
import shlex

try:
	from Queue import Queue, Empty
except ImportError:
	from queue import Queue, Empty # python 3.x

ON_POSIX = 'posix' in sys.builtin_module_names

DEFAULT_HEADERS = {'User-Agent': "A GW2 Discord bot",
'Accept': 'application/json'}

settings = {"POLL_DURATION" : 86400}

class APIError(Exception):
	pass

class APIConnectionError(APIError):
	pass

class APIForbidden(APIError):
	pass

class APIBadRequest(APIError):
	pass

class ShinyAPIError(Exception):
	pass

class APIKeyError(APIError):
	pass

class APINotFound(APIError):
	pass


class misc:
	"""Misc commands. Some of these commands are only meant to be used with specific discord servers."""

	def __init__(self, bot):
		self.bot = bot
		self.report_base = "data/reports"
		self.evtc_base = "data/reports"
		self.gandaracheck = True
		self.session = aiohttp.ClientSession(loop=self.bot.loop)
		self.poll_sessions = []

	def __unload(self):
		self.session.close()

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

	@commands.command(no_pm=True)
	async def poll(self, ctx, *text):
		"""Starts/stops a poll

		Usage example:
		poll Is this a poll?;Yes;No;Maybe
		poll stop"""
		message = ctx.message
		if len(text) == 1:
			if text[0].lower() == "stop":
				await self.endpoll(message, ctx)
				return
		await ctx.send("Enter the duration of the poll in hours: ")
		def waitcheck(m):
			return m.author == ctx.author and m.channel == ctx.channel
		try:
			answer = await self.bot.wait_for('message', timeout=30, check=waitcheck)
		except:
			await ctx.send("You took too long...")
			return
		try:
			duration = int(answer.content)
			duration = duration * 60 * 60
		except ValueError:
			await ctx.send("Please enter only a duration in hours e.g 24 ")
			return
		if not self.getPollByChannel(message):
			check = " ".join(text).lower()
			if "@everyone" in check or "@here" in check:
				await ctx.send("Nice try.")
				return
			p = NewPoll(message, " ".join(text), self)
			if p.valid:
				self.poll_sessions.append(p)
				await p.start(duration)
			else:
				await ctx.send("poll question;option1;option2 (...)")
		else:
			await ctx.send("A poll is already ongoing in this channel.")

	async def endpoll(self, message, ctx):
		if self.getPollByChannel(message):
			p = self.getPollByChannel(message)
			if p.author == message.author.id: # or isMemberAdmin(message)
				await self.getPollByChannel(message).endPoll()
			else:
				await ctx.send("Only admins and the author can stop the poll.")
		else:
			await ctx.send("There's no poll ongoing in this channel.")

	def getPollByChannel(self, message):
		for poll in self.poll_sessions:
			if poll.channel == message.channel:
				return poll
		return False

	async def check_poll_votes(self, message):
		if message.author.id != self.bot.user.id:
			if self.getPollByChannel(message):
					await self.getPollByChannel(message).checkAnswer(message)

	def fetch_joined_at(self, user, server):
		"""Just a special case for someone special :^)"""
		if user.id == "96130341705637888" and server.id == "133049272517001216":
			return datetime.datetime(2016, 1, 10, 6, 8, 4, 443000)
		else:
			return user.joined_at


class NewPoll():
	def __init__(self, message, text, main):
		self.channel = message.channel
		self.author = message.author.id
		self.client = main.bot
		self.poll_sessions = main.poll_sessions
		msg = [ans.strip() for ans in text.split(";")]
		if len(msg) < 2: # Needs at least one question and 2 choices
			self.valid = False
			return None
		else:
			self.valid = True
		self.already_voted = []
		self.question = msg[0]
		msg.remove(self.question)
		self.answers = {}
		i = 1
		for answer in msg: # {id : {answer, votes}}
			self.answers[i] = {"ANSWER" : answer, "VOTES" : 0}
			i += 1

	async def start(self, duration):
		msg = "**POLL STARTED!**\n\n{}\n\n".format(self.question)
		for id, data in self.answers.items():
			msg += "{}. *{}*\n".format(id, data["ANSWER"])
		msg += "\nType the number to vote!"
		await self.channel.send(msg)
		await asyncio.sleep(duration)
		if self.valid:
			await self.endPoll()

	async def endPoll(self):
		self.valid = False
		msg = "**POLL ENDED!**\n\n{}\n\n".format(self.question)
		for data in self.answers.values():
			msg += "*{}* - {} votes\n".format(data["ANSWER"], str(data["VOTES"]))
		await self.channel.send(msg)
		self.poll_sessions.remove(self)

	async def checkAnswer(self, message):
		try:
			i = int(message.content)
			if i in self.answers.keys():
				if message.author.id not in self.already_voted:
					data = self.answers[i]
					data["VOTES"] += 1
					self.answers[i] = data
					self.already_voted.append(message.author.id)
					channel = message.channel
					response = await channel.send("Response recorded.")
					try:
						await message.delete()
						await asyncio.sleep(30)
						await response.delete()
					except:
						await channel.send("Can't delete your message")
		except ValueError:
			pass
