# encoding: utf-8
#
# TODO: maggiore astrazione
#       sulle operazioni con lambda function,
#       aggiungere controllo rate limit su ogni api call, caching del
#       rate limit, gestire l'eventuale doppia esecuzione.
#       Scegliere in
#       modo dinamico il  numero di followers da analizzare
#

from twython import Twython
from twython import (
        TwythonError, TwythonRateLimitError, TwythonAuthError
)
import Queue
import os
import threading
import time
import sys
import optparse, os, random, re
from requests import *
from gexf import *

t_inattesa = Queue.Queue()
coda_account = Queue.Queue()
t_inesecuzione = Queue.Queue()
t_terminati = Queue.Queue()

lista_followers_target = []

class MinerThreads(threading.Thread):
	'''
	os.chdir IS THREAD UNSAFE
	devo usare path assolute
	'''
	def __init__(self, lock, target,operation, path, arcobaleno):
		'''
		arcobaleno indica se sto lavorando con ids (0) o screen_name (1)
		'''
		threading.Thread.__init__(self)
		self.lock = lock
		self.target = target.strip('\n')
		self.cursore_path = 'cursore_'+self.target+'.txt'
		self.my_path = path
		self.origin = str(os.getcwd())
		self.twitter = None
		self.hoatteso = False
		self.operation = operation
		self.arcobaleno = arcobaleno
	def __get_twython(self):
		global coda_account
		acc = coda_account.get()
		return acc
	def __put_twython(self):
		global coda_account
		coda_account.put(self.twitter)
	'''
	Introdurre caching rate limit !!!!!
	'''
	def __check_us_limit(self):
		'''
			controlla le soglie del limit rate delle api
			non controllo le soglie relative alla richiesta stessa
			idi rate limit
			Twitter API returned a 503 (Service Unavailable), Over capacity
		'''
		try:
			rate = self.twitter.get_rate_limit()
		except TwythonError,e:
			print 'twython error2'+str(e)
			return -1
		except ConnectionError,e:
			print '\t connection error'
			return -1
		except:
			print "Unexpected error:", sys.exc_info()[0]
			raise
		limit = rate['resources']['users']['/users/show']['remaining']
		print self.name+' il limite users/show e: ' + str(limit)+' '+str(self.target)+' twitter vale: '+ str(self.twitter.get_authorized_tokens)
		return limit
	def __check_f_limit(self):
		'''
		controlla le soglie del limit rate delle api
		non controllo le soglie relative alla richiesta stessa
		di rate limit
		Twitter API returned a 503 (Service Unavailable), Over capacity
		'''
		try:
			rate = self.twitter.get_rate_limit()
		except TwythonError,e:
			print 'twython error2'+str(e)
			return -1
		except ConnectionError,e:
			print '\t connection error'
			return -1
		except:
			print "Unexpected error:", sys.exc_info()[0]
			raise
		limit = rate['resources']['followers']['/followers/ids']['remaining']
		print self.name+' il limite e: ' + str(limit)+' '+str(self.target)+' twitter vale: '+ str(self.twitter.get_authorized_tokens)
		return limit
	def __salva_dati(self, data, flag, objtarget):
		if not flag:
			if objtarget == 'friends':
				follopath = self.origin+'/friends_'+self.target+'.txt'
			elif objtarget == 'followers':
				follopath = self.origin+'/followers_'+self.target+'.txt'
			try:
				fpout = open(follopath, 'a')
			except IOError, e:
				print 'ASD2 '+str(follpath)+' '+str(e)
				return
			for ids in data['ids']:
				lista_followers_target.append(ids)
				fpout.write("%s\n" % str(ids)) #aggiunge un newline di troppo..
		else:
			if objtarget == 'followers':
				follopath = self.origin+'/followers/'+self.target+'/followers_'+self.target+'.txt'
			elif objtarget == 'friends':
				follopath = self.origin+'/followers/'+self.target+'/friends_'+self.target+'.txt'
			try:
				fpout = open(follopath, 'a')
			except:
				print 'ASD4 '+str(follopath)
				return
			for ids in data['ids']:
				fpout.write("%s\n" % str(ids)) #aggiunge un newline di troppo..
		fpout.flush()
		fpout.close()
	def __salva_user_info(self):
		'''
		TODO: Controllo se le info sono già state scaricate, nel caso
		return
		'''
		data = ''
		info = None
		try:
			if self.arcobaleno == 0:
				infopath = self.origin+'/followers/'+self.target
				if os.path.exists(infopath): return
				os.mkdir(infopath)
				infopath += '/user_info_'+self.target+'.txt'
			else:
				infopath = self.origin+'/user_info_'+self.target+'.txt'
				if os.path.exists(infopath): return
		except OSError, e:
			print '\terrore salva info mkdir '+str(e)+' target:'+self.target+' ' +os.getcwd()
		fpout = open(infopath,'a')
		while True:
			hodormito = False
			try:
				'''
				limite = self.__check_us_limit()
				if limite == 0 or limite == -1:
					self.__dormi(0, flag)
				'''
				if int(self.arcobaleno) == 0:
					info = self.twitter.show_user(user_id=self.target,include_entities='0')
				else:
					info = self.twitter.show_user(screen_name=self.target,include_entities='0')
			except TwythonError, e:
				print ' target '+self.target+' errore retrive user info '+str(e)
				print ' magia: '+str(self.arcobaleno)
				hodormito = True
				self.__dormi(0,False)
			except ConnectionError, e:
				print 'connection error '+str(e)
				hodormito= True
				self.__dormi(0, False)
			if not hodormito:
				for key in info.keys():
					if isinstance(info[key], str):
						data += key + ':' + unicode(info[key], 'utf-8') + '\n'
					elif isinstance(info[key], unicode):
						data += key + ':' + info[key] + '\n'
					else:
						data += key + ':' + str(info[key]) + '\n'
				break
		fpout.write(data.encode('utf-8'))
		fpout.flush()
		fpout.close()
	def __check_cursore(self, flag):
		if flag: cursorpath  = self.origin+'/followers/cursore_'+self.target+'.txt'
		else: cursorpath = self.origin+'/cursore_'+self.target+'.txt'
		'''
		se il file del cursore esiste
		prende il valore e lo usa come nextcursor,
		altrimenti -1
		'''
		try:
			with open(cursorpath, 'r') as fp:
				ret = str(fp.readline())
		except IOError, e:
			return -1
		fp.close()
		return ret
	def __salva_cursore(self, cursore, flag):
		if flag: cursorpath = self.origin+'/followers/'+self.target+'/cursore_'+self.target+'.txt'
		else: cursorpath = self.origin+'/cursore_'+self.target+'.txt'
