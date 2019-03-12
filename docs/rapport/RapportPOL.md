Tableau Desktop
=============

Connexion au serveur Thrift local et sources de données
-----------------------------------------------

Depuis l'onglet source de données dans Tableau Desktop, ajout d'une nouvelle connexion de type **Spark SQL**. Le formulaire doit être rempli comme suit :

IMAGE_TO_DO Connexion_Tableau_Spark_SQL.png

Afin de récupérer une vue temporaire créée depuis Spark, il est nécessaire d'ajouter une **Nouvelle requête SQL personnalisée** à la source de données. Elle doit avoir la forme suivante :

```sql
select * from [nom_de_la_table_désirée]
```

Création des différentes sources de données qui seront nécessaires au projet :
1. Partie 1 :
	* **global_awt** : Temps d'attente moyen pour la ligne L ;
	* **max_awt** : Station ayant le temps d'attente moyen le plus important sur la Ligne L, il s'agit d'une *inner join* entre les tables suivantes : *max_awt* et *stations_data* ;
	* **min_awt** : Station ayant le temps d'attente moyen le plus faible sur la Ligne L, il s'agit d'une *inner join* entre les tables suivantes : *min_awt* et *stations_data* ;
	* **ordered_awt** : Stations de la ligne L avec leur temps d'attente moyen, il s'agit d'une *inner join* entre les tables suivantes : *ordered_awt* et *stations_data*.
2. Partie 2 :
	* **stations_and_trains** : Stations et trains de la ligne L avec leurs positions, il s'agit d'une *full outer join* entre les tables suivantes : *trains_progression* et *stations_data* ;
	* **stations_and_trains_with_rail** : Stations et trains de la ligne L avec leurs positions, il s'agit d'une *full outer join* entre :
		* Une *union* du fichier CSV local *courbe-des-voies_L.csv* sur lui même
		* Et des tables suivantes : *trains_progression* et *stations_data* ;
	*  **trains_progression** : Trains de la ligne L avec leur progression.

Les *inner join* permettent des jointures classiques.

Les *full outer join* se font sur des conditions fictives toujours fausses, par exemple 0 = 1, afin d'afficher des données de différentes source sur une même feuille dans Tableau Desktop.

Les *union* permettent de dupliquer des données contenant des segments, du moins leur début et leur fin, afin de les afficher sous forme de ligne dans une feuille.

Dans ces trois cas, des colonnes calculées sont nécessaires afin d'assurer la cohérence des données lors de leur restitution.

Partie 1
--------------------

Les feuilles suivantes sont créées pour cette partie :
*  **AWT** : Affichage sous forme de *carte* des données de la source *ordered_awt*. Les stations sont colorées en fonction de leur temps d'attente moyen ;
* **TAB-AWT** : Affichage sous forme de *barres horizontales* des données de la source *ordered_awt*. Les stations sont colorées et ordonnées en fonction de leur temps d'attente moyen ;
* **MIN-AWT** : Affichage sous forme d'une *barre horizontale* de la donnée de la source *min_awt*. La ligne est colorée en fonction de son temps d'attente moyen ;
* **MAX-AWT** : Affichage sous forme d'une *barre horizontale* de la donnée de la source *max_awt*. La ligne est colorée en fonction de son temps d'attente moyen ;
* **GLO-AWT** : Affichage sous forme d'une *barre horizontale* de la donnée de la source *global_awt*. La ligne est colorée en fonction de son temps d'attente moyen ;

Elles sont rassemblées dans un unique tableau de bord **TAM-LIGNE-L** :

IMAGE_TO_DO TAM-LIGNE-L.png

Partie 2
--------------------

