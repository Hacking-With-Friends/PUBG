import ssl, json
from socket import *
from urllib.parse import urlencode, quote_plus
from select import epoll, EPOLLIN, EPOLLHUP

api_key = ""

placement_score = {
	1: 300,
	2: 150,
	3: 100,
	4: 75,
	5: 60,
	6: 50,
	7: 40,
	8: 30,
	9: 20,
	10: 10
}

base_killscore = 10
base_killmultiplier = 1

# account.c5afe..bbeb #DeathDeler

# https://api.pubg.com/shards/$platform/players?filter[playerNames]=$playerName

def request(url, options={}):
	s = socket()

	#if len(options):
	#	url += '?'
	#	for key, val in options.items():
	#		url += quote_plus(key) + '=' + quote_plus(val) + '&'
	#	url = url[:-1]

	print(url)
	hostname = 'api.pubg.com'
	context = ssl.create_default_context()

	with create_connection((hostname, 443)) as sock:
		with context.wrap_socket(sock, server_hostname=hostname) as s:
			poller = epoll()
			poller.register(s.fileno(), EPOLLIN | EPOLLHUP)


			r = f'GET {url} HTTP/1.1\r\n'
			r += f'Host: {hostname}\r\n'
			r += f'Authorization: Bearer {api_key}\r\n'
			r += 'Accept: application/vnd.api+json\r\n'
			r += '\r\n'

			s.send(bytes(r, 'UTF-8'))
			response = b''
			alive = True
			got_first = False
			while alive or got_first is False:
				alive = False
				for fileno, event in poller.poll(0.25):
					got_first = True
					alive = True
					data = s.recv(8192)
					if len(data) <= 0:
						alive = False
						break
					response += data

			headers = {}
			code = 0
			header, response = response.split(b'\r\n\r\n', 1)
			for index, item in enumerate(header.split(b'\r\n')):
				if index == 0:
					_, code, _ = item.split(b' ', 2)
					code = int(code)
				else:
					key, val = item.split(b':', 1)
					headers[key.decode('UTF-8').lower().strip()] = val.decode('UTF-8').strip()

			if 'transfer-encoding' in headers and headers['transfer-encoding'] == 'chunked':
				tmp = response
				block = b''
				data = b''
				while b'\r\n' in tmp:
					length, block = tmp.split(b'\r\n',1)
					if length == b'' and block == b'0\r\n\r\n':
						break

					try:
						if int(length, 16) > len(block):
							print('[Error] Parsing length issue: {} vs reality {}'.format(int(length, 16), len(block)))
							exit(1)
					except:
						print('Error@78:', length, block[:30])
						exit(1)

					#print(block)
					#print(block[:int(length, 16)])
					data += block[:int(length, 16)]
					#print(tmp[:20], '---', block[-10:])
					tmp = tmp[int(length, 16)+len(length)+4:]

				#print(data)
				return code, headers, data
			else:
				return code, headers, response

def getMatch(gid, mode=None, custom=False):
	code, headers, response = request(f'/shards/pc-eu/matches/{gid}')
#	print(json.dumps(headers, indent=4, sort_keys=True))
	with open('test.bin', 'wb') as fh:
		fh.write(response)

	data = json.loads(response)
	with open(f'./games/{gid}.json', 'w') as fh:
		fh.write(json.dumps(data, indent=4, sort_keys=True))

	if mode:
		if not mode in data['data']['attributes']['gameMode']:
			print(f'[Notice] Game {gid} did not match a {mode} game')
			return None

	if custom:
		if not data['data']['attributes']['isCustomMatch']:
			print(f'[Notice] Game {gid} is not a custom game.')
			return None

	return data

def parse_leaderboard(game_data):
	if not game_data: return None, None
	#print(json.dumps(game_data['included'], indent=4, sort_keys=True))
	players = {}
	teams = {}
	for player in game_data['included']:
#		try:
		if player['type'] == 'participant':
			players[player['id']] = player
			#print('Name: {}, Kills: {}, Placement: {}'.format(player['attributes']['stats']['name'],
			#												  player['attributes']['stats']['kills'],
			#												  player['attributes']['stats']['winPlace']))
		elif player['type'] == 'roster':
			teams[player['id']] = player
#		except:
#			print(json.dumps(player, indent=4, sort_keys=True))
#			exit(1)

	return players, teams

code, headers, response = request(f'/shards/pc-eu/players?filter[playerNames]=DeathDeler')
data = json.loads(response)

#{'type': 'match', 'id': '1f04e9db-968a-4179-9358-15a37370d5fc'}
#{'type': 'match', 'id': 'b5ccec6d-976e-4099-842d-24b278123736'}
#{'type': 'match', 'id': '2daaf7f1-6d92-4ef7-83f7-4fa2dae70b56'}
#{'type': 'match', 'id': '1024424a-7487-4387-94b8-b00b38da9606'}
for match in data['data'][0]['relationships']['matches']['data']:
	#getMatch(match['id'])
	match_data = getMatch(match['id'], mode='duo')

	players, teams = parse_leaderboard(match_data)#, custom=True))
	if not players or not teams:
		print(f' - {match["id"]}: Skipped...')
		continue

	with open(f'./stats/{match["id"]}.csv', 'w') as score:
		for team_id, team in teams.items():
			new_struct = []
			team_score = {'kills' : 0, 'winPlace' : 0, 'points' : 0}
			for player in team['relationships']['participants']['data']:
				if not player['id'] in players:
					print('[Error] Malformed player struct')

				team_score['kills'] += players[player['id']]['attributes']['stats']['kills']
				team_score['winPlace'] = players[player['id']]['attributes']['stats']['winPlace']
				new_struct.append(players[player['id']])

			team['relationships']['participants']['data'] = new_struct
			base_killscore
			if team_score['winPlace'] in placement_score:
				team_score['points'] += placement_score[team_score['winPlace']]
			if team_score['kills']:
				final_score = 0
				worth = base_killscore
				for i in range(team_score['kills']):
					final_score += worth
					worth += base_killmultiplier

				team_score['points'] += final_score
			team['ninjat_score'] = team_score

			tmp = team['relationships']['participants']['data']
			if len(tmp) == 1:
				tmp_players = [tmp[0]['attributes']['stats']['name']]
			else:
				tmp_players = [tmp[0]['attributes']['stats']['name'], tmp[1]['attributes']['stats']['name']]
			print('Team {} scored {} kills and {} placement. ({}).'.format(team_id,
						team['ninjat_score']['kills'],
						team['ninjat_score']['winPlace'],
						' & '.join(tmp_players)))

			score.write('{},{},{},{},{},{},{}\r\n'.format(match_data['data']['attributes']['createdAt'],
												match_data['data']['attributes']['titleId'],
												team_id,
												team['ninjat_score']['kills'],
												team['ninjat_score']['winPlace'],
												team['ninjat_score']['points'],
												' & '.join(sorted(tmp_players))))

#	print(json.dumps(teams, indent=4, sort_keys=True))
	#parse_leaderboard(getMatch('1a1033c4-dfb1-48ad-aa79-0e5610ac1098'))
	exit(1)

#print(json.dumps(, indent=4, sort_keys=True))
#print(json.dumps(data['data'][0]['relationships']['matches'], indent=4, sort_keys=True))