#		print '\t SALVA CURSORE IN: '+cursorpath+' valore: '+str(cursore)
		'''
		Scrive il next_cursor su file
		I cursori vengono usati per verificare se sono stati prelevati tutti i
		follower e se uno specifico twitter id e' stato gia' analizzato
		'''
		try:
			cursor_file = open(cursorpath,'w')
		except:
			print '\t\t\tASD5'
			pass
		cursor_file.write(str(cursore))
		cursor_file.flush()
		cursor_file.close()
	def __dormi(self, cursore, flag):
		'''
		se sto prendendo le info di un utente non cursori da salvare
		'''
		if self.operation is not 'userinfo':
			print 'mi addormento con il cursore: '+str(cursore)
			self.__salva_cursore(cursore, flag)
		self.lock.acquire()
		t_inesecuzione.get(block=True)
		t_inattesa.put(self)
		t_inesecuzione.task_done()
		self.lock.release()
		print '\t '+self.name+' ANNUNCIAZIO buona notte, target: '+self.target+' attesa: '+str(t_inattesa.qsize())+' exec: '+str(t_inesecuzione.qsize())
		time.sleep(8*60)
		print '\t '+self.name+' ANNUNCIAZIO SONO SVEGLIO!! '+self.target+' attesa: '+str(t_inattesa.qsize())+' exec: '+str(t_inesecuzione.qsize())
		self.lock.acquire()
		t_inattesa.get(block=True)
		t_inesecuzione.put(self)
		t_inattesa.task_done()
		self.lock.release()
	def __controllo_target(self, objtarget):
		'''
		controllo se il target id non ha troppi followers
		'''
		userpath = self.origin+'/followers/'+self.target+'/user_info_'+self.target+'.txt'
		try:
			fpin = open(userpath,'r')
		except OSError, e:
			print 'PUTTANAZZA '+ str(e)
			return -1
		for line in fpin:
			line = line.strip('\n')
			if objtarget == 'followers':
				m = re.search('followers_count',line)
			elif objtarget == 'friends':
				m = re.search('friends_count', line)
			if m:
				key,val = line.split(':',1)
				if int(val) < 15000:
					return 1
		return 0
	def __my_write_error(self,data,flag):
		if not flag:
			errorpath = self.origin+'/errori_'+self.target+'.txt'
			try:
				fpout = open(errorpath, 'a')
			except:
				print 'ASD20'
				pass
			 #for ids in data['ids']:
