import spacy
import re
from datetime import datetime, timedelta
import dateparser

from ConversationContext import SmartContext


class NLPAnalyzer:
    def __init__(self, patient_recognizer=None):
        try:
            self.nlp = spacy.load("fr_core_news_md")
        except OSError:
            import subprocess
            subprocess.call([
                "python", "-m", "spacy", "download", "fr_core_news_md"
            ])
            self.nlp = spacy.load("fr_core_news_md")

        # ✅ UTILISER LE RECOGNIZER PASSÉ EN PARAMÈTRE OU EN CRÉER UN NOUVEAU
        if patient_recognizer is not None:
            self.patient_recognizer = patient_recognizer
            print("🔗 NLPAnalyzer utilise le PatientNameRecognizer partagé")
        else:
            # Seulement si aucun recognizer n'est fourni, en créer un nouveau
            from PatientNameRecognizer import PatientNameRecognizer
            self.patient_recognizer = PatientNameRecognizer()
            print("🆕 NLPAnalyzer crée un nouveau PatientNameRecognizer")

        # Ajouter dans la méthode __init__
        self.number_words = {
            "zéro": 0, "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4,
            "cinq": 5, "six": 6, "sept": 7, "huit": 8, "neuf": 9, "dix": 10,
            "onze": 11, "douze": 12, "treize": 13, "quatorze": 14, "quinze": 15,
            "seize": 16, "dix-sept": 17, "dix sept": 17, "dix-huit": 18, "dix huit": 18,
            "dix-neuf": 19, "dix neuf": 19, "vingt": 20,
            "vingt-et-un": 21, "vingt et un": 21, "vingt-deux": 22, "vingt deux": 22,
            "vingt-trois": 23, "vingt trois": 23, "vingt-quatre": 24, "vingt quatre": 24,
            "vingt-cinq": 25, "vingt cinq": 25, "vingt-six": 26, "vingt six": 26,
            "vingt-sept": 27, "vingt sept": 27, "vingt-huit": 28, "vingt huit": 28,
            "vingt-neuf": 29, "vingt neuf": 29, "trente": 30, "trente-et-un": 31, "trente et un": 31
        }

        # Patterns pour les recherches par période
        self.period_patterns = {
            "MONTH": [
                r'\bpour\s+(?:le\s+mois\s+(?:de\s+)?)?(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\b',
                r'\bdu\s+mois\s+(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\b',
                r'\ben\s+(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\b'
            ],
            "YEAR": [
                r'\bpour\s+(?:l\'année\s+)?(\d{4})\b',
                r'\ben\s+(\d{4})\b',
                r'\bde\s+(?:l\'année\s+)?(\d{4})\b'
            ]
        }

        self.intent_keywords = {
            "RENDEZ_VOUS": [
                "rendez-vous", "rdv", "consultation", "visite", "entrevue", "rencontre",
                "appointment", "consultations", "visites", "voir", "rencontrer",
                "planifié", "programmé", "calendrier", "agenda", "échéance", "booking",
                "consulter", "se présenter", "présentation", "apparaître", "tous les rdv",
                "tous les rendez-vous", "tout les rdv", "tout les rendez-vous"
            ],
            "DOSSIER_PATIENT": [
                "dossier", "informations", "données", "patient", "fiche", "profil",
                "historique", "antécédents", "fichier", "cas", "info",
                "détails", "renseignements", "dossiers", "fiches", "infos",
                "anamnèse", "dossier médical", "informations personnelles", "profils",
                "archives", "fichiers", "analyses", "résultats", "tests", "examens",
                "rapports", "bilans", "évaluations", "diagnostics", "études"
            ],
            "PRESCRIPTION": [
                "médicament", "prescription", "ordonnance", "ordonnances", "traitement", "médicaments",
                "prescriptions", "traitements", "remède", "thérapie", "médication",
                "soin", "dose", "régime", "prescrit", "ordonné", "pharmaceutique",
                "pharmacie", "posologie", "médication", "cure", "remèdes", "thérapies",
                "soins", "ordonner", "prescrire", "traiter", "médications", "cachets",
                "pilules", "comprimés", "gélules", "sirop", "ampoules", "teinture",
                "drogue", "pharmaceutiques", "pharmacologique", "médicamenteux"
            ],
            "DOCUMENT_PATIENT": [
                "document", "pdf", "fichier", "scan", "image", "upload", "télécharger",
                "importer", "ajouter", "ajouter document","joindre", "attacher", "scanner", "numériser",
                "documentation", "pièce", "dossier médical", "rapport", "résultat d'examen",
                "ordonnance", "compte-rendu", "certificat", "analyse", "importer",
                "téléverser", "charger", "uploader", "enregistrer", "sauvegarder",
                "déposer", "stocker", "ajout"
            ]
        }
        self.general_keywords = {
            "ALL_INDICATORS": [
                "tous", "toutes", "tout", "tous les", "toutes les", "tout les",
                "liste complète", "ensemble", "complet", "complète", "entier", "entière",
                "global", "globale", "général", "générale", "intégral", "intégrale",
                "total", "totale", "totalité", "liste", "répertoire", "inventaire"
            ]
        }
        # Dictionnaire étendu pour les contraintes temporelles
        self.time_keywords = {
            "LAST": [
                "dernier", "précédent", "récent", "passé", "était", "avait", "ancien",
                "antérieur", "précédente", "dernière", "ultérieur", "antérieure",
                "juste avant", "hier", "avant-hier", "la semaine dernière",
                "le mois dernier", "la dernière fois", "auparavant", "préalablement"
            ],
            "NEXT": [
                "prochain", "suivant", "futur", "prévu", "sera", "aura", "à venir",
                "bientôt", "prochaine", "future", "suivante", "imminent", "demain",
                "après-demain", "la semaine prochaine", "le mois prochain",
                "ultérieurement", "sous peu", "dans peu de temps", "d'ici peu"
            ],
            "PRESENT": [
                "aujourd'hui", "maintenant", "actuel", "ce jour", "en ce moment",
                "actuellement", "présentement", "à l'heure actuelle", "courante",
                "courant", "actuelle", "présent", "même jour", "en cours", "cette semaine",
                "ce mois", "ce mois-ci", "cette semaine-ci", "ces jours-ci", "en ce moment"
            ],
            "ALL": [
                "tous", "toutes", "tout", "tous les", "toutes les", "tout les", "liste complète",
                "ensemble", "complet", "complète", "entier", "entière"
            ]
        }

        # Jours de la semaine pour l'analyse de dates
        self.days = {
            "lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3,
            "vendredi": 4, "samedi": 5, "dimanche": 6
        }

        # Mois pour l'analyse des dates
        self.months = {
            "janvier": 1, "février": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
            "juillet": 7, "août": 8, "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12
        }

        self.smart_context = SmartContext()

    def analyze(self, text):
        try:
            print(f"🔍 Analyse de: '{text}'")

            doc = self.nlp(text.lower())
            intent = self.identify_intent(doc, text)
            entities = self.extract_entities(doc, text)
            time_constraint, specific_date = self.identify_time_constraint(doc, text)

            analysis = {
                "intent": intent,
                "entities": entities,
                "time_constraint": time_constraint,
                "specific_date": specific_date,
                "original_text": text
            }

            enriched_analysis = self.smart_context.enrich_analysis(analysis, doc)

            print(f"📊 Analyse finale: Intent={intent}, Patient={enriched_analysis['entities'].get('patient')}, "
                  f"Action={enriched_analysis.get('context_decision', {}).get('action')}")

            return enriched_analysis

        except Exception as e:
            print(f"❌ Erreur dans analyze: {e}")
            import traceback
            traceback.print_exc()
            return {
                "intent": "UNKNOWN",
                "entities": {},
                "time_constraint": "ALL",
                "specific_date": None,
                "original_text": text,
                "context_decision": {"action": "error", "reason": str(e)}
            }

    def extract_entities(self, doc, text):
        entities = {
            "patient": None,
            "date": None,
            "time": None,
            "unknown_patient": None
        }

        # 🆕 DÉTECTION PRIORITAIRE DES REQUÊTES GÉNÉRALES AVEC "TOUS"
        text_lower = text.lower()

        # Vérifier les patterns généraux avec "tous"
        if self._is_general_query(text_lower):
            entities["all_patients"] = True
            entities["general_query"] = True
            entities["use_context"] = False
            print("🌐 REQUÊTE GÉNÉRALE détectée avec 'tous' - Pas de gestion de contexte")
            return entities

        entities["all_patients"] = False

        # Vérifier d'abord si c'est une requête générale (ancienne logique maintenue)
        if any(term in text_lower for term in
               ["tous les patients", "tous patient", "tous", "ensemble", "totalité"]):
            entities["all_patients"] = True
            print("🔍 Détection d'une requête sur TOUS les patients")
            entities["general_query"] = True
            entities["use_context"] = False
            return entities

        has_time_indicators = any(term in text_lower for term in [
            "mois", "semaine", "janvier", "février", "mars", "avril", "mai", "juin",
            "juillet", "août", "septembre", "octobre", "novembre", "décembre",
            "aujourd'hui", "demain", "hier"
        ])

        has_general_indicators = any(term in text_lower.split() for term in [
            "tous", "toutes", "ensemble", "totalité", "liste"
        ])

        if has_time_indicators and has_general_indicators and "patient" not in text_lower:
            entities["general_time_query"] = True
            entities["use_context"] = False
            print("📅 Détection d'une requête temporelle GÉNÉRALE sans patient spécifique")
            return entities

        if has_time_indicators and "patient" not in text_lower and entities["patient"] is None:
            pronouns = ["son", "sa", "ses", "ces", "ce", "cette", "cet", "le", "la", "les"]
            has_pronoun = any(pronoun in text_lower.split() for pronoun in pronouns)

            if not has_pronoun:
                entities["general_time_query"] = True
                entities["use_context"] = False
                print("📅 Requête temporelle sans pronoms - considérée comme générale")
                return entities

        # ✅ UTILISER LE RECOGNIZER PARTAGÉ AU LIEU DE CRÉER UN NOUVEAU
        patient_result = self.patient_recognizer.find_patient_in_text(text)

        if patient_result:
            if isinstance(patient_result, str):
                # C'est un patient connu
                entities["patient"] = patient_result.capitalize()
                entities["use_context"] = True
                return entities
            elif isinstance(patient_result, dict) and "unknown_patient" in patient_result:
                # C'est un patient inconnu détecté par spaCy
                entities["unknown_patient"] = patient_result["unknown_patient"].capitalize()
                print(f"⚠️ Patient inexistant détecté: {entities['unknown_patient']}")
                return entities

        patient_name = self._extract_patient_manually(doc, text)
        if patient_name:
            entities["patient"] = patient_name

        date_text = self._extract_date_manually(text)
        if date_text:
            entities["date"] = date_text

        time_text = self._extract_time_manually(text)
        if time_text:
            entities["time"] = time_text

        if entities["patient"]:
            keywords_to_exclude = (
                    set(self.intent_keywords['RENDEZ_VOUS']) |
                    set(self.intent_keywords['DOSSIER_PATIENT']) |
                    set(self.intent_keywords['PRESCRIPTION']) |
                    set(self.months.keys()) |
                    {"patient", "dossier", "document", "nom", "prenom"}
            )

            if entities["patient"].lower() in keywords_to_exclude:
                entities["patient"] = None
        return entities

    def _is_general_query(self, text_lower):
        """
        🆕 NOUVELLE MÉTHODE : Détecte si c'est une requête générale avec "tous"
        """
        # Patterns spécifiques pour détecter les requêtes générales
        general_patterns = [
            # Tous + intent spécifique
            r'\btous\s+les?\s+(rdv|rendez[- ]vous|consultations?|visites?)\b',
            r'\btoutes?\s+les?\s+(prescriptions?|ordonnances?|médicaments?|traitements?)\b',
            r'\btous?\s+les?\s+(patients?|dossiers?|fiches?)\b',

            # Tous seul avec un intent dans la phrase
            r'\btous?\b.*\b(rdv|rendez[- ]vous|consultation|prescription|ordonnance|patient|dossier)\b',
            r'\btoutes?\b.*\b(prescriptions?|ordonnances?|consultations?|visites?)\b',

            # Liste + intent
            r'\bliste\s+(des?|complète)?\s*(rdv|rendez[- ]vous|prescriptions?|patients?|dossiers?)\b',
            r'\brépertoire\s+(des?|complet)?\s*(patients?|rdv|prescriptions?)\b',

            # Expressions complètes
            r'\bensemble\s+des?\s+(rdv|rendez[- ]vous|prescriptions?|patients?|dossiers?)\b',
            r'\btotalité\s+des?\s+(rdv|rendez[- ]vous|prescriptions?|patients?|dossiers?)\b',

            # Formes contractées communes
            r'\btout\s+les?\s+(rdv|rendez[- ]vous|prescriptions?|patients?)\b',
        ]

        for pattern in general_patterns:
            if re.search(pattern, text_lower):
                match = re.search(pattern, text_lower)
                print(f"🌐 Pattern général détecté: '{match.group()}' → Requête GÉNÉRALE")
                return True

        # Vérification par mots-clés combinés
        words = text_lower.split()
        has_all_indicator = any(word in self.general_keywords["ALL_INDICATORS"] for word in words)

        if has_all_indicator:
            # Vérifier si il y a un intent dans la phrase
            all_intent_words = (
                    self.intent_keywords["RENDEZ_VOUS"] +
                    self.intent_keywords["PRESCRIPTION"] +
                    self.intent_keywords["DOSSIER_PATIENT"]
            )

            has_intent_word = any(word in all_intent_words for word in words)

            if has_intent_word:
                print(f"🌐 Combinaison 'tous' + intent détectée → Requête GÉNÉRALE")
                return True

        return False

    def _extract_patient_manually(self, doc, text):
        # Liste étendue des mots à exclure
        common_words = {
            "le", "la", "les", "un", "une", "des", "de", "du", "patient", "rendez-vous","patients",
            "rdv", "consultation", "prescription", "dossier", "aujourd'hui", "demain", "hier",
            "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche",
            # ✅ AJOUT DES MOTS TEMPORELS QUI CAUSENT LE PROBLÈME
            "mois", "semaine", "année", "jour", "prochain", "dernier", "précédent",
            "suivant", "courant", "actuel", "présent", "futur", "passé",
            # Mois de l'année
            "janvier", "février", "mars", "avril", "mai", "juin",
            "juillet", "août", "septembre", "octobre", "novembre", "décembre",
            # Autres mots temporels
            "maintenant", "bientôt", "hier", "demain", "aujourd'hui",
            # Mots liés aux actions médicales
            "document", "fichier", "ordonnance", "traitement", "médicament",
            "dossier", "information", "données", "résultat", "examen",
            "analyse", "rapport", "bilan", "diagnostic", "prescription",
            # 🆕 AJOUT DES MOTS "TOUS" POUR ÉVITER QU'ILS SOIENT PRIS COMME NOMS DE PATIENTS
            "tous", "toutes", "tout", "liste", "ensemble", "complet", "complète",
            "entier", "entière", "global", "général", "total", "totalité"
        }

        potential_names = []
        for token in doc:
            if (token.pos_ in ["PROPN", "NOUN"] and
                    token.text.lower() not in common_words and
                    len(token.text) > 1 and
                    token.text.isalpha() and
                    # ✅ VÉRIFICATION SUPPLÉMENTAIRE : éviter les mots qui sont des entités temporelles
                    not self._is_temporal_word(token.text.lower())):
                potential_names.append(token.text.title())

        if potential_names:
            if len(potential_names) >= 2:
                return " ".join(potential_names[:2])
            else:
                return potential_names[0]

        return None

    def _is_temporal_word(self, word):
        """Vérifie si un mot est lié au temps/temporalité"""
        temporal_indicators = {
            # Mots temporels de base
            "mois", "semaine", "année", "jour", "heure", "minute",
            "prochain", "dernier", "précédent", "suivant", "courant",
            "actuel", "présent", "futur", "passé", "récent",
            # Mois
            "janvier", "février", "mars", "avril", "mai", "juin",
            "juillet", "août", "septembre", "octobre", "novembre", "décembre",
            # Jours
            "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche",
            # Adverbes temporels
            "maintenant", "bientôt", "hier", "demain", "aujourd'hui",
            "avant-hier", "après-demain",
            # Qualificatifs temporels
            "matinée", "après-midi", "soirée", "nuit", "matin", "soir"
        }
        return word in temporal_indicators

    def _extract_date_manually(self, text):
        date_patterns = [
            r'\b(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{2,4})\b',
            r'\b(\d{1,2})\s+(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s*(\d{4})?\b'
        ]

        for pattern in date_patterns:
            match = re.search(pattern, text.lower())
            if match:
                return match.group(0)

        return None

    def _extract_time_manually(self, text):
        time_patterns = [
            r'\b(\d{1,2})[h:](\d{2})\b',
            r'\b(\d{1,2})h\b',
            r'\b(\d{1,2}):(\d{2})\s*(am|pm)?\b'
        ]

        for pattern in time_patterns:
            match = re.search(pattern, text.lower())
            if match:
                return match.group(0)

        return None

    def identify_intent(self, doc, text):
        intent_scores = {intent: 0 for intent in self.intent_keywords}

        for token in doc:
            for intent, keywords in self.intent_keywords.items():
                if token.text in keywords or token.lemma_ in keywords:
                    intent_scores[intent] += 1

        for i in range(len(doc) - 1):
            bigram = f"{doc[i].text} {doc[i + 1].text}"
            for intent, keywords in self.intent_keywords.items():
                if bigram in keywords:
                    intent_scores[intent] += 2

        if "tous les rdv" in text.lower() or "tous les rendez-vous" in text.lower():
            intent_scores["RENDEZ_VOUS"] += 3

        max_score = max(intent_scores.values()) if intent_scores.values() else 0
        if max_score > 0:
            return max(intent_scores.items(), key=lambda x: x[1])[0]

        return "UNKNOWN"

    def identify_time_constraint(self, doc, text):
        """Identifier la contrainte temporelle dans le texte

        Args:
            doc: Le document spaCy
            text: Le texte brut de la requête

        Returns:
            tuple: (contrainte_temporelle, date_spécifique)
        """
        # Convertir le texte pour normalisation
        text_normalized = text.lower()
        time_constraint = "ALL"  # Par défaut, considérer toutes les dates
        specific_date = None
        today = datetime.now()

        # Créer un dictionnaire temporaire qui contient tous les mots-clés pour chaque intention
        all_keywords = {}
        for intent, keywords in self.intent_keywords.items():
            all_keywords[intent] = [kw.lower() for kw in keywords]

        # Mots-clés temporels pour "prochain" et "dernier"
        next_keywords = [
            "prochain", "prochaine", "prochains", "prochaines",
            "suivant", "suivante", "suivants", "suivantes",
            "futur", "future", "futurs", "futures",
            "à venir", "prévu", "prévue", "prévus", "prévues",
            "sera", "aura", "bientôt", "imminent", "imminente", "imminents", "imminentes"
        ]

        last_keywords = [
            "dernier", "derniers", "dernière", "dernières",
            "précédent", "précédents", "précédente", "précédentes",
            "récent", "récents", "récente", "récentes",
            "passé", "passés", "passée", "passées",
            "était", "avait",
            "ancien", "anciens", "ancienne", "anciennes",
            "antérieur", "antérieure", "antérieurs", "antérieures"
        ]

        # Pattern générique pour "mot-clé d'intention + mot temporel" ou "mot temporel + mot-clé d'intention"
        for intent, keywords in all_keywords.items():
            # Créer une expression régulière avec tous les mots-clés pour cette intention
            intent_keywords_pattern = '|'.join([re.escape(kw) for kw in keywords])

            # Créer patterns pour "intention + temps" et "temps + intention"
            next_patterns = [
                rf'\b({intent_keywords_pattern})\s+({"|".join(next_keywords)})\b',
                rf'\b({"|".join(next_keywords)})\s+({intent_keywords_pattern})\b'
            ]

            last_patterns = [
                rf'\b({intent_keywords_pattern})\s+({"|".join(last_keywords)})\b',
                rf'\b({"|".join(last_keywords)})\s+({intent_keywords_pattern})\b'
            ]

            # Vérifier les patterns "prochain/suivant"
            for pattern in next_patterns:
                if re.search(pattern, text_normalized):
                    return "NEXT", None

            # Vérifier les patterns "dernier/précédent"
            for pattern in last_patterns:
                if re.search(pattern, text_normalized):
                    return "LAST", None

        # Dates relatives simples avec gestion directe
        relative_dates = {
            "hier": {"offset": -1, "constraint": "LAST"},
            "yesterday": {"offset": -1, "constraint": "LAST"},
            "avant-hier": {"offset": -2, "constraint": "LAST"},
            "aujourd'hui": {"offset": 0, "constraint": "PRESENT"},
            "today": {"offset": 0, "constraint": "PRESENT"},
            "demain": {"offset": 1, "constraint": "NEXT"},
            "tomorrow": {"offset": 1, "constraint": "NEXT"},
            "après-demain": {"offset": 2, "constraint": "NEXT"}
        }

        # Vérification précise pour chaque date relative
        for word, date_info in relative_dates.items():
            if re.search(r'\b' + re.escape(word) + r'\b', text_normalized):
                target_date = today + timedelta(days=date_info["offset"])
                specific_date = target_date.strftime("%Y-%m-%d")  # Formatez la date correctement
                time_constraint = date_info["constraint"]
                print(f"🗓️ Contrainte temporelle: {word} ({specific_date})")
                return time_constraint, specific_date

        # Convertir les nombres composés
        composed_numbers = {
            "vingt et un": 21, "vingt-et-un": 21, "vingt deux": 22, "vingt-deux": 22,
            "vingt trois": 23, "vingt-trois": 23, "vingt quatre": 24, "vingt-quatre": 24,
            "vingt cinq": 25, "vingt-cinq": 25, "vingt six": 26, "vingt-six": 26,
            "vingt sept": 27, "vingt-sept": 27, "vingt huit": 28, "vingt-huit": 28,
            "vingt neuf": 29, "vingt-neuf": 29, "trente et un": 31, "trente-et-un": 31,
            "trente deux": 32, "trente-deux": 32, "trente trois": 33, "trente-trois": 33,
            "trente quatre": 34, "trente-quatre": 34, "trente cinq": 35, "trente-cinq": 35,
        }

        # Traiter les nombres composés
        for num_word, num_value in composed_numbers.items():
            text_normalized = text_normalized.replace(num_word, str(num_value))

        # Remplacer les mots de nombres simples
        for word, number in sorted(self.number_words.items(), key=lambda x: len(x[0]), reverse=True):
            text_normalized = re.sub(r'\b' + word + r'\b', str(number), text_normalized)

        # Motifs de détection de mois plus flexibles et étendus
        month_period_patterns = [
            # Patterns pour capturer explicitement "pour le mois mars", "du mois mars", "de mois mars"
            r'\bpour\s+(?:le\s+)?mois\s+(?:de\s+)?(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)(?:\s+(\d{4}))?\b',
            r'\bdu\s+mois\s(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)(?:\s+(\d{4}))?\b',
            r'\bde\s+mois\s+(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)(?:\s+(\d{4}))?\b',

            # Patterns existants améliorés
            r'\bmois\s+(?:de|du|d\')\s+(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)(?:\s+(\d{4}))?\b',
            r'\b(?:de|du)\s+mois\s+(?:de|d\')?\s*(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)(?:\s+(\d{4}))?\b',
            r'\b(?:en|durant|pendant|pour|au|dans)\s+(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)(?:\s+(\d{4}))?\b',
            r'\b(?:en|durant|pendant|pour|au|dans)\s+(?:le\s+)?mois\s+(?:de\s+)?(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)(?:\s+(\d{4}))?\b',
            r'\b(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s*(?:prochain|courant|en cours)(?:\s+(\d{4}))?\b',
            r'\b(?:ce)\s+(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)(?:\s+(\d{4}))?\b',
            r'\bce\s+mois(?:\s+de\s+(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre))?(?:\s+(\d{4}))?\b',
        ]

        # Tester chaque motif de mois
        for pattern in month_period_patterns:
            month_match = re.search(pattern, text_normalized)
            if month_match and month_match.group(1):
                try:
                    month_name = month_match.group(1)
                    month = self.months.get(month_name, 1)

                    # Utiliser l'année du match ou l'année courante
                    year = int(month_match.group(2)) if month_match.group(2) else datetime.now().year

                    # Créer une date pour le premier jour du mois
                    specific_date = datetime(year, month, 1).strftime("%Y-%m-%d")

                    # Déterminer la contrainte temporelle
                    current_month = datetime.now().month
                    if month > current_month:
                        time_constraint = "NEXT"
                    elif month < current_month:
                        time_constraint = "LAST"
                    else:
                        time_constraint = "PRESENT"

                    return time_constraint, specific_date

                except Exception as e:
                    print(f"Erreur lors du traitement du mois : {e}")
                    continue

        # Dates spécifiques - version plus défensive
        try:
            date_patterns = [
                r'\b(?:le|du|de|ce|pour\s+le|au)\s+(\d{1,2})\s+(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)(?:\s+(\d{4}))?\b',
                r'\b(?:le|du|de|ce|pour\s+le|au)\s+(\w+)\s+(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)(?:\s+(\d{4}))?\b'
            ]

            for pattern in date_patterns:
                match = re.search(pattern, text_normalized)
                if match and len(match.groups()) >= 2:
                    try:
                        day = 1
                        month = 1
                        year = datetime.now().year

                        # Vérifier et convertir le jour
                        if match.group(1):
                            day_str = match.group(1)
                            day = int(day_str) if day_str.isdigit() else composed_numbers.get(day_str.lower(), 1)

                        # Convertir le mois
                        month_name = match.group(2)
                        month = self.months.get(month_name, 1)

                        # Année optionnelle
                        if match.group(3):
                            year = int(match.group(3))

                        target_date = datetime(year, month, day)
                        specific_date = target_date.strftime("%Y-%m-%d")
                        time_constraint = "NEXT" if target_date.date() > datetime.now().date() else "LAST" if target_date.date() < datetime.now().date() else "PRESENT"
                        return time_constraint, specific_date
                    except Exception as e:
                        print(f"Erreur lors du traitement de la date : {e}")
                        continue
        except Exception as e:
            print(f"Erreur générale dans la détection de date : {e}")

        # Jours de la semaine - version plus défensive
        try:
            weekday_pattern = r'\b(?:de|du|d\'|pour)\s+(lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)\s+(prochain|dernier)\b'
            weekday_match = re.search(weekday_pattern, text_normalized)
            if weekday_match and len(weekday_match.groups()) == 2:
                day_name = weekday_match.group(1)
                qualifier = weekday_match.group(2) #prochain ou dernier
                today = datetime.now()
                day_num = self.days.get(day_name, 0)
                days_ahead = day_num - today.weekday()

                if qualifier == "prochain":
                    if days_ahead <= 0:
                        days_ahead += 7
                    target_date = today + timedelta(days=days_ahead)
                    time_constraint = "NEXT"
                else:  # dernier
                    if days_ahead >= 0:
                        days_ahead -= 7
                    target_date = today + timedelta(days=days_ahead)
                    time_constraint = "LAST"

                specific_date = target_date.strftime("%Y-%m-%d")
                return time_constraint, specific_date
        except Exception as e:
            print(f"Erreur lors de la détection du jour de la semaine : {e}")

        # Si aucune date n'est trouvée
        return time_constraint, specific_date

