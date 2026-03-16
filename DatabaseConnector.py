from bson import ObjectId
from dateparser import parser
from pymongo import MongoClient
from datetime import datetime, timedelta
import re


class DatabaseConnector:
    def __init__(self, connection_string="mongodb://localhost:27017/"):
        """Initialiser la connexion à MongoDB"""
        self.client = MongoClient(connection_string)
        self.db = self.client.PFE  # Changez "PFE" pour le nom de votre base de données

    def execute_query(self, query_spec):
        """Exécuter une requête MongoDB et formatter le résultat avec gestion des homonymes"""
        # Vérifier si la spécification de requête est valide
        if not query_spec:
            return {"success": False, "message": "Requête non spécifiée"}

        print(">>> DEBUG QUERY SPEC:", query_spec)

        if "query" not in query_spec:
            return {"success": False, "message": query_spec.get("error", "Requête invalide")}

        collection = self.db["patient"]
        projection = query_spec.get("projection")
        results = collection.find(query_spec["query"], projection) if projection else collection.find(
            query_spec["query"])

        result_list = [
            {k: str(v) if isinstance(v, ObjectId) else v for k, v in result.items()}
            for result in results
        ]

        intent = query_spec.get("intent")
        time_constraint = query_spec.get("time_constraint")
        specific_date = query_spec.get("specific_date")

        # CAS SPÉCIAUX : DOCUMENT_PATIENT et DOSSIER_PATIENT
        # Ces intents sont gérés côté frontend, on retourne juste les patients trouvés
        if intent in ["DOCUMENT_PATIENT", "DOSSIER_PATIENT"]:
            if query_spec.get("expect_multiple", False) and len(result_list) > 1:
                return self.format_multiple_patients_response(query_spec, result_list)
            elif len(result_list) == 1:
                # Un seul patient trouvé - retourner directement les données
                return {
                    "success": True,
                    "message": f"Patient trouvé: {result_list[0].get('prenom', '')} {result_list[0].get('nom', '')}",
                    "data": result_list,
                    "intent": intent
                }
            else:
                # Aucun patient trouvé
                return {
                    "success": True,
                    "message": "Aucun patient trouvé avec ce nom",
                    "data": [],
                    "intent": intent
                }

        # Vérifier si on filtre par période mensuelle
        if time_constraint == "MONTH_PERIOD" and specific_date:
            date_parts = specific_date.split("-")
            year, month = int(date_parts[0]), int(date_parts[1])

            all_entries = []
            for patient in result_list:
                if intent == "RENDEZ_VOUS":
                    patient_entries = [
                        rdv for rdv in patient.get("rendez_vous", [])
                        if rdv.get("date", "").startswith(f"{year}-{month:02d}")
                    ]
                elif intent == "PRESCRIPTION":
                    patient_entries = [
                        prescription for prescription in patient.get("prescriptions", [])
                        if prescription.get("date", "").startswith(f"{year}-{month:02d}")
                    ]
                else:
                    return {"success": False, "message": "Intent non reconnu"}

                for entry in patient_entries:
                    formatted_entry = {
                        "date": entry.get("date", "Date non spécifiée"),
                        "medecin": entry.get("medecin", "Médecin non spécifié"),
                        "patient": {
                            "id": str(patient.get("_id", "")),
                            "nom": patient.get("nom", "Nom non spécifié"),
                            "prenom": patient.get("prenom", "Prénom non spécifié")
                        }
                    }
                    if intent == "RENDEZ_VOUS":
                        formatted_entry.update({
                            "heure": entry.get("heure", "Heure non spécifiée"),
                            "motif": entry.get("motif", "Motif non spécifié")
                        })
                    elif intent == "PRESCRIPTION":
                        formatted_entry.update({
                            "medicaments": entry.get("medicaments", "Médicaments non spécifiés")
                        })

                    all_entries.append(formatted_entry)

            month_name = self.get_month_name(month)
            return {
                "success": True,
                "message": f"{len(all_entries)} {intent.lower()}(s) trouvée(s) pour le mois de {month_name} {year}",
                "data": all_entries
            }

        # Gérer les autres types de requêtes
        if query_spec.get("all_patients", False):
            return self.process_all_patients_query(query_spec, result_list)
        if query_spec.get("expect_multiple", False) and len(result_list) > 1:
            return self.format_multiple_patients_response(query_spec, result_list)
        if intent == "RENDEZ_VOUS":
            return self.format_appointment_response(query_spec, result_list)
        elif intent == "PRESCRIPTION":
            return self.format_prescription_response(query_spec, result_list)
        else:
            return {
                "success": True,
                "message": f"{len(result_list)} résultat(s) trouvé(s)",
                "data": result_list
            }

    def format_multiple_patients_response(self, query_spec, result_list):
        """Formatter une réponse pour le cas où plusieurs patients partagent le même nom"""
        intent = query_spec.get("intent")

        # Extraire les informations de base de chaque patient
        patients_basic_info = []
        for patient in result_list:
            patient_info = {
                "_id": str(patient.get("_id")),
                "nom": patient.get("nom", ""),
                "prenom": patient.get("prenom", ""),
                "dateNaissance": patient.get("dateNaissance", ""),
                "image": patient.get("image", ""),
            }
            if patient_info["image"]:
                if patient_info["image"].startswith("data:image"):
                    patient_info["image_type"] = "Base64"
                else:
                    patient_info["image_type"] = "URL"
            else:
                patient_info["image_type"] = "Aucune image disponible"
            patients_basic_info.append(patient_info)

        # Pour DOCUMENT_PATIENT et DOSSIER_PATIENT, pas besoin de traitement complexe
        if intent in ["DOCUMENT_PATIENT", "DOSSIER_PATIENT"]:
            return {
                "success": True,
                "message": f"{len(result_list)} patients trouvés avec ce nom",
                "multiple_patients": True,
                "patients_info": patients_basic_info,
                "intent": intent
            }

        # Traiter chaque patient selon l'intention pour les autres cas
        all_patient_data = []
        for patient in result_list:
            if intent == "RENDEZ_VOUS":
                patient_response = self.get_appointments_for_patient(query_spec, patient)
            elif intent == "PRESCRIPTION":
                patient_response = self.process_prescriptions_for_patient(query_spec, patient)
            else:
                patient_response = patient

            all_patient_data.append({
                "patient_id": str(patient.get("_id")),
                "response": patient_response
            })

        # Construire la réponse finale
        return {
            "success": True,
            "message": f"{len(result_list)} patients trouvés avec ce nom",
            "multiple_patients": True,
            "patients_info": patients_basic_info,
            "all_data": all_patient_data,
            "intent": intent
        }

    def get_month_name(self, month):
        months = {
            1: "janvier", 2: "février", 3: "mars", 4: "avril",
            5: "mai", 6: "juin", 7: "juillet", 8: "août",
            9: "septembre", 10: "octobre", 11: "novembre", 12: "décembre"
        }
        return months.get(month, "mois inconnu")

    def format_appointment_response(self, query_spec, result_list):
        """Formatter la réponse pour une requête de rendez-vous"""
        if not result_list:
            # Vérifier si le patient existe sans les contraintes de rendez-vous
            patient_name = None
            if 'query' in query_spec and '$or' in query_spec['query']:
                # Extraire le nom du patient à partir de la requête
                for condition in query_spec['query']['$or']:
                    if 'nom' in condition and '$regex' in condition['nom']:
                        patient_name = condition['nom']['$regex'].strip('^$')
                        break
                    elif 'prenom' in condition and '$regex' in condition['prenom']:
                        patient_name = condition['prenom']['$regex'].strip('^$')
                        break

            if patient_name:
                # Vérifier si le patient existe sans contrainte de rendez-vous
                patient_query = {'$or': [
                    {'nom': {'$regex': f'^{patient_name}$', '$options': 'i'}},
                    {'prenom': {'$regex': f'^{patient_name}$', '$options': 'i'}}
                ]}

                patient_exists = self.db["patient"].find_one(patient_query)

                if patient_exists:
                    time_constraint = query_spec.get('time_constraint')
                    if time_constraint == "NEXT":
                        return {
                            "success": True,
                            "message": f"Le patient {patient_name} existe mais n'a pas de rendez-vous futurs",
                            "data": []
                        }
                    elif time_constraint == "LAST":
                        return {
                            "success": True,
                            "message": f"Le patient {patient_name} existe mais n'a pas de rendez-vous passés",
                            "data": []
                        }
                    else:
                        return {
                            "success": True,
                            "message": f"Le patient {patient_name} existe mais n'a pas de rendez-vous correspondant aux critères",
                            "data": []
                        }

            # Si on arrive ici, c'est que le patient n'existe pas
            return {
                "success": True,
                "message": "Aucun patient trouvé avec ce nom",
                "data": []
            }

        patient = result_list[0]
        appointment_result = self.get_appointments_for_patient(query_spec, patient)

        # Extraire la liste des rendez-vous du résultat
        appointments = appointment_result.get("data", [])

        specific_date = query_spec.get("specific_date")
        if specific_date:
            if "-" in specific_date:  # Si c'est un mois spécifié (format YYYY-MM)
                # Extraire l'année et le mois de la date spécifique
                date_parts = specific_date.split("-")
                year = int(date_parts[0])
                month = int(date_parts[1])

                # Générer le message avec le mois et l'année
                message = f"{len(appointments)} rendez-vous trouvé(s) pour le mois de {self.get_month_name(month)} {year}"
            else:
                # Si c'est une date précise (format YYYY-MM-DD), la convertir en format français
                try:
                    # Convertir la date au format français (JJ/MM/AAAA)
                    date_obj = datetime.strptime(specific_date, "%Y-%m-%d")
                    date_fr_literal = date_obj.strftime("%d %B %Y").lower()

                    message = f"{len(appointments)} rendez-vous trouvé(s) pour {patient.get('prenom')} {patient.get('nom')} le {date_fr_literal}"
                except ValueError:
                    # Si le format de date n'est pas valide, utiliser la date telle quelle
                    message = f"{len(appointments)} rendez-vous trouvé(s) pour {patient.get('prenom')} {patient.get('nom')} le {specific_date}"
        else:
            # Si aucune date spécifique, afficher le message générique
            message = f"{len(appointments)} rendez-vous trouvé(s) pour {patient.get('prenom')} {patient.get('nom')}"

        return {
            "success": True,
            "message": message,
            "data": appointments
        }

    def get_appointments_for_patient(self, query_spec, patient):
        """Récupérer les rendez-vous pour un patient donné"""
        # Extraction des rendez-vous du patient
        appointments = patient.get("rendez_vous", [])
        print(
            f"Rendez-vous pour le patient {patient.get('nom')} {patient.get('prenom')}: {appointments}")

        # Gestion des rendez-vous par période mensuelle
        if query_spec.get("time_constraint") == "MONTH_PERIOD" and query_spec.get("specific_date"):
            # Extraire l'année et le mois de la date spécifique
            date_parts = query_spec["specific_date"].split("-")
            year = int(date_parts[0])
            month = int(date_parts[1])

            # Filtrer les rendez-vous pour ce mois
            appointments = [
                rdv for rdv in appointments
                if rdv.get("date", "").startswith(f"{year}-{month:02d}")
            ]

            if not appointments:
                message = f"Aucun rendez-vous trouvé pour le mois de {self.get_month_name(month)} {year}"
                return {
                    "message": message,
                    "data": []
                }

            message = f"{len(appointments)} rendez-vous trouvé(s) pour le mois de {self.get_month_name(month)} {year}"

        # Filtrer par date si nécessaire (code existant)
        else:
            specific_date = query_spec.get("specific_date")
            if specific_date == "aujourd'hui":
                specific_date = datetime.now().strftime("%Y-%m-%d")
            elif specific_date == "demain":
                specific_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
            elif specific_date == "hier":
                specific_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            elif specific_date == "avant-hier":
                specific_date = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")

            if specific_date:
                appointments = [
                    rdv for rdv in appointments
                    if rdv.get("date") == specific_date
                ]

            # Si aucun rendez-vous n'est trouvé, retourner un message spécifique
            if not appointments:
                print(
                    f"Aucun rendez-vous trouvé pour le patient {patient.get('nom')} {patient.get('prenom')}")
                return {
                    "message": f"Aucun rendez-vous trouvé pour le patient {patient.get('nom')} {patient.get('prenom')}.",
                    "data": []
                }

            message = f"Rendez-vous trouvé pour le patient {patient.get('nom')} {patient.get('prenom')}"
            if specific_date:
                message += f" le {specific_date}"

        # Formatage des rendez-vous
        formatted_appointments = []
        for rdv in appointments:
            formatted_rdv = {
                "date": rdv.get("date", "Date non spécifiée"),
                "heure": rdv.get("heure", "Heure non spécifiée"),
                "motif": rdv.get("motif", "Motif non spécifié"),
                "medecin": rdv.get("medecin", "Médecin non spécifié"),
                "patient": {
                    "id": str(patient.get("_id", "")),
                    "nom": patient.get("nom", "Nom non spécifié"),
                    "prenom": patient.get("prenom", "Prénom non spécifié")
                }
            }
            formatted_appointments.append(formatted_rdv)

        return {
            "message": message,
            "data": formatted_appointments
        }

    def format_prescription_response(self, query_spec, result_list):
        """Formatter les résultats de prescriptions à partir du document patient"""
        if not result_list:
            return {
                "success": True,
                "message": "Aucun patient trouvé avec ce nom",
                "data": []
            }

        patient = result_list[0]
        # Traitement des prescriptions
        response = self.process_prescriptions_for_patient(query_spec, patient)

        # Création d'informations du patient pour les annexer aux médicaments
        patient_info = {
            "id": str(patient.get("_id", "")),
            "nom": patient.get("nom", ""),
            "prenom": patient.get("prenom", "")
        }

        # Formatage des prescriptions avec les informations du patient
        formatted_data = []

        for prescription in response.get("data", []):
            # Vérifier si la prescription contient un tableau de médicaments
            if "medicaments" in prescription and isinstance(prescription["medicaments"], list):
                # Cas avec tableau de médicaments
                for medicament in prescription["medicaments"]:
                    formatted_med = {
                        "date": prescription.get("date", "Non spécifié"),
                        "patient": patient_info
                    }

                    # Ajouter les détails du médicament
                    if isinstance(medicament, dict):
                        formatted_med["medicament"] = medicament.get("nom", "Non spécifié")
                        formatted_med["dosage"] = medicament.get("dosage", "Non spécifiée")
                        formatted_med["frequence"] = medicament.get("frequence", "Non spécifiée")
                        formatted_med["duree"] = medicament.get("duree", "")
                    else:
                        # Si le médicament est une chaîne simple
                        formatted_med["medicament"] = str(medicament)
                        formatted_med["dosage"] = "Non spécifiée"
                        formatted_med["frequence"] = "Non spécifiée"

                    formatted_data.append(formatted_med)
            else:
                # Cas avec médicament direct dans la prescription
                formatted_med = {
                    "date": prescription.get("date", "Non spécifié"),
                    "medicament": prescription.get("medicament", "Non spécifié"),
                    "dosage": prescription.get("dosage", "Non spécifiée"),
                    "frequence": prescription.get("frequence", "Non spécifiée"),
                    "duree": prescription.get("duree", ""),
                    "patient": patient_info
                }
                formatted_data.append(formatted_med)

        return {
            "success": True,
            "message": response.get("message", ""),
            "data": formatted_data
        }

    def process_prescriptions_for_patient(self, query_spec, patient):
        """Traiter les prescriptions pour un patient spécifique"""
        patient_name = f"{patient.get('prenom', '')} {patient.get('nom', '')}"
        prescriptions = patient.get("prescriptions", [])

        # Créer un objet patient qui sera attaché à chaque prescription
        patient_info = {
            "id": str(patient.get("_id", "")),
            "nom": patient.get("nom", ""),
            "prenom": patient.get("prenom", "")
        }

        if not prescriptions:
            return {
                "message": f"Aucune prescription trouvée pour {patient_name}",
                "data": []
            }

        time_constraint = query_spec.get("time_constraint", "ALL")
        specific_date = query_spec.get("specific_date")

        # Trier les prescriptions par date
        sorted_prescriptions = sorted(prescriptions, key=lambda x: x.get("date", ""))

        # Filtrer par date spécifique si fournie
        if specific_date:
            filtered_prescriptions = [pres for pres in sorted_prescriptions if pres.get("date") == specific_date]
            if filtered_prescriptions:
                # Formater les médicaments
                medications_list = []
                for prescription in filtered_prescriptions:
                    # Ajouter le patient à la prescription
                    prescription["patient"] = patient_info

                    meds = prescription.get("medicaments", [])
                    if meds:
                        for med in meds:
                            if isinstance(med, dict):
                                med_info = f"{med.get('nom', '')} {med.get('dosage', '')}"
                                medications_list.append(med_info)
                            elif isinstance(med, str):
                                medications_list.append(med)

                medications_text = ", ".join(medications_list) if medications_list else "données non disponibles"

                return {
                    "message": f"Prescriptions pour {patient_name} du {specific_date}: {medications_text}",
                    "data": filtered_prescriptions
                }
            else:
                return {
                    "message": f"Aucune prescription trouvée pour {patient_name} le {specific_date}",
                    "data": []
                }

        if time_constraint == "LAST":
            if sorted_prescriptions:

                # Ajouter le patient à la prescription
                last_prescription["patient"] = patient_info

                # Formater les médicaments
                meds = last_prescription.get("medicaments", [])
                medications_list = []

                if meds:
                    for med in meds:
                        if isinstance(med, dict):
                            med_info = f"{med.get('nom', '')} {med.get('dosage', '')}"
                            medications_list.append(med_info)
                        elif isinstance(med, str):
                            medications_list.append(med)

                medications_text = ", ".join(medications_list) if medications_list else "données non disponibles"

                return {
                    "message": f"Dernière prescription pour {patient_name}: {medications_text} (du {last_prescription.get('date', 'date inconnue')})",
                    "data": [last_prescription]
                }
            else:
                return {
                    "message": f"Aucune prescription trouvée pour {patient_name}",
                    "data": []
                }

        elif time_constraint == "PRESENT":
            # Chercher les prescriptions d'aujourd'hui
            today = datetime.now().strftime("%Y-%m-%d")
            today_prescriptions = [pres for pres in sorted_prescriptions if pres.get("date", "") == today]

            if today_prescriptions:
                # Ajouter le patient à chaque prescription
                for prescription in today_prescriptions:
                    prescription["patient"] = patient_info

                # Formater les médicaments
                medications_list = []
                for prescription in today_prescriptions:
                    meds = prescription.get("medicaments", [])
                    if meds:
                        for med in meds:
                            if isinstance(med, dict):
                                med_info = f"{med.get('nom', '')} {med.get('dosage', '')}"
                                medications_list.append(med_info)
                            elif isinstance(med, str):
                                medications_list.append(med)

                medications_text = ", ".join(medications_list) if medications_list else "données non disponibles"

                return {
                    "message": f"Prescriptions d'aujourd'hui pour {patient_name}: {medications_text}",
                    "data": today_prescriptions
                }
            else:
                return {
                    "message": f"Aucune prescription pour aujourd'hui trouvée pour {patient_name}",
                    "data": []
                }
        else:
            # Ajouter le patient à chaque prescription
            for prescription in sorted_prescriptions:
                prescription["patient"] = patient_info

            # Formater toutes les prescriptions
            medications_by_date = {}
            for prescription in sorted_prescriptions:
                date = prescription.get("date", "date inconnue")
                if date not in medications_by_date:
                    medications_by_date[date] = []

                meds = prescription.get("medicaments", [])
                if meds:
                    for med in meds:
                        if isinstance(med, dict):
                            med_info = f"{med.get('nom', '')} {med.get('dosage', '')}"
                            medications_by_date[date].append(med_info)
                        elif isinstance(med, str):
                            medications_by_date[date].append(med)

            # Créer un message résumé
            prescriptions_summary = [f"{date}: {', '.join(meds)}" for date, meds in medications_by_date.items()]
            prescriptions_text = " | ".join(
                prescriptions_summary) if prescriptions_summary else "détails non disponibles"

            return {
                "message": f"{len(prescriptions)} prescriptions trouvées pour {patient_name}. Résumé: {prescriptions_text}",
                "data": sorted_prescriptions
            }

    def process_all_patients_query(self, query_spec, result_list):
        """Traiter une requête qui s'applique à tous les patients"""
        intent = query_spec.get("intent")
        time_constraint = query_spec.get("time_constraint", "ALL")
        specific_date = query_spec.get("specific_date")

        if intent == "RENDEZ_VOUS":
            # Collecter tous les rendez-vous de tous les patients
            all_appointments = []

            # Convertir today en chaîne au format YYYY-MM-DD pour la comparaison
            today = datetime.now().strftime("%Y-%m-%d")

            for patient in result_list:
                appointments = patient.get("rendez_vous", [])

                if not appointments:
                    continue

                # FILTRAGE STRICT PAR DATE SPÉCIFIQUE EN PREMIER
                if specific_date:
                    filtered_appointments = [appt for appt in appointments if
                                             str(appt.get("date", "")) == specific_date]
                elif time_constraint == "NEXT":
                    filtered_appointments = [appt for appt in appointments if str(appt.get("date", "")) >= today]
                    filtered_appointments.sort(key=lambda x: str(x.get("date", "")))
                elif time_constraint == "LAST":
                    filtered_appointments = [appt for appt in appointments if str(appt.get("date", "")) < today]
                    filtered_appointments.sort(key=lambda x: str(x.get("date", "")), reverse=True)
                elif time_constraint == "PRESENT":
                    filtered_appointments = [appt for appt in appointments if str(appt.get("date", "")) == today]
                else:
                    filtered_appointments = sorted(appointments, key=lambda x: str(x.get("date", "")))

                # Ajouter les informations du patient à chaque rendez-vous
                for appt in filtered_appointments:
                    enriched_appt = appt.copy()
                    enriched_appt["date"] = appt.get("date", "Date non spécifiée")
                    enriched_appt["heure"] = appt.get("heure", "Heure non spécifiée")
                    enriched_appt["motif"] = appt.get("motif", "Motif non spécifié")
                    enriched_appt["medecin"] = appt.get("medecin", "Médecin non spécifié")
                    enriched_appt["patient"] = {
                        "id": str(patient.get("_id")),
                        "nom": patient.get("nom", ""),
                        "prenom": patient.get("prenom", "")
                    }
                    all_appointments.append(enriched_appt)

            # DEUXIÈME FILTRAGE DE SÉCURITÉ : S'assurer qu'on a seulement les RDVs de la date demandée
            if specific_date:
                all_appointments = [appt for appt in all_appointments
                                    if str(appt.get("date", "")) == specific_date]

            # Trier tous les rendez-vous par date
            all_appointments.sort(key=lambda x: str(x.get("date", "")))

            # Message à renvoyer selon la requête
            if time_constraint == "NEXT" and all_appointments:
                original_text = query_spec.get("original_text", "").lower()
                singular_indicators = ["prochain rendez", "prochain rdv", "le prochain", "le suivant"]
                plural_indicators = ["prochains rendez", "prochains rdv", "les prochains", "les suivants"]

                is_singular = any(indicator in original_text for indicator in singular_indicators)
                is_plural = any(indicator in original_text for indicator in plural_indicators)

                if is_singular and not is_plural:
                    next_date = all_appointments[0].get("date")

                    import locale

                    all_appointments = [appt for appt in all_appointments if appt.get("date") == next_date]

                    try:
                        # Essayer de mettre la locale en français
                        try:
                            locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
                        except locale.Error:
                            # Fallback si fr_FR.UTF-8 n'est pas disponible
                            try:
                                locale.setlocale(locale.LC_TIME, 'fr_FR')
                            except locale.Error:
                                pass  # Utiliser la locale par défaut si aucune française n'est disponible

                        # Convertir la date au format français
                        date_obj = datetime.strptime(next_date, "%Y-%m-%d")
                        date_fr_literal = date_obj.strftime("%d %B %Y").lower()

                        # Utiliser le format littéral pour le message
                        message = f"Le prochain rendez-vous est prévu le {date_fr_literal}"
                    except Exception as e:
                        print(f"Erreur lors de la conversion de date : {e}")
                        # Fallback au format original en cas d'erreur
                        message = f"Le prochain rendez-vous est prévu le {next_date}"
                else:
                    message = f"{len(all_appointments)} prochains rendez-vous trouvés"
            elif specific_date:
                import locale
                # Si c'est une date précise (format YYYY-MM-DD), la convertir en format français
                try:
                    # Mettre la locale en français
                    locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')

                    # Convertir la date au format français (JJ/MM/AAAA)
                    date_obj = datetime.strptime(specific_date, "%Y-%m-%d")
                    date_fr_literal = date_obj.strftime("%d %B %Y").lower()

                    message = f"{len(all_appointments)} rendez-vous trouvé(s) pour le {date_fr_literal}"

                except ValueError:
                    # Si le format de date n'est pas valide, utiliser la date telle quelle
                    message = f"{len(all_appointments)} rendez-vous trouvé(s) pour le {specific_date}"
            elif time_constraint == "PRESENT":
                message = f"{len(all_appointments)} rendez-vous aujourd'hui"
            elif time_constraint == "NEXT":
                message = "Aucun rendez-vous futur trouvé"
            elif time_constraint == "LAST":
                message = f"{len(all_appointments)} rendez-vous passés trouvés"
            else:
                message = f"{len(all_appointments)} rendez-vous trouvés au total"

            return {
                "success": True,
                "message": message,
                "data": all_appointments
            }

        elif intent == "PRESCRIPTION":
            # Collecter toutes les prescriptions de tous les patients
            all_prescriptions = []

            today = datetime.now().strftime("%Y-%m-%d")

            for patient in result_list:
                prescriptions = patient.get("prescriptions", [])

                if not prescriptions:
                    continue

                # Filtrage par date spécifique
                if specific_date:
                    filtered_prescriptions = [p for p in prescriptions if
                                              str(p.get("date", "")) == specific_date]
                elif time_constraint == "NEXT":
                    filtered_prescriptions = [p for p in prescriptions if
                                              p.get("date", "") and p.get("date", "") >= today]
                    filtered_prescriptions.extend([p for p in prescriptions if not p.get("date")])
                    filtered_prescriptions.sort(key=lambda x: x.get("date", ""))
                elif time_constraint == "LAST":
                    dated_prescriptions = [p for p in prescriptions if p.get("date", "")]
                    dated_prescriptions.sort(key=lambda x: x.get("date", ""), reverse=True)

                    if dated_prescriptions:
                        latest_date = dated_prescriptions[0].get("date")
                        filtered_prescriptions = [p for p in dated_prescriptions if p.get("date") == latest_date]
                    else:
                        filtered_prescriptions = []

                    filtered_prescriptions.extend([p for p in prescriptions if not p.get("date")])
                elif time_constraint == "PRESENT":
                    filtered_prescriptions = [p for p in prescriptions if p.get("date", "") == today]
                    filtered_prescriptions.extend([p for p in prescriptions if not p.get("date")])
                else:
                    filtered_prescriptions = sorted([p for p in prescriptions if p.get("date", "")],
                                                    key=lambda x: x.get("date", ""))
                    filtered_prescriptions.extend([p for p in prescriptions if not p.get("date")])

                for p in filtered_prescriptions:
                    enriched_p = p.copy()

                    # Format avec medicaments array
                    medicaments = p.get("medicaments", [])
                    formatted_meds = []

                    if isinstance(medicaments, list) and len(medicaments) > 0:
                        for med in medicaments:
                            if isinstance(med, dict):
                                formatted_med = {
                                    "medicament": med.get("nom", "Non spécifié"),
                                    "dosage": med.get("dosage", "Non spécifiée"),
                                    "frequence": med.get("frequence", "Non spécifiée"),
                                    "duree": med.get("duree", "")
                                }
                            else:
                                formatted_med = {
                                    "medicament": str(med),
                                    "dosage": "Non spécifiée",
                                    "frequence": "Non spécifiée"
                                }
                            formatted_meds.append(formatted_med)

                    enriched_p["medicaments_formates"] = formatted_meds
                    enriched_p["date_prescription"] = str(p.get("date", "En cours"))
                    enriched_p["patient"] = {
                        "id": str(patient.get("_id")),
                        "nom": patient.get("nom", ""),
                        "prenom": patient.get("prenom", "")
                    }

                    all_prescriptions.append(enriched_p)

            # Filtrage de sécurité
            if specific_date:
                all_prescriptions = [p for p in all_prescriptions
                                     if str(p.get("date_prescription", "")) == specific_date]

            # Trier les prescriptions
            all_prescriptions.sort(key=lambda x: x.get("date_prescription", ""))

            # Messages selon le contexte
            if specific_date:
                import locale
                try:
                    locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
                    date_obj = datetime.strptime(specific_date, "%Y-%m-%d")
                    date_fr_literal = date_obj.strftime("%d %B %Y").lower()
                    message = f"{len(all_prescriptions)} prescription(s) trouvée(s) pour le {date_fr_literal}"
                except ValueError:
                    message = f"{len(all_prescriptions)} prescription(s) trouvée(s) pour le {specific_date}"
            elif time_constraint == "PRESENT":
                message = f"{len(all_prescriptions)} prescription(s) aujourd'hui"
            elif time_constraint == "LAST":
                message = f"{len(all_prescriptions)} prescription(s) récente(s) trouvée(s)"
            elif time_constraint == "NEXT":
                message = f"{len(all_prescriptions)} prescription(s) future(s) trouvée(s)"
            else:
                message = f"{len(all_prescriptions)} prescription(s) trouvée(s) au total"

            formatted_prescriptions = []
            for p in all_prescriptions:
                for med in p.get("medicaments_formates", []):
                    med_with_patient = med.copy()
                    med_with_patient["patient"] = p.get("patient", {})
                    med_with_patient["date_prescription"] = p.get("date_prescription", "En cours")
                    formatted_prescriptions.append(med_with_patient)

            return {
                "success": True,
                "message": message,
                "data": formatted_prescriptions
            }

        return {
            "success": True,
            "message": f"{len(result_list)} patients trouvés",
            "data": result_list
        }