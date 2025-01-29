# Script permettant de copier automatiquement les données du bureau et des documents 
# d'un PC pour les sauvegarder dans un serveur

import shutil
import os
import logging
from pathlib import Path
import socket
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# Configuration du logging (uniquement console)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

# Configuration globale
EXTENSIONS_DOCUMENTS = {'.txt', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.pps', '.ppsx'}
EXTENSIONS_BUREAU = {'.txt', '.doc', '.docx', '.pdf', '.xls', '.xlsx', '.rtf', '.ppt', '.pptx', '.pps', '.ppsx'}
DOSSIERS_A_IGNORER = {'Ma musique', 'Mes images', 'Mes vidéos', 'AppData', 'Application Data', 'Local Settings'}

def verifier_connexion_serveur(chemin_serveur):
    """Vérifie si le serveur est accessible"""
    try:
        # Identifiants fixes
        username = "Nom d'utilisateur de votre serveur"
        password = "Mot de passe"
        
        # Déconnecter et reconnecter au serveur
        os.system('net use * /delete /y >nul 2>&1')
        time.sleep(1)
        
        serveur_base = "Chemin d'acces vers votre serveur"
        resultat = os.system(f'net use {serveur_base} /user:{username} "{password}" >nul 2>&1')
        
        if resultat != 0:
            logging.error("Échec de la connexion au serveur")
            return False
            
        os.makedirs(chemin_serveur, exist_ok=True)
        return True
    except Exception as e:
        logging.error(f"Impossible d'accéder au serveur: {e}")
        return False

def est_fichier_autorise(fichier, est_documents):
    """Vérifie si le fichier a une extension autorisée"""
    extension = fichier.suffix.lower()
    return extension in (EXTENSIONS_DOCUMENTS if est_documents else EXTENSIONS_BUREAU)

def copier_fichier(source, destination, est_documents):
    """Copie un seul fichier si autorisé"""
    try:
        if est_fichier_autorise(source, est_documents):
            shutil.copy2(source, destination)
            logging.info(f"Fichier copié: {source.name}")
            return True
    except Exception as e:
        logging.warning(f"Erreur lors de la copie de {source.name}: {e}")
    return False

def copier_dossier(src, dest, est_documents=False):
    """Copie un dossier avec gestion des threads"""
    try:
        src_path = Path(src)
        dest_path = Path(dest)
        dest_path.mkdir(exist_ok=True)

        fichiers_a_copier = []
        for item in src_path.iterdir():
            if item.name in DOSSIERS_A_IGNORER:
                continue
                
            dest_item = dest_path / item.name
            
            # Pour Documents, on ignore les sous-dossiers
            if item.is_dir():
                if not est_documents:  # Copier les sous-dossiers seulement pour le Bureau
                    copier_dossier(item, dest_item, est_documents)
                else:
                    logging.info(f"Dossier ignoré dans Documents: {item.name}")
                continue
                
            # Traitement des fichiers
            fichiers_a_copier.append((item, dest_item))

        # Copie parallèle des fichiers
        if fichiers_a_copier:  # Vérifier s'il y a des fichiers à copier
            with ThreadPoolExecutor(max_workers=4) as executor:
                executor.map(lambda x: copier_fichier(x[0], x[1], est_documents), fichiers_a_copier)
            
        return True
    except Exception as e:
        logging.error(f"Erreur lors de la copie du dossier {src}: {e}")
        return False

def get_user_info():
    """Récupère et vérifie les informations de l'utilisateur"""
    try:
        # Récupérer le nom d'utilisateur
        username = (
            os.getenv('USERNAME') or 
            os.getenv('USER') or 
            Path.home().name
        )
        
        # Si l'utilisateur est User ou Administrateur, utiliser le nom du PC
        if username.lower() in ['user', 'administrateur', 'administrator']:
            pc_name = socket.gethostname()
            logging.info(f"Session générique détectée ({username}), utilisation du nom du PC: {pc_name}")
            username = pc_name
            
        # Vérifier que le nom d'utilisateur est valide
        if not username or username in ['Default', 'Public', 'All Users']:
            raise ValueError("Nom d'utilisateur invalide")
            
        # Vérifier que le dossier utilisateur existe
        user_path = Path(f"C:\\Users\\{os.getenv('USERNAME')}")  # Toujours utiliser le vrai nom d'utilisateur pour le chemin
        if not user_path.exists():
            raise ValueError(f"Dossier utilisateur introuvable: {user_path}")
            
        # Vérifier les dossiers essentiels
        essential_folders = {
            'Bureau': user_path / 'Desktop',
            'Documents': user_path / 'Documents',
            'Téléchargements': user_path / 'Downloads'
        }
        
        for name, path in essential_folders.items():
            if not path.exists():
                logging.warning(f"Dossier {name} introuvable: {path}")
                
        return username, user_path
        
    except Exception as e:
        logging.error(f"Erreur lors de la récupération des informations utilisateur: {e}")
        raise

def get_unique_folder_name(base_path, username):
    """Crée un nom de dossier unique en ajoutant un numéro si nécessaire"""
    folder_path = base_path / username
    if not folder_path.exists():
        return folder_path
    
    # Si le dossier existe, ajouter un numéro
    counter = 1
    while True:
        new_path = base_path / f"{username}_{counter}"
        if not new_path.exists():
            return new_path
        counter = counter +1

def main():
    try:
        # Récupérer et vérifier les informations utilisateur
        username, user_path = get_user_info()
        logging.info(f"Démarrage sauvegarde pour l'utilisateur: {username}")

        # Chemins source et destination
        bureau_path = user_path / "Desktop"
        documents_path = user_path / "Documents"
        telechargements_path = user_path / "Downloads"
        
        # Utiliser le nom de la session pour le dossier de sauvegarde
        serveur_path = Path(r'\\192.168.100.250\sauvegarde') / username

        if not verifier_connexion_serveur(serveur_path):
            return

        # Création des dossiers de destination
        backup_bureau = serveur_path / "Bureau"
        backup_documents = serveur_path / "Documents"
        backup_telechargements = serveur_path / "Telechargements"

        # Copie parallèle des dossiers principaux
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(copier_dossier, bureau_path, backup_bureau, False),
                executor.submit(copier_dossier, documents_path, backup_documents, True),
                executor.submit(copier_dossier, telechargements_path, backup_telechargements, True)
            ]
            
        logging.info("Sauvegarde terminée avec succès")
        
    except Exception as e:
        logging.error(f"Erreur générale: {e}")
        time.sleep(5)

if __name__ == "__main__":
    start_time = time.time()
    main()
    logging.info(f"Temps total d'exécution: {time.time() - start_time:.2f} secondes")
    time.sleep(3)  # Pause de 3 secondes pour voir le message final
    os.system('exit')  # Ferme la console








































































