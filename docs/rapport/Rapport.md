Rapport de projet Hadoop - Transilien
=============================
P.Hamy, N.Leclercq, L.Poncet
--

Introduction
==========
Le but de ce projet est de mettre en �uvre les diff�rents outils de l'�cosyst�me Hadoop en utilisant la Sandbox [Hortonworks HDP](https://www.cloudera.com/downloads/hortonworks-sandbox.html) ainsi que l'outil de visualisation [Tableau](https://www.tableau.com/).

Les donn�es utilis�es sont celles de l'[API temps r�el Transilien](https://ressources.data.sncf.com/explore/dataset/api-temps-reel-transilien/information/). Nous nous int�ressons en particulier � la ligne L dont nous allons calculer (**en temps r�el?**) les temps d'attente moyens par station et la position des trains sur la ligne et visualiser ces r�sultats dans Tableau.

Une solution alternative de visualisation de la position des train est propos�e en utilisant la librairie [Bokeh](https://bokeh.pydata.org/en/latest/) et Google Maps.

Installation
=========
Les instructions compl�tes d�installation et de configuration du projet sont fournie sur le d�p�t github sous forme de fichier markdown  dans le dossier ["install"](../../install).

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

![Extrait de transilien_ligne_l_by_code.json](./pictures/liste_stations.png)
 
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

![Exemple resultat producer](./pictures/producer.png)

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
  ![enter image description here](./pictures/dataframe.png)


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

![enter image description here](./toPandas1.png)
![enter image description here](./toPandas2.png)


> Written with [StackEdit](https://stackedit.io/).


Tableau Desktop
=============

Connexion au serveur Thrift local et sources de donn�es
-----------------------------------------------

Depuis l'onglet source de donn�es dans Tableau Desktop, ajout d'une nouvelle connexion de type **Spark SQL**. Le formulaire doit �tre rempli comme suit :

IMAGE_TO_DO Connexion_Tableau_Spark_SQL.png

Afin de r�cup�rer une vue temporaire cr��e depuis Spark, il est n�cessaire d'ajouter une **Nouvelle requ�te SQL personnalis�e** � la source de donn�es. Elle doit avoir la forme suivante :

```sql
select * from [nom_de_la_table_d�sir�e]
```

Cr�ation des diff�rentes sources de donn�es qui seront n�cessaires au projet :
1. Partie 1 :
	* **global_awt** : Temps d'attente moyen pour la ligne L ;
	* **max_awt** : Station ayant le temps d'attente moyen le plus important sur la Ligne L, il s'agit d'une *inner join* entre les tables suivantes : *max_awt* et *stations_data* ;
	* **min_awt** : Station ayant le temps d'attente moyen le plus faible sur la Ligne L, il s'agit d'une *inner join* entre les tables suivantes : *min_awt* et *stations_data* ;
	* **ordered_awt** : Stations de la ligne L avec leur temps d'attente moyen, il s'agit d'une *inner join* entre les tables suivantes : *ordered_awt* et *stations_data*.
2. Partie 2 :
	* **stations_and_trains** : Stations et trains de la ligne L avec leurs positions, il s'agit d'une *full outer join* entre les tables suivantes : *trains_progression* et *stations_data* ;
	* **stations_and_trains_with_rail** : Stations et trains de la ligne L avec leurs positions, il s'agit d'une *full outer join* entre :
		* Une *union* du fichier CSV local *courbe-des-voies_L.csv* sur lui m�me
		* Et des tables suivantes : *trains_progression* et *stations_data* ;
	*  **trains_progression** : Trains de la ligne L avec leur progression.

Les *inner join* permettent des jointures classiques.

Les *full outer join* se font sur des conditions fictives toujours fausses, par exemple 0 = 1, afin d'afficher des donn�es de diff�rentes source sur une m�me feuille dans Tableau Desktop.

Les *union* permettent de dupliquer des donn�es contenant des segments, du moins leur d�but et leur fin, afin de les afficher sous forme de ligne dans une feuille.

Dans ces trois cas, des colonnes calcul�es sont n�cessaires afin d'assurer la coh�rence des donn�es lors de leur restitution.

Partie 1
--------------------

Les feuilles suivantes sont cr��es pour cette partie :
*  **AWT** : Affichage sous forme de *carte* des donn�es de la source *ordered_awt*. Les stations sont color�es en fonction de leur temps d'attente moyen ;
* **TAB-AWT** : Affichage sous forme de *barres horizontales* des donn�es de la source *ordered_awt*. Les stations sont color�es et ordonn�es en fonction de leur temps d'attente moyen ;
* **MIN-AWT** : Affichage sous forme d'une *barre horizontale* de la donn�e de la source *min_awt*. La ligne est color�e en fonction de son temps d'attente moyen ;
* **MAX-AWT** : Affichage sous forme d'une *barre horizontale* de la donn�e de la source *max_awt*. La ligne est color�e en fonction de son temps d'attente moyen ;
* **GLO-AWT** : Affichage sous forme d'une *barre horizontale* de la donn�e de la source *global_awt*. La ligne est color�e en fonction de son temps d'attente moyen ;

Elles sont rassembl�es dans un unique tableau de bord **TAM-LIGNE-L** :

IMAGE_TO_DO TAM-LIGNE-L.png

Partie 2
--------------------

Les feuilles suivantes sont cr��es pour cette partie :
* **TRAINS-PROG** : Affichage sous forme de *barres empil�es* des donn�es de la source *trains_progression*. Les trains sont color�s en fonction de leur progression via une �chelle de couleur fixe, allant toujours de 0 � 100, et ordonn�s en fonction de leur mission ;
* **TRAINS-POS** : Affichage sous forme de *carte* des donn�es de la source *stations_and_trains*. Les stations sont diff�renci�es des trains par leur forme et leur couleur ;
* **TRAINS-POS-WITH-RAIL** : Affichage sous forme de *carte* des donn�es de la source *stations_and_trains_with_rail*. Les stations sont diff�renci�es des trains et des rails par leur forme et leur couleur. Il est n�cessaire d'avoir un axe double au niveau des lignes afin d'afficher sur une m�me feuille des *lignes* et des *formes*. La position des trains utilis�e ici est celle *courante* ;
* **TRAINS-ACCURATE-POS-WITH-RAIL** : Affichage sous forme de *carte* des donn�es de la source *stations_and_trains_with_rail*. Les stations sont diff�renci�es des trains et des rails par leur forme et leur couleur. Il est n�cessaire d'avoir un axe double au niveau des lignes afin d'afficher sur une m�me feuille des *lignes* et des *formes*. La position des trains utilis�e ici est celle *affin�e*.

Les tableaux de bord suivant sont cr��s pour cette partie :
* **POS-TRAINS-LIGNE-L** : Rassemble les feuilles *TRAINS-POS* et *TRAINS-PROG* ;

IMAGE_TO_DO POS-TRAINS-LIGNE-L.png

* **POS-TRAINS-LIGNE-L-WITH-RAIL** : Rassemble les feuilles *TRAINS-POS-WITH-RAIL* et *TRAINS-PROG* ;

IMAGE_TO_DO POS-TRAINS-LIGNE-L-WITH-RAIL.png

* **ACCURATE-POS-TRAINS-LIGNE-L-WITH-RAIL** : Rassemble les feuilles *TRAINS-ACCURATE-POS-WITH-RAIL* et *TRAINS-PROG* ;

IMAGE_TO_DO ACCURATE-POS-TRAINS-LIGNE-L-WITH-RAIL.png

* **TRAINS-LIGNE-L-WITH-RAIL** : Rassemble les feuilles *TRAINS-POS-WITH-RAIL* et *TRAINS-ACCURATE-POS-WITH-RAIL*.

IMAGE_TO_DO TRAINS-LIGNE-L-WITH-RAIL.png

Histoire
--------------------

Les diff�rents tableaux de bord pr�sent�s plus haut sont rassembl�s dans une histoire **LINE-L** qui illustre les diff�rentes parties de notre projet.

Traitement et exploitation des donn�es SNCF pour les rails
=============

T�l�chargement des donn�es sur les rails � l'URL suivante : https://ressources.data.sncf.com/explore/dataset/courbe-des-voies/table/

IMAGE_TO_DO France_Rail_Map.png

�puration des donn�es afin de ne garder que les tron�ons de la ligne L.

IMAGE_TO_DO Line_L_Rail_Map.png

Ces informations sont stock�es dans le fichier *courbe-des-voies_L.csv* et sont exploit�es via Tableau Desktop.

Extraction des g�opoints uniques de ces segments entre les diff�rentes gares de la ligne, ne sont gard�s que ceux des lignes principales (NOM_VOIE = V1).

Line_L_GeoPoint_Map.png

Calcul des suites de g�opoints des trajets de la ligne L
--------------------

� partir de la structure de la ligne :

IMAGE_TO_DO line-l.png

D�finition des branches suivantes :
* **0** : de Paris-Saint-Lazare � B�con-les-Bruy�res ;
	* **00** : de B�con-les-Bruy�res � Cergy-le-Haut ;
	* **01** : de B�con-les-Bruy�res � Saint-Cloud ;
		* **010** : de Saint-Cloud � Saint-Nom-la-Bret�che-For�t-de-Marly ;
			* **0100** : de Saint-Nom-la-Bret�che-For�t-de-Marly � Saint-Germain-en-Laye-Grande-Ceinture ;
			* **0100** : de Saint-Nom-la-Bret�che-For�t-de-Marly � Noisy-le-Roy ;
		* **011** : de Saint-Cloud � Versailles-Rive-Droite.

Ordonnancement des diff�rentes stations sur leur branche respective en allant de Paris vers la banlieue.

Idem avec les g�opoints extraits, voir plus haut.

Conception et d�veloppement d'un script **generate_geopoints_path_line_l.py** permettant � partir de ces informations de calculer tous les trajets possibles de la ligne L avec leurs g�opoints ordonn�s et de les sauvegarder dans un fichier **scnf-paths-line-l.json**. Le script se base sur une navigation r�cursive au sein d'un arbre mod�lisant la ligne.

Interpolation de la position des trains
--------------------

Les positions des trains �taient initialement calcul�es via une simple r�gle de trois � partir de :
* La position de leur gare de d�part ;
* La position de leur gare d'arriv�e ;
* Leur progression.

Nous avons �voqu� cette position comme la position **courante** au sein de ce document.

Cependant, dans le cas de trains directs entre des gares �loign�es, ils pouvaient apparaitre � des emplacements aberrants (dans la Seine, sur des champs, etc.).

Nous avons donc utilis� les informations du fichier **scnf-paths-line-l.json** afin d'interpoler leur position sur les voies ferr�es via *Scipy*. Voici un exemple d'interpolation :

IMAGE_TO_DO Interpolation.png

Au sein de ce rapport, il s'agit de la position **affin�e**. En fonction du nombre de g�opoints sur un tron�on entre deux gares, diff�rents types d'interpolation sont effectu�s :
* Peu de points : **Interpolation lin�aire**
* Beaucoup de points : **Interpolation cubique**



Conclusion
======
A inclure dans la conclusion : pour mettre ce code en production, passer le code des notebooks en scripts Python � ex�cuter � l'aide de ``Spark submit``

> Written with [StackEdit](https://stackedit.io/).
