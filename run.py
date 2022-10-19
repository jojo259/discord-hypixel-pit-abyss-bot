print("init")

import discord
from discord.ext import tasks
import requests
from dateutil import parser
import math
import time
import os
import random

from dotenv import load_dotenv
load_dotenv()

debugMode = False
if 'debugmode' in os.environ:
	debugMode = True

alertStr = "PRODUCTION MODE"
if debugMode:
	alertStr = "DEBUG MODE"
for i in range(8):
	print(alertStr)

print('connecting')
import pymongo
mongoConnectString = os.environ['mongoconnectstring']
dbClient = pymongo.MongoClient(mongoConnectString)
curDb = dbClient['hypixel']
discordsCol = curDb['pitdiscords']
print('connected')

botToken = os.environ['bottoken']
pitPandaApiKey = os.environ['pitpandaapikey']
webHookUrl = os.environ['webhookurl']
hypixelApiKey = os.environ['hypixelapikey']

print('getting ench names')

enchNames = {}
with open("enchnames.txt") as enchNamesFile:
	enchNamesFile = enchNamesFile.read()
	for curLine in enchNamesFile.split("\n"):
		curLineSplit = curLine.split(" ")
		enchNames[curLineSplit[0]] = curLineSplit[1]

playerData = {}

leaderboardTypes = {}
leaderboardTypes['gold'] = ['currentGold']
leaderboardTypes['playtime'] = ['playtime']
leaderboardTypes['renown'] = ['doc', 'renown']
leaderboardTypes['pitpandaclout'] = ['doc', 'searches']
leaderboardTypes['sewertreasures'] = ['doc', 'sewerTreasures']
leaderboardTypes['nightquests'] = ['doc', 'nightQuests']
leaderboardTypes['kingsquests'] = ['doc', 'kingsQuests']
leaderboardTypes['xp'] = ['doc', 'xp']
leaderboardTypes['contracts'] = ['doc', 'contracts']
leaderboardTypes['deaths'] = ['doc', 'deaths']

# util

def prettyRound(curNum):
	return round(curNum * 100) / 100

def prettyNumber(curNum):

	if curNum > 1_000_000_000_000:
		return str(prettyRound(curNum / 1_000_000_000_000)) + 't'

	if curNum > 1_000_000_000:
		return str(prettyRound(curNum / 1_000_000_000)) + 'b'

	if curNum > 1_000_000:
		return str(prettyRound(curNum / 1_000_000)) + 'm'

	if curNum > 1_000:
		return str(prettyRound(curNum / 1_000)) + 'k'

	return curNum

guildNamesCache = {}
async def getGuildName(guildId):

	if guildId not in guildNamesCache:

		gotGuild = await botClass.fetch_guild(guildId)

		guildNamesCache[guildId] = str(gotGuild.name)

	return guildNamesCache[guildId]

cachedRequests = {}
def requestsGet(apiUrl, timeout = 30, cacheMinutes = 0):
	curTime = time.time()

	print(f"	getting {apiUrl}")

	if apiUrl in cachedRequests:
		if cachedRequests[apiUrl]["time"] > curTime - cacheMinutes * 60:
			print("	returning cached request")
			return cachedRequests[apiUrl]["data"]
		else:
			print("	deleting cached request")
			cachedRequests.pop(apiUrl)

	try:
		apiGot = requests.get(apiUrl, timeout = timeout).json()
	except:
		print('probably timed out')
		return {'success': False, 'message': 'probably timed out'}

	apiSuccess = True
	if 'success' in apiGot:
		if not apiGot['success']:
			apiSuccess = False
	if apiSuccess:
		cachedRequests[apiUrl] = {"time": curTime, "data": apiGot}

	return apiGot

def getVal(theDict, thePath):
	try:
		for i in range(len(thePath)):
			theDict = theDict[thePath[0]]
			thePath.pop(0)
		return theDict
	except:
		return None

def sendDiscord(toSend):
	def sendDiscordPart(partToSend):
		url = webHookUrl
		data = {}
		data["username"] = "abyss bot"
		data["content"] = partToSend
		requests.post(url, json = data, headers = {"Content-Type": "application/json"}, timeout = 10)
	
	for i in range(int(len(toSend) / 2000) + 1):
		sendDiscordPart(toSend[i * 2000:i* 2000 + 2000])

def stripColorCodes(curStr):
	newStr = ""
	lastBad = False
	for curChar in curStr:
		if curChar == '§':
			lastBad = True
			continue

		if not lastBad:
			newStr += curChar

		lastBad = False

	return newStr

def itemStr(curItem):
	strSpacing = ' ' * 8

	returnStr = ''

	curItemName = "item"
	curItemLore = None
	curItemLastSeen = None

	if 'name' in curItem:
		curItemName = curItem['name']

	if 'lore' in curItem:
		curItemLore = curItem['lore']

	if 'item' in curItem:
		if 'name' in curItem['item']:
			curItemName = curItem['item']['name']

		if 'desc' in curItem['item']:
			curItemLore = curItem['item']['desc']

	if 'lastseen' in curItem:
		curItemLastSeen = curItem['lastseen']

	if 'lastsave' in curItem:
		curItemLastSeen = curItem['lastsave']

	returnStr += f"**{stripColorCodes(curItemName)}**"

	if curItemLore != None:
		livesStr = None
		for curLine in curItemLore:

			if curLine.startswith('§7Lives:'):
				livesStr = f"{strSpacing}Lives: `{stripColorCodes(curLine).split()[1]}`"

			if curLine.startswith('§9') and "As strong as iron" not in curLine and "Attack Damage" not in curLine:
				returnStr += f"{strSpacing}`{curLine[2:].strip()}`"

			if curLine.startswith('§dRARE!'):
				returnStr += f"{strSpacing}`{curLine[10:].strip()}`"

		if livesStr != None:
			returnStr += livesStr
	else:
		if 'enchants' in curItem:
			for curEnch in curItem['enchants']:
				curEnchKey = curEnch['key']
				curEnchLevel = curEnch['level']
				returnStr += f'{strSpacing}`{curEnchKey} {curEnchLevel}`'

	if 'lives' in curItem and 'maxLives' in curItem:
		returnStr += f"""{strSpacing}Lives: {curItem["lives"]}/{curItem["maxLives"]}"""

	if 'owner' in curItem:
		returnStr += f"""{strSpacing}Owner: `{getUsernameFromUuid(curItem["owner"])}`"""

	if curItemLastSeen != None:
		lastSeenStr = curItemLastSeen
		if len(str(lastSeenStr)) > 16:
			lastSeenStr = parseTimestamp(lastSeenStr)

		returnStr += f"""{strSpacing}Last seen: <t:{lastSeenStr}:R>"""

	return returnStr

