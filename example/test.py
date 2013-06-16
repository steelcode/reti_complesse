import twitterminer
import random


accounts= [[],[]]
random.shuffle(accounts)

numero_account=len(accounts)

miner = twitterminer.TwitterMiner("XXXX", accounts)
miner.scarica_followers()

lista = miner.scarica_info('followers_XXXX.txt',1000)
miner.scarica_followers_friends_of_user()
miner.prepara_iterazione()
miner.genera_gexf('XXXX', 'prova_1000.gexf')

