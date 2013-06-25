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

#lista_followers_target = []
#lista_nodi_grafo = []
diz_followers_target = {}
diz_nodi_grafo = {}
counter = 0

'''
Classe che gestisce i thread minatori
'''
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
#		print self.name+' il limite users/show e: ' + str(limit)+' '+str(self.target)+' twitter vale: '+ str(self.twitter.get_authorized_tokens)
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
		print self.name+' il limite e: ' + str(limit)+ \
		' '+str(self.target)+ ' twitter vale: '+ str(self.twitter.get_authorized_tokens)
		return limit
	def __salva_dati(self, data, flag, objtarget):
		'''
		Salva i dati restituiti dalle api twitter
		'''
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
				#lista_followers_target.append(ids)
				diz_followers_target[ids] = ids
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
		Recupera e salva le user info del target
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
			cursor_file = open(cursorpath,'a')
		except:
			print '\t\t\tASD5'
			pass
		cursor_file.write(str(cursore))
#		cursor_file.flush()
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
		print '\t '+self.name+' ANNUNCIAZIO buona notte, target: ' + \
				self.target+' attesa: '+str(t_inattesa.qsize())+' exec: '+str(t_inesecuzione.qsize())
		time.sleep(8*60)
		print '\t '+self.name+' ANNUNCIAZIO SONO SVEGLIO!! ' \
				+self.target+' attesa: '+str(t_inattesa.qsize())+' exec: '+str(t_inesecuzione.qsize())
		self.lock.acquire()
		t_inattesa.get(block=True)
		t_inesecuzione.put(self)
		t_inattesa.task_done()
		self.lock.release()
	def __controllo_target(self, objtarget):
		'''
		controllo se il target id non ha troppi followers o friends
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
		'''
		handling degli errori
		'''
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
		Recupera la lista dei friends
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
							data = self.twitter.get_friends_ids(user_id=self.target,\
									cursor = nextcursor, count='5000', stringify_ids='true')
							nextcursor = data['next_cursor']
							self.__salva_dati(data, flag, 'friends')
						else:
							data = self.twitter.get_friends_ids(screen_name=self.target, \
									cursor = nextcursor, count='5000', \
									stringify_ids='true')
							nextcursor = data['next_cursor']
							self.__salva_dati(data, flag, 'friends')
					except TwythonRateLimitError, e:
						print self.name+' '+self.target+'get_friends twython RATELIMITERROR '+str(e)+ \
						' TWYTHON: '+ str(self.twitter.get_authorized_tokens)
						self.__my_write_error(str(e),flag)
						self.__dormi(nextcursor, flag)
						nextcursor=self.__check_cursore(flag)
					except TwythonError, e:
						''' qui non è un errore di rate limit
							es: errore 401
						'''
						print self.name+' '+self.target+' get_friends twython error'+str(e)
						print str(e.error_code)
						err = str(e)+' ' +str(self.name)+' ' \
						+str(self.target)
						self.__my_write_error(err,flag)
						return -1
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
		Recupera la lista dei followers
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
						print self.name+' '+self.target+' get_followers twython RATELIMITERROR '+str(e)+\
						' TWYTHON: '+ str(self.twitter.get_authorized_tokens)
						print 'chiamato con arcobaleno: '+str(self.arcobaleno)+ ' con target: '+self.target
						self.__my_write_error(str(e),flag)
						#if not flag:
						#	self.__salva_cursore(nextcursor, flag)
						#	return
						self.__dormi(nextcursor, flag)
						nextcursor=self.__check_cursore(flag)
						print 'mi sono svegliato e il cursore vale: '+str(nextcursor)
					except TwythonError, e:
						print self.name+' '+self.target+' get_followers twythonerror '+str(e)
						print 'chiamato con arcobaleno: '+str(self.arcobaleno)+ ' con target: '+self.target
						err = str(e)+' ' +str(self.name)+' ' \
						+str(self.target)
						self.__my_write_error(err,flag)
						return -1
						#self.__dormi(nextcursor, flag)
						#nextcursor=self.__check_cursore(flag)
						#print 'mi sono svegliato e il cursore vale: '+str(nextcursor)
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
	def run(self):
		'''
		Thread main
		'''
		global t_attesa, t_inesecuzione, coda_account
		t_terminati.get(block=True)
		self.twitter = self.__get_twython()
		while True:
			if self.operation == 'followers_target':
				usepath = os.path.abspath(os.getcwd())
				self.__get_followers(False)
				print 'ricevuta lista followers del target!'
				break
			elif self.operation == 'userinfo':
				self.__salva_user_info()
				break
			elif self.operation == 'followersandfriends':
#				print '\t RECUPERO LISTA FOLLOWERS'
				ret = self.__get_followers(True)
#				print '\t RECUPERO LISTA FRIENDS'
				if ret != -1: self.__get_friends(True)
				break
			'''
			elif self.operation == 'undirectedgraph':
				self.__undirected_graph_helper()
				break
			'''
		self.__put_twython()
		t_inesecuzione.get(block=True)
		t_inesecuzione.task_done()
		t_terminati.task_done()
#		print '\t THREAD '+self.name+' TERMINATO con target: '+self.target

class GestoreThreads:
	'''
	Gestisce l'esecuzione dei thread
	viene creato un thread per ogni account e gli viene assegnato un
	target
	'''
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
				t = MinerThreads(self.lock, str(target), self.operation, os.getcwd(),xxx)
				self.lista_threads.append(t)
		else:
			for i in range(tnum):
				t = MinerThreads(self.lock, lista.pop(), self.operation, os.getcwd(),xxx)
				self.lista_threads.append(t)
	def lancia_thread(self, target):
			self.__crea_threads(1, self.lista, self.arcobaleno, target)
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
			'''
			print '\t NUMTHREAD: '+str(num_threads)
			print '\t ITEM INIZIALI: '+str(self.lenlista)
			print '\t ITEM MANCANTI: '+str(len(self.lista))
			print '\t #TERMINAZIONE THREAD '+str(t_terminati.qsize())
			print '\t #THREAD IN ATTESA: '+str(t_inattesa.qsize())
			'''
			if t_inattesa.qsize() == self.lenacc:
				print '\t aspetto tutti i thread in attesa'
				self.lock.release()
				t_inattesa.join()
				self.lock.acquire()
			total = t_inattesa.qsize() + t_inesecuzione.qsize()
			mancanti = self.__thread_mancanti(self.lenlista, num_threads)
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
			print 'aspetto terminazione thread'
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
	def __get_target(self):
		return self.target
	def __makeTwythonObj(self):
		global coda_account
		for i in range(len(self.accounts)):
			coda_account.put(Twython(self.accounts[i][0], self.accounts[i][1],
            self.accounts[i][2],
            self.accounts[i][3],
            headers={'User-Agent':'__twython_Test'}) )
	def __parser_info(self, dest):
		myinfo = ['verified', 'default_profile', 'geo', 'geo_enabled',
		'followers_count', 'friends_count', 'screen_name', 'id', 'protected']

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
	
	def __aggiungi_att(self, nodo, idAtt, valoreAtt):
		nodo.addAttribute(idAtt,valoreAtt)
	def __aggiungi_arco(self, grafo, cont, source, target):
		try:
			grafo.addEdge(cont, source,target)
		except:
			print 'SOURCE: '+source+' TARGET: '+target
			print "Unexpected error:", sys.exc_info()[0]
			raise
	def __aggiungi_nodo(self, grafo, node):
		n3 = grafo.addNode(node,node)
		return n3

	def genera_gexf(self, target, output_file):
		idAtt = {'followers_count':['1', 'integer'], \
				'friends_count':['1','integer'], \
				'screen_name':['-1', 'string'], \
				'verified':['false', 'boolean'], \
				'default_profile':['false', 'boolean'],\
				'geo_enabled':['false', 'boolean'],\
				'protected':['false','boolean']
				}
		idItem = []
		print '\t DEBUG GENERA GEXF'
		startpath = os.getcwd()
		fp_out = open(output_file,'w')
		gexf = Gexf("Valerio Costamagna","Grafo dei followers_counters di un dato utente")
		graph=gexf.addGraph("undirected","static","complex network graph")
		for key in idAtt.keys():
			idItem.append(graph.addNodeAttribute(key, idAtt[key][0], \
			idAtt[key][1]))
		tweet = dict(self.__parser_info(self.target))
		n = self.__aggiungi_nodo(graph,tweet['id'].strip('\n'))
		lista = idAtt.items()
		for item in idItem:
			n.addAttribute(item, tweet[str(lista[int(item)][0])].strip().strip('\n'))
		idAttDegree=graph.addNodeAttribute("T-Degree","-1","integer")
		idAttFiglio=graph.addNodeAttribute("figlio","false","boolean")
		n.addAttribute(idAttDegree, \
				str(int(tweet['friends_count'].strip('\n'))+int(tweet['followers_count'].strip('\n'))))
		self.prova_ricorsiva_grafo(tweet['id'].strip('\n') , \
				tweet['id'].strip('\n'), graph, idItem, idAtt, \
				idAttDegree, idAttFiglio)
		gexf.write(fp_out)
		fp_out.close()
		os.chdir(startpath)


	def prova_ricorsiva_grafo(self, padre, target, grafo, idItem, idAtt, \
			idAttDegree, idAttFiglio):
		'''
		TODO: INSERISCE ARCHI MULTIPLI; RISOLVERE
		SE Y HA AMICO X FACCIO Y -> X, POI SE EVENTUALMENTE X È PRESENTE
		FARÒ ANCHE X -> Y 
		'''
		global counter
		##aggiungo attributi che non ricavo direttamente dalle user info
		'''
		devo costruire la path dinamicamente
		'''
		if padre != target:
			tweet2 = dict(self.__parser_info(target))
			if not grafo.nodeExists(target):
				nodo = self.__aggiungi_nodo(grafo, target)
				if not tweet2.has_key(-1):
					lista = idAtt.items()
					for item in idItem:
						nodo.addAttribute(item, tweet2[str(lista[int(item)][0])].strip().strip('\n'))
					nodo.addAttribute(idAttDegree,str(int(tweet2['friends_count'].strip('\n'))+\
							int(tweet2['followers_count'].strip('\n'))))
					nodo.addAttribute(idAttFiglio, 'false')
			else:
				nodo = grafo.getNode(target)
				if len(nodo.getAttributes()) <= 1:
					if not tweet2.has_key(-1):
						lista = idAtt.items()
						for item in idItem:
							nodo.addAttribute(item, tweet2[str(lista[int(item)][0])].strip().strip('\n'))
						nodo.addAttribute(idAttDegree,str(int(tweet2['friends_count'].strip('\n'))+\
								int(tweet2['followers_count'].strip('\n'))))
						nodo.addAttribute(idAttFiglio, 'false')
			if not grafo.nodeExists(padre):
				self.__aggiungi_nodo(grafo, padre)
			if not grafo.edgeExists(target, padre):
				self.__aggiungi_arco(grafo, counter, target, padre)
			counter += 1
		if os.path.exists('followers'):
			os.chdir('followers')
			listad = os.listdir(os.getcwd())
			if len(listad) == 0: return
			for adir in listad:
				os.chdir(adir)
				self.prova_ricorsiva_grafo(target, adir, grafo, idItem, \
					idAtt, idAttDegree, idAttFiglio)
				os.chdir('../')
			os.chdir('../')
			try:
				fp = open('undirected_'+target+'.txt','r')
				for line in fp:
					line = line.strip().strip('\n')
#					if line in lista_nodi_grafo:
					if line in diz_nodi_grafo:
						if not grafo.nodeExists(str(line)):
							self.__aggiungi_nodo(grafo,str(line))
						if not grafo.edgeExists(target,str(line)):
							self.__aggiungi_arco(grafo,counter,target,str(line))
							counter += 1
			except IOError, e:
				print 'NON HO TROVATO UNDIRECTED'
				pass
		else:
			try:
				fp_in = open('undirected_'+target+'.txt','r')
				for line in fp_in:
					line = line.strip().strip('\n')
#					if line in lista_nodi_grafo:
					if line in diz_nodi_grafo:
						if not grafo.nodeExists(line):
							n2 = self.__aggiungi_nodo(grafo,str(line))
							n2.addAttribute(idAttFiglio, 'true')
						if not grafo.edgeExists(str(line),target):
							self.__aggiungi_arco(grafo, counter, str(line), target)
							counter += 1
#					if line in lista_followers_target:
					if line in diz_followers_target:
						if not grafo.edgeExists(str(line),self.target):
							self.__aggiungi_arco(grafo, counter, str(line), self.target)
							counter += 1
				fp_in.close()
			except IOError, e:
				print 'GRAFO: UNDIRECTED NOT FOUND!!'+os.getcwd() \
						+'target: '+target+ ' padre: '+padre
				return
	def funky_debug(self,out):
		o = open(out, 'a')
#		for line in lista_nodi_grafo:
		for line in diz_nodi_grafo:
			o.write(line)
		o.close()
	def prova_ricorsiva(self, padre, target):
		'''
		Esegue la ricorsione nelle directory che rappresentano il grafo
		e crea il file undirected per ogni dir
		'''
		if os.path.exists('followers'):
			'''
			print '\n ESISTE DIR FOLLOWERS'
			print 'SONO IN: %s ' %os.getcwd()
			print 'PADRE VALE: %s ' % padre
			print 'TARGET VALE %s \n' %target
			'''
			os.chdir('followers')
			listad = os.listdir(os.getcwd())
			if len(listad) == 0: return
			for adir in listad:
				os.chdir(adir)
				self.prova_ricorsiva(target, adir)
				os.chdir('../')
			os.chdir('../')
		else:
			'''
			print '\nnon esiste dir followers'
			print 'PADRE VALE: %s ' % str(padre)
			print 'TARGET VALE: %s ' % str(target)
			print 'sono dentro: %s ' % os.getcwd()
			print 'fine ricorsione \n'
			'''
			try:
				fp_a = open('followers_'+target+'.txt','r')
				fp_b = open('friends_'+target+'.txt', 'r')
				seta = set(fp_a.readlines())
				setb = set(fp_b.readlines())
				setc = seta.intersection(setb)
				fpout = open('undirected_'+target+'.txt', 'w')
				for item in setc:
					fpout.write(item)
				fp_a.close()
				fp_b.close()
				fpout.close()
			except IOError, e:
				print '\t ERRORE RICORSIONE NON TROVO FRIENDS E FOLL'
				return
			return
			
	'''
	def __call_undirected_graph_helper(self, lista):

		self.gthreads.set_operation('undirectedgraph')
		self.gthreads.set_lista(lista)
		self.gthreads.set_lenlista(len(lista))
		self.gthreads.set_arcobaleno(0)
		self.gthreads.set_num(1)