Les feuilles suivantes sont créées pour cette partie :
* **TRAINS-PROG** : Affichage sous forme de *barres empilées* des données de la source *trains_progression*. Les trains sont colorés en fonction de leur progression via une échelle de couleur fixe, allant toujours de 0 à 100, et ordonnés en fonction de leur mission ;
* **TRAINS-POS** : Affichage sous forme de *carte* des données de la source *stations_and_trains*. Les stations sont différenciées des trains par leur forme et leur couleur ;
* **TRAINS-POS-WITH-RAIL** : Affichage sous forme de *carte* des données de la source *stations_and_trains_with_rail*. Les stations sont différenciées des trains et des rails par leur forme et leur couleur. Il est nécessaire d'avoir un axe double au niveau des lignes afin d'afficher sur une même feuille des *lignes* et des *formes*. La position des trains utilisée ici est celle *courante* ;
* **TRAINS-ACCURATE-POS-WITH-RAIL** : Affichage sous forme de *carte* des données de la source *stations_and_trains_with_rail*. Les stations sont différenciées des trains et des rails par leur forme et leur couleur. Il est nécessaire d'avoir un axe double au niveau des lignes afin d'afficher sur une même feuille des *lignes* et des *formes*. La position des trains utilisée ici est celle *affinée*.

Les tableaux de bord suivant sont créés pour cette partie :
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

Les différents tableaux de bord présentés plus haut sont rassemblés dans une histoire **LINE-L** qui illustre les différentes parties de notre projet.

Traitement et exploitation des données SNCF pour les rails
=============

Téléchargement des données sur les rails à l'URL suivante : https://ressources.data.sncf.com/explore/dataset/courbe-des-voies/table/

IMAGE_TO_DO France_Rail_Map.png

Épuration des données afin de ne garder que les tronçons de la ligne L.

IMAGE_TO_DO Line_L_Rail_Map.png

Ces informations sont stockées dans le fichier *courbe-des-voies_L.csv* et sont exploitées via Tableau Desktop.

Extraction des géopoints uniques de ces segments entre les différentes gares de la ligne, ne sont gardés que ceux des lignes principales (NOM_VOIE = V1).

Line_L_GeoPoint_Map.png

Calcul des suites de géopoints des trajets de la ligne L
--------------------

À partir de la structure de la ligne :

IMAGE_TO_DO line-l.png

Définition des branches suivantes :
* **0** : de Paris-Saint-Lazare à Bécon-les-Bruyères ;
	* **00** : de Bécon-les-Bruyères à Cergy-le-Haut ;
	* **01** : de Bécon-les-Bruyères à Saint-Cloud ;
		* **010** : de Saint-Cloud à Saint-Nom-la-Bretèche-Forêt-de-Marly ;
			* **0100** : de Saint-Nom-la-Bretèche-Forêt-de-Marly à Saint-Germain-en-Laye-Grande-Ceinture ;
			* **0100** : de Saint-Nom-la-Bretèche-Forêt-de-Marly à Noisy-le-Roy ;
		* **011** : de Saint-Cloud à Versailles-Rive-Droite.

Ordonnancement des différentes stations sur leur branche respective en allant de Paris vers la banlieue.

Idem avec les géopoints extraits, voir plus haut.

Conception et développement d'un script **generate_geopoints_path_line_l.py** permettant à partir de ces informations de calculer tous les trajets possibles de la ligne L avec leurs géopoints ordonnés et de les sauvegarder dans un fichier **scnf-paths-line-l.json**. Le script se base sur une navigation récursive au sein d'un arbre modélisant la ligne.

Interpolation de la position des trains
--------------------

Les positions des trains étaient initialement calculées via une simple règle de trois à partir de :
* La position de leur gare de départ ;
* La position de leur gare d'arrivée ;
* Leur progression.

Nous avons évoqué cette position comme la position **courante** au sein de ce document.

Cependant, dans le cas de trains directs entre des gares éloignées, ils pouvaient apparaitre à des emplacements aberrants (dans la Seine, sur des champs, etc.).

Nous avons donc utilisé les informations du fichier **scnf-paths-line-l.json** afin d'interpoler leur position sur les voies ferrées via *Scipy*. Voici un exemple d'interpolation :

IMAGE_TO_DO Interpolation.png

Au sein de ce rapport, il s'agit de la position **affinée**. En fonction du nombre de géopoints sur un tronçon entre deux gares, différents types d'interpolation sont effectués :
* Peu de points : **Interpolation linéaire**
* Beaucoup de points : **Interpolation cubique**
