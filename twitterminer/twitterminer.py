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
		self.origin = path
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
				print ' ASD1'
				pass
			try:
				fpout = open('followers_'+self.target+'.txt', 'a')
			except:
				print 'ASD2'
				pass
			for ids in data['ids']:
				fpout.write("%s\n" % str(ids)) #aggiunge un newline di troppo..
		else:
			try:
				os.chdir(self.my_path)
				os.chdir(self.target)
			except:
				print 'ASD3'
				pass
			try:
				fpout = open('followers_'+self.target+'.txt', 'a')
			except:
				print 'ASD4'
				pass
			for ids in data['ids']:
				fpout.write("%s\n" % str(ids)) #aggiunge un newline di troppo..
		fpout.flush()
		fpout.close()
	def __salva_user_info(self,init2):
		os.chdir(init2)
		data = ''
		info = None
		try:
			if self.arcobaleno == 0:
				os.mkdir(self.target)
		except OSError, e:
			print '\terrore salva info mkdir '+str(e)+ \
			' target:'+self.target+' ' +os.getcwd()
			
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
			print 'ASD5'
			pass
		cursor_file.write(str(cursore))
		cursor_file.flush()
		cursor_file.close()
	def __dormi(self, cursore):
		self.__salva_cursore(cursore)
		#self.__put_twython()
		t_inesecuzione.get()
		t_inattesa.put(self)
		flag = True
		try: 
			self.lock.release()
		except:
			print '\t ANNUNCIAZIO ERRORE BUONA NOTTE'
			print sys.exc_info()
			flag = False
		print '\t\t ANNUNCIAZIO buona notte, target: '+self.target
		time.sleep(10*60)
		if flag: self.lock.acquire()
		#self.twitter=self.__get_twython()
		t_inattesa.get()
		t_inesecuzione.put(self)
		t_inattesa.task_done()
	def __controllo_target(self):
		'''
		controllo se il target id non ha troppi followers
		'''
		os.chdir(self.target)
		#print '\t CONTROLLO TARGET '+ os.getcwd()
		try:
			fpin = open('user_info_'+self.target+'.txt','r')
		except OSError, e:
			print 'PUTTANAZZA '+ str(e)
			return
		for line in fpin:
			line = line.strip('\n')
			m = re.search('followers_count',line)
			if m:
				key,val = line.split(':',1)
				if int(val) < 15000:
					return 1
		return 0
	def _write_error(self,data,flag):
		start = os.getcwd()
		if not flag:
			try:
				os.chdir(self.my_path)
			except:
				print ' ASD10'
				pass
			try:
				fpout = open('errori_'+self.target+'.txt', 'a')
			except:
				print 'ASD20'
				pass
			for ids in data['ids']:
				fpout.write("%s\n" % str(ids)) #aggiunge un newline di troppo..
		else:
			try:
				os.chdir(self.my_path)
				os.chdir(self.target)
			except:
				print 'ASD30'
				pass
			try:
				fpout = open('errori_'+self.target+'.txt', 'a')
			except:
				print 'ASD40'
				pass
		fpout.write(data)+'\n'
		fpout.flush()
		fpout.close()
		os.chdir(start)
	def __get_followers(self, flag):
		test = 1
		if flag: test = self.__controllo_target()
		if test:
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
						print str(e.error_code)
						self.__write_error(self.target+' '+str(e),flag)
						nextcursor=0
						break
					except ConnectionError, e:
						print 'cazzo cazzo iu iu'+str(e)
						nextcursor=0
						break
					nextcursor = data['next_cursor']
				self.__salva_followers(data, flag)
		else:
			print '\t AAAA target con troppi followers: '+self.target
			return
	def run(self):
		global t_attesa, t_inesecuzione, coda_account
		t_inesecuzione.put(self)
		self.twitter = self.__get_twython()
		#print 'ciao sono: '+self.name+' twitter vale:' + \
		#str(self.twitter.get_authorized_tokens)
		while True:
			if self.operation == 'followers':