def getUsernameFromUuid(curUuid):
	print(f'	getting username for {curUuid}')

	if curUuid == 'unknown':
		return 'unknown'

	if len(curUuid) <= 16:
		return curUuid

	apiUrl = f"https://sessionserver.mojang.com/session/minecraft/profile/{curUuid}"
	try:
		apiGot = requestsGet(apiUrl, cacheMinutes = 1)
	except:
		print(f'	failed to get api {apiUrl}')
		return "unknown"

	if "name" in apiGot:
		uuidUsername = apiGot["name"]

		return uuidUsername

	print(f'	failed to get username from {apiUrl}')
	return "unknown"
def getUuidFromUsername(curUsername):
	print(f'	getting uuid for {curUsername}')

	if curUsername == 'unknown':
		return 'unknown'

	if len(curUsername) > 16:
		return curUsername

	apiUrl = f"https://api.mojang.com/users/profiles/minecraft/{curUsername}"
	try:
		apiGot = requestsGet(apiUrl, cacheMinutes = 1)
	except:
		print(f'	failed to get api {apiUrl}')
		return "unknown"

	if "id" in apiGot:
		usernameUuid = apiGot["id"]

		return usernameUuid

	print(f'	failed to get uuid from {apiUrl}')
	return "unknown"

def parseTimestamp(curTimestamp):
	return int(parser.parse(curTimestamp).timestamp())

def getUrlParams(paramWords, forPanda):
	atPage = None

	print(f'forPanda: {forPanda}')
	print(f'paramWords: {paramWords}')

	specialKeyWords = ["page", "tier", "curlives", "lives", "tokens", "nonce", "id", "name", "owner"]

	urlParams = []

	atEnchant = 1

	lastWord = None
	for atWord in range(len(paramWords) - 1, -1, -1):
		curWord = paramWords[atWord]

		print(f'	cur word: {curWord}')

		# check if preceeding word is a keyword

		if atWord > 0:
			if paramWords[atWord - 1] in specialKeyWords:
				lastWord = curWord
				print('		skipping')
				continue

		# check if word is just a paramLevel e.g. 1+ 2 3-

		if len(curWord) <= 2 and any(char.isdigit() for char in curWord):
			lastWord = curWord
			continue

		# init

		paramKey = ""
		paramLevel = ""

		# check last characters for level modifier

		curWordLastChar = curWord[-1]
		curWordSecondToLastChar = None
		if len(curWord) > 1:
			curWordSecondToLastChar = curWord[-2]

		if curWordLastChar.isnumeric() or curWordLastChar == '+' or curWordLastChar == '-': # moc2
			paramLevel = ""
			for atChar, curChar in enumerate(reversed(curWord)):
				print(f'			at char {atChar}: {curChar}')
				if curChar.isnumeric() or curChar == '+' or curChar == '-':
					paramLevel += curChar
				else:
					paramKey = curWord[:len(curWord) - atChar]
					paramLevel = paramLevel[::-1]
					break
			else:
				print('			big fail?')

			print(f"			{paramKey}-{paramLevel}")
		elif curWordLastChar == '+' or curWordLastChar == '-': # moc2+ moc2-
			paramKey = curWord[:-2]
			paramLevel = curWordSecondToLastChar + curWordLastChar
		elif lastWord != None: # moc 2 moc 2+ moc 2-
			paramKey = curWord
			paramLevel = lastWord

			lastWord = None
		else: # moc
			paramKey = curWord
			paramLevel = ''

		# check for keywords

		if curWord in ["gem", "gemmed"]:
			if forPanda:
				urlParams.append("gemmed")
			else:
				urlParams.append("gemmed=true")
			continue
		if curWord in ["ug", "ungem", "ungemmed"]:
			if forPanda:
				urlParams.append("!gemmed")
			else:
				urlParams.append("gemmed=false")
			continue

		if paramKey in specialKeyWords: # add owner too

			print('			special word')

			if paramKey == "page":
				atPage = int(paramLevel) - 1
				continue

			elif paramKey == "owner": # owner is a 'paramLevel'

				ownerUuid = paramLevel
				if len(paramLevel) < 32:
					ownerUuid = getUuidFromUsername(paramLevel)

				if forPanda:
					urlParams.append(f"uuid{ownerUuid}")
				else:
					urlParams.append(f"owner={ownerUuid}")

				continue

			else:

				print(f"			{paramKey}-{paramLevel}")

				if paramKey == 'lives':
					paramKey = 'maxlives'
				elif paramKey == 'curlives':
					paramKey = 'lives' 

				if not forPanda:
					print('			not for panda')
					paramKey = paramKey + '='

				urlParams.append(f"{paramKey}{paramLevel}")
				print(f"			{paramKey}-{paramLevel}")

				continue

		# convert to proper enchant name

		if paramKey in enchNames:
			paramKey = enchNames[paramKey]

		# re-append level modifier

		if paramLevel == "":
			paramLevel = "0+" # pit panda uses "0+", jojo.boats doesn't care and uses "" (actually 0+ would work too...)

		if forPanda:
			paramStr = paramKey + paramLevel
		else:
			paramStr = f'enchant{atEnchant}={paramKey + paramLevel}'

		# increment atEnchant

		atEnchant += 1

		# append to list

		urlParams.append(paramStr)

	return urlParams, atPage

# commands

async def commandHelp(curMessage):
	curMessageSplit = curMessage.content.lower().split()

	if len(curMessageSplit) == 2:
		await postCommandHelpMessage(curMessage, getCommandFunc(curMessageSplit[1]))
	else:
		await postCommandHelpMessage(curMessage, commandHelp)