#				fpout.write("%s\n" % str(ids)) #aggiunge un newline di troppo..
		else:
			errorpath = self.origin+'/followers/'+self.target+'/errori_'+self.target+'.txt'
			try:
				fpout = open(errorpath, 'a')
			except:
				print 'ASD40'
				pass
		fpout.write(data)
		fpout.write('\n')
		fpout.flush()
		fpout.close()
	def __get_friends(self, flag):
		'''
		TODO: 
		'''
		test = 1
		if flag: 
			possiblepath = self.origin+'/followers/'+self.target+'/friends_'+self.target+'.txt'
			if os.path.exists(possiblepath): return
			test = self.__controllo_target('friends')
		if test:
			nextcursor = self.__check_cursore(flag)
			while nextcursor is not 0:
				'''
				limite = self.__check_f_limit()
				if limite == 0 or limite == -1:
					self.__salva_cursore(nextcursor, flag)
					self.__dormi(nextcursor, flag)
					nextcursor = self.__check_cursore(flag)
					print 'dopo la dormitina rinizio con: '+str(nextcursor)
				else:
				'''
				if True:
					try:
						if self.arcobaleno == 0:
							data = self.twitter.get_friends_ids(user_id=self.target, cursor = nextcursor, count='5000', stringify_ids='true')
							nextcursor = data['next_cursor']
							self.__salva_dati(data, flag, 'friends')
						else:
							data = self.twitter.get_friends_ids(screen_name=self.target, cursor = nextcursor, count='5000', stringify_ids='true')
							nextcursor = data['next_cursor']
							self.__salva_dati(data, flag, 'friends')
					except TwythonRateLimitError, e:
						print self.name+' '+self.target+' get_followers twython RATELIMITERROR'+str(e)
						self.__my_write_error(str(e),flag)
						self.__dormi(nextcursor, flag)
						nextcursor=self.__check_cursore(flag)
					except TwythonError, e:
						''' qui non è un errore di rate limit
							es: errore 401
						'''
						print self.name+self.target+' get_friends twython error'+str(e)
						print str(e.error_code)
						self.__my_write_error(str(e),flag)
						#self.__dormi(nextcursor, flag)
						#nextcursor=self.__check_cursore(flag)
						break
					except ConnectionError, e:
						print 'get_friends cazzo cazzo iu iu'+str(e)
						self.__dormi(nextcursor,flag)
						nextcursor=self.__check_cursore(flag)
						#break
		else:
			print '\t AAAA target con troppi friends: '+self.target
			return
	def __get_followers(self, flag):
		'''
		flag False quando sto scaricando i followers del target, True
		quando sto scaricando i followers dei followers
		'''
		test = 1
		if flag: 
			possiblepath = self.origin+'/followers/'+self.target+'/followers_'+self.target+'.txt'
			if os.path.exists(possiblepath): return
			test = self.__controllo_target('followers')
		if test:
			nextcursor = self.__check_cursore(flag)
			while nextcursor is not 0:
