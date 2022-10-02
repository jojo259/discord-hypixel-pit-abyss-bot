debugMode = False

print("init")

import discord
from discord.ext import tasks
import requests
from dateutil import parser
import math
import time
import os

from dotenv import load_dotenv
load_dotenv()

alertStr = "PRODUCTION MODE"
if debugMode:
	alertStr = "DEBUG MODE"
for i in range(8):
	print(alertStr)

print('connecting')

print('connecting')
import pymongo
mongoConnectString = os.environ['mongoconnectstring']
dbClient = pymongo.MongoClient(mongoConnectString)
curDb = dbClient['hypixel']
serversCol = curDb['servers']
print('connected')

# sensitive data
botToken = os.environ['bottoken']
pitPandaApiKey = os.environ['pitpandaapikey']
webHookUrl = os.environ['webhookurl']
hypixelApiKey = os.environ['hypixelapikey']
# sensitive data

print('getting ench names')

enchNames = {}
with open("enchnames.txt") as enchNamesFile:
	enchNamesFile = enchNamesFile.read()
	for curLine in enchNamesFile.split("\n"):
		curLineSplit = curLine.split(" ")
		enchNames[curLineSplit[0]] = curLineSplit[1]

playerData = {}

serverData = {}

kosData = {'atUuid': 0, 'finishedIndexingMinute': 0, 'uuidsDict': {}}
print('set kos data')

# util

cachedRequests = {}
def requestsGet(apiUrl, timeout = 10, cacheMinutes = 0):
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

def reloadServerData():
	print('reloading server data')

	kosData["uuidsDict"] = {}
	kosData["atUuid"] = 0
	
	for curData in serversCol.find():
		serverId = curData["_id"]

		serverData[serverId] = curData

		for curUuid in curData['koslist']:
			if curUuid not in kosData["uuidsDict"]:
				kosData["uuidsDict"][curUuid] = []

			kosData['uuidsDict'][curUuid].append(serverId)

	uuidsDictLen = len(kosData['uuidsDict'])
	print(f'tracking {uuidsDictLen} uuids for kos')

def getServerData(serverId):
	serverDoc = None
	if serverId in serverData:
		serverDoc = serverData[serverId]

	if serverDoc == None:
		serverDoc = {}

	if "_id" not in serverDoc:
		serverDoc["_id"] = serverId

	if "koslist" not in serverDoc:
		serverDoc["koslist"] = []

	return serverDoc

