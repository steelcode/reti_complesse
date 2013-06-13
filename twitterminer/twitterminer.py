# encoding: utf-8

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

class MinerThreads(threading.Thread):
	def __init__(self, lock, target,operation, path, arcobaleno):
		'''
		arcobaleno indica se sto lavorando con ids (0) o screen_name (1)
		'''
		threading.Thread.__init__(self)
		self.lock = lock
		self.target = target.strip('\n')
		self.cursore_path = 'cursore_'+self.target+'.txt'
		self.my_path = path
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
	def __salva_followers(self, data, flag):
		if not flag:
			try:
				os.chdir(self.my_path)
			except:
				pass
			try:
				fpout = open('followers_'+self.target+'.txt', 'a')
			except:
				pass
			for ids in data['ids']:
				fpout.write("%s\n" % str(ids)) #aggiunge un newline di troppo..
		else:
			try:
				os.chdir(self.my_path)
				os.chdir(self.target)
			except:
				pass
			try:
				fpout = open('followers_'+self.target+'.txt', 'a')
			except:
				pass
			for ids in data['ids']:
				fpout.write("%s\n" % str(ids)) #aggiunge un newline di troppo..
		fpout.flush()
		fpout.close()
	def __salva_user_info(self):
		os.chdir(self.my_path)
		data = ''
		info = None
		try:
			if self.arcobaleno == 0:
				os.mkdir(self.target)
		except OSError, e:
			print 'errore salva info mkdir '+str(e)
			#se dir exist continuo
		try:
			if self.arcobaleno == 0:
				os.chdir(self.my_path+'/'+self.target)
		except OSError, e:
			print 'errore salva info chdir: '+str(e)
			return
		fpout = open('user_info_'+self.target+'.txt','a')
		try:
			if int(self.arcobaleno) == 0:
				info = self.twitter.show_user(user_id=self.target,include_entities='0')
			else:
				info = self.twitter.show_user(screen_name=self.target,include_entities='0')
		except TwythonError, e:
			print 'target '+self.target+'errore retrive user info'+str(e)
			print 'magia: '+str(self.arcobaleno)
			return
		for key in info.keys():
			if isinstance(info[key], str):
				data += key + ':' + unicode(info[key], 'utf-8') + '\n'
			elif isinstance(info[key], unicode):
				data += key + ':' + info[key] + '\n'
			else:
				data += key + ':' + str(info[key]) + '\n'
		fpout.write(data.encode('utf-8'))
		fpout.flush()
		fpout.close()
		os.chdir(self.my_path)
	def __check_cursore(self):
		os.chdir(self.my_path)
		'''
		se il file del cursore esiste
		prende il valore e lo usa come nextcursor,
		altrimenti -1
		'''
		try:
			with open(self.cursore_path):
				fp = open(self.cursore_path,'r')
				ret = str(fp.readline())
		except IOError:
			return -1
		fp.close()
		return ret
	def __salva_cursore(self, cursore):
		os.chdir(self.my_path)
		'''
		Scrive il next_cursor su file
		I cursori vengono usati per verificare se sono stati prelevati tutti i
		follower e se uno specifico twitter id e' stato gia' analizzato
		'''
		try:
			cursor_file = open(self.cursore_path,'w')
		except:
			pass
		cursor_file.write(str(cursore))
		cursor_file.flush()
		cursor_file.close()
	def __dormi(self, cursore):
		self.__salva_cursore(cursore)
		self.__put_twython()
		t_inesecuzione.get()
		t_inattesa.put(self)
		print 'buona notte, target: '+self.target
		time.sleep(15*60)
		t_inattesa.get()
		t_inesecuzione.put(self)
		t_inattesa.task_done()
	def __get_followers(self, flag):
		nextcursor = self.__check_cursore()
		while nextcursor is not 0:
			limite = self.__check_f_limit()
			if limite == 0 or limite == -1:
				self.__salva_cursore(nextcursor)
				self.__dormi(nextcursor)
			else:
				try:
					if self.arcobaleno == 0:
						data = self.twitter.get_followers_ids(user_id=self.target, cursor = nextcursor)
					else:
						data = self.twitter.get_followers_ids(screen_name =self.target, cursor = nextcursor)
				except TwythonError, e:
					print self.name+self.target+' get_followers twython error'+str(e)
					nextcursor=0
					break
				nextcursor = data['next_cursor']
				self.__salva_followers(data, flag)
	def run(self):
		global t_attesa, t_inesecuzione, coda_account
		t_inesecuzione.put(self)
		self.twitter = self.__get_twython()
		#print 'ciao sono: '+self.name+' twitter vale:' + \
		#str(self.twitter.get_authorized_tokens)
		while True:
			if self.operation == 'followers':
				self.__get_followers(False)
				break
			elif self.operation == 'userinfo':
				#print self.name+' target: '+self.target
				self.lock.acquire()
				self.__salva_user_info()
				self.lock.release()
				break
			elif self.operation == 'followersandfriends':
				self.__get_followers(True)
				break
		self.__put_twython()
		t_inesecuzione.get()
		t_inesecuzione.task_done()