#				print 'NEXTCURSOR VALE: '+str(nextcursor)
				limite = self.__check_f_limit()
				'''
				if limite == 0 or limite == -1:
					self.__salva_cursore(nextcursor, flag)
					self.__dormi(nextcursor, flag)
					nextcursor = self.__check_cursore(flag)
					print 'dopo la dormitina rinizio con: '+str(nextcursor)
				else:
				'''
				if True:
					try:
						if self.arcobaleno == 0:
							data = self.twitter.get_followers_ids(user_id=self.target, cursor = nextcursor)
							nextcursor = data['next_cursor']
							self.__salva_dati(data, flag, 'followers')
						else:
							data = self.twitter.get_followers_ids(screen_name=self.target, cursor = nextcursor)
							nextcursor = data['next_cursor']
							self.__salva_dati(data, flag, 'followers')
					except TwythonRateLimitError, e:
						print self.name+' '+self.target+' get_followers twython RATELIMITERROR'+str(e)
						self.__my_write_error(str(e),flag)
						#if not flag:
						#	self.__salva_cursore(nextcursor, flag)
						#	return
						self.__dormi(nextcursor, flag)
						nextcursor=self.__check_cursore(flag)
						print 'mi sono svegliato e il cursore vale: '+str(nextcursor)
					except TwythonError, e:
						print self.name+' '+self.target+' get_followers twythonerror '+str(e)
						self.__my_write_error(str(e),flag)
						#self.__dormi(nextcursor, flag)
						#nextcursor=self.__check_cursore(flag)
						#print 'mi sono svegliato e il cursore vale: '+str(nextcursor)
						break
					except ConnectionError, e:
						print 'cazzo cazzo iu iu'+str(e)
						self.__dormi(nextcursor,flag)
						nextcursor=self.__check_cursore(flag)
						print 'mi sono svegliato e il cursore vale: '+str(nextcursor)
						#break
					#nextcursor = data['next_cursor']
#					print 'NEXTCURSOR VALE: '+str(nextcursor)
		else:
			print '\t AAAA target con troppi followers: '+self.target
			return
	def __undirected_graph_helper(self):
		usepath = os.getcwd()
#		listdirs = os.listdirs(os.getcwd())
		seta = setb = None
		try:
			fp_a = open(usepath+'/'+self.target+'/'+'followers_'+self.target+'.txt', 'r')
		except IOError, e:
			print 'UNDIRECTED ERRORE FOLLOWERS: '+str(e)
			print usepath+'/'+self.target+'/'+'followers_'+self.target+'.txt'
			return
		try:
			fp_b = open(usepath+'/'+self.target+'/'+'friends_'+self.target+'.txt', 'r')
		except IOError, e:
			print 'UNDIRECTED ERRORE FRIENDS: '+str(e)
			print usepath+'/'+self.target+'/'+'friends_'+self.target+'.txt'
			return
		seta = set(fp_a.readlines())
		setb = set(fp_b.readlines())
		setc = seta & setb
		fpout = open(usepath+'/'+self.target+'/'+'undirected_'+self.target+'.txt', 'a')
		for item in setc:
			fpout.write(str(item))
		fp_a.close()
		fp_b.close()
		fpout.close()
	def run(self):
		global t_attesa, t_inesecuzione, coda_account
		t_terminati.get(block=True)
		self.twitter = self.__get_twython()
		while True:
			if self.operation == 'followers':
				usepath = os.path.abspath(os.getcwd())
				self.__get_followers(False)
				print 'ricevuta lista followers del target!'
				break
			elif self.operation == 'userinfo':
				self.__salva_user_info()
				break
			elif self.operation == 'followersandfriends':
#				print '\t RECUPERO LISTA FOLLOWERS'
				self.__get_followers(True)
#				print '\t RECUPERO LISTA FRIENDS'
				self.__get_friends(True)
				break
			elif self.operation == 'undirectedgraph':
				self.__undirected_graph_helper()
				break
		self.__put_twython()
		t_inesecuzione.get(block=True)
		t_inesecuzione.task_done()
		t_terminati.task_done()
		print '\t THREAD '+self.name+' TERMINATO con target: '+self.target