def saveServerData(serverDoc):
	serversCol.replace_one({"_id":serverDoc["_id"]}, serverDoc, upsert = True)

	reloadServerData()

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
		apiGot = requestsGet(apiUrl, timeout = 10, cacheMinutes = 1440)
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
		apiGot = requestsGet(apiUrl, timeout = 10, cacheMinutes = 1440)
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
		searchApiGot = requestsGet(searchApiUrl, timeout = 10, cacheMinutes = 1)
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
			searchApiGot = requestsGet(searchApiUrl, timeout = 10, cacheMinutes = 1)
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
		idApiGot = requestsGet(idApiUrl, timeout = 10, cacheMinutes = 1)
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
		apiGot = requestsGet(apiUrl, timeout = 10, cacheMinutes = 0)
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
	curMessageSplit = curMessage.content.lower().split()

	if len(curMessageSplit) < 2:
		await postCommandHelpMessage(curMessage, commandKos)
		return

	curMessageGuild = curMessage.guild
	if curMessageGuild == None:
		await curMessage.reply("The `.kos` command can only be used in servers. Add me to your server by clicking my profile.")
		return
	serverId = curMessageGuild.id

	serverData = getServerData(serverId)

	if curMessageSplit[1] == 'add':

		guildMembersCount = curMessage.guild.member_count
		print(f'	guild has {guildMembersCount} members')
		if guildMembersCount != None:
			if guildMembersCount < 5:
				await curMessage.reply("You need at least 5 members in your server to use the KOS bot.")
				return

		if not curMessage.author.guild_permissions.manage_channels and not curMessage.author.guild_permissions.ban_members and not curMessage.author.guild_permissions.administratorand and not curMessage.author.guild_permissions.kick_members and not curMessage.author.guild_permissions.administrator: # duplicated
			await curMessage.reply("You need to have a staff-level permission in order to edit the KOS list (manage channels, ban members etc.).")
			return
		
		if len(curMessageSplit) < 3:
			await curMessage.reply("Specify which player to add with `.kos add username`.")
			return

		for targetUsername in curMessageSplit[2:]:
			if len(serverData['koslist']) >= 5:
				await curMessage.reply(f"Not enough KOS list space, remove other targets.")
				return

			print(f"	adding {targetUsername}")

			targetUuid = getUuidFromUsername(targetUsername)

			if targetUuid == 'unknown':
				await curMessage.reply(f"Player does not exist.")
				continue

			if targetUuid in serverData['koslist']:
				await curMessage.reply(f"Player already added to KOS list.")
				continue

			serverData['koslist'].append(targetUuid)

			saveServerData(serverData)

			await curMessage.reply(f"Added `{targetUsername}` to KOS list. Make sure there is a channel called exactly `#kos` to send KOS messages to.")

		return

	elif curMessageSplit[1] == 'remove' or curMessageSplit[1] == 'delete' or curMessageSplit[1] == 'del':

		if not curMessage.author.guild_permissions.manage_channels and not curMessage.author.guild_permissions.ban_members and not curMessage.author.guild_permissions.administratorand and not curMessage.author.guild_permissions.kick_members and not curMessage.author.guild_permissions.administrator: # duplicated
			await curMessage.reply("You need to have a staff-level permission in order to edit the KOS list (manage channels, ban members etc.).")
			return
		
		if len(curMessageSplit) < 3:
			await curMessage.reply("Specify which player to remove with `.kos remove username`.")
			return

		targetIdentity = curMessageSplit[2]
		targetUsername = targetIdentity

		if len(targetIdentity) < 32:
			targetIdentity = getUuidFromUsername(targetUsername)
		else:
			targetUsername = getUsernameFromUuid(targetUsername)

		if targetIdentity not in serverData["koslist"]:
			await curMessage.reply(f"Player is not on the KOS list.")
			return

		serverData["koslist"].remove(targetIdentity)

		saveServerData(serverData)

		await curMessage.reply(f"Removed `{targetUsername}` from KOS list.")
		return
	
	elif curMessageSplit[1] == 'status' or curMessageSplit[1] == 'stats' or curMessageSplit[1] == 'list' or curMessageSplit[1] == 'players':
		
		embedStr = ""
		if len(serverData["koslist"]) > 0:
			for curUuid in serverData["koslist"]:
				playerUsername = getUsernameFromUuid(curUuid)

				embedStr += f"""`{playerUsername}{' ' * (17 - len(playerUsername))}` `{curUuid}`\n"""
		else:
			embedStr += "No players on KOS list."

		replyEmbed = discord.Embed(title = "", color = discord.Color.red())
		replyEmbed.add_field(name = "KOS List:", value = embedStr[:1024])

		await curMessage.reply('', embed = replyEmbed)
		return

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
		apiGot = requestsGet(apiUrl, timeout = 10, cacheMinutes = 1440)
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
		searchApiGot = requestsGet(searchApiUrl, timeout = 10, cacheMinutes = 60)
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
		searchApiGot = requestsGet(searchApiUrl, timeout = 10, cacheMinutes = 60)
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
	''' api doesnt count fast enough
	if 'count' in searchApiGot:
		if searchApiGot['count'] >= 0:
			itemsStr += f"""({searchApiGot["count"]} items found)"""
	'''
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
		firstApiGot = requestsGet(firstApiUrl, timeout = 10, cacheMinutes = 60)
	except:
		print(f'	failed to get api {firstApiUrl}')
		await curMessage.reply("API failed or timed out.")
		return

	if not firstApiGot['success']:
		await curMessage.reply("API failed, are you sure those players exist?")
		return

	secondApiUrl = f"https://pitpanda.rocks/api/friends/{secondPlayerUuid}?key={pitPandaApiKey}"
	try:
		secondApiGot = requestsGet(secondApiUrl, timeout = 10, cacheMinutes = 60)
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