class TwitterMiner:
	def __init__(self,target, accounts, operation):
		self.target = target
		self.accounts = accounts
		self.operation = operation
		self.lock = threading.Lock()
		self.lista_threads = []
		self.__makeTwythonObj()
	def __change_operation(self, newop):
		self.operation = newop
	def __set_target(self,target):
		self.target = target
	def __makeTwythonObj(self):
		global coda_account
		for i in range(len(self.accounts)):
			coda_account.put(Twython(self.accounts[i][0], self.accounts[i][1],
            self.accounts[i][2],
            self.accounts[i][3],
            headers={'User-Agent':'__twython_Test'}) )
	def __crea_threads(self, num, lista, xxx):
		if len(lista) == 0:
			for i in range(num):
				t = MinerThreads(self.lock, self.target, self.operation, os.getcwd(),xxx)
				self.lista_threads.append(t)
		else:
			for i in range(num):
				t = MinerThreads(self.lock, lista.pop(), self.operation, os.getcwd(),xxx)
				self.lista_threads.append(t)
	def __parser_info(self):
		myinfo = ['verified', 'default_profile', 'geo', 'geo_enabled',
		'followers_count', 'friends_count', 'screen_name']
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
			fp_info = open('user_info_'+self.target+'.txt','r')
			# print 'prima del for'
			# print 'dopo readline'
			for line in fp_info:
				line = line.strip('\n')
				for i in myinfo:
					m = re.search(i+':',line)
					if m:
						#print line
						line = line.strip(' ')
						key, val = line.split(':',1)
						#print key,val
						yield key, val
                        #for (key,val) in line.split(':',1):
                        #    pass
			fp_info.close()
		except IOError,e:
			print '\t azz'+self.target+' '+str(e)
			yield -1,-1
	def __genera_gexf(self, target, output_file):
		'''
		genero il grafo indiretto in formato gexf
		i nodi rappresentano gli utenti twitter
		ogni nodo possiede gli attributi estratti dalle info dell'utente
		'''
		self.__set_target(target)
		counter = 0
		local_path = os.getcwd()
		os.chdir('../')
		fp_out = open(output_file,'w')
		tweet = dict(self.__parser_info())
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
		n = graph.addNode(self.target,tweet['screen_name'].strip())
		n.addAttribute(idAttInDegree,str(int(tweet['followers_count'])))
		n.addAttribute(idAttOutDegree,str(int(tweet['friends_count'])))
		os.chdir(local_path)
		listdirs = os.listdir(os.getcwd())
		for adir in listdirs:
			self.__set_target(adir)
			os.chdir(adir)
			tweet2 = dict(self.__parser_info())
			n2 = graph.addNode(adir,adir)
			graph.addEdge(counter, adir, self.target)
			counter += 1
			if not tweet.has_key(-1):
				n2.addAttribute(idAttInDegree,str(int(tweet2['followers_count'].strip('\n'))))
				n2.addAttribute(idAttOutDegree,str(int(tweet2['friends_count'].strip().strip('\n'))))
				n2.addAttribute(idAttDegree,str(int(tweet2['friends_count'].strip('\n'))+int(tweet2['followers_count'].strip('\n'))))
				n2.addAttribute(idAttGeo,tweet2['default_profile'].strip('\n').strip())
				n2.addAttribute(idAttVerified,tweet2['verified'].strip('\n').strip())
				n2.addAttribute(idAttDefault,tweet2['geo_enabled'].strip('\n').strip())
				tweet['screen_name'] = tweet2['screen_name'].strip('\n').strip()
				n2.addAttribute(idAttName,tweet2['screen_name'])
				#print tweet['followers_count']
				if not int(tweet2['followers_count']) > 51:
					try:
						#print 'ricorsione'
						with open('followers_'+ids+'.txt','r') as fp2:
							for line in fp2:
								line = line.strip()
								line = line.strip('\n')
								#print line
								if not graph.nodeExists(line):
									n3 = graph.addNode(line,line)
									n3.addAttribute(idAttFiglio, 'True')
								graph.addEdge(counter, line, ids)
								counter += 1
					except:
						pass
						#print os.getcwd()+' followers_'+ids+'.txt'
			else:
				#print 'nodo senza attributi: '+ids
				n2.addAttribute(idAttPriv, 'True')
			os.chdir('../')
		gexf.write(fp_out)
		fp_out.close()
	def __scegli_account_random(self, path, num):
		lista = []
		try:
			fp = open(path, 'r')
		except:
			print 'xxxxxxxxxxxxx'
			return -1
		lines = fp.readlines()
		random.shuffle(lines)
		for i in range(num):
			lista.append(random.choice(lines))
		fp.close()
		return lista
	def __thread_mancanti(self,num,num_threads):
		if num < num_threads:
			return -1
		elif num > num_threads:
			return num-num_threads
		pass
	def genera_gexf(self, target, output_file):
		print '\t DEBUG GENERA GEXF'
		try:
			os.chdir('followers')
		except OSError, e:
			print str(e)
		self.__genera_gexf(target,output_file)
		pass
	def scarica_followers(self):
		empty_list = []
		try:
			os.mkdir(self.target)
		except OSError,e:
			print 'aaaaa'
		os.chdir(os.getcwd()+'/'+self.target)
		self.__crea_threads(1, empty_list, 1)
		th = self.lista_threads.pop()
		th.setDaemon(True)
		th.start()
		th.join()
		'''
		scarico le user info del target
		TODO: mi servono i friends del target?
		'''
		self.operation = 'userinfo'
		self.__crea_threads(1, [self.target], 1)
		th2 = self.lista_threads.pop()
		th2.setDaemon(True)
		th2.start()
		th2.join()
	def scarica_followers_friends_of_user(self):
		print 'followers and friends: '+os.getcwd()+self.target
		'''
		anche qui devo ottimizzare con i thread
		come sotto.
		Per ogni dir in 'followers' scarica nella cartella dell utente
		la lista dei suoi followers e dei suoi friends
		'''
		start_path = os.getcwd()
		self.__change_operation('followersandfriends')
		try:
			os.chdir('followers')
		except OSError, e:
			print 'li mortacci'
			return
		listdirs = os.listdir(os.getcwd())
		num = len(listdirs)
		num_threads = 0
		while True:
			self.lock.acquire()
			if t_inattesa.qsize() == 0 and t_inesecuzione.qsize() == 0:
				print ' A BOMBAZZAAAA'
				try:
					self.__crea_threads(8, [listdirs.pop() for x in range(8)], 0)
				except IndexError, e:
					break
				num_threads += 8
				#print '\t DEBUGGGG: '+str(len(lista))
			elif t_inesecuzione.qsize() == 8:
				print 'prima o poi devo fermarmi, ORA'
				t_inesecuzione.join()
			else:
				q_size = t_inattesa.qsize()
				q_size2 = t_inesecuzione.qsize()
				total = q_size + q_size2
				print '\t BBBB DEBUGELSE in attesa: '+str(q_size)
				print '\t BBB DEBUGELSE inexec: '+str(q_size2)
				if q_size == 0:
					resto = self.__thread_mancanti(len(listdirs),num_threads)
					if resto >= 8:
						run = 8 - q_size2
						try:
							self.__crea_threads(run, [listdirs.pop() for y in range(run)], 0)
						except IndexError, e:
							break
						num_threads += run
					elif resto > 0:
						try:
							self.__crea_threads(resto, [listdirs.pop() for x in range(resto)], 0)
						except IndexError, e:
							break
						num_threads += resto
					else:
						print '\t\t PORCODIO '
						break
			self.lock.release()
			print '\t DEBUG #threads: '+str(len(self.lista_threads))
			for i in range(len(self.lista_threads)):
				th = self.lista_threads.pop()
				th.setDaemon(True)
				th.start()
			if num_threads >= num:
				break
		t_inattesa.join()
		print 'thread in attesa rientrari'
		t_inesecuzione.join()
		print 'thread in esecuzione \
		rientrati'+str(t_inesecuzione.qsize())
		print 'FINE: ' + str(num_threads)
		os.chdir(start_path)
	def scarica_info(self, followers_path, num):
		start_path = os.getcwd()
		self.__change_operation('userinfo')
		lista = self.__scegli_account_random(followers_path, num)
		try:
			os.mkdir('followers')
		except OSError, e:
			pass
		os.chdir('followers')
		print '\t scarica_info DEBUG: '+str(len(lista))
		num_threads = 0
		while True:
			self.lock.acquire()
			if t_inattesa.qsize() == 0 and t_inesecuzione.qsize() == 0:
				try:
					self.__crea_threads(8, [lista.pop() for x in range(8)], 0)
				except IndexError,e :
					break
				num_threads += 8
				#print '\t DEBUGGGG: '+str(len(lista))
			elif t_inesecuzione.qsize() == 8:
				t_inesecuzione.join()
			else:
				q_size = t_inattesa.qsize()
				q_size2 = t_inesecuzione.qsize()
				total = q_size + q_size2
				print '\t BBBB DEBUGELSE in attesa: '+str(q_size)
				print '\t BBB DEBUGELSE inexec: '+str(q_size2)
				if q_size == 0:
					resto = self.__thread_mancanti(num,num_threads)
					if resto >= 8:
						run = 8 - q_size2
						self.__crea_threads(run, [lista.pop() for y in range(run)], 0)
						num_threads += run
					else:
						self.__crea_threads(resto, [lista.pop() for x in range(resto)], 0)
						num_threads += resto
			self.lock.release()
			print '\t DEBUG #threads: '+str(len(self.lista_threads))
			for i in range(len(self.lista_threads)):
				th = self.lista_threads.pop()
				th.setDaemon(True)
				th.start()
			if num_threads >= num:
				break
		t_inattesa.join()
		t_inesecuzione.join()
		print 'FINE: ' + str(num_threads)
		os.chdir(start_path)