class GestoreThreads:
	def __init__(self, operation, lista, arcobaleno, num, lenacc):
		self.operation = operation
		self.lista = lista
		self.arcobaleno = arcobaleno
		self.lenlista = len(self.lista)
		self.num = num
		self.lock = threading.Lock()
		self.lenacc = lenacc
		self.lista_threads = []
	
	def set_lenlista(self, lenlista):
		self.lenlista = lenlista

	def set_operation(self, operation):
		self.operation = operation
	
	def set_arcobaleno(self, arcobaleno):
		self.arcobaleno = arcobaleno
	
	def set_lista(self,lista):
		self.lista = lista

	def set_num(self,num):
		self.num = num

	def set_lenacc(self,lenacc):
		self.lenacc = lenacc

	def __thread_mancanti(self,num,num_threads):
		if num < num_threads:
			return num
		elif num >= num_threads:
			return num-num_threads

	def __crea_threads(self, tnum, lista, xxx, target):
		'''
		xxx è self.arcobaleno dei threads
		'''
		if len(lista) == 0:
			for i in range(tnum):
				t = MinerThreads(self.lock, target, self.operation, os.getcwd(),xxx)
				self.lista_threads.append(t)
		else:
			for i in range(tnum):
				t = MinerThreads(self.lock, lista.pop(), self.operation, os.getcwd(),xxx)
				self.lista_threads.append(t)
	def lancia_thread(self, target):

			self.__crea_threads(1, self.lista, 1, target)
			th = self.lista_threads.pop()
			t_inesecuzione.put(th)
			t_terminati.put(th)
			th.setDaemon(True)
			th.start()
			t_terminati.join()

	def lancia_threads(self):
		num_threads = 0
		while True:
			self.lock.acquire()
			print '\t NUMTHREAD: '+str(num_threads)
			print '\t ITEM INIZIALI: '+str(self.lenlista)
			print '\t ITEM MANCANTI: '+str(len(self.lista))
			print '\t #TERMINAZIONE THREAD '+str(t_terminati.qsize())
			print '\t #THREAD IN ATTESA: '+str(t_inattesa.qsize())
			if t_inattesa.qsize() == self.lenacc:
				print '\t aspetto tutti i thread in attesa'
				self.lock.release()
				t_inattesa.join()
				self.lock.acquire()
			total = t_inattesa.qsize() + t_inesecuzione.qsize()
			mancanti = self.__thread_mancanti(len(self.lista), num_threads)
			if mancanti < self.lenacc:
				if mancanti > (self.lenacc-total):
					corse = self.lenacc-total
				else:
					corse = mancanti
			else:
				corse = self.lenacc-total
			print '\t creo %s corse!' % corse
			for corsa in range(corse):
				self.__crea_threads(1, [self.lista.pop() for x in range(1)], 0, 0) #qui il target non conta
				num_threads += 1
			for x in range(len(self.lista_threads)):
				th = self.lista_threads.pop()
				t_inesecuzione.put(th)
				t_terminati.put(th)
				th.setDaemon(True)
				th.start()
			self.lock.release()
			print 'scarica info user aspetto terminazione thread'
			t_inesecuzione.join()
			if num_threads >= self.lenlista:
				break
		print '\t FINE FINE aspetto eventuali thread appesi'
		t_terminati.join()