async def commandOwnerHistory(curMessage):
	ownersPerPage = 16

	curMessageSplit = curMessage.content.lower().split()

	if len(curMessageSplit) < 2:
		await postCommandHelpMessage(curMessage, commandOwnerHistory)
		return

	ownerUsername = curMessageSplit[1].lower()
	ownerUsername = getUsernameFromUuid(ownerUsername)
	ownerUsername = getUuidFromUsername(ownerUsername)
	if ownerUsername == 'unknown':
		await curMessage.reply("API failed, are you sure that player exists?")
		return

	searchParams = []

	atPage = None

	searchParams, atPage = getUrlParams(curMessageSplit[2:], True)

	searchParams.append(f"uuid{ownerUsername}")

	urlParamsStr = ",".join(searchParams)

	searchApiUrl = f"https://pitpanda.rocks/api/itemsearch/{urlParamsStr}?key={pitPandaApiKey}"
	try:
		searchApiGot = requestsGet(searchApiUrl, cacheMinutes = 1)
	except:
		print(f'	failed to get api {searchApiUrl}')
		await curMessage.reply("API failed or timed out.")
		return

	itemsList = searchApiGot["items"]
	itemsListLen = len(itemsList)

	if itemsListLen == 0:
		print('		couldnt find, searching past owners too')

		searchParams.remove(f"uuid{ownerUsername}")
		searchParams.append(f"past{ownerUsername}")

		urlParamsStr = ",".join(searchParams)

		searchApiUrl = f"https://pitpanda.rocks/api/itemsearch/{urlParamsStr}?key={pitPandaApiKey}"
		try:
			searchApiGot = requestsGet(searchApiUrl, cacheMinutes = 1)
		except:
			print(f'	failed to get api {searchApiUrl}')
			await curMessage.reply("API failed or timed out.")
			return

		itemsList = searchApiGot["items"]
		itemsListLen = len(itemsList)

	if itemsListLen == 0:
		await curMessage.reply("No items found.")
		return
	elif itemsListLen > 1:
		replyStr = "Too many items found, be more specific."

		for atItem, curItem in enumerate(itemsList):
			replyStr += f"\n{itemStr(curItem)}"

			if atItem > 10:
				replyStr += "\nMore..."
				break

		await curMessage.reply(replyStr[:2000])
		return
	elif itemsListLen != 1: # should never trigger due to above conditions
		return

	foundItem = itemsList[0]
	foundItemId = foundItem["id"]

	idApiUrl = f"https://pitpanda.rocks/api/item/{foundItemId}?key={pitPandaApiKey}"
	try:
		idApiGot = requestsGet(idApiUrl, cacheMinutes = 1)
	except:
		print(f'	failed to get api {idApiUrl}')
		await curMessage.reply("API failed or timed out.")
		return

	realItem = idApiGot["item"]

	itemOwners = idApiGot["item"]["owners"]
	totalPages = math.ceil(len(itemOwners) / ownersPerPage)

	if atPage == None:
		atPage = totalPages - 1

	numBack = 0
	if atPage == totalPages - 1:
		numBack = ownersPerPage - (len(itemOwners) % ownersPerPage)
		if numBack == ownersPerPage:
			numBack = 0

	itemOwnersSlice = itemOwners[max(0, atPage * ownersPerPage - numBack):atPage * ownersPerPage + ownersPerPage]

	if atPage < 0:
		await curMessage.reply(f"Page {atPage + 1}/{totalPages} is too low.")
		return
	elif atPage > totalPages - 1:
		await curMessage.reply(f"Page {atPage + 1}/{totalPages} is too high.")
		return

	embedStr = ""
	for ownerData in itemOwnersSlice:
		ownerUuid = ownerData["uuid"]
		ownerUsername = getUsernameFromUuid(ownerUuid)

		ownerTime = parseTimestamp(ownerData["time"])

		embedStr += f"""`{ownerUsername}{' ' * (17 - len(ownerUsername))}` <t:{ownerTime}:R>\n"""

	replyEmbed = discord.Embed(title = "", color = discord.Color.red())
	replyEmbed.add_field(name = f'Owners: (page {atPage + 1}/{totalPages})', value = embedStr[:1024])

	await curMessage.reply(itemStr(foundItem), embed = replyEmbed)

async def commandPlayerStatus(curMessage):
	curTime = time.time()

	curMessageSplit = curMessage.content.lower().split()

	if len(curMessageSplit) != 2:
		await postCommandHelpMessage(curMessage, commandPlayerStatus)
		return

	curUsername = curMessageSplit[1]

	apiUrl = f"https://pitpanda.rocks/api/players/{curUsername}"
	try:
		apiGot = requestsGet(apiUrl, cacheMinutes = 1)
	except:
		print(f'	failed to get api {apiUrl}')
		await curMessage.reply("API failed or timed out.")
		return

	if not apiGot['success']:
		await curMessage.reply("API failed, are you sure that player exists?")
		return

	playerUuid = getVal(apiGot, ['data', 'uuid'])
	if playerUuid == None: playerUuid = 'unknown'

	formattedName = getVal(apiGot, ['data', 'formattedName'])
	if formattedName == None: formattedName = 'unknown'

	formattedLevel = getVal(apiGot, ['data', 'formattedLevel'])
	if formattedLevel == None: formattedLevel = 'unknown'

	playerGold = getVal(apiGot, ['data', 'currentGold'])
	if playerGold == None: playerGold = 0

	playerPlaytime = getVal(apiGot, ['data', 'playtime'])
	if playerPlaytime == None: playerPlaytime = 0
	
	playerOnlineStatus = getVal(apiGot, ['data', 'online'])
	if playerOnlineStatus == None: playerOnlineStatus = False

	playerLastSave = getVal(apiGot, ['data', 'lastSave'])
	if playerLastSave == None: playerLastSave = 0

	embedStr = ""
	if playerOnlineStatus or curTime - playerLastSave / 1000 < 180:
		embedStr = "[ONLINE]"
		embedStr += f"\nIn Pit <t:{int(playerLastSave / 1000)}:R>"
	else:
		playerLastLogout = getVal(apiGot, ['data', 'lastLogout'])

		if playerLastLogout == None:
			playerLastLogout = "[unknown]"
		else:
			playerLastLogout = f"<t:{int(playerLastLogout / 1000)}:R>"

		embedStr += f"In Pit <t:{int(playerLastSave / 1000)}:R>"
		embedStr += f"\nLast seen in Hypixel {playerLastLogout}"

	embedTitle = f"{stripColorCodes(formattedName)}"

	embedFieldName = ""
	embedFieldName += f"\nLevel: {stripColorCodes(formattedLevel)}"
	embedFieldName += f"\nGold: {int(playerGold)}g"
	embedFieldName += f"\nPlayed: {int(playerPlaytime / 60)}hrs"

	replyEmbed = discord.Embed(title = embedTitle, color = discord.Color.red())
	replyEmbed.add_field(name = embedFieldName, value = embedStr[:1024])

	replyEmbed.set_thumbnail(url = f"https://crafatar.com/avatars/{playerUuid}")

	await curMessage.reply('', embed = replyEmbed)

async def commandKos(curMessage):
	await postCommandHelpMessage(curMessage, commandKos)
		
