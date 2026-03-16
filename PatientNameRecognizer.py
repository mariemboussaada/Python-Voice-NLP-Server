# PatientNameRecognizer.py - Reconnaissance des noms de patients à partir de la base de données
from pymongo import MongoClient
import re
import spacy


class PatientNameRecognizer:
    def __init__(self, connection_string="mongodb://localhost:27017/"):
        """Initialiser la connexion à MongoDB et charger les noms de patients UNE SEULE FOIS"""
        self.client = MongoClient(connection_string)
        self.db = self.client.PFE  # Utilisez le nom de votre base de données

        # ✅ CHARGEMENT UNIQUE AU DÉMARRAGE
        self.patient_names = self._load_patient_names()

        # Charger le modèle spaCy (le même que celui utilisé dans NLPAnalyzer)
        try:
            self.nlp = spacy.load("fr_core_news_md")
        except OSError:
            # Si le modèle n'est pas disponible, téléchargez-le
            import subprocess
            subprocess.call([
                "python", "-m", "spacy", "download", "fr_core_news_md"
            ])
            self.nlp = spacy.load("fr_core_news_md")

    def _load_patient_names(self):
        """Charger tous les noms et prénoms de patients depuis la base de données"""
        patient_names = set()

        try:
            patients = self.db.patient.find({}, {"nom": 1, "prenom": 1, "dateNaissance": 1})
            for patient in patients:
                if "nom" in patient and patient["nom"]:
                    patient_names.add(patient["nom"].lower())
                if "prenom" in patient and patient["prenom"]:
                    patient_names.add(patient["prenom"].lower())

                    if "nom" in patient and patient["nom"]:
                        patient_names.add(f"{patient['prenom']} {patient['nom']}".lower())
                        patient_names.add(f"{patient['nom']} {patient['prenom']}".lower())

            print(f"✅ Chargé {len(patient_names)} noms de patients depuis la base de données")

        except Exception as e:
            print(f"❌ Erreur lors du chargement des noms de patients: {e}")

        return patient_names

    def find_patient_in_text(self, text):
        """
        Chercher un patient dans le texte en utilisant les noms DÉJÀ CHARGÉS
        ⚡ AUCUN ACCÈS À LA BASE DE DONNÉES ICI
        """
        text_lower = text.lower()
        common_words = {"le", "la", "les", "un", "une", "des", "de", "du", "que", "qui", "quoi",
                        "où", "quand", "comment", "pourquoi", "et", "ou", "à", "au", "aux",
                        "par", "pour", "avec", "sans", "en", "dans", "sur", "sous", "entre",
                        "patient", "quelqu'un"}

        # ✅ UTILISER LES NOMS DÉJÀ CHARGÉS EN MÉMOIRE
        for name in self.patient_names:
            if name in text_lower:
                pattern = r'(^|\s)' + re.escape(name) + r'(\s|$|\.|\,|\;|\:|\!|\?)'
                if re.search(pattern, text_lower):
                    return name

        # Si aucun patient connu n'est trouvé, chercher une entité PER avec spaCy
        doc = self.nlp(text)
        person_entities = [ent.text.lower() for ent in doc.ents if ent.label_ == "PER"]

        for person in person_entities:
            if person not in common_words and len(person) > 2:
                return {"unknown_patient": person}

        return None

    def refresh_patient_names(self):
        """
        Méthode optionnelle pour recharger les noms depuis la base de données
        Appelez cette méthode seulement si de nouveaux patients ont été ajoutés
        """
        print("🔄 Rechargement des noms de patients...")
        self.patient_names = self._load_patient_names()
        print(f"✅ {len(self.patient_names)} noms de patients rechargés")