class TwitterMiner:
	def __init__(self,target, accounts):
		self.target = target
		self.accounts = accounts
		self.lista_threads = []
		self.__makeTwythonObj()
		self.gthreads = GestoreThreads(None,[],None, None, len(self.accounts))
	def __set_target(self,target):
		self.target = target
	def __makeTwythonObj(self):
		global coda_account
		for i in range(len(self.accounts)):
			coda_account.put(Twython(self.accounts[i][0], self.accounts[i][1],
            self.accounts[i][2],
            self.accounts[i][3],
            headers={'User-Agent':'__twython_Test'}) )
	def __parser_info(self, dest):
		myinfo = ['verified', 'default_profile', 'geo', 'geo_enabled',
		'followers_count', 'friends_count', 'screen_name', 'id']
		'''
		parsifico le informazioni dell'utente
		per inserirle come attributi nel grafo
		Info che mi servono:
		u'verified'
		u'default_profile_image'
		u'followers_count'
		u'created_at'
		u'coordinates'
		u'geo'
		u'friends_count'
		u'location'
		u'geo_enabled'
		'''
		try:
			fp_info = open('user_info_'+dest+'.txt','r')
			for line in fp_info:
				line = line.strip('\n')
				for i in myinfo:
					m = re.search(i+':',line)
					if m:
						line = line.strip(' ')
						key, val = line.split(':',1)
						yield key, val
			fp_info.close()
		except IOError,e:
			print '\t azz '+dest+' '+str(e)
			yield -1,-1
	def __gexf_itera_nodo(self):
		pass
	def __genera_gexf(self, target, output_file):
		global lista_followers_target
		'''
		genero il grafo indiretto in formato gexf
		i nodi rappresentano gli utenti twitter
		ogni nodo possiede gli attributi estratti dalle info dell'utente
		TODO: salvare i nodi con ids sempre!! aggiungere tutti i
		followers del target 
		'''
		self.__set_target(target)
		counter = 0
		local_path = os.getcwd()
		os.chdir('../')
		fp_out = open(output_file,'w')
		tweet = dict(self.__parser_info(self.target))
		os.chdir(local_path)
		gexf = Gexf("Valerio Costamagna","Grafo dei followers_counters di un dato utente")
		graph=gexf.addGraph("undirected","static","complex network graph")
		idAttInDegree=graph.addNodeAttribute("T-In-Degree","-1","integer")
		idAttOutDegree=graph.addNodeAttribute("T-Out-Degree","-1","integer")
		idAttDegree=graph.addNodeAttribute("T-Degree","-1","integer")
		idAttName=graph.addNodeAttribute("screen_name","None","string")
		idAttVerified=graph.addNodeAttribute("verified","false","boolean")
		idAttDefault=graph.addNodeAttribute("default_profile","false","boolean")
		idAttGeo=graph.addNodeAttribute("geo_enabled","false","boolean")
		idAttPriv=graph.addNodeAttribute("private","false","boolean")
		idAttFiglio=graph.addNodeAttribute("figlio","false","boolean")
		#n = graph.addNode(self.target,tweet['screen_name'].strip())
		'''
		aggiungo il nodo rappresentante il target
		'''
		n = graph.addNode(tweet['id'].strip('\n'),tweet['id'].strip('\n'))
#		print 'cerco gli amici dei followers del target, che sono: '+str(len(lista_followers_target))
		listdirs = os.listdir(os.getcwd())
#		print 'len listdir: '+str(len(listdirs))
		'''
		for node in lista_followers_target:
			node = str(node)
			if node not in listdirs:
				node.strip('\n')
				graph.addNode(node, node)
				graph.addEdge(counter, node, tweet['id'])
				counter += 1
		'''
#		print 'aggiunti tutti i followers del target'
		n.addAttribute(idAttInDegree,str(int(tweet['followers_count'])))
		n.addAttribute(idAttOutDegree,str(int(tweet['friends_count'])))
		n.addAttribute(idAttDegree,str(int(tweet['friends_count'].strip('\n'))+int(tweet['followers_count'].strip('\n'))))
		n.addAttribute(idAttName,str(tweet['screen_name']))
		self.__call_undirected_graph_helper(os.listdir(os.getcwd()))
		print 'analizzo i friends dei followers del target'
		'''
		itero su ogni followers del target
		'''
		for adir in listdirs:
			adir = adir.strip('\n')
			os.chdir(adir)
			tweet2 = dict(self.__parser_info(adir))
			tweet2['screen_name'] = tweet2['screen_name'].strip('\n').strip()