#				print 'lsita followers'
				self.__get_followers(False)
				break
			elif self.operation == 'userinfo':
				self.lock.acquire()
				#print 'prenso lock '+self.name+' target: '+self.target
				init2 = os.getcwd()
				#print '\t '+self.name+' thread target: '+self.target+' userinfo nato in: '+init2
				self.__salva_user_info(init2)
				#print '\t '+self.name+' thread taget: '+self.target+' userinfo morto in: '+init2
				os.chdir(init2)
				self.lock.release()
				#print 'lasciato lock '+self.name
				break
			elif self.operation == 'followersandfriends':
				self.lock.acquire()
				initial = os.getcwd()
				#print self.name+' NATO con target: '+self.target+ 'dir: '+os.getcwd()
				self.__get_followers(True)
				os.chdir(initial)
				self.lock.release()
				#print '\t get followers RIENTRATA in dir: '+os.getcwd()
				break
		self.__put_twython()
		#self.lock.release()
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
	def __set_operation(self, newop):
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
#				print '\t MAXI DIR: '+os.getcwd()
				t = MinerThreads(self.lock, self.target, self.operation, os.getcwd(),xxx)
				self.lista_threads.append(t)
		else:
			for i in range(num):
#				print '\t MAXI DIR: '+os.getcwd()
				t = MinerThreads(self.lock, lista.pop(), self.operation, os.getcwd(),xxx)
				self.lista_threads.append(t)
	def __parser_info(self, dest):
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
			fp_info = open('user_info_'+dest+'.txt','r')
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
			print '\t azz '+dest+' '+str(e)
			yield -1,-1
	def __genera_gexf(self, target, output_file):
		'''
		genero il grafo indiretto in formato gexf
		i nodi rappresentano gli utenti twitter
		ogni nodo possiede gli attributi estratti dalle info dell'utente
		TODO: salvare i nodi con lo screen_name
		'''
		self.__set_target(target)
		counter = 0
		local_path = os.getcwd()
		os.chdir('../')
		fp_out = open(output_file,'w')
		tweet = dict(self.__parser_info(self.target))
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
		n.addAttribute(idAttDegree,str(int(tweet['friends_count'].strip('\n'))+int(tweet['followers_count'].strip('\n'))))
		os.chdir(local_path)
		listdirs = os.listdir(os.getcwd())
		for adir in listdirs:
			os.chdir(adir)
			tweet2 = dict(self.__parser_info(adir))
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
				if not int(tweet2['followers_count']) > 500:
					try:
						with open('followers_'+str(adir)+'.txt','r') as fp2:
							for line in fp2:
								line = line.strip()
								line = line.strip('\n')
								#print line
								if not graph.nodeExists(line):
									n3 = graph.addNode(line,line)
									n3.addAttribute(idAttFiglio, 'True')
								graph.addEdge(counter, line, adir)
								counter += 1
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
	def __uniq(self,ainput):
		output = []
		for x in ainput:
			if x not in output:
				output.append(x)
		return output
	def __scegli_account_random(self, path, num):
		lista = []
		random.seed()
		try:
			fp = open(path, 'r')
		except:
			print 'xxxxxxxxxxxxx'
			return -1
		lines = fp.readlines()
		random.shuffle(lines)
		for i in range(num):
			lista.append(random.choice(lines))
			time.sleep(0.01)
		fp.close()
		return lista
	def __thread_mancanti(self,num,num_threads):
		if num < num_threads:
			return num
		elif num > num_threads:
			return num-num_threads
	def genera_gexf(self, target, output_file):
		print '\t DEBUG GENERA GEXF'
		try:
			os.chdir('followers')
		except OSError, e:
			print str(e)
		self.__genera_gexf(target,output_file)
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
		print 'terminato 1'
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
		'''
		anche qui devo ottimizzare con i thread
		come sotto.
		Per ogni dir in 'followers' scarica nella cartella dell utente
		la lista dei suoi followers e dei suoi friends
		'''
		start_path = os.getcwd()
		self.__set_operation('followersandfriends')
		try:
			os.chdir('followers')
		except OSError, e:
			print 'li mortacci'
			return
		print 'followers and friends: '+os.getcwd()+' '+self.target
		listdirs = os.listdir(os.getcwd())
		num = len(listdirs)
		num_threads = 0
		while True:
			#print 'sto prendendo il lock: '
			self.lock.acquire()
			#print ' PRESO: '
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
				print 'attesa: '+str(t_inattesa.qsize())+' exec: '+str(t_inesecuzione.qsize())
				t_inesecuzione.join()
			else:
				q_size = t_inattesa.qsize()
				q_size2 = t_inesecuzione.qsize()
				total = q_size + q_size2
