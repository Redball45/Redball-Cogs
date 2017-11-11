from collections import OrderedDict
from itertools import chain
from operator import itemgetter

import discord
from discord.ext import commands
from discord.ext.commands.cooldowns import BucketType

from .exceptions import APIError


class AccountMixin:
    @commands.command()
    @commands.cooldown(1, 10, BucketType.user)
    async def account(self, ctx):
        """General information about your account

        Required permissions: account
        """
        user = ctx.author
        await ctx.trigger_typing()
        try:
            doc = await self.fetch_key(user, ["account"])
            results = await self.call_api("account", key=doc["key"])
        except APIError as e:
            return await self.error_handler(ctx, e)
        accountname = doc["account_name"]
        created = results["created"].split("T", 1)[0]
        hascommander = "Yes" if results["commander"] else "No"
        data = discord.Embed(colour=self.embed_color)
        data.add_field(name="Created account on", value=created)
        if "progression" in doc["permissions"]:
            try:
                endpoints = ["account/achievements", "account"]
                achievements, account = await self.call_multiple(
                    endpoints, ctx.author, ["progression"])
            except APIError as e:
                return await self.error_handler(ctx, e)
            possible_ap = await self.total_possible_ap()
            user_ap = await self.calculate_user_ap(achievements, account)
            data.add_field(
                name="Achievement Points",
                value="{} earned out of {} possible".format(
                    user_ap, possible_ap),
                inline=False)
        data.add_field(name="Commander tag", value=hascommander, inline=False)
        if "fractal_level" in results:
            fractallevel = results["fractal_level"]
            data.add_field(name="Fractal level", value=fractallevel)
        if "wvw_rank" in results:
            wvwrank = results["wvw_rank"]
            data.add_field(name="WvW rank", value=wvwrank)
        if "pvp" in doc["permissions"]:
            try:
                pvp = await self.call_api("pvp/stats", user)
            except APIError as e:
                return await self.error_handler(ctx, e)
            pvprank = pvp["pvp_rank"] + pvp["pvp_rank_rollovers"]
            data.add_field(name="PVP rank", value=pvprank)
        data.set_author(name=accountname)
        try:
            await ctx.send(embed=data)
        except discord.Forbidden:
            await ctx.send("Need permission to embed links")

    @commands.command()
    @commands.cooldown(1, 15, BucketType.user)
    async def li(self, ctx):
        """Shows how many Legendary Insights you have earned

        Required permissions: inventories, characters
        """
        user = ctx.author
        scopes = ["inventories", "characters"]
        await ctx.trigger_typing()
        try:
            doc = await self.fetch_key(user, scopes)
            endpoints = [
                "account/bank", "account/materials", "account/inventory",
                "characters?page=0"
            ]
            results = await self.call_multiple(endpoints, key=doc["key"])
            bank, materials, shared, characters = results
        except APIError as e:
            return await self.error_handler(ctx, e)
        # Items to look for
        ids = self.gamedata.get("insights")
        id_legendary_insight = ids.get("legendary_insight")
        id_gift_of_prowess = ids.get("gift_of_prowess")
        id_envoy_insignia = ids.get("envoy_insignia")
        ids_refined_envoy_armor = set(ids.get("refined_envoy_armor").values())
        ids_perfected_envoy_armor = set(
            ids.get("perfected_envoy_armor").values())

        # Filter empty slots and uninteresting items out of the inventories.
        #
        # All inventories are converted to lists as they are used multiple
        # times. If they stay as generators, the first scan on each wil
        # exhaust them, resulting in empty results for later scans (this was
        # was really hard to track down, since the scans are also
        # generators, so the order of access to an inventory is not immediately
        # obvious in the code).
        __pre_filter = ids_perfected_envoy_armor.union(
            {id_legendary_insight, id_gift_of_prowess,
             id_envoy_insignia}, ids_refined_envoy_armor)

        # If an item slot is empty, or the item is not interesting,
        # filter it out.
        def pre_filter(a, b=__pre_filter):
            return a is not None and a["id"] in b

        inv_bank = list(filter(pre_filter, bank))
        del bank  # We don't need these anymore, free them.

        inv_materials = list(filter(pre_filter, materials))
        del materials

        inv_shared = list(filter(pre_filter, shared))
        del shared

        # Bags have multiple inventories for each character, so:
        # Step 5: Discard the empty and uninteresting
        inv_bags = list(
            filter(
                pre_filter,
                # Step 4: Flatten!
                chain.from_iterable(
                    # Step 3: Flatten.
                    chain.from_iterable(
                        # Step 2: Get inventories from each existing bag
                        (
                            map(itemgetter("inventory"), filter(None, bags))
                            for bags in
                            # Step 1: Get all bags
                            map(itemgetter("bags"), characters))))))
        # Now we have a simple list of items in all bags on all characters.

        # Step 3: Discard empty and uninteresting
        equipped = list(
            filter(
                pre_filter,
                # Step 2: Flatten
                chain.from_iterable(
                    # Step 1: get all character equipment
                    map(itemgetter("equipment"), characters))))
        del characters

        # Like the bags, we now have a simple list of character gear

        # Filter out items that don't match the ones we want.
        # Step 1: Define a test function for filter(). The id is passed in with
        # an optional argument to avoid any potential issues with scope.
        def li_scan(a, b=id_legendary_insight):
            return a["id"] == b

        # Step 2: Filter out all items we don't care about
        # Step 3: Extract the `count` field.
        li_bank = map(itemgetter("count"), filter(li_scan, inv_bank))
        li_materials = map(itemgetter("count"), filter(li_scan, inv_materials))
        li_shared = map(itemgetter("count"), filter(li_scan, inv_shared))
        li_bags = map(itemgetter("count"), filter(li_scan, inv_bags))

        def prowess_scan(a, b=id_gift_of_prowess):
            return a["id"] == b

        prowess_bank = map(itemgetter("count"), filter(prowess_scan, inv_bank))
        prowess_shared = map(
            itemgetter("count"), filter(prowess_scan, inv_shared))
        prowess_bags = map(itemgetter("count"), filter(prowess_scan, inv_bags))

        def insignia_scan(a, b=id_envoy_insignia):
            return a["id"] == b

        insignia_bank = map(
            itemgetter("count"), filter(insignia_scan, inv_bank))
        insignia_shared = map(
            itemgetter("count"), filter(insignia_scan, inv_shared))
        insignia_bags = map(
            itemgetter("count"), filter(insignia_scan, inv_bags))

        # This one is slightly different: since we are matching against a set
        # of ids, we use `in` instead of a simple comparison.
        perfect_armor_scan = (
            lambda a, b=ids_perfected_envoy_armor: a["id"] in b)
        perfect_armor_bank = map(
            itemgetter("count"), filter(perfect_armor_scan, inv_bank))
        perfect_armor_shared = map(
            itemgetter("count"), filter(perfect_armor_scan, inv_shared))
        perfect_armor_bags = map(
            itemgetter("count"), filter(perfect_armor_scan, inv_bags))
        # immediately converting this to a list because we'll need the length
        # later and that would exhaust the generator, resulting in surprises if
        # it's used more later.
        perfect_armor_equipped = list(filter(perfect_armor_scan, equipped))

        # Repeat for Refined Armor
        def refined_armor_scan(a, b=ids_refined_envoy_armor):
            return a["id"] in b

        refined_armor_bank = map(
            itemgetter("count"), filter(refined_armor_scan, inv_bank))
        refined_armor_shared = map(
            itemgetter("count"), filter(refined_armor_scan, inv_shared))
        refined_armor_bags = map(
            itemgetter("count"), filter(refined_armor_scan, inv_bags))
        refined_armor_equipped = list(filter(refined_armor_scan, equipped))

        # Now that we have all the items we are interested in, it's time to
        # count them! Easy enough to just `sum` the `chain`.
        sum_li = sum(chain(li_bank, li_materials, li_bags, li_shared))
        sum_prowess = sum(chain(prowess_bank, prowess_shared, prowess_bags))
        sum_insignia = sum(
            chain(insignia_bank, insignia_shared, insignia_bags))
        # Armor is a little different. The ones in inventory have a count like
        # the other items, but the ones equipped don't, so we can just take the
        # length of the list there.
        sum_refined_armor = sum(
            chain(refined_armor_bank, refined_armor_shared,
                  refined_armor_bags)) + len(refined_armor_equipped)
        sum_perfect_armor = sum(
            chain(perfect_armor_bank, perfect_armor_shared,
                  perfect_armor_bags)) + len(perfect_armor_equipped)

        # LI is fine, but the others are composed of 25 or 50 LIs.
        li_prowess = sum_prowess * 25
        li_insignia = sum_insignia * 25
        # Refined Envoy Armor. First set is free!
        # But, keeping track of it is troublesome. What we do is add up to 6
        # perfected armor pieces to this (the ones that used the free set), but
        # not more (`min()`).
        # Then, subtract 6 for the free set. If one full set of perfected armor
        # has been crafted, then we have just the count of refined armor. This
        # is exactly what we want, because the free set is now being counted by
        # `li_perfect_armor`.
        li_refined_armor = max(
            min(sum_perfect_armor, 6) + sum_refined_armor - 6, 0) * 25
        # Perfected Envoy Armor. First set is half off!
        li_perfect_armor = min(sum_perfect_armor, 6) * 25 + max(
            sum_perfect_armor - 6, 0) * 50
        # Stagger the calculation for detail later.
        crafted_li = (
            li_prowess + li_insignia + li_perfect_armor + li_refined_armor)
        total_li = sum_li + crafted_li

        # Construct an embed object for better formatting of our data
        embed = discord.Embed()
        # Right up front, the information everyone wants:
        embed.title = "{0} Legendary Insights Earned".format(total_li)
        # Identify the user that asked
        embed.set_author(name=doc["account_name"], icon_url=user.avatar_url)
        # LI icon as thumbnail looks pretty cool.
        embed.set_thumbnail(url="https://render.guildwars2.com/file"
                            "/6D33B7387BAF2E2CC9B5D37D1D1B01246AB6FA22"
                            "/1302744.png")
        # Legendary color!
        embed.colour = 0x4C139D
        # Quick breakdown. No detail on WHERE all those LI are.
        # That's for $search
        embed.description = "{1} on hand, {2} used in crafting".format(
            total_li, sum_li, crafted_li)
        # Save space by skipping empty sections
        if sum_perfect_armor:
            embed.add_field(
                name="{0} Perfected Envoy Armor Pieces".format(
                    sum_perfect_armor),
                value="Representing {0} Legendary Insights".format(
                    li_perfect_armor),
                inline=False)
        if sum_refined_armor:
            embed.add_field(
                name="{0} Refined Envoy Armor Pieces".format(
                    sum_refined_armor),
                value="Representing {0} Legendary Insights".format(
                    li_refined_armor),
                inline=False)
        if sum_prowess:
            embed.add_field(
                name="{0} Gifts of Prowess".format(sum_prowess),
                value="Representing {0} Legendary Insights".format(li_prowess),
                inline=False)
        if sum_insignia:
            embed.add_field(
                name="{0} Envoy Insignia".format(sum_insignia),
                value="Representing {0} Legendary Insights".format(
                    li_insignia),
                inline=False)
        # Identify the bot
        embed.set_footer(
            text=self.bot.user.name, icon_url=self.bot.user.avatar_url)

        # Edit the embed into the initial message.
        await ctx.send(
            "{.mention}, here are your Legendary Insights".format(user),
            embed=embed)

    @commands.command()
    @commands.cooldown(1, 10, BucketType.user)
    async def bosses(self, ctx):
        """Shows your raid progression for the week

        Required permissions: progression
        """
        user = ctx.author
        scopes = ["progression"]
        endpoint = "account/raids"
        try:
            doc = await self.fetch_key(user, scopes)
            results = await self.call_api(endpoint, key=doc["key"])
        except APIError as e:
            return await self.error_handler(ctx, e)
        raids = await self.get_raids()
        embed = self.boss_embed(raids, results)
        embed.set_author(name=doc["account_name"], icon_url=user.avatar_url)
        try:
            await ctx.send(
                "{.mention}, here are your raid bosses:".format(user),
                embed=embed)
        except discord.Forbidden:
            await ctx.send("Need permission to embed links")

    @commands.command()
    @commands.cooldown(1, 5, BucketType.user)
    async def search(self, ctx, *, item):
        """Find items on your account

        Required permissions: inventories, characters
        """
        user = ctx.author
        scopes = ["inventories", "characters"]
        choice = await self.itemname_to_id(ctx, item, user)
        if not choice:
            ctx.command.reset_cooldown(ctx)
            return
        await ctx.trigger_typing()
        try:
            endpoints = [
                "account/bank", "account/inventory", "account/materials",
                "characters?page=0"
            ]
            results = await self.call_multiple(endpoints, user, scopes)
            storage_spaces = ("bank", "shared", "material storage")
            storage_spaces = OrderedDict(list(zip(storage_spaces, results)))
            characters = results[3]
        except APIError as e:
            return await self.error_handler(ctx, e)

        def check(item):
            return item is not None and item["id"] == choice["_id"]

        storage_counts = OrderedDict()
        for k, v in storage_spaces.items():
            count = 0
            for item in filter(check, v):
                count += item["count"]
            storage_counts[k] = count
        for character in characters:
            bags = [
                bag["inventory"] for bag in filter(None, character["bags"])
            ]
            bag_total = 0
            for bag in bags:
                bag_total += sum(
                    [item["count"] for item in filter(check, bag)])
            equipment = sum(
                [1 for piece in filter(check, character["equipment"])])
            count = bag_total + equipment
            storage_counts[character["name"]] = count
        seq = [k for k, v in storage_counts.items() if v]
        if not seq:
            return await ctx.send("Sorry, not found on your account. "
                                  "Make sure you've selected the "
                                  "correct item.")
        longest = len(max(seq, key=len))
        if longest < 8:
            longest = 8
        output = [
            "LOCATION{}COUNT".format(" " * (longest - 5)),
            "--------{}|-----".format("-" * (longest - 6))
        ]
        total = 0
        storage_counts = OrderedDict(
            sorted(storage_counts.items(), key=lambda kv: kv[1], reverse=True))
        for k, v in storage_counts.items():
            if v:
                total += v
                output.append("{} {} | {}".format(k.upper(), " " * (
                    longest - len(k)), v))
        output.append(
            "--------{}------".format("-" * (longest - len("location") + 2)))
        output.append("TOTAL:{}{}".format(" " * (longest - 2), total))
        await ctx.send("```ml\n" + "\n".join(output) + "```")

    @commands.command()
    @commands.cooldown(1, 10, BucketType.user)
    async def cats(self, ctx):
        """Displays the cats you haven't unlocked yet

        Required permissions: progression"""
        user = ctx.message.author
        endpoint = "account/home/cats"
        try:
            results = await self.call_api(endpoint, user, ["progression"])
        except APIError as e:
            return await self.error_handler(ctx, e)
        else:
            listofcats = []
            for cat in results:
                cat_id = cat["id"]
                try:
                    hint = cat["hint"]
                except:
                    thanks_anet = {
                        34: "holographic",
                        36: "bluecatmander",
                        37: "yellowcatmander"
                    }
                    hint = thanks_anet.get(cat_id)
                listofcats.append(hint)
            catslist = list(set(list(self.gamedata["cats"])) ^ set(listofcats))
            if not catslist:
                await ctx.send(
                    ":cat: Congratulations {0.mention}, "
                    "you've collected all the cats :cat:. Here's another: "
                    ":cat2:".format(user))
            else:
                formattedlist = []
                output = (":cat: {0.mention}, you haven't collected the "
                          "following cats yet: :cat:\n```")
                catslist.sort(
                    key=lambda val: self.gamedata["cats"][val]["order"])
                for cat in catslist:
                    formattedlist.append(self.gamedata["cats"][cat]["name"])
                for x in formattedlist:
                    output += "\n" + x
                output += "```"
                await ctx.send(output.format(user))

    def boss_embed(self, raids, results):
        def is_killed(boss):
            return "+" if boss["id"] in results else "-"

        def readable_id(_id):
            _id = _id.split("_")
            dont_capitalize = ("of", "the")
            return " ".join([
                x.capitalize() if x not in dont_capitalize else x for x in _id
            ])

        not_completed = []
        embed = discord.Embed(title="Bosses", color=self.embed_color)
        for raid in raids:
            for wing in raid["wings"]:
                wing_done = True
                value = ["```diff"]
                for boss in wing["events"]:
                    if boss["id"] not in results:
                        wing_done = False
                        not_completed.append(boss)
                    value.append(is_killed(boss) + readable_id(boss["id"]))
                value.append("```")
                name = readable_id(wing["id"])
                if wing_done:
                    name += " :white_check_mark:"
                else:
                    name += " :x:"
                embed.add_field(name=name, value="\n".join(value))
        if len(not_completed) == 0:
            description = "Everything completed this week :star:"
        else:
            bosses = list(filter(lambda b: b["type"] == "Boss", not_completed))
            events = list(
                filter(lambda b: b["type"] == "Checkpoint", not_completed))
            if bosses:
                suffix = ""
                if len(bosses) > 1:
                    suffix = "es"
                bosses = "{} boss{}".format(len(bosses), suffix)
            if events:
                suffix = ""
                if len(events) > 1:
                    suffix = "s"
                events = "{} event{}".format(len(events), suffix)
            description = (", ".join(filter(None, [bosses, events])) +
                           " not completed this week")
        embed.description = description
        embed.set_footer(text="Green (+) means completed this week. Red (-) "
                         "means not")
        return embed