#			n2 = graph.addNode(tweet2['screen_name'],tweet2['screen_name'])
			'''
			aggiungo il nodo rappresentate il follower del target
			'''
			n2 = graph.addNode(tweet2['id'].strip('\n'), tweet2['id'].strip('\n'))
			graph.addEdge(counter, tweet2['id'], tweet['id'] )
			counter += 1
			if not tweet2.has_key(-1):
				'''
				se sono disponibili gli attributi gli aggiungo al grafo
				'''
				n2.addAttribute(idAttInDegree,str(int(tweet2['followers_count'].strip('\n'))))
				n2.addAttribute(idAttOutDegree,str(int(tweet2['friends_count'].strip().strip('\n'))))
				n2.addAttribute(idAttDegree,str(int(tweet2['friends_count'].strip('\n'))+int(tweet2['followers_count'].strip('\n'))))
				n2.addAttribute(idAttGeo,tweet2['default_profile'].strip('\n').strip())
				n2.addAttribute(idAttVerified,tweet2['verified'].strip('\n').strip())
				n2.addAttribute(idAttDefault,tweet2['geo_enabled'].strip('\n').strip())
				tweet2['screen_name'] = tweet2['screen_name'].strip('\n').strip()
				n2.addAttribute(idAttName,tweet2['screen_name'])
				if not int(tweet2['friends_count']) > 15000:
					try:
						with open('undirected_'+str(adir)+'.txt','r') as fp2:
							'''
							itero per ogni FRIENDS del followers del
							target
							'''
							for line in fp2:
								line = line.strip()
								line = line.strip('\n')
								if not graph.nodeExists(line):
									n3 = graph.addNode(line,line)
									n3.addAttribute(idAttFiglio, 'True')
								graph.addEdge(counter, line,tweet2['id'])
								counter += 1
								'''
								Controllo se è nella lista dei followers
								del target
								'''
								if line in lista_followers_target:
									print 'aggiungo arco dal figlio del figlio al target'
									graph.addEdge(counter, line, tweet['id'] )
									counter += 1
								'''
								devo controllare se line è anche amico di
								altri nodi nel grafo, più precisamente
								se è amico di altre line. In quanto:
								- se fosse amico del target sarebbe stato
								  aggiunto al punto sopra
								- se fosse amico di altri followers del
								  target che sono stati analizzati
								  sarà aggiunto o è già stato aggiunto
								- rimane da controllare se è amico con
								  altri amici dei followers del target
								Per farlo devo scaricare followers,
								friends e user_info di ogni line
								'''
					except NameError, e:
						print '\t GEXF PUTTANA MADONNA BUCAIOLA'
						print os.getcwd()+' followers_'+str(adir)+'.txt'
						pass
					except IOError, e:
						pass
			else:
				print 'nodo senza attributi: '+ids
				n2.addAttribute(idAttPriv, 'True')
			os.chdir('../')
		gexf.write(fp_out)
		fp_out.close()
	def __call_undirected_graph_helper(self, lista):

		self.gthreads.set_operation('undirectedgraph')
		self.gthreads.set_lista(lista)
		self.gthreads.set_lenlista(len(lista))
		self.gthreads.set_arcobaleno(0)
		self.gthreads.set_num(1)
#		self.gthreads.set_lenacc(len(accounts))
		self.gthreads.lancia_threads()


		'''
		lenlista = len(lista)
		num_threads = 0
		maxthreads = 20

		self.__set_operation('undirectedgraph')
		while True:
			self.lock.acquire()
			print '\t IMPORTANTE UNDIRECTED'
			print '\t th in attesa: '+str(t_inattesa.qsize())
			print '\t th in exec: '+str(t_inesecuzione.qsize())
			total = t_inesecuzione.qsize()
			mancanti = self.__thread_mancanti(len(lista),num_threads)
			print '\t MANCANTI: '+str(mancanti)
			if mancanti < maxthreads:
				corse = mancanti
			else: corse = maxthreads
			print '\t NUMTHREAD: '+str(num_threads)
			print '\t len list: '+str(len(lista))
			print '\t #CORSE: '+str(corse)
			for i in range(corse):
				self.__crea_threads(1, [lista.pop() for x in range(1)], 0)
				num_threads += 1
			for y in range(len(self.lista_threads)):
				#print 'avvio un thread'
				th = self.lista_threads.pop()
				th.setDaemon(True)
				t_inesecuzione.put(th)
				t_terminati.put(th)
				th.start()
			print 'aspetto th in exec'
			self.lock.release()
			t_inesecuzione.join()
			print 'th in exec rientrati'
			if num_threads >= lenlista:
				break
		print '\t FUORI WHILE ASPETTO TERMINATI'
		t_terminati.join()
		print '\t THIS IS THE END'
		'''
	def __scegli_account_random(self, path, num):
		lista = []
		ret = []
		random.seed()
		try:
			fp = open(path, 'r')
		except IOError, e:
			print 'xxxxxxxxxxxxx '+str(e)
			print 'path: '+str(path)
			return -1
		lines = fp.readlines()
		for line in lines:
			lista.append(line)
		for i in range(num):
			index = random.randrange(len(lista))
			ret.append(lista.pop(index))
		fp.close()
		return ret
	def genera_gexf(self, target, output_file):
		print '\t DEBUG GENERA GEXF'
		try:
			os.chdir('followers')
		except OSError, e:
			print str(e)
		self.__genera_gexf(target,output_file)
	def scarica_followers(self):
		'''
		TODO: prendere prima le userinfo per verificare
		il numero di followers
		'''
		empty_list = []
		try:
			os.mkdir(self.target)
		except OSError, e:
			print 'Followers e User info del target già presenti '+str(e)
			if e.errno == 17:
				os.chdir(os.getcwd()+'/'+self.target)
				return
			return
		os.chdir(os.getcwd()+'/'+self.target)
		print 'sono dentro'
		self.gthreads.set_operation('followers')	
		self.gthreads.set_num(1)
		self.gthreads.set_lista(empty_list)
		self.gthreads.set_lenlista(0)
		self.gthreads.set_arcobaleno(1)