async def commandScammerCheck(curMessage):
	await curMessage.reply(f"temporarily disabled\ncheck at https://pitpanda.rocks/players/{curMessage.content.lower().split()[1]}")
	return

	curMessageSplit = curMessage.content.lower().split()

	curMessageSplitLen = len(curMessageSplit)

	if curMessageSplitLen != 2:
		await postCommandHelpMessage(curMessage, commandScammerCheck)

	targetIdentity = curMessageSplit[1]

	apiUrl = f"https://pitpanda.rocks/api/players/{targetIdentity}?key={pitPandaApiKey}"
	try:
		apiGot = requestsGet(apiUrl, timeout = 10, cacheMinutes = 1)
	except:
		print(f'	failed to get api {apiUrl}')
		await curMessage.reply("API failed or timed out.")
		return

	if not apiGot['success']:
		await curMessage.reply("API failed, are you sure that player exists?")
		return

	targetUuid = getVal(apiGot, ['data', 'uuid'])

	tagType = getVal(apiGot, ['data', 'doc', 'flag', 'type'])
	if tagType != "scammer":
		replyEmbed = discord.Embed(title = "", color = discord.Color.red())
		replyEmbed.add_field(name = f"Not scammer", value = "Not tagged as scammer.")
		replyEmbed.set_thumbnail(url = f"https://crafatar.com/avatars/{targetUuid}")

		await curMessage.reply('', embed = replyEmbed)
		return

	scammerNotes = getVal(apiGot, ['data', 'doc', 'flag', 'notes'])

	replyEmbed = discord.Embed(title = "", color = discord.Color.red())
	replyEmbed.add_field(name = "SCAMMER", value = f"Notes: {scammerNotes}")
	replyEmbed.set_thumbnail(url = f"https://crafatar.com/avatars/{targetUuid}")

	await curMessage.reply('', embed = replyEmbed)

async def commandEvents(curMessage):
	apiUrl = "https://events.mcpqndq.dev/"
	try:
		apiGot = requestsGet(apiUrl, timeout = 10, cacheMinutes = 0)
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

# other