async def commandNameHistory(curMessage): # broken, prob remove
	curMessageSplit = curMessage.content.lower().split()

	if len(curMessageSplit) != 2:
		await postCommandHelpMessage(curMessage, commandNameHistory)
		return

	targetIdentity = curMessageSplit[1]
	targetIdentity = getUuidFromUsername(targetIdentity)

	if targetIdentity == "unknown":
		await curMessage.reply("Player not found.")
		return

	apiUrl = f"https://api.mojang.com/user/profiles/{targetIdentity}/names"
	try:
		apiGot = requestsGet(apiUrl, cacheMinutes = 1440)
	except:
		print(f'	failed to get api {apiUrl}')
		await curMessage.reply("API failed or timed out.")
		return

	if type(apiGot) is not list:
		await curMessage.reply("API failed, are you sure that player exists?")
		return

	embedStr = ""
	for curData in apiGot:
		curUsername = ""
		if "name" in curData:
			curUsername = curData["name"]
		curTime = "Original"
		if "changedToAt" in curData:
			curTime = f"""<t:{int(curData["changedToAt"] / 1000)}:R>"""
		embedStr += f"""`{curUsername}{' ' * (17 - len(curUsername))}` {curTime}\n"""

	replyEmbed = discord.Embed(title = "", color = discord.Color.red())
	replyEmbed.add_field(name = "Usernames", value = embedStr[:1024])

	await curMessage.reply('', embed = replyEmbed)

async def commandItemSearch(curMessage):
	itemsPerPage = 8

	curMessageSplit = curMessage.content.lower().split()

	if len(curMessageSplit) < 2:
		await postCommandHelpMessage(curMessage, commandItemSearch)
		return

	searchParams = []

	atPage = None

	searchParams, atPage = getUrlParams(curMessageSplit[1:], True)

	urlParamsStr = ",".join(searchParams)

	searchApiUrl = f"https://pitpanda.rocks/api/itemsearch/{urlParamsStr}?key={pitPandaApiKey}"
	try:
		searchApiGot = requestsGet(searchApiUrl, cacheMinutes = 1)
	except:
		print(f'	failed to get api {searchApiUrl}')
		await curMessage.reply("API failed or timed out.")
		return

	itemsList = searchApiGot["items"]
	totalPages = math.ceil(len(itemsList) / itemsPerPage)

	if atPage == None:
		atPage = 0

	itemsListSlice = itemsList[max(0, atPage * itemsPerPage):atPage * itemsPerPage + itemsPerPage]

	if len(itemsList) == 0:
		await curMessage.reply('No items found.')
		return

	if atPage < 0:
		await curMessage.reply(f"Page {atPage + 1}/{totalPages} is too low.")
		return
	elif atPage > totalPages - 1:
		await curMessage.reply(f"Page {atPage + 1}/{totalPages} is too high.")
		return

	itemsStr = f"Items: (page {atPage + 1}/{totalPages})"
	for curItem in itemsListSlice:
		itemsStr += f"\n{itemStr(curItem)}"

	await curMessage.reply(itemsStr)

async def commandBoatsSearch(curMessage):
	itemsPerPage = 8

	curMessageSplit = curMessage.content.lower().split()

	if len(curMessageSplit) < 2:
		await postCommandHelpMessage(curMessage, commandBoatsSearch)
		return

	ownerUsername = curMessageSplit[1].lower()

	searchParams = []

	atPage = None

	searchParams, atPage = getUrlParams(curMessageSplit[1:], False)

	urlParamsStr = ",".join(searchParams)

	searchApiUrl = f"https://jojo-boats.herokuapp.com/api/items/{urlParamsStr}"
	try:
		searchApiGot = requestsGet(searchApiUrl, cacheMinutes = 1)
	except:
		print(f'	failed to get api {searchApiUrl}')
		await curMessage.reply("API failed or timed out.")
		return

	itemsList = searchApiGot["items"]
	totalPages = math.ceil(len(itemsList) / itemsPerPage)

	if atPage == None:
		atPage = 0

	itemsListSlice = itemsList[max(0, atPage * itemsPerPage):atPage * itemsPerPage + itemsPerPage]

	if len(itemsList) == 0:
		await curMessage.reply('No items found.')
		return

	if atPage < 0:
		await curMessage.reply(f"Page {atPage + 1}/{totalPages} is too low.")
		return
	elif atPage > totalPages - 1:
		await curMessage.reply(f"Page {atPage + 1}/{totalPages} is too high.")
		return

	itemsStr = f"Items: (page {atPage + 1}/{totalPages})"

	for curItem in itemsListSlice:
		itemsStr += f"\n{itemStr(curItem)}"

	await curMessage.reply(itemsStr)

async def commandMutuals(curMessage):
	curMessageSplit = curMessage.content.lower().split()

	curMessageSplitLen = len(curMessageSplit)

	if curMessageSplitLen != 3:
		await postCommandHelpMessage(curMessage, commandMutuals)
		return

	firstPlayerUuid = getUuidFromUsername(curMessageSplit[1])
	secondPlayerUuid = getUuidFromUsername(curMessageSplit[2])

	firstApiUrl = f"https://pitpanda.rocks/api/friends/{firstPlayerUuid}?key={pitPandaApiKey}"
	try:
		firstApiGot = requestsGet(firstApiUrl, cacheMinutes = 1)
	except:
		print(f'	failed to get api {firstApiUrl}')
		await curMessage.reply("API failed or timed out.")
		return

	if not firstApiGot['success']:
		await curMessage.reply("API failed, are you sure those players exist?")
		return

	secondApiUrl = f"https://pitpanda.rocks/api/friends/{secondPlayerUuid}?key={pitPandaApiKey}"
	try:
		secondApiGot = requestsGet(secondApiUrl, cacheMinutes = 1)
	except:
		print(f'	failed to get api {secondApiUrl}')
		await curMessage.reply("API failed or timed out.")
		return

	if not secondApiGot['success']:
		await curMessage.reply("API failed, are you sure those players exist?")
		return

	mutualsList = []

	firstFriendsDict = {}
	for curFriendData in firstApiGot["friends"]:
		curFriendUuid = curFriendData["uuid"]
		firstFriendsDict[curFriendUuid] = True

	for curFriendData in secondApiGot["friends"]:
		curFriendUuid = curFriendData["uuid"]
		if curFriendUuid in firstFriendsDict:
			mutualsList.append(curFriendUuid)

	mutualsListLen = len(mutualsList)

	embedStr = ""
	if mutualsListLen > 0:
		atNum = 0
		for curMutualUuid in mutualsList[:64]: # redundant slicing
			playerUsername = getUsernameFromUuid(curMutualUuid)

			embedStr += f"""`{playerUsername}`\n"""

			atNum += 1
			if atNum >= 32:
				embedStr += "More..."
				break
	else:
		embedStr += "No mutual friends."

	replyEmbed = discord.Embed(title = "", color = discord.Color.red())
	replyEmbed.add_field(name = f"Mutual friends: ({mutualsListLen})", value = embedStr[:1024])

	await curMessage.reply('', embed = replyEmbed)

