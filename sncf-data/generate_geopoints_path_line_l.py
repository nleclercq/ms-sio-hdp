# Import des packages et librairies nécessaires au bon fonctionnement du script
import csv
import math
import json
from copy import copy

# Définition de la classe Station
class Station:
    def __init__(self, code, label, latitude, longitude, branch=None, order=None, parentPath=None, childPath=None):
        self.code = code
        self.label = label
        self.localisation = {"latitude": latitude, "longitude": longitude}
        self.branch = branch
        self.order = order
        self.parentPath = parentPath
        self.childPath = childPath
    
    # Setter de la branche de la station
    def setBranch(self, branch):
        self.branch = branch

    # Setter de l'odre de la station
    def setOrder(self, order):
        self.order = order

    # Setter du chemin parent
    def setParentPath(self, parentPath):
        self.parentPath = parentPath

    # Affichage d'une station sous forme de chaine de caractères
    def __str__(self):
        res = self.code + " - " + self.label + " - " + str(self.localisation)
        res += "" if not self.branch else " - " + self.branch
        res += "" if self.order == None else " - " + str(self.order)
        #res += "" if not self.parentPath else " - " + str(self.parentPath)
        #res += "" if not self.childPath else " - " + str(self.childPath)
        return res

# Définition de la classe chemin
class Path():
    def __init__(self, geoPoints, branch, upStation, downStation):
        self.upStation = upStation
        self.downStation = downStation
        self.geoPoints = geoPoints
        self.branch = branch

    # Affichage d'un chemin  sous forme de chaine de caractères
    def __str__(self):
        return "[" + str(self.upStation.code) + " - " + str(sorted(self.geoPoints)) + " - " + str(self.downStation.code) + "]"

