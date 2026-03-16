from NLPAnalyzer import NLPAnalyzer
from QueryBuilder import QueryBuilder
from DatabaseConnector import DatabaseConnector
from bson import ObjectId
import json


class SimpleContextTester:
    def __init__(self):
        """Initialise le testeur avec tous les composants"""
        try:
            self.nlp_analyzer = NLPAnalyzer()
            self.query_builder = QueryBuilder()
            self.db_connector = DatabaseConnector("mongodb://localhost:27017/")
            print("✅ Testeur initialisé avec tous les composants")
        except Exception as e:
            print(f"❌ Erreur: {e}")

    def test_scenario_with_responses(self, queries):
        """Teste une liste de requêtes avec gestion correcte des patients inexistants"""
        print("🚀 Début du test avec réponses complètes")
        print("=" * 60)

        for i, query in enumerate(queries, 1):
            print(f"\n{'🔍' * 3} REQUÊTE {i}: '{query}' {'🔍' * 3}")

            try:
                # 1. Analyser la requête avec NLP
                analysis = self.nlp_analyzer.analyze(query)

                # 2. 🚨 NOUVEAU: Vérifier si patient inexistant AVANT de passer par DB
                context_decision = analysis.get("context_decision", {})
                if context_decision.get("action") == "unknown_patient":
                    # Afficher les informations d'analyse
                    self._display_context_info(analysis)

                    # Créer une réponse d'erreur directement
                    unknown_patient = context_decision.get("unknown_patient")
                    error_response = {
                        "success": False,
                        "message": f"Le patient '{unknown_patient}' n'existe pas dans la base de données. Veuillez vérifier le nom ou créer ce patient.",
                        "data": [],
                        "error_type": "unknown_patient"
                    }

                    # Afficher la réponse d'erreur
                    self._display_database_response(error_response)
                    print("-" * 60)
                    continue  # ⚡ PASSER À LA REQUÊTE SUIVANTE

                # 3. Construire et exécuter la requête DB seulement si patient valide
                query_spec = self.query_builder.build_query(analysis)

                if "query" in query_spec and query_spec["query"] is not None:
                    db_result = self.db_connector.execute_query(query_spec)
                    converted_result = self._convert_objectid(db_result)
                else:
                    converted_result = {
                        "success": False,
                        "message": query_spec.get("error", "Requête invalide"),
                        "data": []
                    }

                # 4. Afficher les informations
                self._display_context_info(analysis)
                self._display_database_response(converted_result)

                print("-" * 60)

            except Exception as e:
                print(f"   ❌ Erreur: {e}")
                import traceback
                traceback.print_exc()

        print("\n" + "=" * 60)
        print("✅ Test terminé")


    # AUSSI, modifier _display_database_response pour ne pas afficher "patients multiples" si c'est une erreur
    def _display_database_response(self, db_result):
        """Affiche la réponse de la base de données de manière lisible"""
        print("\n💾 RÉPONSE DE LA BASE DE DONNÉES:")

        # Statut de la requête
        success = db_result.get("success", True)
        status_icon = "✅" if success else "❌"
        print(f"   {status_icon} Statut: {'Succès' if success else 'Échec'}")

        # Message
        message = db_result.get("message", "Pas de message")
        print(f"   📝 Message: {message}")

        # 🚨 NOUVEAU: Si c'est une erreur, ne pas afficher les détails des données
        if not success:
            error_type = db_result.get("error_type")
            if error_type:
                print(f"   🚨 Type d'erreur: {error_type}")
            return  # ⚡ SORTIR ICI pour les erreurs

        # Continuer seulement pour les succès
        data = db_result.get("data", [])
        print(f"   📊 Nombre de résultats: {len(data) if isinstance(data, list) else 'N/A'}")

        # Afficher les données en détail
        if data:
            if isinstance(data, list):
                print(f"\n   📋 DÉTAILS DES RÉSULTATS:")
                for idx, item in enumerate(data[:3], 1):  # Limiter à 3 premiers résultats
                    print(f"      {idx}. {self._format_data_item(item)}")
                if len(data) > 3:
                    print(f"      ... et {len(data) - 3} autres résultats")
            else:
                print(f"   📋 DÉTAIL: {self._format_data_item(data)}")

        # Gestion des patients multiples (seulement pour les succès)
        if db_result.get("multiple_patients", False):
            patients_info = db_result.get("patients_info", [])
            print(f"\n   👥 PATIENTS MULTIPLES DÉTECTÉS:")
            for idx, patient in enumerate(patients_info, 1):
                print(
                    f"      {idx}. {patient.get('prenom', '')} {patient.get('nom', '')} (ID: {patient.get('_id', 'N/A')})")

    def _display_context_info(self, analysis):
        """Affiche les informations de contexte et d'analyse"""
        print("\n📊 INFORMATIONS D'ANALYSE:")

        # Contexte
        current_context = self.nlp_analyzer.smart_context.get_current_context()
        print(f"   🎯 Intent détecté: {analysis.get('intent', 'UNKNOWN')}")
        print(f"   👤 Patient mentionné: {analysis.get('entities', {}).get('patient', 'Aucun')}")
        print(f"   🏠 Patient en contexte: {current_context.get('patient', 'Aucun')}")

        # Décision du contexte
        context_decision = analysis.get("context_decision", {})
        print(f"   ⚡ Action du contexte: {context_decision.get('action', 'unknown')}")
        print(f"   💭 Raison: {context_decision.get('reason', 'Pas de raison')}")

        # Entités temporelles
        if analysis.get("entities", {}).get("date"):
            print(f"   📅 Date détectée: {analysis['entities']['date']}")
        if analysis.get("entities", {}).get("time"):
            print(f"   🕒 Heure détectée: {analysis['entities']['time']}")

    def _format_data_item(self, item):
        """Formate un élément de données pour l'affichage"""
        if isinstance(item, dict):
            # Pour les rendez-vous
            if "date" in item and "heure" in item:
                patient_info = item.get("patient", {})
                patient_name = f"{patient_info.get('prenom', '')} {patient_info.get('nom', '')}"
                return f"RDV - {item.get('date')} à {item.get('heure')} - Patient: {patient_name} - Médecin: {item.get('medecin', 'N/A')} - Motif: {item.get('motif', 'N/A')}"

            # Pour les prescriptions
            elif "medicament" in item or "medicaments" in item:
                patient_info = item.get("patient", {})
                patient_name = f"{patient_info.get('prenom', '')} {patient_info.get('nom', '')}"
                medication = item.get("medicament", item.get("medicaments", "N/A"))
                return f"PRESCRIPTION - Patient: {patient_name} - Médicament: {medication} - Dosage: {item.get('dosage', 'N/A')}"

            # Pour les dossiers patients
            elif "nom" in item and "prenom" in item:
                return f"PATIENT - {item.get('prenom', '')} {item.get('nom', '')} - Âge: {self._calculate_age(item.get('date_naissance'))} - Tel: {item.get('telephone', 'N/A')}"

            # Formatage générique
            else:
                key_info = []
                for key, value in list(item.items())[:3]:  # Premiers 3 champs
                    if key != "_id" and value:
                        key_info.append(f"{key}: {value}")
                return " - ".join(key_info)

        return str(item)

    def _calculate_age(self, date_naissance):
        """Calcule l'âge à partir de la date de naissance"""
        if not date_naissance:
            return "N/A"
        try:
            from datetime import datetime
            birth_date = datetime.strptime(date_naissance, "%Y-%m-%d")
            today = datetime.now()
            age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
            return f"{age} ans"
        except:
            return "N/A"

    def _convert_objectid(self, obj):
        """Convertit les ObjectId en chaînes pour l'affichage"""
        if isinstance(obj, dict):
            return {k: self._convert_objectid(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_objectid(item) for item in obj]
        elif isinstance(obj, ObjectId):
            return str(obj)
        return obj

    def test_scenario_json(self, queries):
        """Teste et affiche les réponses en format JSON"""
        print("🚀 Test avec réponses JSON")
        print("=" * 60)

        for i, query in enumerate(queries, 1):
            print(f"\n🔍 REQUÊTE {i}: '{query}'")

            try:
                # Simuler process_nlp_query complet
                analysis = self.nlp_analyzer.analyze(query)

                # Vérifier si patient inexistant
                context_decision = analysis.get("context_decision", {})
                if context_decision.get("action") == "unknown_patient":
                    unknown_patient = context_decision.get("unknown_patient")
                    response = {
                        "success": False,
                        "message": f"Le patient '{unknown_patient}' n'existe pas dans la base de données.",
                        "data": [],
                        "error_type": "unknown_patient",
                        "context_info": self.nlp_analyzer.smart_context.get_current_context(),
                        "context_decision": context_decision
                    }
                else:
                    # Traitement normal
                    query_spec = self.query_builder.build_query(analysis)

                    if "query" in query_spec and query_spec["query"] is not None:
                        db_result = self.db_connector.execute_query(query_spec)
                        response = self._convert_objectid(db_result)
                        response["context_info"] = self.nlp_analyzer.smart_context.get_current_context()
                        response["context_decision"] = context_decision
                    else:
                        response = {
                            "success": False,
                            "message": query_spec.get("error", "Requête invalide"),
                            "data": [],
                            "context_info": self.nlp_analyzer.smart_context.get_current_context()
                        }

                # Afficher la réponse JSON
                print("📄 RÉPONSE JSON:")
                print(json.dumps(response, indent=2, ensure_ascii=False))

            except Exception as e:
                print(f"❌ Erreur: {e}")
                import traceback
                traceback.print_exc()


# ✅ EXEMPLES D'UTILISATION

def main():
    """Exemples de tests avec réponses complètes"""
    tester = SimpleContextTester()

    # Test 1: Scénario normal
    print("\n📋 TEST 1: Scénario avec réponses complètes")
    queries1 = [
        "rendez-vous de sophie",
        "ses prescriptions",
        "dossier de ahmed"  # Patient inexistant
    ]
    tester.test_scenario_with_responses(queries1)

    # Test 2: Format JSON
    print("\n📋 TEST 2: Réponses en format JSON")
    queries2 = [
        "prescriptions de sophie",
        "ses rendez-vous"
    ]
    tester.test_scenario_json(queries2)


def test_quick_responses():
    """Test rapide avec réponses"""
    tester = SimpleContextTester()

    my_queries = [
        "ajouter document de francois",
        "et sophie",
        "ses rendez-vous",
        "et de sophie",
    ]

    tester.test_scenario_with_responses(my_queries)


if __name__ == "__main__":
    # Lance le test que tu veux
    # main()  # Pour tous les exemples
    test_quick_responses()  # Pour un test rapide