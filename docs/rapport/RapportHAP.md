Rapport de projet Hadoop - Transilien
=============================
P.Hamy, N.Leclercq, L.Poncet
--

Installation
======
Les instructions complètes d’installation et de configuration du projet sont fournie sur le dépôt github sous forme de fichier markdown  dans le dossier "install".

**Les points principaux sont rappelés ci-après :** 
* Installation de la Sandbox HDP Hortonworks ;
* Configuration de la timezone de la Sandbox ;
* Installation des paquets et dépendances (Miniconda, Git, JupyterLab) ;
* Configuration de JupyterLab ;
* Configuration de Git ;
* Configuration de la durée de rétention des messages dans Kafka.

**Sur la machine locale :**
* Récupération du repository git ;
* Configuration de Tableau Software.

Travail préliminaire
==

Création du fichier ``transilien_ligne_l_by_code.json`` contenant la liste des stations de la ligne L, ainsi que leur nom et leur position géographique : 

![Extrait de transilien_ligne_l_by_code.json](http://onea.me/hadoop/liste_stations.png)
 
**Étapes principales :** 

* Téléchargement et enregistrement dans des fichiers .JSON suivants depuis 
[le site open data SNCF](https://ressources.data.sncf.com/) : 

| Fichier                    | Description         |
| :--------------------------| :-------------------|
|``sncf-lignes-par-gares-idf.json``|Liste des lignes passant par chaque station du réseau transilien.|
|``sncf-gares-et-arrets-transilien-ile-de-france.json``|	Liste des stations du réseau avec les coordonnées géographiques. |

* Tri pour ne conserver que les stations de la ligne L et les informations suivantes : 
    * code UIC ;
    * nom de la station.
* Ajout d’une station manquante ;
* Tri par ordre croissant des stations ;
* Récupération des positions géographiques des stations de la ligne L.

Producer Kafka
===
Utilitaires
---
On définit au préalable les utilitaires suivants :
* Task : classe permettant d'exécuter périodiquement une requête à l'API transilien et l'envoi dans un stream Kafka ;
* NotebookCellContent : classe permettant le logging asynchrone ;
* Logging : event logging en utilisant la bibliothèque python [logging](https://docs.python.org/3/library/logging.html)  ;
* Credentials : enregistrement dans le fichier ``api_transilien_login.json`` de nos trois couples login / mot de passe d'accès à l'API Transilien.

Classes
--
### TransilienAPI
Cette classe a les deux fonctions principales suivantes : 
* Faire des requêtes sur l'API transilien ;
* Convertir les données reçues au format XML en JSON.

### Converter et JsonConverter
Les classes filles de Converter ont pour rôle de convertir les données préformatées par l’API transilien en un format différent. JsonConverter hérite de Converter et prend en charge le format JSON.

### KafkaProducerTask
Cette classe exécute périodiquement une requête sur l’API transilien et injecte les données retournées dans un stream Kafka.

Producer Kafka
---
Pour la configuration du producer, on utilise un dictionnaire contenant les informations suivantes : 
* Niveau de débogage ;
* Nom du fichier ``api_transilien_login_json`` ;
* Adresse et port du bootstrap server ;
* Topic Kafka ;
* API polling period.


On instancie un KafkaProducerTask en lui passant en paramètres ce fichier de configuration et on lance ce producer de façon asynchrone.

Pour faire les requêtes à l’API Transilien, on itère sur nos login/mdp et sur les stations. Chaque exécution fera donc 3 requêtes : une par couple login/mdp et pour une station différente à chaque fois :

![Exemple resultat producer](http://onea.me/hadoop/producer.png)

Consumer Kafka
===
Partie I : Calcul moyen du temps d'attente moyen par station
---
On explique dans cette partie la façon dont on répond à la question du calcul du temps moyen d'attente par station sur toute la ligne.

Les étapes principales sont les suivantes : 
* Import des packages (dont ``SparkSessions`` depuis ``pyspark.sql`` ; ``Window`` depuis ``pyspark.sql.window``) ;
* Mise en place du logging (utilisation de ``NotebookCellContent`` défini plus haut, et de [Py4J](https://www.py4j.org/)) ;
* Création d'une session Spark ;
* Création d'un [Structured Spark Stream](https://spark.apache.org/docs/latest/structured-streaming-programming-guide.html) à partir d'un flux Kafka ;
* Désérialisation et formatage des messages grâce à la fonction Spark ``fromJson`` :
    * Utilisation d'un schéma JSON ;
    * Définition du format des *timestamp*.
 * Configuration de la fenêtre : *watermark*, *window length*, *sliding interval* ;
 * ``GroupBy`` par station et pour la fenêtre définie ;
* Suppression des doublons de couples (train, heure de départ) ;
* Création d'une aggrégation contenant : 
    * le nombre *nt* de trains sur la période 
    * le temps moyen *awt* d'attente sur la période
  ![enter image description here](http://onea.me/hadoop/dataframe.png)


Partie I & II : Calcul des temps d'attente et de la progression des trains
--
### Classe *TransilienStreamProcessor*
Cette classe implémente l'intégralité des fonctionnalités pour les parties I et II du projet.

* Partie I : 
    * *setup_last_hour_awt_stream*
    * *computeAwtMetricsAndSaveAsTempViews*
*  Partie II : 
    * *setup_trains_progression_stream*
    * *computeTrainsProgressionAndSaveAsTempView*

### Étapes principales de fonctionnement du consumer 
* Import des packages Python requis
* Mise en place du logging
* Définition de paramètres de configuration :
    * Schéma et options de désérialisation
    * Options de la session Spark
    * Source Kafka (broker et topic)
    * Fenêtre du stream Kafka
    * Configuration du serveur thrift local
* Instanciation de la classe *TransilienStreamProcessor*

![enter image description here](http://onea.me/hadoop/toPandas1.png)
![enter image description here](http://onea.me/hadoop/toPandas2.png)


> Written with [StackEdit](https://stackedit.io/).