async def commandEvents(curMessage):
	apiUrl = "https://events.mcpqndq.dev/"
	try:
		apiGot = requestsGet(apiUrl, cacheMinutes = 1)
	except:
		print(f'	failed to get api {apiUrl}')
		return

	embedStr = ""
	for curEvent in apiGot:
		if len(embedStr) > 512:
			break
		curEventName = curEvent["event"]
		curEventTime = curEvent["timestamp"]
		embedStr += f"""`{curEventName}{' ' * (17 - len(curEventName))}` <t:{int(curEventTime / 1000)}:R>\n"""

	replyEmbed = discord.Embed(title = "", color = discord.Color.red())
	replyEmbed.add_field(name = "Events", value = embedStr[:1024])

	await curMessage.reply('', embed = replyEmbed)

async def commandKingsQuestCalc(curMessage):
	curMessageSplit = curMessage.content.lower().split()

	curMessageSplitLen = len(curMessageSplit)

	if curMessageSplitLen != 2:
		await postCommandHelpMessage(curMessage, commandKingsQuestCalc)
		return

	targetIdentity = curMessageSplit[1]

	apiUrl = f"https://pitpanda.rocks/api/players/{targetIdentity}?key={pitPandaApiKey}"
	try:
		apiGot = requestsGet(apiUrl, cacheMinutes = 1)
	except:
		print(f'	failed to get api {apiUrl}')
		await curMessage.reply("API failed or timed out.")
		return

	if not apiGot['success']:
		await curMessage.reply("API failed, are you sure that player exists?")
		return

	playerUsername = getVal(apiGot, ['data', 'name'])

	playerTotalXp = getVal(apiGot, ['data', 'doc', 'xp'])

	# calculate current prestige

	prestigeSumXps = [0, 65950, 138510, 217680, 303430, 395760, 494700, 610140, 742040, 906930, 1104780, 1368580, 1698330, 2094030, 2555680, 3083280, 3676830, 4336330, 5127730, 6051030, 7106230, 8293330, 9612330, 11195130, 13041730, 15152130, 17526330, 20164330, 23132080, 26429580, 31375830, 37970830, 44631780, 51292730, 57953680, 64614630, 71275580, 84465580, 104250580, 130630580, 163605580, 213068080, 279018080, 361455580, 460380580, 575793080, 707693080, 905543080, 1235293080, 1894793080, 5192293080, 11787293080]

	levelMultipliers = [1, 1.1, 1.2, 1.3, 1.4, 1.5, 1.75, 2, 2.5, 3, 4, 5, 6, 7, 8, 9, 10, 12, 14, 16, 18, 20, 24, 28, 32, 36, 40, 45, 50, 75, 100, 101, 101, 101, 101, 101, 200, 300, 400, 500, 750, 1000, 1250, 1500, 1750, 2000, 3000, 5000, 10000, 50000, 100000]
	levelBaseXps = [15, 30, 50, 75, 125, 300, 600, 800, 900, 1000, 1200, 1500]

	playerPrestige = 0

	for atPrestige, curXp in enumerate(reversed(prestigeSumXps)):
		if playerTotalXp > curXp:
			playerPrestige = len(prestigeSumXps) - atPrestige - 1
			break

	playerTotalXp -= prestigeSumXps[playerPrestige]

	# add extra for king's quest

	playerTotalXp += (prestigeSumXps[playerPrestige + 1] - prestigeSumXps[playerPrestige]) / 3

	# calculate new level

	playerLevel = 0
	while playerTotalXp > 0 and playerLevel < 120:
		playerTotalXp -= levelBaseXps[math.floor(playerLevel / 10)] * levelMultipliers[playerPrestige]
		playerLevel += 1

	# reply

	embedStr = f"King's Quest would bring {playerUsername} to p{playerPrestige} lvl{playerLevel}"

	replyEmbed = discord.Embed(title = "", color = discord.Color.red())
	replyEmbed.add_field(name = "King's Quest", value = embedStr)

	await curMessage.reply('', embed = replyEmbed)

async def commandsTradeLimits(curMessage):
	curMessageSplit = curMessage.content.lower().split()

	curMessageSplitLen = len(curMessageSplit)

	if curMessageSplitLen != 2:
		await postCommandHelpMessage(curMessage, commandsTradeLimits)
		return

	targetIdentity = curMessageSplit[1]
	targetUuid = getUuidFromUsername(targetIdentity)

	apiUrl = f"https://api.hypixel.net/player?key={hypixelApiKey}&uuid={targetUuid}"
	try:
		apiGot = requestsGet(apiUrl, cacheMinutes = 1)
	except:
		print(f'	failed to get api {apiUrl}')
		await curMessage.reply("API failed or timed out.")
		return

	if not apiGot['success']:
		await curMessage.reply("API failed, are you sure that player exists?")
		return

	playerUsername = getVal(apiGot, ['player', 'displayname'])

	if playerUsername == None:
		await curMessage.reply('No player data found.')
		return

	playerTrades = getVal(apiGot, ['player', 'stats', 'Pit', 'profile', 'trade_timestamps'])

	curTime = time.time()
	playerTrades = list(filter(lambda x: x > (curTime - 86400) * 1000, playerTrades)) 

	if playerTrades == None or len(playerTrades) == 0:
		await curMessage.reply('No trade limits found. 0/25')
		return

	#playerGoldTransactions = getVal(apiGot, ['player', 'stats', 'Pit', 'profile', 'gold_transactions'])
	#if playerGoldTransactions != None and len(playerGoldTransactions) != 0:
	#	playerGoldTransactions = list(filter(lambda x: x['timestamp'] > (curTime - 86400) * 1000, playerGoldTransactions)) 

	# reply

	#totalGoldLimitUsed = 0

	embedStr = ""
	embedStr += f"""`{str(len(playerTrades)) + '/25'}{' ' * (17 - len(str(len(playerTrades)) + '/25'))}` Now\n"""
	for atTrade, curTradeTime in enumerate(playerTrades):

		if len(embedStr) > 512:
			break

		tradeLimitsStr = f'{len(playerTrades) - atTrade - 1}/25'

		#for curGoldTransaction in playerGoldTransactions:
		#	if curGoldTransaction['timestamp'] == curTradeTime:
		#		curGoldTransactionAmount = int(curGoldTransaction['amount'])
		#		totalGoldLimitUsed += curGoldTransactionAmount
		
		#tradeLimitsStr += f'    {int((50000 - totalGoldLimitUsed) / 1000)}k/50k'

		embedStr += f"""`{tradeLimitsStr}{' ' * (17 - len(tradeLimitsStr))}` <t:{int((curTradeTime / 1000) + 86400)}:R>\n"""

	replyEmbed = discord.Embed(title = "", color = discord.Color.red())
	replyEmbed.add_field(name = f"Trade limits for {playerUsername}", value = embedStr)

	await curMessage.reply('', embed = replyEmbed)

