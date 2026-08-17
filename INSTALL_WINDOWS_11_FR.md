# 🪟 Outil de Nettoyage XML — Guide d'Installation pour Windows 11

Ce guide fournit des instructions étape par étape pour installer et exécuter l'outil de nettoyage XML sur **Windows 11** exclusivement.

---

## Table des matières

- [Configuration système requise](#configuration-système-requise)
- [Étape 1 : Installer Python 3.9+](#étape-1--installer-python-39)
- [Étape 2 : Télécharger le projet](#étape-2--télécharger-le-projet)
- [Étape 3 : Créer les dossiers d'entrée/sortie](#étape-3--créer-les-dossiers-dentréesortie)
- [Étape 4 : Configurer l'environnement virtuel](#étape-4--configurer-lenvironnement-virtuel)
- [Étape 5 : Installer les dépendances](#étape-5--installer-les-dépendances)
- [Étape 6 : Exécuter l'application](#étape-6--exécuter-lapplication)
- [Dépannage](#dépannage)
- [Sujets avancés](#sujets-avancés)

---

## Configuration système requise

**Windows 11** (toute édition : Home, Pro, Enterprise, Education)

- Minimum : 4 Go de RAM, processeur 2 GHz
- Recommandé : 16+ Go de RAM, processeur multi-cœurs (4+ cœurs)
- Espace disque minimum : 500 Mo pour l'installation + espace pour vos fichiers XML
- Connexion Internet (pour télécharger Python et les dépendances)

---

## Étape 1 : Installer Python 3.9+

### Option A : Télécharger depuis python.org (Recommandé)

1. **Ouvrez votre navigateur** et allez sur [python.org/downloads](https://www.python.org/downloads/)

2. **Cliquez sur "Download Python 3.12"** (ou la dernière version 3.9+)
   - L'installateur Windows devrait se télécharger automatiquement

3. **Exécutez l'installateur** (cherchez dans votre dossier Téléchargements `python-3.12.x-amd64.exe`)

4. **✅ IMPORTANT :** Sur le premier écran, **cochez les deux cases :**
   - ✓ **Install launcher for all users**
   - ✓ **Add Python 3.12 to PATH** ← **C'est crucial !**
   
5. **Cliquez sur "Install Now"**
   - Attendez la fin de l'installation (~1 minute)
   - Cliquez sur "Disable path length limit" si demandé (optionnel, mais recommandé)

6. **Vérifiez l'installation :**
   - Appuyez sur `Win + R` pour ouvrir la boîte de dialogue Exécuter
   - Tapez `cmd` et appuyez sur Entrée
   - Tapez la commande suivante et appuyez sur Entrée :
     ```
     python --version
     ```
   - Vous devriez voir : `Python 3.12.x`

### Option B : Gestionnaire de paquets Windows (winget)

Si vous disposez de Windows 11 avec `winget` installé :

1. **Ouvrez PowerShell en tant qu'administrateur :**
   - Appuyez sur `Win`, tapez `PowerShell`
   - Clic droit sur **Windows PowerShell** → **Exécuter en tant qu'administrateur**

2. **Exécutez :**
   ```powershell
   winget install Python.Python.3.12
   ```

3. **Vérifiez :**
   ```powershell
   python --version
   ```

---

## Étape 2 : Télécharger le projet

### Option A : Utiliser Git (si vous l'avez installé)

1. **Ouvrez PowerShell** (appuyez sur `Win`, tapez `PowerShell`, appuyez sur Entrée)

2. **Naviguez vers l'endroit où vous voulez le projet :**
   ```powershell
   cd C:\Users\VotreNomUtilisateur\Documents
   ```

3. **Clonez le référentiel :**
   ```powershell
   git clone https://github.com/snoucair/XML_CALL_CLEANUP.git
   cd XML_CALL_CLEANUP
   ```

### Option B : Télécharger en ZIP (Git non nécessaire)

1. **Ouvrez le navigateur** et allez sur [github.com/snoucair/XML_CALL_CLEANUP](https://github.com/snoucair/XML_CALL_CLEANUP)

2. **Cliquez sur le bouton vert "Code"** → **Download ZIP**

3. **Extrayez le fichier ZIP :**
   - Clic droit sur le fichier `.zip` téléchargé
   - Sélectionnez **Extraire tout...**
   - Choisissez un emplacement (par ex. `C:\Users\VotreNomUtilisateur\Documents\`)
   - Cliquez sur **Extraire**

4. **Ouvrez PowerShell** et naviguez vers le dossier extrait :
   ```powershell
   cd C:\Users\VotreNomUtilisateur\Documents\XML_CALL_CLEANUP
   ```

---

## Étape 3 : Créer les dossiers d'entrée/sortie

1. **Dans le répertoire du projet**, créez deux nouveaux dossiers :

   **Utiliser PowerShell (Recommandé) :**
   ```powershell
   New-Item -ItemType Directory -Name Input -Force
   New-Item -ItemType Directory -Name Output -Force
   ```

   **Utiliser l'Explorateur de fichiers Windows :**
   - Ouvrez l'Explorateur de fichiers
   - Naviguez vers le dossier du projet
   - Clic droit → **Nouveau** → **Dossier**
   - Nommez-le `Input`
   - Répétez et nommez le deuxième `Output`

2. **Placez vos fichiers XML** dans le dossier `Input` (ou dans des sous-dossiers)

Votre structure de dossiers devrait maintenant ressembler à :

```
XML_CALL_CLEANUP/
├── Input/                 ← Mettez vos fichiers XML ici
├── Output/                ← Les résultats apparaîtront ici
├── README.md
├── Xml_Call_Cleanup.py
├── requirements.txt
└── .gitignore
```

---

## Étape 4 : Configurer l'environnement virtuel

Un environnement virtuel garde les dépendances isolées de votre Python système.

1. **Ouvrez PowerShell** dans le répertoire du projet :
   - Appuyez sur `Win + X` → **Terminal (Admin)** ou
   - Appuyez sur `Win`, tapez `PowerShell`, clic droit → **Exécuter en tant qu'administrateur**

2. **Naviguez vers le projet :**
   ```powershell
   cd C:\Users\VotreNomUtilisateur\Documents\XML_CALL_CLEANUP
   ```

3. **Créez l'environnement virtuel :**
   ```powershell
   python -m venv venv
   ```
   Attendez ~10 secondes pour la fin.

4. **Activez l'environnement virtuel :**
   ```powershell
   .\venv\Scripts\Activate.ps1
   ```

   Si vous obtenez une erreur concernant la politique d'exécution :
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```
   Puis réessayez la commande d'activation.

   **✅ Succès :** Votre prompt PowerShell devrait maintenant commencer par `(venv)` :
   ```
   (venv) C:\Users\VotreNomUtilisateur\Documents\XML_CALL_CLEANUP>
   ```

---

## Étape 5 : Installer les dépendances

Avec l'environnement virtuel activé (vous devez voir `(venv)` dans votre prompt) :

```powershell
pip install --upgrade pip
pip install streamlit lxml
```

**Résultat attendu :** Plusieurs installations de paquets, se terminant par quelque chose comme :
```
Successfully installed streamlit-1.xx.0 lxml-4.xx.0 ...
```

> **Note :** `lxml` est optionnel mais fournit une analyse XML ~3–5× plus rapide. Si l'installation échoue, l'application utilisera l'analyseur intégré `xml.etree.ElementTree` de Python.

---

## Étape 6 : Exécuter l'application

1. **Assurez-vous que l'environnement virtuel est activé :**
   - Votre prompt PowerShell devrait afficher `(venv)` au début
   - Sinon, exécutez : `.\venv\Scripts\Activate.ps1`

2. **Démarrez l'application :**
   ```powershell
   streamlit run Xml_Call_Cleanup.py
   ```

3. **Le navigateur s'ouvre automatiquement :**
   - Sinon, ouvrez manuellement `http://localhost:8501`
   - L'application devrait se charger avec un thème sombre et des accents violets

4. **Pour arrêter l'application :**
   - Appuyez sur `Ctrl + C` dans PowerShell

---

## Dépannage

### Problème : "python is not recognized"

**Solution :** Python n'a pas été ajouté au PATH lors de l'installation.

1. **Réinstallez Python :**
   - Téléchargez depuis [python.org](https://www.python.org/downloads/)
   - Lors de l'installation, **VOUS DEVEZ COCHER** ✓ "Add Python 3.12 to PATH"
   - Redémarrez PowerShell après la réinstallation

2. **Correction manuelle du PATH (Avancé) :**
   - Appuyez sur `Win + X` → **Paramètres**
   - Recherchez **"Variables d'environnement"**
   - Cliquez sur **"Modifier les variables d'environnement pour votre compte"**
   - Cliquez sur **"Nouveau"** et ajoutez : `C:\Users\VotreNomUtilisateur\AppData\Local\Programs\Python\Python312`
   - Cliquez sur **OK** et redémarrez PowerShell

### Problème : Erreur de politique d'exécution PowerShell

**Solution :**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Problème : "pip is not recognized"

**Solution :** Assurez-vous que Python et l'environnement virtuel sont correctement configurés :
```powershell
python -m pip --version
```

Si cela échoue, réinstallez Python avec l'option PATH.

### Problème : "streamlit is not installed"

**Solution :** Assurez-vous que l'environnement virtuel est activé :
```powershell
(venv) C:\path\to\project> pip install streamlit lxml
```

### Problème : Le navigateur ne s'ouvre pas automatiquement

**Solution :** Naviguez manuellement vers `http://localhost:8501` dans votre navigateur.

### Problème : "ModuleNotFoundError: No module named 'lxml'"

**C'est OK.** L'application utilisera l'analyseur XML intégré de Python. lxml est optionnel mais plus rapide.

---

## Sujets avancés

### Exécuter l'application sans activation à chaque fois

Créez un fichier batch pour automatiser le démarrage :

1. **Ouvrez le Bloc-notes** (appuyez sur `Win`, tapez `Bloc-notes`, appuyez sur Entrée)

2. **Copiez et collez :**
   ```batch
   @echo off
   cd /d "%~dp0"
   call venv\Scripts\activate.bat
   streamlit run Xml_Call_Cleanup.py
   pause
   ```

3. **Enregistrez sous** `run_app.bat` dans votre dossier de projet

4. **Double-cliquez sur `run_app.bat`** à l'avenir pour démarrer l'application instantanément

### Exécuter avec un nombre de travailleurs spécifique

Pour remplacer la détection CPU de l'application et utiliser un nombre spécifique de travailleurs :

```powershell
streamlit run Xml_Call_Cleanup.py -- --workers 4
```

(Remplacez `4` par votre nombre souhaité de processus parallèles)

### Mettre à jour les dépendances

Pour obtenir les dernières versions de Streamlit et lxml :

```powershell
pip install --upgrade streamlit lxml
```

### Désinstaller l'application

Pour supprimer complètement tout :

1. **Supprimez le dossier du projet :**
   ```powershell
   Remove-Item -Recurse -Force "C:\path\to\XML_CALL_CLEANUP"
   ```

2. **Python reste installé** (pour le supprimer : Paramètres → Applications → Fonctionnalités des applications → Python 3.12)

---

## Obtenir de l'aide

Si vous rencontrez des problèmes :

1. **Consultez le [README principal](README.md)** pour le dépannage général
2. **Vérifiez `Log.log`** dans le dossier du projet pour les détails des erreurs
3. **Vérifiez l'installation de Python :** `python --version`
4. **Vérifiez les dépendances :** `pip list | findstr streamlit`

---

**Bon nettoyage ! 🎉**