# Définition récursive du chemin complet entre deux stations
def pathBetweenStations(current_stat, arrival_stat):

    # Initialisation de la réponse
    res = []
    res.append(copy(current_stat.localisation))

    # Si la branche de la station courante est plus courte que celle d'arrivée, cela signifie que l'on va de Paris vers la banlieue et donc que la station courante est en amont de celle d'arrivée
    if len(current_stat.branch) < len(arrival_stat.branch):

        # Si les deux stations sont sur des branches des connexes, alors il est nécessaire d'avancer sur la ligne en allant vers la banlieue
        if current_stat.branch[:len(current_stat.branch)] == arrival_stat.branch[:len(current_stat.branch)]:
            
            # Si la station courante ne dispose que d'un unique chemin vers la banlieue
            if len(current_stat.childPath) == 1:

                # Récupération des géopoints du chemin vers la prochaine station de banlieue
                for point in sorted(current_stat.childPath[0].geoPoints):
                    res.append(copy(current_stat.childPath[0].geoPoints[point]))
	
                # Appel récursif entre la station suivante de banlieue et la station d'arrivée
                res += pathBetweenStations(current_stat.childPath[0].downStation, arrival_stat)
                return res

            # Sinon la station courante dispose de plusieurs chemin vers la banlieue (embranchement)
            else:

                # Sélection du bon chemin à prendre au regard de la branche de la station d'arrivée
                selected_child = int(arrival_stat.branch[len(current_stat.branch)])
                
                # Récupération des géopoints du chemin vers la prochaine station de banlieue
                for point in sorted(current_stat.childPath[selected_child].geoPoints):
                    res.append(copy(current_stat.childPath[selected_child].geoPoints[point]))
                
                # Appel récursif entre la station suivante de banlieue et la station d'arrivée		
                res += pathBetweenStations(current_stat.childPath[selected_child].downStation, arrival_stat)
                return res
        
        # Sinon les deux stations ne sont pas sur des branches connexes, alors il est nécessaire de remonter la ligne vers Paris afin de retrouver le bon embranchement qui permettra d'avancer vers la station de banlieue désirée
        else:

            # Récupération des géopoints du chemin vers la prochaine station en direction de Paris, nécéssité de récupérer ces points en ordre inverse car ils sont stockés de Paris vers la banlieue dans notre modèle
            for point in reversed(sorted(current_stat.parentPath.geoPoints)):
                res.append(copy(current_stat.parentPath.geoPoints[point]))

            # Appel récursif entre la station suivante vers Paris et la station d'arrivée
            res += pathBetweenStations(current_stat.parentPath.upStation, arrival_stat)
            return res

    # Sinon si la branche de la station courante est plus longue que celle d'arrivée, cela signifie que l'on va de la banlieue vers Paris et donc que la satation courante est en avale de celle d'arrivée
    elif len(current_stat.branch) > len(arrival_stat.branch):

        # Récupération des géopoints du chemin vers la prochaine station en direction de Paris, nécéssité de récupérer ces points en ordre inverse car ils sont stockés de Paris vers la banlieue dans notre modèle
        for point in reversed(sorted(current_stat.parentPath.geoPoints)):
            res.append(copy(current_stat.parentPath.geoPoints[point]))

        # Appel récursif entre la station suivante vers Paris et la station d'arrivée
        res += pathBetweenStations(current_stat.parentPath.upStation, arrival_stat)
        return res

    # Si les branches des deux stations sont de même taille, alors les deux stations sont soit sur la même branche soit sur des branches différentes de même niveau sur la ligne
    else:

        # Si les deux stations sont sur la même branche
        if current_stat.branch == arrival_stat.branch:

            # Si les deux stations ont également le même ordre, alors elles sont identiques
            if current_stat.order == arrival_stat.order:

                # Le trajet est terminé, fin des appels récursifs
                return res

            # Si la station courante a un odre plus faible que celui de la station d'arrivée, cela signifie que l'on va de Paris vers la banlieue et donc que la station courante est en amont de celle d'arrivée
            elif current_stat.order < arrival_stat.order:

                # Récupération des géopoints du chemin vers la prochaine station de banlieue
                for point in sorted(current_stat.childPath[0].geoPoints):
                    res.append(copy(current_stat.childPath[0].geoPoints[point]))

                # Appel récursif entre la station suivante de banlieue et la station d'arrivée
                res += pathBetweenStations(current_stat.childPath[0].downStation, arrival_stat)
                return res

            # Sinon la station courante a un ordre plus grand que celui de la station d'arrivée, cela signifie que l'on va de la banlieue vers Paris et donc que la satation courante est en avale de celle d'arrivée
            else:

                # Récupération des géopoints du chemin vers la prochaine station en direction de Paris, nécéssité de récupérer ces points en ordre inverse car ils sont stockés de Paris vers la banlieue dans notre modèle
                for point in reversed(sorted(current_stat.parentPath.geoPoints)):
                    res.append(copy(current_stat.parentPath.geoPoints[point]))

                # Appel récursif entre la station suivante vers Paris et la station d'arrivée
                res += pathBetweenStations(current_stat.parentPath.upStation, arrival_stat)
                return res

        # Sinon les deux stations sont sur des branches différentes de même niveau sur la ligne, alors il est nécessaire de remonter la ligne vers Paris afin de retrouver le bon embranchement qui permettra d'avancer vers la station de banlieue désirée
        else:

            # Récupération des géopoints du chemin vers la prochaine station en direction de Paris, nécéssité de récupérer ces points en ordre inverse car ils sont stockés de Paris vers la banlieue dans notre modèle
            for point in reversed(sorted(current_stat.parentPath.geoPoints)):
                res.append(copy(current_stat.parentPath.geoPoints[point]))

            # Appel récursif entre la station suivante vers Paris et la station d'arrivée
            res += pathBetweenStations(current_stat.parentPath.upStation, arrival_stat)
            return res

# Définition des différents path des fichiers contenant les données
file_gare = "./transilien_line_l_stations_by_code.csv"
file_gare_path_order = "./transilien_line_l_stations_order.csv"
file_path_point_order = "./transilien_line_l_path_point.csv"
file_result = "../api-transilien/scnf-paths-line-l.json"

# Initialisation d'un dictionnaire vide qui contiendra toutes les gares de la ligne L
gares = {}

# Lecture du fichier contenant les codes, libellés, latitudes et longitudes des gares de la ligne L
with open(file_gare, "r") as f:
    reader = csv.reader(f)

    # Pour chaque ligne du fichier sauf la première (en-tête)
    for i, line in enumerate(reader):
        if i != 0:

           # Ajour de la gare correspondante au dictionnaire
            gares[str(line[0])] = Station(str(line[0]), str(line[1]), str(line[2]), str(line[3])) 

