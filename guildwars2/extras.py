import discord
from discord.ext import commands

import json
import asyncio
import random
import time
import urllib
import ssl
from urllib.request import urlopen
from bs4 import BeautifulSoup #not used atm but should probably rewrite the arcdps check to use this to be consistent (wiki command uses bs4)
from .exceptions import (APIBadRequest, APIConnectionError, APIError,
                         APIForbidden, APIInvalidKey, APINotFound)


class ExtrasMixin:
    @commands.command()
    async def sab(self, ctx, *, charactername : str):
        """Displays unlocked SAB items for the character specified

        Required permissions: characters, progression"""
        user = ctx.author
        scopes = ["characters", "progression"]
        charactername = charactername.replace(" ", "%20")
        endpoint = "characters/" + charactername + "/sab"
        try:
            results = await self.call_api(endpoint, user, scopes)
        except APIKeyError as e:
            await ctx.send(e)
            return
        except APIError as e:
            await self.error_handler(ctx, e)
            return
        data = discord.Embed(title='SAB Character Info')
        for elem in results["unlocks"]:
            data.add_field(name=elem["name"].replace('_', ' ').title(), value="Unlocked")
        for elem in results["songs"]:
            data.add_field(name=elem["name"].replace('_', ' ').title(), value="Unlocked")
        try:
            await ctx.send(embed=data)
        except discord.HTTPException:
            await ctx.send("Need permission to embed links")


    @commands.group()
    async def container(self, ctx):
        """Command used to find out what's the most expensive item inside a container"""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)
            return
    
    @container.command(hidden=True, name="add")
    @commands.has_any_role('Bot Dev', 'Server Admin')
    async def containeradd(self, ctx, *, input_data: str):
        """Add a container data. Format is !container add name;data (data in JSON format)"""
        try:
            name, data = input_data.split(';',1)
        except IndexError:
            await ctx.send("Plz format as !container add name;data (data in JSON format)")
            return
        try:
            self.containers[name] = json.loads(data)
        except ValueError:
            await ctx.send("Error in reading the JSON format")
            return
        self.save_containers()
        await ctx.send("Data added")
    
    @container.command(hidden=True, name="del")
    @commands.has_any_role('Bot Dev', 'Server Admin')
    async def containerdelete(self, ctx, *, input_data: str):
        """Remove a container data. Format is !container del name"""
        try:
            del self.containers[input_data]
        except KeyError:
            await ctx.send("Couldn't find the required container")
            return
        self.save_containers()
        await ctx.send("Data removed")
    
    @container.command(hidden=True, name="list")
    @commands.has_any_role('Bot Dev', 'Server Admin')
    async def containerlist(self, ctx, *, input_data: str=""):
        """List container data.
        List either all container names (without argument) or a specific container (with the name as argument)"""
        if input_data == "":
            await ctx.send(', '.join(self.containers.keys()))
            return
        else:
            try:
                await ctx.send(json.dumps(self.containers[input_data]))
            except KeyError:
                await ctx.send("Couldn't find the required container")
                return

    def save_containers():
        with open(
                "cogs/CogManager/cogs/guildwars2/containers.json", encoding="utf-8", mode="w") as f:
            json.dump(self.containers, f, indent=4,sort_keys=True,
                separators=(',',' :'))
    
    @container.command(name="check")
    async def containercheck(self, ctx, *, input_name: str):
        """Gets the prices of a container's contents and give the most expensive ones.
        container check [Container name] (copy-paste from in-game chat), also works without []"""
        user = ctx.author
        # Remove the [] around the copied name
        clean_name = input_name.strip('[]')
        # Make sure it's a single item 
        if clean_name[0] in [str(i) for i in range(10)]:
            await ctx.send("Please copy the name of a single box. You don't want me to handle plurals, do you?")
            return
        try:
            # Hope the container is in the database
            l_contents = self.containers[clean_name]
        except KeyError:
            # Report and ban
            await ctx.send("Couldn't find said item in the container database.")
            return 
        # Add prices to l_contents, result is l_tot
        # The items will look like {'sell_price': -, 'buy_price': -, u'name': -, u'id': -}
        base_URL = "commerce/prices?ids="
        comma_IDs = ','.join([elem["id"] for elem in l_contents])
        endpoint = base_URL + comma_IDs
        try:
            data_prices = await self.call_api(endpoint)
        except APINotFound as e:
            await ctx.send("API may be down, the following error was returned {0}".format(e))
            return
        l_prices = {str(elem["id"]): elem for elem in data_prices}
        l_tot = []
        for elem in l_contents:
            try:
                p = l_prices[elem["id"]]
                d = dict.copy(elem)
                d["sell_price"] = p["sells"]["unit_price"]
                d["buy_price"] = p["buys"]["unit_price"]
                l_tot.append(d)
            except KeyError:
                # Happens if the content is account bound
                pass
        # Sort l_tot in various ways to get best items 
        data = discord.Embed(title='Most expensive items')
        best_item = sorted(l_tot, key=lambda elem:elem["sell_price"])[-1]
        data.add_field(name="Best sell price", 
                value="{0} at {1}".format(best_item["name"], self.gold_to_coins(best_item["sell_price"])),
                  inline=False)
        best_item =  sorted(l_tot, key=lambda elem:elem["buy_price"])[-1]
        data.add_field(name="Best buy price", 
                value="{0} at {1}".format(best_item["name"], self.gold_to_coins(best_item["buy_price"])),
                  inline=False)
        try:
            await ctx.send(embed=data)
        except discord.HTTPException:
            await ctx.send("Need permission to embed links")    

    @commands.command()
    async def playlist(self, ctx):
        await ctx.send("{0.mention}, Sorry, I can't play audio currently, for the time being you'll need to use the other bot via +play.".format(ctx.author))

    @commands.command()
    async def quaggan(self, ctx, *, quaggan_name : str = 'random'):
        """This displays a quaggan"""
        user = ctx.author
        endpoint = 'quaggans'
        base_quaggan = 'https://static.staticwars.com/quaggans/'
        try:
            l_quaggans = await self.call_api(endpoint)
            if quaggan_name == 'random':
                quaggan_name = random.choice(l_quaggans)
                URL_quaggan = base_quaggan + quaggan_name + '.jpg'
                await ctx.send(URL_quaggan)
            elif quaggan_name == 'list':
                data = discord.Embed(title='Available quaggans')
                data.add_field(name="List of quaggans", value=', '.join(l_quaggans))
                try:
                    await ctx.send(embed=data)
                except discord.HTTPException:
                    await ctx.send("Need permission to embed links")    
            elif quaggan_name in l_quaggans:
                URL_quaggan = base_quaggan + quaggan_name + '.jpg'
                await ctx.send(URL_quaggan)
            else:
                await ctx.send("I couldn't find the requested quaggan. List of all available quaggans:")
                data = discord.Embed(title='Available quaggans')
                data.add_field(name="List of quaggans", value=', '.join(l_quaggans))
                try:
                    await ctx.send(embed=data)
                except discord.HTTPException:
                    await ctx.send("Need permission to embed links")                
        except APIError as e:
            await ctx.send("{0.mention}, API returned the following error:  "
                            "`{1}`".format(user, e))
            return
    
    @commands.command()
    async def ubm(self, ctx, MC_price_str : str = "0"):
        """This displays which way of converting unbound magic to gold is the most profitable.
        It takes as an optional argument the value the user gives to mystic clovers (in copper), defaults to 0"""
        user = ctx.author
        # The result will be the coin return per that amount of UBM
        UBM_UNIT = 1000
        # Mystic clover data. Required because they're not sellable on TP
        MC_ID = "19675"
        MC_price = self.coins_to_gold(MC_price_str)
        # Container prices
        packet_price_coin = 5000
        packet_price_magic = 250
        bundle_price_coin_1 = 10000
        bundle_price_magic_1 = 500
        bundle_price_coin_2 = 4000
        bundle_price_magic_2 = 1250
        # Data agglomerated from various sources. "Item_ID": "number of such items obtained" 
        # in ["samples"]["container"] tries
        d_data = {
            "bundle": {
                "70957": 33, "72315": 28, "24330": 88, "24277": 700,
                "24335": 126, "75654": 16, "24315": 96, "24310": 96,
                "24358": 810, "24351": 490, "24357": 780, "24370": 24,
                "76491": 31, "37897": 810, "68942": 102, "19721": 310,
                "24320": 204, "70842": 84, "24325": 110, "24300": 630,
                "74988": 16, "24305": 106, "72504": 23, "68063": 64,
                "19675": 58, "24289": 760, "76179": 19, "24283": 730,
                "24295": 780, "48884": 950},
            "packet": {
                "19719": 330, "19718": 260, "19739": 590, "19731": 620,
                "19730": 1010, "19732": 465, "19697": 290, "19698": 250,
                "19699": 1300, "19748": 240, "19700": 670, "19701": 155,
                "19702": 670, "19703": 250, "19741": 1090, "19743": 870,
                "19745": 95, "46736": 43, "46739": 47, "46738": 42,
                "19728": 810, "19729": 580, "19726": 860, "19727": 920,
                "19724": 890, "19725": 285, "19722": 640, "19723": 300,
                "46741": 44},
            "samples": {"packet": 1720, "bundle": 1595}}
        # Build the price list
        URL = "commerce/prices?ids="
        l_IDs = list(d_data["packet"].keys()) + list(d_data["bundle"].keys())
        # For now, the API doesn't take non-sellable IDs into account when using ?ids=
        # It's still safer to explicitely remove that ID
        l_IDs.remove("19675")
        endpoint = URL + ','.join(l_IDs)
        try:
            prices_data = await self.call_api(endpoint)
        except APINotFound as e:
            await ctx.send("API may be down, the following error was returned {0}".format(e))
            return
        d_prices = {str(elem["id"]): int(0.85 * elem["sells"]["unit_price"])
                    for elem in prices_data}
        d_prices[MC_ID] = MC_price
        # Get raw content of containers
        numerator = sum([d_prices[elem] * d_data["packet"][elem]
                         for elem in  d_data["packet"].keys()])
        packet_content = int(numerator/float(d_data["samples"]["packet"]))

        numerator = sum([d_prices[elem] * d_data["bundle"][elem]
                         for elem in  d_data["bundle"].keys()])
        bundle_content = int(numerator/float(d_data["samples"]["bundle"]))
        # Compute net returns
        return_per_packet = (packet_content - packet_price_coin)
        return_per_bunch_p = int(return_per_packet * float(UBM_UNIT) / packet_price_magic)
        return_per_bundle_1 = (bundle_content - bundle_price_coin_1)
        return_per_bunch_b_1 = int(return_per_bundle_1 * float(UBM_UNIT) / bundle_price_magic_1)
        return_per_bundle_2 = (bundle_content - bundle_price_coin_2)
        return_per_bunch_b_2 = int(return_per_bundle_2 * float(UBM_UNIT) / bundle_price_magic_2)
        # Display said returns
        r1 = "{1} per {0} unbound magic".format(UBM_UNIT, self.gold_to_coins(return_per_bunch_p))
        r2 = "{1} per {0} unbound magic".format(UBM_UNIT, self.gold_to_coins(return_per_bunch_b_1))
        r3 = "{1} per {0} unbound magic".format(UBM_UNIT, self.gold_to_coins(return_per_bunch_b_2))
        data = discord.Embed(title="Unbound magic conversion returns using Magic-Warped...")
        data.add_field(name="Packets", value=r1, inline=False)
        data.add_field(name="Bundles", value=r2, inline=False)
        data.add_field(name="Bundles (Ember Bay)", value=r3, inline=False)
        try:
            await ctx.send(embed=data)
        except discord.HTTPException:
            await ctx.send("Need permission to embed links")        

            
    @commands.command()
    async def tptrend(self, ctx, *, item: str):
        """Returns price trends for a specified tradeable item"""
        user = ctx.author
        choice = await self.itemname_to_id(ctx, item, user)
        try:
            commerce = 'commerce/prices/'
            choiceid = str(choice["_id"])
            shinies_endpoint = 'history/' + choiceid
            history = await self.call_shiniesapi(shinies_endpoint)
        except APIError as e:
            await self.error_handler(ctx, e)
            return
        
        time_now = int(time.time())
        
        # Select 96 entries, each (usually) spaced 15 minutes apart.
        last_week = history[:96]
        
        # No data returned?
        if not last_week:
            await ctx.send("{0.mention}, there was no historical data found.".format(user))
            return
        
        buy_avg = 0
        sell_avg = 0
        buy_min = float("inf")
        sell_min = float("inf")
        buy_max = 0
        sell_max = 0
        
        # Get average from 96 most recent entries
        for record in last_week:
            buy = int(record["buy"])
            sell = int(record["sell"])
            buy_avg += buy
            sell_avg += sell
            buy_min = min(buy_min, buy)
            sell_min = min(sell_min, sell)
            buy_max = max(buy_max, buy)
            sell_max = max(sell_max, sell)
        
        buy_avg /= len(last_week)
        sell_avg /= len(last_week)
        
        # Display data
        data = discord.Embed(title="Daily average of id " + choiceid)
        data.add_field(name="Average Buy",value=self.gold_to_coins(buy_avg))
        data.add_field(name="Minimum Buy",value=self.gold_to_coins(buy_min))
        data.add_field(name="Maximum Buy",value=self.gold_to_coins(buy_max))
        data.add_field(name="Average Sell",value=self.gold_to_coins(sell_avg))
        data.add_field(name="Minimum Sell",value=self.gold_to_coins(sell_min))
        data.add_field(name="Maximum Sell",value=self.gold_to_coins(sell_max))
        
        try:
            await ctx.send(embed=data)
        except discord.HTTPException:
            await ctx.send("Need permission to embed links")
    
    @commands.command()
    async def baglevel(self, ctx):
        """This computes the best level for opening champion bags"""
        user = ctx.author
        
        d_gains = {}
        global_coefs = {"wood": 19*0.949/37,
                "metal": (6*1.53 + 19*0.578)/37,
                "leather": 6*2.26/37,
                "cloth": 6*2.26/37}
        d_IDs = {"wood": [19723, 19726, 19727, 19724, 19722, 19725],
            "metal": [19697, 19699, 19702, 19700, 19701],
            "leather": [19719, 19728, 19730, 19731, 19729, 19732],
            "cloth": [19718, 19739, 19741, 19743, 19748, 19745]}
        l_IDs =  [str(item) for sublist in d_IDs.values() for item in sublist]
        max_tier = {"wood": 6, "metal": 5, "leather": 6, "cloth": 6}
        d_bounds = {"wood":{1: {"min":1, "max":20},
                2: {"min":16, "max":33},
                3: {"min":31, "max":48},
                4: {"min":46, "max":63},
                5: {"min":59, "max":80},},
            "metal": {1: {"min": 1, "max": 23},
                2: {"min": 19, "max": 53},
                3: {"min": 49, "max": 62},
                4: {"min": 63, "max": 80},},
            "leather": {1: {"min": 1, "max": 18},
                2: {"min": 16, "max": 33},
                3: {"min": 31, "max": 48},
                4: {"min": 46, "max": 63},
                5: {"min": 61, "max": 80},},
            "cloth": {1: {"min": 1, "max": 20},
                2: {"min": 16, "max": 33},
                3: {"min": 31, "max": 48},
                4: {"min": 44, "max": 63},
                5: {"min": 58, "max": 80},},}
        l_mats = ["wood", "metal", "leather", "cloth"]
        TP_prices = {mat:{} for mat in l_mats}
        try:
            endpoint = "commerce/prices?ids=" + ','.join(l_IDs)
            l_prices = await self.call_api(endpoint)
        except APIKeyError as e:
            await ctx.send(e)
            return
        except APIError as e:
            await self.error_handler(ctx, e)
            return
        d_prices = {elem["id"]: elem for elem in l_prices}
        for mat in l_mats:
            for i, ID in enumerate(d_IDs[mat]):
                mat_price = d_prices[ID]["sells"]["unit_price"]/float(100)
                TP_prices[mat][i+1] = mat_price
        for lvl in range(1, 81):
            gain = 0
            for mat in l_mats:
                r_tier = range(1, max_tier[mat] + 1)
                nb = 0
                coef = {elem: 0 for elem in r_tier}
                for tier in r_tier[:-1]:
                    try:
                        lb = d_bounds[mat][tier]
                        if lb["min"] <= lvl <= lb["max"]:
                            nb += 1
                            coef[tier] += 0.9
                            coef[tier + 1] += 0.1
                    except KeyError:
                        pass
                for tier in r_tier:
                    mat_price = float(TP_prices[mat][tier])
                    temp = coef[tier] * mat_price / nb
                    gain += global_coefs[mat] * temp
            d_gains[lvl] = gain
        max_profit = max(d_gains.values())
        profit_levels = [lv for lv in range(1, 81) if d_gains[lv] == max_profit]


        # Display data
        data = discord.Embed(title="Best character levels to open champion bags")
        data.add_field(name="Best levels",value=', '.join([str(elem) for elem in profit_levels]))
        data.add_field(name="Estimated profit",value=self.gold_to_coins(int(100*max_profit)))

        try:
            await ctx.send(embed=data)
        except discord.HTTPException:
            await ctx.send("Need permission to embed links")

    @commands.command()
    async def craft(self, ctx, *, input_data: str):
        """Experimental command, currently gets the crafting price if you bought subcomponents at buyprice.
        Limitations: Only goes up to 2 tiers of subcomponents currently.
        You can specify a quantity by specifying a quantity after the item name, seperated by ;
        Example: Fried Oysters;10"""
        overallquantity = 1
        if ';' in input_data:
            try:
                item, overallquantity = input_data.split(';',1)
            except IndexError:
                await ctx.send("Wrong formatting.")
                return
            try:
                overallquantity = int(overallquantity)
            except ValueError:
                await ctx.send("That's an invalid quantity.")
        else:
            item = input_data
        def is_number(n):
            try:
                float(n)
                return True
            except ValueError:
                return False
        user = ctx.author
        choice = await self.itemname_to_id(ctx, item, user)
        if not choice:
            return
        ingredients = await self.findingredients(choice["_id"])
        if not ingredients:
            await ctx.send("That's not something that can be crafted by a crafting discipline.")
            return
        cursor = await self.db.recipes.find_one({"output_item_id": choice["_id"]})
        output = "```"
        if cursor["output_item_count"] * overallquantity > 1:
            output += "\nProduces: " + str(cursor["output_item_count"] * overallquantity)
        recipes = {}
        totalcost = 0
        multilayer = False
        for item in ingredients:
            name = await self.getitemname(item["item_id"])
            recipes[item["item_id"]] = {}
            recipes[item["item_id"]]['name'] = name
            results = await self.getrecipeprice(item["item_id"])
            if results:
                price = results["buys"]["unit_price"]
                cost = item["count"] * price
            else:
                cost = 'Not available on TP'
            recipes[item["item_id"]]['cost'] = cost
            recipes[item["item_id"]]['count'] = item["count"]   
            if await self.subcomponentcheck(item["item_id"]) != None:
                subingredients = await self.findingredients(item["item_id"])
                subtotal = 0
                recipes[item["item_id"]]['sub1id'] = []
                for subitem in subingredients:
                    subname = await self.getitemname(subitem["item_id"])
                    recipes[item["item_id"]][subitem["item_id"]] = {}
                    recipes[item["item_id"]][subitem["item_id"]]['name'] = subname
                    subresults = await self.getrecipeprice(subitem["item_id"])
                    if subresults:
                        subprice = subresults["buys"]["unit_price"]
                        subcost = subitem["count"] * item["count"] * subprice
                        subtotal += subcost
                    else:
                        subcost = 'Not available on TP'
                    recipes[item["item_id"]][subitem["item_id"]]['cost'] = subcost
                    recipes[item["item_id"]][subitem["item_id"]]['count'] = subitem["count"] * item["count"]
                    recipes[item["item_id"]]['sub1id'].append(subitem["item_id"])
                    if await self.subcomponentcheck(subitem["item_id"]) != None:
                        if multilayer == False:
                            await ctx.send("This item has more than two levels of subcomponents which isn't currently supported, values provided below will limit subcomponents to the maximum of two tiers - so it may be cheaper than listed if you craft more subcomponents!")
                recipes[item["item_id"]]['sub1cost'] = subtotal
        #with open('data.json', 'w') as fp:
        #   json.dump(recipes, fp)
        for item in recipes:
            if is_number(recipes[item]['cost']):
                if 'sub1cost' in recipes[item]:
                    if is_number(recipes[item]['sub1cost']):
                        if recipes[item]['cost'] < recipes[item]['sub1cost']:
                            price = recipes[item]['cost'] * overallquantity
                            count = recipes[item]['count'] * overallquantity
                            name = recipes[item]['name']
                            totalcost += price
                            output += '\n' + str(count) + ' ' + name + ' ' + self.gold_to_coins(price)
                        else:
                            for subid in recipes[item]['sub1id']:
                                price = recipes[item][subid]['cost']
                                count = recipes[item][subid]['count']  * overallquantity
                                name = recipes[item][subid]['name']
                                try:
                                    int(price)
                                    price = price * overallquantity
                                    totalcost += price
                                    price = self.gold_to_coins(price)
                                except:
                                    pass
                                output += '\n' + str(count) + ' ' + name + ' ' + price
                else:
                    try:
                        int(recipes[item]['cost'])
                        price = recipes[item]['cost'] * overallquantity
                    except ValueError:
                        price = recipes[item]['cost']
                    count = recipes[item]['count']  * overallquantity
                    name = recipes[item]['name']
                    totalcost += price
                    output += '\n' + str(count) + ' ' + name + ' ' + self.gold_to_coins(price)
            else:
                if 'sub1cost' in recipes[item]:
                    if is_number(recipes[item]['sub1cost']):
                        for subid in recipes[item]['sub1id']:
                            price = recipes[item][subid]['cost'] * overallquantity
                            count = recipes[item][subid]['count']  * overallquantity
                            name = recipes[item][subid]['name']
                            totalcost += price
                            output += '\n' + str(count) + ' ' + name + ' ' + self.gold_to_coins(price)
                    else:
                        price = 'Not bought from TP'
                        count = recipes[item]['count']  * overallquantity
                        name = recipes[item]['name']
                        output += '\n' + str(count) + ' ' + name + ' ' + price
        output += '\nTotal Cost: ' + self.gold_to_coins(totalcost) 
        output += '```'
        await ctx.send(output)

    async def getitemname(self, item):
        cursor = await self.db.items.find_one({"_id": item})
        name = cursor["name"]
        return name

    async def getrecipeprice(self, item):
        try:
            commerce = 'commerce/prices/'
            endpoint = commerce + str(item)
            results = await self.call_api(endpoint)
        except APIError as e:
            return None
        return results

    async def subcomponentcheck(self, item):
        cursor = await self.db.recipes.find_one({"output_item_id": item})
        return cursor

    async def findingredients(self, item):
        cursor = await self.db.recipes.find_one({"output_item_id": item})
        try:
            ingredients = cursor["ingredients"]
        except:
            ingredients = None
        return ingredients


    async def call_shiniesapi(self, shiniesendpoint):
        shinyapiserv = 'https://www.gw2shinies.com/api/json/'
        url = shinyapiserv + shiniesendpoint
        async with self.session.get(url) as r:
            shiniesresults = await r.json()
        if shiniesresults is None:
            raise APIError("Could not find an item by that name")
        if "error" in shiniesresults:
            raise APIError("The API is dead!")
        if "text" in shiniesresults:
            raise APIError(shiniesresults["text"])
        return shiniesresults

    def coins_to_gold(self, input_string):
        # Convert a gold string into a gold int
        # You can use , or spaces as million/thousand/unit separators and g, s and c (lower-case)
        # "1,234g 56s 78c" -> 12345678
        # "1g 3c" -> 10003
        # "1 234 567" -> 1234567
        current_string = input_string.replace(",", "").replace(" ", "")
        l_separators = [
            {"symbol": "g", "value": 100**2},
            {"symbol": "s", "value": 100**1},
            {"symbol": "c", "value": 100**0}]
        total = 0
        for elem in l_separators:
            if elem["symbol"] in current_string:
                amount, current_string = current_string.split(elem["symbol"])
                total += int(amount) * elem["value"]
        if current_string != "":
            total += int(current_string)
        return total

    @commands.group()
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def arcdps(self, ctx):
        """Commands for setting up arcdps update feed"""
        if ctx.invoked_subcommand is None:
            return await self.bot.send_cmd_help(ctx)

    @arcdps.command(name="check")
    async def arc_check(self, ctx):
        """Checks and returns current arcdps version"""
        context = ssl._create_unverified_context()
        URL = "https://www.deltaconnected.com/arcdps/"
        page = urlopen(URL, context=context).read().decode('utf8')
        i = page.find("x64: current</a>")
        await ctx.send(page[i+17:i+30])

    @arcdps.command(name="channel")
    async def arcdps_channel(self, ctx, channel: discord.TextChannel):
        """Sets the channel to send ArcDPS update notifications to"""
        guild = ctx.guild
        if not guild.me.permissions_in(channel).send_messages:
            return await ctx.send("I do not have permissions to send "
                                  "messages to {.mention}".format(channel))
        await self.bot.database.set_guild(guild, {"arcdps.channel": channel.id},
                                          self)
        doc = await self.bot.database.get_guild(guild, self)
        enabled = doc["arcdps"].get("on", False)
        if enabled:
            await channel.send("Channel set to {.mention}.".format(channel))
        else:
            await channel.send("Channel set to {.mention}. In order to receive updates, you still need to enable it using "
                            "`arcdps toggle on`.".format(channel))


    @arcdps.command(name="toggle")
    async def arcdps_toggle(self, ctx, on_off: bool):
        """Toggles posting arcdps updates"""
        guild = ctx.guild
        await self.bot.database.set_guild(guild, {"arcdps.on": on_off}, self)
        if on_off:
            doc = await self.bot.database.get_guild(guild, self)
            channel = doc["arcdps"].get("channel")
            if channel:
                channel = guild.get_channel(channel)
                if channel:
                    msg = ("I will now send ArcDPS updates to {.mention}.".format(channel))
            else:
                msg = ("ArcDPS updates toggled on. In order to receive "
                       "updates, you still need to set a channel using "
                       "`arcdps channel <channel>`.".format(channel))
        else:
            msg = ("ArcDPS updates disabled")
        await ctx.send(msg)


    async def check_arc(self):
        doc = await self.bot.database.get_cog_config(self)
        if not doc:
            return False
        try:
            context = ssl._create_unverified_context()
            URL = "https://www.deltaconnected.com/arcdps/"
            page = urlopen(URL, context=context).read().decode('utf8')
            i = page.find("x64: current</a>")
            current = page[i+17:i+30]
        except:
            print("Arcdps check has encountered an exception: {0}".format(e))
            return False
        try:
            current_arc = doc["cache"]["arcdps"]
        except KeyError:
            current_arc = current
        if current != current_arc:
            await self.bot.database.set_cog_config(self,
                                                   {"cache.arcdps": current})
            return True
        else:
            return False

    async def arcdps_checker(self):
        while self is self.bot.get_cog("GuildWars2"):
            try:
                if await self.check_arc():
                    await self.arcdps_send()
                await asyncio.sleep(300)
            except Exception as e:
                self.log.exception(e)
                await asyncio.sleep(60)
                continue
            except asyncio.CancelledError:
                self.log.info("ARC Check terminated")

    async def arcdps_send(self):
        try:
            channels = []
            name = self.__class__.__name__
            cursor = self.bot.database.get_guilds_cursor({
                "arcdps.on": True,
                "arcdps.channel": {
                    "$ne": None
                }
            }, self)
            async for doc in cursor:
                try:
                    guild = doc["cogs"][name]["arcdps"]
                    channels.append(guild["channel"])
                except:
                    pass
            try:
                context = ssl._create_unverified_context()
                URL = "https://www.deltaconnected.com/arcdps/"
                page = urlopen(URL, context=context).read().decode('utf8')
                i = page.find("x64: current</a>")
                current = page[i+17:i+30]
            except:
                current = "An ArcDPS update was released but I wasn't able to find the version"
            message = ("ArcDPS has been updated. {0} Link: https://www.deltaconnected.com/arcdps/x64/".format(current))
            for chanid in channels:
                try:
                    await self.bot.get_channel(chanid).send(message)
                except:
                    pass
        except Exception as e:
            self.log.exception(e)
