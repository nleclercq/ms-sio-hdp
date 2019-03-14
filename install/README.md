HOW TO
=========

Au préalable, une fois la HDP 2.6.5 installée et le mot de passe root modifié.

Connexion ssh en root sur le container HDP Sandbox
```sh
ssh root@localhost -p 2222
```

Modification de la durée maximum de connexion ssh en tant que user root :
```sh
sed -i -e 's/#ClientAliveInterval 0/ClientAliveInterval 120/g' /etc/ssh/sshd_config
sed -i -e 's/#ClientAliveCountMax 3/ClientAliveCountMax 720/g' /etc/ssh/sshd_config
service sshd restart
```

Vérification de la bonne configuration de sa timezone
```sh
ls -l /etc/localtime
```

Si le résultat n'est pas :
```sh
lrwxrwxrwx 1 root root 34 Mar 11 15:22 /etc/localtime -> ../usr/share/zoneinfo/Europe/Paris
```

Alors il est nécessaire d'effectuer la commande suivante :
```sh
timedatectl set-timezone Europe/Paris
```

Telechargement de miniconda
```sh
curl -O https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
```

Installation de paquets
```sh
yum install -y bzip2 git
```

Installation de miniconda
```sh
chmod +x Miniconda3-latest-Linux-x86_64.sh
 ./Miniconda3-latest-Linux-x86_64.sh # Répondre yes tout le temps (surtout pour le .bashrc)
```

Nécessaire si absence de redémarrage pour la suite
```sh
export PATH=/root/miniconda3/bin:$PATH
```

Installation des librairies via pip
```sh
pip install npm
```

Installation des librairies via conda
```sh
conda install -c conda-forge -y jupyterlab kafka-python pyspark xmltodict 

conda install -c conda-forge -y nodejs bokeh ipywidgets scipy 
```

Installation des extension jupyterlab de ipywidgets & bokeh
```sh
jupyter labextension install @jupyter-widgets/jupyterlab-manager

jupyter labextension install jupyterlab_bokeh
```

Vérification que jupyter fonctionne
```sh
jupyter-lab --no-browser --ip=0.0.0.0 --port 60000 --allow-root
```

Via votre navigateur accéder à http://localhost:60000
* Copie du token qui apparait dans la console (token=[token_à_récupérer])
* Le coller dans le navigateur (champ token) et renseigner un mot de passe associé
* Puis cliquer sur "Login and set new password"

**Génèration d'une erreur 500, ne pas en tenir compte le mot de passe a bien été configuré**

Accéder, pour cette fois seulement, à jupyter via votre navigateur grâce  à l'url : http://localhost:60000

Intégration d'une clé RSA à son compte GitHub (source : https://help.github.com/articles/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent/)
```sh
ssh-keygen -t rsa -b 4096 -C "[votre_mail]" # Génération par defaut d'une clé rsa dans ~/.ssh/
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_rsa
cat ~/.ssh/id_rsa.pub # Copier la totatlité du texte (tout sur une ligne mail compris)
# Aller dans GitHub > Profil > Setting > SSH and GPG keys > New SSH Key
```

Récupération du repository git dans le conteneur (positionnement dans le répertoire /root)
```sh
cd /root
git clone https://github.com/nleclercq/ms-sio-hdp.git
cd prj-hdp-ms-sio/
git checkout [nom_branche] # Changement de branche
git fetch origin # Synchronisation de la branche courante et du master
git rebase origin/master
git push
```

Ajout les droits d'execution au script jupyspark
```sh
chmod +x /root/ms-sio-hdp/jupyter/jupyspark
```

Création d'un lien symbolique vers le /bin d'anaconda
```sh
ln -s /root/ms-sio-hdp/jupyter/jupyspark /root/miniconda3/bin
```

Lancement de jupyspark afin de tester
```sh
jupyspark
```

De nouveau dans jupyter :
1. Exécution de ms-sio-hdp/api-transilier/api-transilien-sncf-data.ipynb => Des .json sont créés dans le répertoire
2. Exécution de ms-sio-hdp/api-transilier/api-transilien-producer.ipynb en suivant la procédure permettant d'intégrer le ou les mots de passe
3. Exécution de ms-sio-hdp/api-transilier/api-transilien-consumer.ipynb

Modification de la durée de rétention des messages à 8h dans kafka pour notre topic :
```sh
cd /usr/hdp/current/kafka-broker
./bin/kafka-topics.sh --zookeeper localhost:2181 --alter --topic transilien-02 --config retention.ms=28800000
```

Récupération du repository git sur votre machine locale
```sh
cd /[répertoire de votre choix]
git clone https://github.com/nleclercq/ms-sio-hdp.git
```

Connexion à Tableau, s'assurer que le connecteur Spark SQL est renseigné comme suit pour toutes les sources de données du fichier .twb :
* Serveur : localhost
* Port : 10015
* Type : SparkThriftServer (Spark 1.1 et ultérieur)
* Authentification : Nom d'utilisateur
* Transport : SASL
* Nom d'utilisateur hive