# Lecture du fichier contenant la branche et l'ordre des gares de la ligne L
with open(file_gare_path_order, "r") as f:
    reader = csv.reader(f)

    # Pour chaque ligne du fichier sauf la première (en-tête)
    for i, line in enumerate(reader):
        if i != 0:

            # Association des branches et ordres respectifs aux gares du dictionnaire
            gares[str(line[0])].setBranch(str(line[1]))
            gares[str(line[0])].setOrder(int(line[2]))

# Initialisation d'un dictionnaire vide qui contiendra tous les chemins de la ligne L
paths = {}

# Lecture du fichier contenant les géopoints des différents chemins de la ligne L, par chemin on entend ici ceux reliant deux gares de la ligne
with open(file_path_point_order, "r") as f:
    reader = csv.reader(f)

     # Pour chaque ligne du fichier sauf la première (en-tête)
    for i, line in enumerate(reader):
        if i != 0 :

            # Identification du chemin décrit par la ligne courante
            current_path = str(line[0]) + "-" + str(line[1])
            departure_gare = str(line[0])
            arrival_gare = str(line[1])

            # Si chemin n'est pas déjà renseigné dans le dictionnaire
            if not current_path in paths.keys():

                # Ajout du chemin courant au dictionnaire
                paths[current_path] = Path({}, str(line[2]), gares[departure_gare], gares[arrival_gare])

            # Ajout du géopoint courant au chemin associé dans le dictionnaire
            paths[current_path].geoPoints[int(line[4])] = {"latitude":str(line[10]), "longitude":str(line[9])}

# Pour chaque chemin contenu dans le dictionnaire
for path in paths.values():

    # Association du chemin courant à la station avale (vers la banlieue) qui lui est rattaché 
    gares[path.downStation.code].setParentPath(path)

    # Si la station amont (vers Paris) qui lui est rattaché n'a pas déjà de chemin associé
    if not gares[path.upStation.code].childPath:

        # Association du chemin courant à la station amont (vers Paris) qui lui est rattaché en tant que chemin unique, il ne s'agit donc pas d'un embranchement
        gares[path.upStation.code].childPath = {}
        gares[path.upStation.code].childPath[0] = path

    # Sinon la station amont (vers Paris) est un embranchement avec plusieurs chemins de banlieue possibles
    else:
	
        # Identification de la branche de destination pour le chemin de banlieue déjà rattaché à la station amont (vers Paris) afin de déterminer sa position dans l'embranchement
        selected_child = int(gares[path.upStation.code].childPath[0].branch[-1])

        # Réassociation de ce chemin à la station amont (vers Paris) qui lui est rattaché en tant que chemin possible vers une branche connue pour cet embranchement
        gares[path.upStation.code].childPath[selected_child] = gares[path.upStation.code].childPath[0]

        # Identication de la branche de destination pour le chemin courant qui sera attché à la station amont (vers Paris) afin de déterminer sa position dans l'embranchement
        selected_child = int(str(path.branch)[-1])

        # Association du chemin courant à la station amont (vers Paris) en tant que chemin possible vers une branche connue pour cet embranchement
        gares[path.upStation.code].childPath[selected_child] = path

# Initialisation d'un dictionnaire vide qui contiendra tous les trajets possibles sur la ligne L
all_known_paths = {}

# Pour chaque gare de la ligne
for gare_departure in gares.values():

    # Pour chaque gare de la ligne
    for gare_arrival in gares.values():

        # Identification du chemin courant
        current_path = gare_departure.code + "-" + gare_arrival.code

        # Renseignement du trajet dans le dictionnaire
        all_known_paths[current_path] = {}
        all_known_paths[current_path]["departure"] = gare_departure.code
        all_known_paths[current_path]["arrival"] = gare_arrival.code
        all_known_paths[current_path]["geoPoints"] = pathBetweenStations(gare_departure, gare_arrival)
        all_known_paths[current_path]["number_step"] = len(all_known_paths[current_path]["geoPoints"])

# Sauvegarde du dictionnaire contenant tous les trajets possibles de la ligne L sous forme de JSON
with open(file_result, 'w') as f:
    json.dump(all_known_paths, f)
