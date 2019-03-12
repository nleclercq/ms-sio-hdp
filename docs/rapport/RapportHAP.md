Rapport de projet Hadoop - Transilien
=============================
P.Hamy, N.Leclercq, L.Poncet
--

Installation
======
Les instructions compl�tes d�installation et de configuration du projet sont fournie sur le d�p�t github sous forme de fichier markdown  dans le dossier "install".

**Les points principaux sont rappel�s ci-apr�s :** 
* Installation de la Sandbox HDP Hortonworks ;
* Configuration de la timezone de la Sandbox ;
* Installation des paquets et d�pendances (Miniconda, Git, JupyterLab) ;
* Configuration de JupyterLab ;
* Configuration de Git ;
* Configuration de la dur�e de r�tention des messages dans Kafka.

**Sur la machine locale :**
* R�cup�ration du repository git ;
* Configuration de Tableau Software.

Travail pr�liminaire
==

Cr�ation du fichier ``transilien_ligne_l_by_code.json`` contenant la liste des stations de la ligne L, ainsi que leur nom et leur position g�ographique : 

![Extrait de transilien_ligne_l_by_code.json](http://onea.me/hadoop/liste_stations.png)
 
**�tapes principales :** 

* T�l�chargement et enregistrement dans des fichiers .JSON suivants depuis 
[le site open data SNCF](https://ressources.data.sncf.com/) : 

| Fichier                    | Description         |
| :--------------------------| :-------------------|
|``sncf-lignes-par-gares-idf.json``|Liste des lignes passant par chaque station du r�seau transilien.|
|``sncf-gares-et-arrets-transilien-ile-de-france.json``|	Liste des stations du r�seau avec les coordonn�es g�ographiques. |

* Tri pour ne conserver que les stations de la ligne L et les informations suivantes : 
    * code UIC ;
    * nom de la station.
* Ajout d�une station manquante ;
* Tri par ordre croissant des stations ;
* R�cup�ration des positions g�ographiques des stations de la ligne L.

Producer Kafka
===
Utilitaires
---
On d�finit au pr�alable les utilitaires suivants :
* Task : classe permettant d'ex�cuter p�riodiquement une requ�te � l'API transilien et l'envoi dans un stream Kafka ;
* NotebookCellContent : classe permettant le logging asynchrone ;
* Logging : event logging en utilisant la biblioth�que python [logging](https://docs.python.org/3/library/logging.html)  ;
* Credentials : enregistrement dans le fichier ``api_transilien_login.json`` de nos trois couples login / mot de passe d'acc�s � l'API Transilien.

Classes
--
### TransilienAPI
Cette classe a les deux fonctions principales suivantes : 
* Faire des requ�tes sur l'API transilien ;
* Convertir les donn�es re�ues au format XML en JSON.

### Converter et JsonConverter
Les classes filles de Converter ont pour r�le de convertir les donn�es pr�format�es par l�API transilien en un format diff�rent. JsonConverter h�rite de Converter et prend en charge le format JSON.

### KafkaProducerTask
Cette classe ex�cute p�riodiquement une requ�te sur l�API transilien et injecte les donn�es retourn�es dans un stream Kafka.

Producer Kafka
---
Pour la configuration du producer, on utilise un dictionnaire contenant les informations suivantes : 
* Niveau de d�bogage ;
* Nom du fichier ``api_transilien_login_json`` ;
* Adresse et port du bootstrap server ;
* Topic Kafka ;
* API polling period.


On instancie un KafkaProducerTask en lui passant en param�tres ce fichier de configuration et on lance ce producer de fa�on asynchrone.

Pour faire les requ�tes � l�API Transilien, on it�re sur nos login/mdp et sur les stations. Chaque ex�cution fera donc 3 requ�tes : une par couple login/mdp et pour une station diff�rente � chaque fois :

![Exemple resultat producer](http://onea.me/hadoop/producer.png)

Consumer Kafka
===
Partie I : Calcul moyen du temps d'attente moyen par station
---
On explique dans cette partie la fa�on dont on r�pond � la question du calcul du temps moyen d'attente par station sur toute la ligne.

Les �tapes principales sont les suivantes : 
* Import des packages (dont ``SparkSessions`` depuis ``pyspark.sql`` ; ``Window`` depuis ``pyspark.sql.window``) ;
* Mise en place du logging (utilisation de ``NotebookCellContent`` d�fini plus haut, et de [Py4J](https://www.py4j.org/)) ;
* Cr�ation d'une session Spark ;
* Cr�ation d'un [Structured Spark Stream](https://spark.apache.org/docs/latest/structured-streaming-programming-guide.html) � partir d'un flux Kafka ;
* D�s�rialisation et formatage des messages gr�ce � la fonction Spark ``fromJson`` :
    * Utilisation d'un sch�ma JSON ;
    * D�finition du format des *timestamp*.
 * Configuration de la fen�tre : *watermark*, *window length*, *sliding interval* ;
 * ``GroupBy`` par station et pour la fen�tre d�finie ;
* Suppression des doublons de couples (train, heure de d�part) ;
* Cr�ation d'une aggr�gation contenant : 
    * le nombre *nt* de trains sur la p�riode 
    * le temps moyen *awt* d'attente sur la p�riode
  ![enter image description here](http://onea.me/hadoop/dataframe.png)


Partie I & II : Calcul des temps d'attente et de la progression des trains
--
### Classe *TransilienStreamProcessor*
Cette classe impl�mente l'int�gralit� des fonctionnalit�s pour les parties I et II du projet.

* Partie I : 
    * *setup_last_hour_awt_stream*
    * *computeAwtMetricsAndSaveAsTempViews*
*  Partie II : 
    * *setup_trains_progression_stream*
    * *computeTrainsProgressionAndSaveAsTempView*

### �tapes principales de fonctionnement du consumer 
* Import des packages Python requis
* Mise en place du logging
* D�finition de param�tres de configuration :
    * Sch�ma et options de d�s�rialisation
    * Options de la session Spark
    * Source Kafka (broker et topic)
    * Fen�tre du stream Kafka
    * Configuration du serveur thrift local
* Instanciation de la classe *TransilienStreamProcessor*

![enter image description here](http://onea.me/hadoop/toPandas1.png)
![enter image description here](http://onea.me/hadoop/toPandas2.png)


> Written with [StackEdit](https://stackedit.io/).
