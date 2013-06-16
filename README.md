[Intro]
Framework per data mining su twitter, utilizza il modulo Twython per
comunicare con le REST API Twitter 1.1. Multi-threads, un thread per
ogni api key disponibile.
Permette la raccolta di ogni tipo di informazione resa disponibile della
API di twitter. Crea la seguente struttura:

TARGET/
			user_info.txt
			followers_target.txt
			FOLLOWERS/
								ID_FOLLOWER_1/
															user_info.txt
															followers
															friends
															intersect_friends_followers
															TRUST/
																		TARGET_1/
																							user_info.txt
																							....
								...
								ID_FOLLOWER_N/

[Restrizioni]
Il grafo costruito è di tipo undirected
Restrizione sulla lista followers ad un bound di MAXBOUND

[Descrizione]
intersect_friends_followers: contiene gli id che sono AMICI dell'
ID_FOLLOWER_N relativo. La relazione di amicizia è resa forte, cioè gli
AMICI di un dato user sono l'intersezione tra l'insieme dei followers e
l'insieme dei following.
TRUST: contiene una directory per ogni utente presente in
intersect_friends_followers.

[Implementazione]

passo 1.
	scarico user info e [followers] del target del TARGET
passo 2.
	scelgo in modo casuale n utenti tra i followers del TARGET
passo 3.
	per ogni utente in n, scarico le user info e le liste dei: followers e
	friends
passo 4.
	genero intersect_friends_followers
passo 5.
	itero dal passo 1 su TRUST (mi fermo dopo 1 iterazione)
passo 6.
	genero il .gexf del social network del TARGET. Ogni nodo rappresenta
	un utente, un arco la relazione di amicizia tra due utenti.
	Ogni ID_FOLLOWER_* lo collego al TARGET (qui la relazione di AMICIZIA
	è debole) 
	Ogni utente in intesect_friends_followers lo collego al ID_FOLLOWER_N
	relativo (AMICIZIA forte) e nel caso anche al TARGET

[TODO]
Implementare il passo 5. descritto sopra, permettendo di verificare le
relazioni tra gli amici di un follower e il resto del social network
	