#				print '\t BBBB DEBUGELSE in attesa: '+str(q_size)
#				print '\t BBBB DEBUGELSE inexec: '+str(q_size2)
#				print '\t BBBB DEBUGELSE #threads: '+str(num_threads)
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
					if resto < 8:
						try:
							self.__crea_threads((8-q_size2),[listdirs.pop() for x in range((8-q_size2))], 0)
						except  IndexError, e:
							break
					else:
						try:
							self.__crea_threads(resto, [listdirs.pop() for x in range((resto))], 0)
						except  IndexError, e:
							break
						print '\t\t PORCODIO '+str(resto)+' lista: '+str(len(listdirs))
						num_threads += (8-qsize2)
			self.lock.release()
			print '\t DEBUG #threads: '+str(len(self.lista_threads))
			for i in range(len(self.lista_threads)):
				th = self.lista_threads.pop()
				th.setDaemon(True)
				th.start()
			if num_threads >= num:
				print '\t\t PORCODIO LA MADONNA FINITO'
				break
		print '\t\t FINE FINE '
		print 'creati: '+str(num_threads)+' th in attesa: '+str(t_inattesa.qsize())+' th in exec: '+str(t_inesecuzione.qsize())
		print 'coda account: '+str(coda_account.qsize())
		t_inattesa.join()
		print 'thread in attesa rientrari'
		t_inesecuzione.join()
		print 'thread in esecuzione rientrati'+str(t_inesecuzione.qsize())
		print 'FINE: ' + str(num_threads)
		os.chdir(start_path)
	def scarica_info(self, followers_path, num):
		start_path = os.getcwd()
		self.__set_operation('userinfo')
		lista1 = self.__scegli_account_random(followers_path, num)
		lista = self.__uniq(lista1)
		num = len(lista)
		fpdebug = open('DEBUG.log', 'a')
		for k in lista:
			fpdebug.write(str(k))
		fpdebug.close()
		try:
			os.mkdir('followers')
		except OSError, e:
			print '\t ZZZZ male'
			pass
		os.chdir('followers')
		print '\t scarica_info DEBUG: '+str(len(lista))
		num_threads = 0
		while True:
			self.lock.acquire()
			if t_inattesa.qsize() == 0 and t_inesecuzione.qsize() == 0:
				resto = self.__thread_mancanti(num,num_threads)
				if resto < 8:
					self.__crea_threads(resto, [lista.pop() for x in range(resto)], 0)
					num_threads += resto
				else:
					try:
						self.__crea_threads(8, [lista.pop() for x in range(8)], 0)
					except IndexError,e :
						print '\t CAZZI AMARI'+str(e)+' '+str(lista)
						break
					num_threads += 8
				#print '\t DEBUGGGG: '+str(len(lista))
			elif t_inesecuzione.qsize() == 8:
				t_inesecuzione.join()
			else:
				q_size = t_inattesa.qsize()
				q_size2 = t_inesecuzione.qsize()
				total = q_size + q_size2
#				print '\t BBBB DEBUGELSE in attesa: '+str(q_size)
#				print '\t BBBB DEBUGELSE inexec: '+str(q_size2)
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
			print '\t DEBUG #thread creati: '+str(len(self.lista_threads))
			for i in range(len(self.lista_threads)):
				th = self.lista_threads.pop()
				th.setDaemon(True)
				th.start()
			if num_threads >= num:
				print '\t\t PORCODIO LA MADONNA'
				break
		print '\t\t FINE FINE '
		print 'creati: '+str(num_threads)+' th in attesa: '+str(t_inattesa.qsize())+' th in exec: '+str(t_inesecuzione.qsize())
		t_inesecuzione.join()
		t_inattesa.join()
		print 'FINE: ' + str(num_threads)+ ' '+str(t_inesecuzione.qsize())+' '+str(t_inattesa.qsize())
		os.chdir(start_path)