async def commandsDupeCheck(curMessage):
	curMessageSplit = curMessage.content.lower().split()

	if len(curMessageSplit) < 2:
		await postCommandHelpMessage(curMessage, commandOwnerHistory)
		return

	ownerUsername = curMessageSplit[1].lower()
	ownerUsername = getUsernameFromUuid(ownerUsername)
	ownerUsername = getUuidFromUsername(ownerUsername)
	if ownerUsername == 'unknown':
		await curMessage.reply("API failed, are you sure that player exists?")
		return

	searchParams = []

	atPage = None

	searchParams, atPage = getUrlParams(curMessageSplit[2:], True)

	searchParams.append(f"uuid{ownerUsername}")

	urlParamsStr = ",".join(searchParams)

	searchApiUrl = f"https://pitpanda.rocks/api/itemsearch/{urlParamsStr}?key={pitPandaApiKey}"
	try:
		searchApiGot = requestsGet(searchApiUrl, cacheMinutes = 1)
	except:
		print(f'	failed to get api {searchApiUrl}')
		await curMessage.reply("API failed or timed out.")
		return

	searchItemsList = searchApiGot["items"]
	searchItemsListLen = len(searchItemsList)

	if searchItemsListLen == 0:
		print('		couldnt find, searching past owners too')

		searchParams.remove(f"uuid{ownerUsername}")
		searchParams.append(f"past{ownerUsername}")

		urlParamsStr = ",".join(searchParams)

		searchApiUrl = f"https://pitpanda.rocks/api/itemsearch/{urlParamsStr}?key={pitPandaApiKey}"
		try:
			searchApiGot = requestsGet(searchApiUrl, cacheMinutes = 1)
		except:
			print(f'	failed to get api {searchApiUrl}')
			await curMessage.reply("API failed or timed out.")
			return

		searchItemsList = searchApiGot["items"]
		searchItemsListLen = len(searchItemsList)

	if searchItemsListLen == 0:
		await curMessage.reply("No items found.")
		return
	elif searchItemsListLen > 1:
		replyStr = "Too many items found, be more specific."

		for atItem, curItem in enumerate(searchItemsList):
			replyStr += f"\n{itemStr(curItem)}"

			if atItem > 10:
				replyStr += "\nMore..."
				break

		await curMessage.reply(replyStr[:2000])
		return
	elif searchItemsListLen != 1: # should never trigger due to above conditions
		return

	foundItem = searchItemsList[0]
	foundItemNonce = foundItem["nonce"]

	# check panda

	pandaNonceApiUrl = f"https://pitpanda.rocks/api/itemsearch/nonce{foundItemNonce}?key={pitPandaApiKey}"
	try:
		pandaNonceApiGot = requestsGet(pandaNonceApiUrl, cacheMinutes = 1)
	except:
		print(f'	failed to get api {pandaNonceApiUrl}')
		await curMessage.reply("API failed or timed out.")
		return

	pandaNonceItemsList = pandaNonceApiGot["items"]
	pandaNonceItemsListLen = len(pandaNonceItemsList)

	# check jojo.boats

	boatsNonceApiUrl = f"http://www.jojo.boats/api/items/nonce={foundItemNonce}"
	try:
		boatsNonceApiGot = requestsGet(boatsNonceApiUrl, cacheMinutes = 1)
	except:
		print(f'	failed to get api {boatsNonceApiUrl}')
		await curMessage.reply("API failed or timed out.")
		return

	boatsNonceItemsList = boatsNonceApiGot["items"]
	boatsNonceItemsListLen = len(boatsNonceItemsList)

	# reply

	embedStr = f"""
	Item's nonce is {foundItemNonce}
	`Panda has:         {pandaNonceItemsListLen}`
	`Jojo Boats has:    {boatsNonceItemsListLen}`
	"""

	replyEmbed = discord.Embed(title = "", color = discord.Color.red())
	replyEmbed.add_field(name = f"Dupe check", value = embedStr)

	await curMessage.reply(itemStr(foundItem) + "\nNeither of these numbers is guaranteed to be accurate.\nTo see the items that were found search with `.is nonce <nonce>` and `.bs nonce <nonce>`", embed = replyEmbed)

async def commandVerify(curMessage):

	userDoc = discordsCol.find_one({'_id': curMessage.author.id})

	if userDoc != None:

		userDocIdentifier = 'null'

		if 'uuid' in userDoc:
			userDocUsername = userDoc['uuid']

		if 'username' in userDoc:
			userDocUsername = userDoc['username']

		await curMessage.reply(f'Already verified as `{userDocUsername}`, use `.unverify` to remove this verification.')

		return

	curMessageSplit = curMessage.content.lower().split()

	if len(curMessageSplit) != 2:
		await postCommandHelpMessage(curMessage, commandVerify)
		return

	playerUsername = curMessageSplit[1]

	playerApiUrl = f"https://pitpanda.rocks/api/players/{playerUsername}?key={pitPandaApiKey}"
	try:
		playerApiGot = requestsGet(playerApiUrl, cacheMinutes = 1)
	except:
		print(f'	failed to get api {playerApiUrl}')
		await curMessage.reply("API failed or timed out.")
		return

	if 'success' in playerApiGot:
		if playerApiGot['success'] != True:
			await curMessage.reply("Player doesn't exist.")
			return

	apiDiscord = getVal(playerApiGot, ['data', 'doc', 'discord'])

	messageDiscord = curMessage.author.name + '#' + curMessage.author.discriminator

	if apiDiscord != messageDiscord:
		await curMessage.reply("Hypixel Discord doesn't match your Discord.")
		return

	# get uuid

	if 'data' not in playerApiGot:
		await curMessage.reply("Data error.")
		return

	if 'uuid' not in playerApiGot['data']:
		await curMessage.reply("Data error.")
		return

	playerUuid = playerApiGot['data']['uuid']

	# get username

	if 'data' not in playerApiGot:
		await curMessage.reply("Data error.")
		return

	if 'name' not in playerApiGot['data']:
		await curMessage.reply("Data error.")
		return

	playerUsername = playerApiGot['data']['name']

	discordsCol.insert_one({'_id': curMessage.author.id, 'uuid': playerUuid, 'username': playerUsername})
	await curMessage.reply(f"Successfully verified as `{playerUsername}`.")

async def commandUnverify(curMessage):

	userDoc = discordsCol.find_one({'_id': curMessage.author.id})

	if userDoc == None:

		await curMessage.reply(f'No verification found.')
		return

	discordsCol.delete_one({'_id': curMessage.author.id})
	await curMessage.reply(f"Successfully unverified.")