#		self.gthreads.set_lenacc(1)
		self.gthreads.lancia_thread(self.target)

		self.gthreads.set_operation('userinfo')	
		self.gthreads.set_num(1)
		self.gthreads.set_lista([self.target])
		self.gthreads.set_lenlista(1)
		self.gthreads.set_arcobaleno(1)
#		self.gthreads.set_lenacc(1)
		self.gthreads.lancia_thread(self.target)

	def scarica_followers_friends_of_user(self):
		'''
		anche qui devo ottimizzare con i thread
		come sotto.
		Per ogni dir in 'followers' scarica nella cartella dell utente
		la lista dei suoi followers e dei suoi friends
		TODO: scaricare lista friends
		'''
		start_path = os.getcwd()
		print 'followers and friends: '+os.getcwd()+' '+self.target
		ffpath = os.getcwd()+'/followers/'
		listdirs = os.listdir(ffpath)
		self.gthreads.set_operation('followersandfriends')
		self.gthreads.set_lista(listdirs)
		self.gthreads.set_lenlista(len(listdirs))
		self.gthreads.set_arcobaleno(0)
		self.gthreads.set_num(1)
#		self.gthreads.set_lenacc(len(self.accounts))
		self.gthreads.lancia_threads()
	def prepara_iterazione(self):
		localpath = os.getcwd()
		listdirs = os.listdir(os.getcwd()+'/followers/')
		for adir in listdirs:
			os.chdir(getcwd()+'/followers/'+adir)
			fpin = open('undirected_'+adir, 'r')
			os.mkdir('followers')
			os.chdir('followers')
			for line in fpin:
				self.__set_target(line)
				self.scarica_followers()
		os.chdir(localpath)


	def scarica_info(self, followers_path, num):
		'''
		TODO: scegliere il numero casuale di followers in proporzione al
		numero totale degli stessi.
		'''
		print 'inizio scarica info dei followers !!'
		start_path = os.getcwd()
		lista = self.__scegli_account_random(followers_path, num)
#		num = len(lista)
		fpdebug = open('DEBUG.log', 'a')
		for k in lista:
			fpdebug.write(str(k))
		fpdebug.close()
		try:
			os.mkdir('followers')
		except OSError, e:
			print '\t Scarica Info: Cartella followers esistente!!'
			return
		print '\t scarica_user_info DEBUG: '+str(len(lista))
		self.gthreads.set_operation('userinfo')
		self.gthreads.set_lista(lista)
		self.gthreads.set_lenlista(len(lista))
		self.gthreads.set_arcobaleno(0)
		self.gthreads.set_num(1)
#		self.gthreads.set_lenacc(len(self.accounts))
		self.gthreads.lancia_threads()