async def indexKosPlayer(theBot):
	curTime = time.time()
	curMinute = int(curTime / 60)

	if curMinute > kosData["finishedIndexingMinute"]:
		if kosData["atUuid"] > len(list(kosData['uuidsDict'].keys())) - 1:
			kosData["atUuid"] = 0
			kosData["finishedIndexingMinute"] = curMinute
		kosUuid = list(kosData["uuidsDict"].keys())[kosData["atUuid"]]
		kosData["atUuid"] += 1

		if kosUuid not in playerData:
			playerData[kosUuid] = {}

		print(f"indexing kos player {kosUuid}")

		apiUrl = f"https://api.hypixel.net/player?key={hypixelApiKey}&uuid={kosUuid}"
		try:
			apiGot = requestsGet(apiUrl, timeout = 10, cacheMinutes = 0)
		except:
			print(f'	failed to get api {apiUrl}')
			return

		# calculate difference in number of kills

		playerKills = getVal(apiGot, ['player', 'stats', 'Pit', 'pit_stats_ptl', 'kills'])
		if playerKills == None:
			print('	no player kills data found')
			return
		playerKillsOld = getVal(playerData, [kosUuid, "kills"])
		if playerKillsOld == None:
			playerKillsOld = playerKills
		playerData[kosUuid]["kills"] = playerKills

		killDiff = playerKills - playerKillsOld

		# calculate difference in number of assists

		playerAssists = getVal(apiGot, ['player', 'stats', 'Pit', 'pit_stats_ptl', 'assists'])
		if playerAssists == None:
			print('	no player assists data found')
			return
		playerAssistsOld = getVal(playerData, [kosUuid, "assists"])
		if playerAssistsOld == None:
			playerAssistsOld = playerAssists
		playerData[kosUuid]["assists"] = playerAssists

		assistDiff = playerAssists - playerAssistsOld

		if killDiff == 0 or assistDiff == 0:
			print('	player has not gained any kills nor assists')
			return

		# calculate current bounty

		playerBounties = getVal(apiGot, ['player', 'stats', 'Pit', 'profile', 'bounties'])
		playerBounty = 0
		if playerBounties != None:
			for curBounty in playerBounties:
				playerBounty += curBounty['amount']

		if playerBounty == 0:
			print('	player has no bounty')
			return

		kosUsername = getUsernameFromUuid(kosUuid)
		playerCurrentMegaStreak = getVal(apiGot, ['player', 'stats', 'Pit', 'profile', 'selected_megastreak_except_uber'])
		megaStreakNames = {'grand_finale': 'Grand Finale', 'hermit': 'Hermit', 'to_the_moon': 'To The Moon', 'highlander': 'Highlander', 'beastmode': 'Beastmode', 'overdrive': 'Overdrive'}
		if playerCurrentMegaStreak == None:
			playerCurrentMegaStreak = "unknown"
		if playerCurrentMegaStreak in megaStreakNames:
			playerCurrentMegaStreak = megaStreakNames[playerCurrentMegaStreak]

		print(f'	player streaking on {playerCurrentMegaStreak} +{killDiff} kills +{assistDiff} assists')

		for guildId in kosData["uuidsDict"][kosUuid]:
			print(f'		finding channel for {guildId}')
			for curChannel in theBot.get_guild(guildId).text_channels:
				if curChannel.name.lower() == "kos":

					print(f'		sending kos msg to guild {guildId}')

					kosEmbed = discord.Embed(title = "", color = discord.Color.red())
					kosEmbed.add_field(name = f"{kosUsername}", value = f"Bounty: {playerBounty}g\nMega: {playerCurrentMegaStreak}\n+{killDiff} kills +{assistDiff} assists\n**USE http://www.jojo.boats/kos - DISCORD KOS SYSTEM WILL BE DISCONTINUED.**")

					kosEmbed.set_thumbnail(url = f"https://crafatar.com/avatars/{kosUuid}")

					await curChannel.send("", embed = kosEmbed)
	else:
		pass # finished minute's worth of indexing

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
	`.kos add username`
	Add a player to the KOS list.
	Requires a staff-level Discord permission to use (manage channels, ban members etc.)
	Requires 5 total members in the server for usage.

	`.kos remove username`
	Remove a player from the KOS list.
	Requires a staff-level Discord permission to use (manage channels, ban members etc.)

	`.kos list`
	Show the current KOS player list.

	Allowed 5 players on KOS list per server.
	Requires a channel called exactly `#kos` to send KOS messages to.

	**USE http://www.jojo.boats/kos - DISCORD KOS SYSTEM WILL BE DISCONTINUED.**
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

	helpMessages[commandMutuals] = """
	`.mutuals player1 player2`

	Finds mutual Hypixel friends of two players.
	"""

	helpMessages[commandScammerCheck] = """
	`.sc username`

	Check if a player is tagged as a scammer using data from Pit Panda.
	"""

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

	**.scammercheck**
	Check if a player is scammer tagged by Pit Panda.

	**.itemsearch**
	Search for a mystic using Pit Panda data.

	**.boatssearch**
	Search for any item (*any*) using jojo.boats data. Includes regs, darks, etc.


	**Add me to your server by clicking my profile and then "Add to Server".**
	**Code at https://github.com/jojo259/discord-hypixel-pit-abyss-bot**
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
			print(f'in guild with {guild.member_count} members named {guild.name}')
			await guild.me.edit(nick = "Abyss Bot") # bot tries to reset nickname, doesn't matter if it can't

		await theBot.change_presence(activity = discord.Game(".help"))

		if not debugMode:
			theBot.biSecondlyTask.start()

	@tasks.loop(seconds=0.5)
	async def biSecondlyTask(theBot):
		try:
			await indexKosPlayer(theBot)
		except Exception as e:
			print(f'indexing failed: {e}')

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

			noParamCommands = [commandEvents]

			if len(curMessageSplit) == 1 and curMessageCommandFunc not in noParamCommands:
				await postCommandHelpMessage(curMessage, curMessageCommandFunc)
				return

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

commandsList["sc"] = commandScammerCheck
commandsList["scam"] = commandScammerCheck
commandsList["scammer"] = commandScammerCheck
commandsList["scammercheck"] = commandScammerCheck
commandsList["checkscammer"] = commandScammerCheck
commandsList["checksscammer"] = commandScammerCheck

commandsList["ev"] = commandEvents
commandsList["events"] = commandEvents

reloadServerData()

intents = discord.Intents.default()
intents.message_content = True
botClass = botClass(intents = intents)
botClass.run(botToken)