async def commandLeaderboards(curMessage):

	curMessageSplit = curMessage.content.lower().split()

	if len(curMessageSplit) != 2:
		await postCommandHelpMessage(curMessage, commandLeaderboards)
		return

	curLbType = curMessageSplit[1]

	if curLbType not in leaderboardTypes.keys():
		await curMessage.reply(f"Leaderboard type not found. Available types: `{', '.join(leaderboardTypes.keys())}`")
		return

	guildVals = {} # key = guild id, value = list of values for this leaderboard type

	allDiscordDocs = discordsCol.find()

	for curDoc in allDiscordDocs:

		if 'guilds' not in curDoc:
			continue

		if 'gamedata' not in curDoc:
			continue

		if curLbType not in curDoc['gamedata']:
			continue

		for curGuildId in curDoc['guilds']:

			if curGuildId not in guildVals:
				guildVals[curGuildId] = []

			guildVals[curGuildId].append(curDoc['gamedata'][curLbType])

	# sort guild values and put into totals

	topPlayersCount = 16

	guildTotals = {}

	for curGuildId, curGuildVals in guildVals.items():

		curGuildVals.sort(reverse = True)

		guildTotals[curGuildId] = sum(guildVals[curGuildId][:topPlayersCount])

	guildTotals = list(guildTotals.items())

	guildTotals.sort(key = lambda x: x[1], reverse = True)

	lbString = ''

	for atGuild, (curGuildId, curGuildTotal) in enumerate(guildTotals[:16]):

		curGuildName = await getGuildName(curGuildId)

		lbString += f"""`{str(atGuild + 1)[:3]}{' ' * (3 - len(str(atGuild + 1)))}` `{curGuildName[:32]}{' ' * (32 - len(curGuildName))}` `{prettyNumber(curGuildTotal)}`\n"""

	replyEmbed = discord.Embed(title = "", color = discord.Color.red())
	replyEmbed.add_field(name = f"Leaderboard - {curLbType}", value = lbString[:1024])

	await curMessage.reply('', embed = replyEmbed)

# other

def getCommandFunc(commandStr):
	if commandStr in commandsList:
		return commandsList[commandStr]
	return None

async def postCommandHelpMessage(curMessage, helpCommandFunc):
	if helpCommandFunc == None:
		await curMessage.reply("Command not found, type `.help`")
		return

	helpMessages = {}

	helpMessages[commandKos] = """
	KOS system has been removed, use http://www.jojo.boats/kos
	If you need help feel free to DM Jojo.
	"""

	helpMessages[commandOwnerHistory] = """
	`.oh username ench1 [ench2] [ench3] [lives X] [page X]`
	View the owner history of a mystic using data from Pit Panda.

	`lives` means maximum lives, not current lives.

	For example:
	`.oh jojoq booboo moc3 lives 100`
	"""

	helpMessages[commandNameHistory] = """
	`.nh username`
	Get the name history of a player.
	"""

	helpMessages[commandPlayerStatus] = """
	`.pl username`
	Get the current status of a player.
	"""

	helpMessages[commandEvents] = """
	`.ev`
	View upcoming events.
	"""

	helpMessages[commandItemSearch] = """
	`.is ench1 [ench2] [ench3] [lives X]`
	Search for a mystic using data from Pit Panda.

	For example:
	`.is moc3 shark`
	"""

	helpMessages[commandBoatsSearch] = """
	`.bs ench1 [ench2] [ench3] [extra [X]]`
	Search for a mystic using data from jojo.boats

	Extra search terms:
	Name: lowercase, no special characters e.g. minicake, mysticsword, tieriiiragepants
	Owner: player username/uuid
	Tier: number, 0, 1, 2, 3
	CurLives: number, **current** lives, 1 - 150
	Lives: number, **maximum** lives, 1 - 150
	Gemmed: either `gemmed` or `ungemmed`
	Nonce: number, 5 = aqua, 6 = dark, 8 = sewer, 9 = rage, other mystics have random nonces
	Tokens: number
	Id: number, minecraft item id
	Enchants: enchant name + number + optional '+' or '-' e.g. regularity3, rgm2+, sweaty

	For example:
	`.bs moc3 tier 2`
	`.bs moc shark ungemmed`
	`.bs name tinykloonfish`
	"""

	helpMessages[commandsDupeCheck] = """
	`.dc username ench1 [ench2] [ench3] [lives X] [page X]`
	Check if an item appears to be duped using data from Pit Panda and Jojo Boats.

	`lives` means maximum lives, not current lives.

	For example:
	`.dc jojoq booboo moc3 lives 100`
	"""

	helpMessages[commandMutuals] = """
	`.mutuals player1 player2`

	Finds mutual Hypixel friends of two players.
	"""

	helpMessages[commandKingsQuestCalc] = """
	`.kq username`

	Calculate level gain from King's Quest.
	"""

	helpMessages[commandsTradeLimits] = """
	`.tr username`

	View when your trades limits expire.
	"""

	helpMessages[commandVerify] = """
	`.verify username`
	Verify to link your Discord account with Hypixel.
	"""

	helpMessages[commandUnverify] = """
	`.unverify`
	Remove your current Discord-Hypixel link.
	"""

	# too long already...
	helpMessages[commandHelp] = """
	**.help**
	Display available commands. Use `.help [command]` to view individual command usage.

	**.ownerhistory**
	View the owner history of a mystic.

	**.kos**
	Use the KOS tracker system.

	**.player**
	View player information and status.

	**.events**
	View upcoming events.
	
	**.namehistory**
	View the name history of a player.

	**.mutuals**
	Show mutual Hypixel friends of two players.

	**.kingsquest**
	Calculate your new level after completing King's Quest.

	**.tradelimits**
	View when your trades limits expire.

	**.itemsearch**
	Search for a mystic using Pit Panda data.

	**.verify**
	Verify to link your Discord account with your Hypixel account.

	**.unverify**
	Remove your current Discord-Hypixel link.

	**.boatssearch**
	Search for any item (*any*) using jojo.boats data. Includes regs, darks, etc.

	**.dupecheck**
	Check if an item appears to be duped.

	**Code at https://github.com/jojo259/discord-hypixel-pit-abyss-bot**
	**Add me to your server by clicking my profile and then "Add to Server".**
	"""

	helpStr = helpMessages[helpCommandFunc]

	replyEmbed = discord.Embed(title = "", color = discord.Color.red())
	replyEmbed.add_field(name = f"Command", value = helpStr[:1024])

	await curMessage.reply('', embed = replyEmbed)

# bot init stuff