#		self.gthreads.set_lenacc(len(accounts))
		self.gthreads.lancia_threads()
	'''
	def __scegli_account_random(self, path, num):
		'''
		Restituisce una lista casuale di elementi
		contenuti nel file rappresentato dalla path
		'''
		lista = []
		ret = []
		random.seed()
		try:
			fp = open(path, 'r')
		except IOError, e:
			print 'xxxxxxxxxxxxx '+str(e)
			print 'path: '+str(path)+ 'sono in: '+os.getcwd()
			return []
		lines = fp.readlines()
		if len(lines) < num: return [ lines.pop() for i in range(len(lines)) ]
		for line in lines:
			lista.append(line)
		for i in range(num):
			index = random.randrange(len(lista))
			ret.append(lista.pop(index))
		fp.close()
		return ret
	def scarica_target(self,flag):
#		global lista_nodi_grafo
		global diz_nodi_grafo
		'''
		TODO: prendere prima le userinfo per verificare
		il numero di followers
		Flag indica se sto passando un screen_name (1) o  un ids (0)
		'''
		empty_list = []
		try:
			os.mkdir(self.target)
		except OSError, e:
			print 'Followers e User info del target già presenti '+str(e)
			if e.errno == 17:
				os.chdir(os.getcwd()+'/'+self.target)
				try:
					f = open('user_info_'+self.target+'.txt', 'r')
					l = f.readlines()
					for line in l:
						line = line.strip().strip('\n')
						m = re.search('id_str', line)
						if m:
							key,val = line.split(':',1)
#							lista_nodi_grafo.append(val)
							diz_nodi_grafo[val] = val
					f.close()
				except IOError, e:
					pass
				return
			return
		os.chdir(os.getcwd()+'/'+self.target)
		print 'SCARICA FOLLOWERS: sono dentro: '+os.getcwd()+' flag: '+str(flag)
		self.gthreads.set_operation('followers_target')	
		self.gthreads.set_num(1)
		self.gthreads.set_lista(empty_list)
		self.gthreads.set_lenlista(0)
		self.gthreads.set_arcobaleno(flag)
		self.gthreads.lancia_thread(self.target)

		self.gthreads.set_operation('userinfo')	
		self.gthreads.set_num(1)
		self.gthreads.set_lista(empty_list)
		self.gthreads.set_lenlista(1)
		self.gthreads.set_arcobaleno(flag)
		self.gthreads.lancia_thread(self.target)
		try:
			f = open('user_info_'+self.target+'.txt', 'r')
			l = f.readlines()
			for line in l:
				line = line.strip().strip('\n')
				m = re.search('id_str', line)
				if m:
					key,val = line.split(':',1)
#					lista_nodi_grafo.append(val)
					diz_nodi_grafo[val] = val
			f.close()
		except IOError, e:
			pass


	def scarica_followers_friends_of_user(self):
		'''
		Per ogni dir in 'followers' scarica nella cartella dell utente
		la lista dei suoi followers e dei suoi friends
		'''
		start_path = os.getcwd()
		print 'followers and friends: '+os.getcwd()+' '+self.target
		ffpath = os.getcwd()+'/followers/'
		try:
			listdirs = os.listdir(ffpath)
		except OSError, e:
			if e.errno == 2:
				return
		self.gthreads.set_operation('followersandfriends')
		self.gthreads.set_lista(listdirs)
		self.gthreads.set_lenlista(len(listdirs))
		self.gthreads.set_arcobaleno(0)
		self.gthreads.set_num(1)
#		self.gthreads.set_lenacc(len(self.accounts))
		self.gthreads.lancia_threads()
		os.chdir(start_path)
		self.prova_ricorsiva(self.target,self.target)

	def prepara_iterazione(self, num):
		'''
		Ripete il processo di scaricamento followers and friends
		su un nuovo target
		'''
		startpath = os.getcwd()
		print 'PREPARA IT: sono stato lanciato dentro: '+startpath
		os.chdir('followers')
		listdirs = os.listdir(os.getcwd())
		for adir in listdirs:
			print 'sono in: '+os.getcwd()+' vado in: '+adir
			os.chdir(adir)
			self.scarica_info('undirected_'+adir+'.txt', num)
			self.scarica_followers_friends_of_user()
			os.chdir('../')
		os.chdir(startpath)


	def scarica_info(self, followers_path, num):
		'''
		Scarica le informazioni degli utenti scelti casualmente
		dal file followers_path
		'''
#		global lista_nodi_grafo
		global diz_nodi_grafo
		'''
		TODO: scegliere il numero casuale di followers in proporzione al
		numero totale degli stessi.
		'''
		print 'SCARICA INFO: inizio scarica info dei followers !! sono in: '+os.getcwd()
		start_path = os.getcwd()
		lista = self.__scegli_account_random(followers_path, num)
		if len(lista) == 0:
			print "\nl'utente ha troppi pochi followers!!!\n"
			return
		else:
			print 'Ho scelto: '+str(len(lista))+' accounts'
#		num = len(lista)
		fpdebug = open('DEBUG.log', 'a')
		for k in lista:
			k = k.strip().strip('\n')
			fpdebug.write(str(k))
#			lista_nodi_grafo.append(k.strip().strip('\n'))
			diz_nodi_grafo[k] = k
		fpdebug.close()
		try:
			os.mkdir('followers')
		except OSError, e:
			print '\t Scarica Info: Cartella followers esistente!!'
			return
		self.gthreads.set_operation('userinfo')
		self.gthreads.set_lista(lista)
		self.gthreads.set_lenlista(len(lista))
		self.gthreads.set_arcobaleno(0)
		self.gthreads.set_num(1)
		self.gthreads.lancia_threads()
#		print '\t IL GRAFO HA NUM NODI: '+str(len(lista_nodi_grafo))

