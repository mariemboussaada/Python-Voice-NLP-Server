# SmartContext.py - Classe complète avec intelligence contextuelle des intentions

import spacy
from datetime import datetime
import re


class SmartContext:
    def __init__(self):
        self.current_patient = None
        self.current_intent = None
        self.last_analysis = None
        self.session_active = True
        # 🆕 NOUVEAU: Stocker la dernière intention même en cas d'échec
        self.last_intent_attempt = None  # Pour mémoriser même les intents qui ont échoué

    def analyze_request(self, analysis, doc):
        """
        Analyseur intelligent principal avec spaCy et intelligence contextuelle
        args:
            analysis: résultat de l'analyse NLP
            doc: document spaCy traité
        Retourne: { "use_context": bool, "action": str, "patient": str }
        """
        intent = analysis.get("intent", "UNKNOWN")
        entities = analysis.get("entities", {})
        patient_mentioned = entities.get("patient")
        unknown_patient = entities.get("unknown_patient")

        print(f"🧠 Analyse contexte:")
        print(f"   Intent: {intent}")
        print(f"   Patient mentionné: {patient_mentioned}")
        print(f"   Patient inexistant: {unknown_patient}")
        print(f"   Dernière intention: {self.last_intent_attempt}")

        # 🆕 NOUVELLE LOGIQUE: Intent intelligent avec contexte
        if intent == "UNKNOWN" and patient_mentioned and self.last_intent_attempt:
            print(f"🧠 Intelligence contextuelle d'intention activée!")
            print(f"   Intent: UNKNOWN → {self.last_intent_attempt}")
            print(f"   Patient: {patient_mentioned}")
            print(f"   Interprétation: '{self.last_intent_attempt.lower()} de {patient_mentioned}'")

            # Réutiliser la dernière intention avec le nouveau patient
            intent = self.last_intent_attempt
            analysis["intent"] = intent  # Mettre à jour l'analyse

            decision = {
                "use_context": False,  # Nouveau patient = nouveau contexte
                "action": "intelligent_intent_reuse",
                "patient": patient_mentioned,
                "reused_intent": self.last_intent_attempt,
                "reason": f"Réutilisation intelligente de l'intention '{self.last_intent_attempt}' avec le nouveau patient '{patient_mentioned}'"
            }

            # 🚨 CORRECTION CRITIQUE: APPELER _update_context AVANT DE RETOURNER
            self._update_context(decision, analysis)
            return decision

        # 🚨 Vérifier patient inexistant AVANT tout
        if unknown_patient:
            print(f"⚠️ Patient inexistant détecté: {unknown_patient}")
            # 🆕 STOCKER L'INTENTION MÊME EN CAS D'ÉCHEC
            if intent != "UNKNOWN":
                self.last_intent_attempt = intent
                print(f"💾 Intention sauvegardée pour réutilisation: {intent}")

            decision = {
                "use_context": False,
                "action": "unknown_patient",
                "patient": None,
                "unknown_patient": unknown_patient,
                "reason": f"Patient '{unknown_patient}' n'existe pas dans la base de données"
            }

            # 🚨 APPELER _update_context AVANT DE RETOURNER
            self._update_context(decision, analysis)
            return decision

        # 🆕 STOCKER CHAQUE INTENTION VALIDE DÉTECTÉE
        if intent != "UNKNOWN":
            self.last_intent_attempt = intent
            print(f"💾 Nouvelle intention sauvegardée: {intent}")

        # 🚀 UTILISER SPACY POUR DÉTECTER LES ENTITÉS TEMPORELLES
        has_datetime = self._detect_temporal_with_spacy(doc, analysis)

        # 🧠 MATRICE DE DÉCISION INTELLIGENTE
        decision = self._apply_decision_matrix(intent, patient_mentioned, has_datetime)

        # 📊 MISE À JOUR DU CONTEXTE
        self._update_context(decision, analysis)

        return decision

    def _detect_temporal_with_spacy(self, doc, analysis):
        """Utilise spaCy pour détecter les entités temporelles + patterns"""
        temporal_detected = False
        temporal_info = []

        # 1. ENTITÉS SPACY TEMPORELLES
        for ent in doc.ents:
            if ent.label_ in ["DATE", "TIME"]:
                temporal_detected = True
                temporal_info.append({
                    "text": ent.text,
                    "label": ent.label_,
                    "start": ent.start_char,
                    "end": ent.end_char
                })
                print(f"🕒 spaCy détecté {ent.label_}: '{ent.text}'")

        # 2. DÉTECTION POS (Part-of-Speech) POUR LES ADVERBES TEMPORELS
        temporal_pos_tags = ["ADV"]
        for token in doc:
            if token.pos_ in temporal_pos_tags:
                temporal_adverbs = [
                    "aujourd'hui", "demain", "hier", "maintenant", "bientôt",
                    "récemment", "prochainement", "tard", "tôt", "souvent",
                    "parfois", "toujours", "jamais", "avant", "après"
                ]
                if token.lemma_.lower() in temporal_adverbs or token.text.lower() in temporal_adverbs:
                    temporal_detected = True
                    temporal_info.append({
                        "text": token.text,
                        "label": "TEMPORAL_ADV",
                        "lemma": token.lemma_,
                        "pos": token.pos_
                    })
                    print(f"🕒 spaCy adverbe temporel détecté: '{token.text}' (lemma: {token.lemma_})")

        # 3. DÉTECTION PAR DEPENDENCY PARSING
        for token in doc:
            if token.dep_ in ["advmod", "nmod:tmod", "obl:tmod"]:
                if any(child.text.lower() in ["aujourd'hui", "demain", "hier", "maintenant"]
                       for child in token.children):
                    temporal_detected = True
                    temporal_info.append({
                        "text": token.text,
                        "label": "TEMPORAL_DEP",
                        "dependency": token.dep_
                    })
                    print(f"🕒 spaCy relation temporelle détectée: '{token.text}' (dep: {token.dep_})")

        # 4. PATTERNS REGEX COMPLÉMENTAIRES
        text = analysis.get("original_text", "").lower()
        additional_patterns = [
            r'\b(ce\s+matin|cet?\s+après-midi|ce\s+soir|cette\s+nuit)\b',
            r'\b(la\s+semaine\s+(prochaine|dernière)|le\s+mois\s+(prochain|dernier))\b',
            r'\b\d{1,2}h\d{2}\b',
            r'\b\d{1,2}:\d{2}\b',
            r'\b\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\b',  # Dates
            r'\b(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\b',

            # Nouveaux motifs ajoutés pour "totalité", "ensemble", etc.
            r'\b(tous|toutes|tout)\s+les\b',
            r'\b(tout|tous|toutes|ensemble|complet|complète|entier|entière|global|globale|général|générale|intégral|intégrale|total|totale|totalité)\b',
            r'\b(liste\s+complète|liste|répertoire|inventaire)\b'
        ]

        for pattern in additional_patterns:
            if re.search(pattern, text):
                temporal_detected = True
                match = re.search(pattern, text)
                temporal_info.append({
                    "text": match.group(),
                    "label": "REGEX_PATTERN"
                })
                print(f"🕒 Pattern regex temporel détecté: '{match.group()}'")

        # 5. LOGGING DÉTAILLÉ
        if temporal_detected:
            print(f"⏰ Informations temporelles détectées: {len(temporal_info)} éléments")
        else:
            print("⏰ Aucune information temporelle détectée")

        return temporal_detected

    def _apply_decision_matrix(self, intent, patient_mentioned, has_datetime):
        """Matrice de décision basée sur tes règles métier"""

        print(f"🧠 Matrice de décision:")
        print(f"   Intent: {intent}")
        print(f"   Patient mentionné: {patient_mentioned}")
        print(f"   A datetime: {has_datetime}")
        print(f"   Contexte actuel: {self.current_patient}")

        # RÈGLE 1: Intent inconnu = pas de contexte
        if intent == "UNKNOWN":
            return {
                "use_context": False,
                "action": "unknown_intent",
                "patient": None,
                "reason": "Intent non reconnu"
            }

        # RÈGLE 2: Nouveau patient mentionné = nouveau contexte
        if patient_mentioned and patient_mentioned.strip():
            return {
                "use_context": False,
                "action": "new_patient_context",
                "patient": patient_mentioned,
                "reason": f"Nouveau patient détecté: {patient_mentioned}"
            }

        # RÈGLE 3: Date/temps mentionné = requête générale
        if has_datetime:
            return {
                "use_context": False,
                "action": "general_query",
                "patient": None,
                "reason": "Requête générale avec date/temps détectée par spaCy"
            }

        # RÈGLE 4: Intent seul + contexte existant = utiliser contexte
        if intent != "UNKNOWN" and self.current_patient:
            return {
                "use_context": True,
                "action": "continue_context",
                "patient": self.current_patient,
                "reason": f"Continuation pour patient: {self.current_patient}"
            }

        # RÈGLE 5: Intent seul + pas de contexte = requête générale
        return {
            "use_context": False,
            "action": "general_query",
            "patient": None,
            "reason": "Pas de contexte patient disponible"
        }

    def _update_context(self, decision, analysis):
        """Met à jour le contexte avec gestion des intentions intelligentes"""
        action = decision["action"]

        if action == "new_patient_context":
            self.current_patient = decision["patient"]
            self.current_intent = analysis.get("intent")
            print(f"✅ Nouveau contexte: Patient = {self.current_patient}, Intent = {self.current_intent}")

        elif action == "intelligent_intent_reuse":
            # 🆕 NOUVEAU CAS: Réutilisation intelligente d'intention
            self.current_patient = decision["patient"]
            self.current_intent = decision["reused_intent"]
            print(f"🧠 Contexte intelligent: Patient = {self.current_patient}, Intent réutilisé = {self.current_intent}")

        elif action == "continue_context":
            self.current_intent = analysis.get("intent")
            print(f"🔄 Continuation contexte: Patient = {self.current_patient}, Intent = {self.current_intent}")

        elif action == "general_query":
            self._clear_context()
            print("🌐 Requête générale détectée - contexte nettoyé")

        elif action == "unknown_intent":
            print("❓ Intent inconnu - contexte maintenu")

        elif action == "unknown_patient":
            # ⚠️ Patient inexistant: garder l'intention pour réutilisation future
            print(f"⚠️ Patient inexistant: {decision.get('unknown_patient')} - intention conservée pour réutilisation")
            # NE PAS nettoyer last_intent_attempt ici !

        # Sauvegarder la dernière analyse
        self.last_analysis = analysis

    def _clear_context(self):
        """Nettoie le contexte complètement"""
        self.current_patient = None
        self.current_intent = None
        # 🆕 GARDER last_intent_attempt même après nettoyage
        # pour permettre la réutilisation intelligente
        print("🧹 Contexte nettoyé (intention conservée pour réutilisation)")

    def get_current_context(self):
        """Retourne le contexte actuel avec informations d'intention"""
        return {
            "patient": self.current_patient,
            "intent": self.current_intent,
            "last_intent_attempt": self.last_intent_attempt,  # 🆕 NOUVEAU
            "has_context": bool(self.current_patient)
        }

    def enrich_analysis(self, analysis, doc):
        """Enrichit l'analyse avec le contexte si nécessaire"""
        decision = self.analyze_request(analysis, doc)

        if decision["use_context"] and decision["patient"]:
            if "entities" not in analysis:
                analysis["entities"] = {}
            analysis["entities"]["patient"] = decision["patient"]
            print(f"✨ Analyse enrichie avec patient: {decision['patient']}")

        analysis["context_decision"] = decision
        return analysis

    # 🆕 NOUVELLES MÉTHODES UTILITAIRES
    def get_intelligent_interpretation(self):
        """Retourne une interprétation intelligente du contexte actuel"""
        if self.current_patient and self.current_intent:
            intent_mapping = {
                "DOSSIER_PATIENT": "dossier",
                "RENDEZ_VOUS": "rendez-vous",
                "PRESCRIPTION": "prescriptions"
            }
            readable_intent = intent_mapping.get(self.current_intent, self.current_intent.lower())
            return f"{readable_intent} de {self.current_patient}"
        elif self.last_intent_attempt:
            intent_mapping = {
                "DOSSIER_PATIENT": "dossier",
                "RENDEZ_VOUS": "rendez-vous",
                "PRESCRIPTION": "prescriptions"
            }
            readable_intent = intent_mapping.get(self.last_intent_attempt, self.last_intent_attempt.lower())
            return f"Prêt pour: {readable_intent} d'un patient"
        return None

    def reset_session(self):
        """Réinitialise complètement la session"""
        self.current_patient = None
        self.current_intent = None
        self.last_analysis = None
        self.last_analysis = None
        self.last_intent_attempt = None  # 🆕 Nettoyer aussi l'intention
        self.session_active = True
        print("🔄 Session entièrement réinitialisée (y compris intentions)")

    def has_mentioned_patient(self):
        """Vérifie si un patient a été mentionné dans la session actuelle"""
        return self.current_patient is not None