class botClass(discord.Client):
	commandsPrefix = "."

	async def on_ready(theBot):
		print(f"Logged in as {theBot.user}")

		for guild in theBot.guilds:
			print(f'in guild with {guild.member_count}\t members named {guild.name}')
			await guild.me.edit(nick = "Abyss Bot") # bot tries to reset nickname, doesn't matter if it can't

		await theBot.change_presence(activity = discord.Game(".help"))

		theBot.updateLeaderboardPlayer.start()
		theBot.updateLeaderboardGuilds.start()

	@tasks.loop(minutes = 1)
	async def updateLeaderboardGuilds(theBot):

		print('updating leaderboard guilds')

		userGuildsDict = {} # dictionary with list of guilds a user is in (key = user id, value = list of guilds)

		for curGuild in theBot.guilds:

			for curMember in curGuild.members:

				if curMember.id not in userGuildsDict:
					userGuildsDict[curMember.id] = []

				userGuildsDict[curMember.id].append(curGuild.id)

		guildMemberDocs = discordsCol.find({'_id': {'$in': list(userGuildsDict.keys())}})

		updatesList = []

		for curDoc in guildMemberDocs:

			userGuilds = userGuildsDict[curDoc['_id']]

			updatesList.append(pymongo.UpdateOne({'_id': curDoc['_id']}, {'$set': {'guilds': userGuilds}}))

		discordsCol.bulk_write(updatesList)

	@tasks.loop(seconds = 5)
	async def updateLeaderboardPlayer(theBot):

		print('updating leaderboard player')
		
		# get random document (good enough)

		allDiscordDocs = discordsCol.find()

		randomDoc = random.choice(list(allDiscordDocs))

		userDiscordId = randomDoc['_id']
		userUuid = randomDoc['uuid']

		# get data

		playerApiUrl = f"https://pitpanda.rocks/api/players/{userUuid}?key={pitPandaApiKey}"
		try:
			playerApiGot = requestsGet(playerApiUrl, cacheMinutes = 10)
		except:
			print(f'	failed to get api {playerApiUrl}')
			return

		# process

		lbSetVals = {}

		for curLbName, curLbPath in leaderboardTypes.items():

			curLbVal = getVal(playerApiGot, ['data'] + curLbPath)
			
			if curLbVal == None:
				continue

			lbSetVals['gamedata.' + curLbName] = curLbVal

		# set vals

		discordsCol.update_one({'_id': userDiscordId}, {'$set': lbSetVals})

	async def on_message(theBot, curMessage):
		curAuthor = curMessage.author
		if curAuthor == theBot.user:
			return

		if debugMode and curMessage.channel.id != 1010870694650847272: # debug bot only enabled inside test channel
			return

		if not debugMode and curMessage.channel.id == 1010870694650847272: # production bot disabled inside test channel
			return

		curMessageContent = curMessage.content
		if not len(curMessageContent) > 0:
			return
		if curMessageContent[0] != botClass.commandsPrefix:
			return

		curMessageSplit = curMessageContent.lower().split()

		curMessageCommand = curMessageSplit[0][1:]

		if curMessageCommand in commandsList:
			if curAuthor.id != 121692189230104577: # jojo's discord ID (i don't need logs for my own commands)
				curGuildName = curMessage.guild.name
				logStr = f"user `{curAuthor}` in `{curGuildName}` sent command: `{curMessageContent}`"
				print(logStr)
				sendDiscord(logStr)

			curMessageCommandFunc = getCommandFunc(curMessageCommand)

			async with curMessage.channel.typing():
				await commandsList[curMessageCommand](curMessage)

commandsList = {}

commandsList["h"] = commandHelp
commandsList["help"] = commandHelp

commandsList["oh"] = commandOwnerHistory
commandsList["owner"] = commandOwnerHistory
commandsList["owners"] = commandOwnerHistory
commandsList["pastowners"] = commandOwnerHistory
commandsList["ownerhistory"] = commandOwnerHistory
commandsList["ownershistory"] = commandOwnerHistory

commandsList["pl"] = commandPlayerStatus
commandsList["player"] = commandPlayerStatus
commandsList["status"] = commandPlayerStatus
commandsList["playerstatus"] = commandPlayerStatus

commandsList["kos"] = commandKos
commandsList["killonsite"] = commandKos
commandsList["killonsight"] = commandKos

commandsList["nh"] = commandNameHistory
commandsList["name"] = commandNameHistory
commandsList["namehistory"] = commandNameHistory

commandsList["is"] = commandItemSearch
commandsList["itemsearch"] = commandItemSearch
commandsList["searchitem"] = commandItemSearch
commandsList["searchpanda"] = commandItemSearch
commandsList["pandasearch"] = commandItemSearch

commandsList["bs"] = commandBoatsSearch
commandsList["boat"] = commandBoatsSearch
commandsList["boats"] = commandBoatsSearch
commandsList["search"] = commandBoatsSearch
commandsList["boatsearch"] = commandBoatsSearch
commandsList["boatssearch"] = commandBoatsSearch
commandsList["searchboats"] = commandBoatsSearch

commandsList["mu"] = commandMutuals
commandsList["moots"] = commandMutuals
commandsList["mutual"] = commandMutuals
commandsList["mutuals"] = commandMutuals

commandsList["ev"] = commandEvents
commandsList["events"] = commandEvents

commandsList["kc"] = commandKingsQuestCalc
commandsList["kq"] = commandKingsQuestCalc
commandsList["kqc"] = commandKingsQuestCalc
commandsList["kingcalc"] = commandKingsQuestCalc
commandsList["kingscalc"] = commandKingsQuestCalc
commandsList["kingquest"] = commandKingsQuestCalc
commandsList["kingsquest"] = commandKingsQuestCalc
commandsList["kingquestcalc"] = commandKingsQuestCalc
commandsList["kingsquestcalc"] = commandKingsQuestCalc

commandsList["tr"] = commandsTradeLimits
commandsList["trade"] = commandsTradeLimits
commandsList["trades"] = commandsTradeLimits
commandsList["tradelims"] = commandsTradeLimits
commandsList["tradelimits"] = commandsTradeLimits

commandsList["dc"] = commandsDupeCheck
commandsList["dupe"] = commandsDupeCheck
commandsList["duped"] = commandsDupeCheck
commandsList["checkdupe"] = commandsDupeCheck
commandsList["dupecheck"] = commandsDupeCheck

commandsList["ve"] = commandVerify
commandsList["verify"] = commandVerify

commandsList["un"] = commandUnverify
commandsList["unverify"] = commandUnverify

commandsList["lb"] = commandLeaderboards
commandsList["leaderboard"] = commandLeaderboards

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
botClass = botClass(intents = intents)
botClass.run(botToken)