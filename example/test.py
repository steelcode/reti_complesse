import twitterminer
import random


accounts = ['INSERT YOUR DATA HERE']
random.shuffle(accounts)

numero_account=len(accounts)

# create TwitterMiner Object with followers start operation
miner = twitterminer.TwitterMiner("TWITTER_SCREEN_NAME", accounts, 'followers')
miner.scarica_followers()

lista = miner.scarica_info('FOLLOWERS OUTPUT FILE','FOLLOWERS BOUND')
miner.scarica_followers_friends_of_user()
miner.genera_gexf('TWITTER_SCREEN_NAME', 'GEXF GRAPH OUTPUT FILE')

