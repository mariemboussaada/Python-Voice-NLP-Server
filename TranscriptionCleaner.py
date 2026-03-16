# TranscriptionCleaner.py - Solution améliorée pour les cas complexes avec un nom en fin de phrase
import re


class TranscriptionCleaner:
    def __init__(self):
        # Liste des marqueurs d'hésitation courants en français
        self.hesitation_markers = [
            "euh", "hum", "hmm", "emm", "ohhh", "ben", "bah", "euhm", "mmm",
            "pfff", "aah", "eh bien", "ehm", "eum", "bon"
        ]

        # Expressions régulières pour détecter les répétitions
        self.repetition_patterns = [
            # Répétition d'articles: "le... le", "la... la"
            r'\b(le|la|les|un|une|des)\s+(?:[^a-zA-Z0-9]+\s+)?\1\b',
            # Répétition de début de phrase: "je... je", "il... il"
            r'\b(je|tu|il|elle|nous|vous|ils|elles)\s+(?:[^a-zA-Z0-9]+\s+)?\1\b'
        ]

        # Prépositions et articles communs qui peuvent précéder un nom
        self.prepositions = ["de", "du", "des", "à", "au", "aux", "pour", "avec", "chez", "par", "sur", "dans"]

        # Mots spécifiques au domaine médical et temporels qui ne sont PAS des patients
        self.domain_keywords = [
            "rendez-vous", "rdv", "dossier", "consultation", "patient",
            "document", "prescription", "médicament", "ordonnance",
            "demain", "aujourd'hui", "hier", "matin", "soir", "après-midi",
            "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche",
            "janvier", "février", "mars", "avril", "mai", "juin",
            "juillet", "août", "septembre", "octobre", "novembre", "décembre"
        ]

    def clean(self, text):
        """Nettoie le texte transcrit et extrait potentiellement le nom du patient"""
        # Conserver le texte original pour déboguer
        original_text = text

        # Remplacer les caractères non-latins (comme les caractères arabes) par des espaces
        text = re.sub(r'[^\x00-\x7F]+', ' ', text)

        # Normaliser les espaces avant de commencer
        text = re.sub(r'\s+', ' ', text).strip()

        cleaned_text = text.lower()

        # 1. Supprimer les marqueurs d'hésitation
        for marker in self.hesitation_markers:
            cleaned_text = re.sub(r'\b' + re.escape(marker) + r'\b', ' ', cleaned_text)

        # 2. Nettoyer les variations d'hésitation
        cleaned_text = re.sub(r'e{2,}u+h+', ' ', cleaned_text)
        cleaned_text = re.sub(r'h+m+', ' ', cleaned_text)
        cleaned_text = re.sub(r'o+h+', ' ', cleaned_text)
        cleaned_text = re.sub(r'e+m+', ' ', cleaned_text)

        # 3. Gérer les répétitions
        for pattern in self.repetition_patterns:
            cleaned_text = re.sub(pattern, r'\1', cleaned_text)

        # Avant de continuer, corriger le problème spécifique de "d ain"
        cleaned_text = cleaned_text.replace(" d ain", " demain")
        cleaned_text = cleaned_text.replace(" de d ain", " de demain")

        # 4. Détection du nom en fin de phrase - stratégie principale
        words = cleaned_text.split()
        if len(words) >= 2:
            # Vérifier si l'avant-dernier mot est une préposition
            if len(words) >= 3 and words[-2] in self.prepositions:
                last_word = words[-1]

                # Si le dernier mot est un mot temporel, ne pas le traiter comme un nom
                if last_word in self.domain_keywords:
                    pass  # Ne rien faire, garder la phrase comme elle est
                else:
                    # Traiter normalement si ce n'est pas un mot temporel
                    if (len(last_word) >= 2 and
                            last_word not in self.hesitation_markers):
                        # Identifier l'action et l'objet comme avant...
                        action_parts = []
                        object_type = ""

                        for i, word in enumerate(words):
                            if i < 3:  # Les premiers mots sont généralement l'action
                                action_parts.append(word)
                            elif word in ["rendez-vous", "rdv", "dossier", "document", "prescription"]:
                                object_type = word
                                break

                        if action_parts and object_type:
                            action = " ".join(action_parts)
                            cleaned_text = f"{action} les {object_type} de {last_word}"
            else:
                # Cas normal (pas de préposition avant le dernier mot)
                last_word = words[-1]

                if (len(last_word) >= 2 and
                        last_word not in self.hesitation_markers and
                        last_word not in self.domain_keywords):

                    action_parts = []
                    object_type = ""

                    for i, word in enumerate(words):
                        if i < 3:
                            action_parts.append(word)
                        elif word in ["rendez-vous", "rdv", "dossier", "document", "prescription"]:
                            object_type = word
                            break

                    if action_parts and object_type:
                        action = " ".join(action_parts)
                        cleaned_text = f"{action} les {object_type} de {last_word}"

        # 5. Normaliser les espaces
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()

        return cleaned_text