from calendar import monthrange
from datetime import datetime, date, timedelta


class QueryBuilder:
    def __init__(self):
        pass

    def build_query(self, analysis):
        intent = analysis["intent"]
        entities = analysis["entities"]
        time_constraint = analysis["time_constraint"]
        specific_date = analysis.get("specific_date")
        original_text = analysis.get("original_text", "")

        if intent == "UNKNOWN":
            return {
                "query": None,
                "projection": None,
                "error": "Je ne comprends pas votre demande. Pouvez-vous reformuler ou préciser ce que vous recherchez concernant les rendez-vous, les dossiers patients ou les prescriptions?"
            }

        if intent == "RENDEZ_VOUS":
            return self.build_appointment_query(entities, time_constraint, specific_date, original_text)
        elif intent == "DOSSIER_PATIENT":
            return self.build_patient_info_query(entities)
        elif intent == "PRESCRIPTION":
            return self.build_prescription_query(entities, time_constraint, specific_date, original_text)
        elif intent == "DOCUMENT_PATIENT":
            return self.build_document_query(entities)
        else:
            return {
                "query": None,
                "projection": None,
                "error": "Intention non reconnue. Je peux vous aider avec vos rendez-vous, dossiers patients ou prescriptions."
            }

    def build_document_query(self, entities):
        patient = entities.get("patient")

        if not patient:
            return {
                "query": {},
                "projection": None,
                "intent": "DOCUMENT_PATIENT",
                "expect_multiple": True
            }

        patient_parts = patient.strip().split()
        query = {"$or": []}

        if len(patient_parts) == 1:
            query["$or"].extend([
                {"nom": {"$regex": f"^{patient_parts[0]}$", "$options": "i"}},
                {"prenom": {"$regex": f"^{patient_parts[0]}$", "$options": "i"}}
            ])
        elif len(patient_parts) >= 2:
            query["$or"].extend([
                {"$and": [
                    {"prenom": {"$regex": f"^{patient_parts[0]}$", "$options": "i"}},
                    {"nom": {"$regex": f"^{patient_parts[1]}$", "$options": "i"}}
                ]},
                {"$and": [
                    {"nom": {"$regex": f"^{patient_parts[0]}$", "$options": "i"}},
                    {"prenom": {"$regex": f"^{patient_parts[1]}$", "$options": "i"}}
                ]}
            ])

        projection = None

        return {
            "query": query,
            "projection": projection,
            "intent": "DOCUMENT_PATIENT",
            "expect_multiple": True
        }

    def build_appointment_query(self, entities, time_constraint, specific_date, original_text):
        """Construire une requête pour les rendez-vous d'un patient ou tous les rendez-vous"""
        # S'assurer que entities est toujours un dictionnaire, même vide
        if entities is None:
            entities = {}

        patient = entities.get("patient")

        # Corriger les faux positifs temporels
        if patient and patient.lower() in ["demain", "aujourd'hui", "hier", "next", "tomorrow", "today", "yesterday"]:
            patient = None

        query = {}

        projection = {
            "nom": 1,
            "prenom": 1,
            "dateNaissance": 1,
            "rendez_vous": 1,
            "image": 1
        }

        # Vérifier si la requête concerne un mois spécifique en analysant le texte original
        if "mois" in original_text.lower():
            # Dictionnaire des mois en français
            months_fr = {
                "janvier": "01", "février": "02", "mars": "03", "avril": "04",
                "mai": "05", "juin": "06", "juillet": "07", "août": "08",
                "septembre": "09", "octobre": "10", "novembre": "11", "décembre": "12"
            }

            # Extraire le mois du texte original
            for month_name, month_num in months_fr.items():
                if month_name in original_text.lower():
                    # Extraire l'année (par défaut l'année en cours si non spécifiée)
                    year = datetime.now().year
                    for year_str in [str(y) for y in range(2020, 2030)]:
                        if year_str in original_text:
                            year = int(year_str)
                            break

                    # Premier jour du mois
                    start_date = f"{year}-{month_num}-01"

                    # Dernier jour du mois
                    from calendar import monthrange
                    _, last_day = monthrange(int(year), int(month_num))
                    end_date = f"{year}-{month_num}-{last_day}"

                    # Requête pour couvrir toute la période du mois
                    query["rendez_vous.date"] = {
                        "$gte": start_date,  # À partir du 1er jour du mois
                        "$lte": end_date  # Jusqu'au dernier jour du mois
                    }

                    # Mettre à jour time_constraint pour cohérence
                    time_constraint = "MONTH_PERIOD"
                    specific_date = f"{year}-{month_num}"
                    break
        # Traiter le cas où time_constraint est déjà MONTH_PERIOD
        elif time_constraint == "MONTH_PERIOD" and specific_date:
            # Extraire le mois et l'année du texte spécifique
            try:
                month_year = specific_date.split('-')
                year = month_year[0]
                month = month_year[1]

                # Premier jour du mois
                start_date = f"{year}-{month}-01"

                # Dernier jour du mois
                from calendar import monthrange
                _, last_day = monthrange(int(year), int(month))
                end_date = f"{year}-{month}-{last_day}"

                # Requête pour couvrir toute la période du mois
                query["rendez_vous.date"] = {
                    "$gte": start_date,  # À partir du 1er jour du mois
                    "$lte": end_date  # Jusqu'au dernier jour du mois
                }

            except Exception as e:
                # En cas d'erreur, renvoyer la requête standard
                print(f"Erreur lors du traitement de la date spécifique : {e}")
                query["rendez_vous.date"] = specific_date

        # Gérer les dates spécifiques comme "hier", "aujourd'hui", "demain"
        if specific_date in ["hier", "yesterday"]:
            specific_date = (datetime.now() - timedelta(1)).strftime('%Y-%m-%d')  # Calculer la date d'hier
        elif specific_date in ["aujourd'hui", "today"]:
            specific_date = datetime.now().strftime('%Y-%m-%d')  # Calculer la date d'aujourd'hui
        elif specific_date == "demain" or specific_date == "tomorrow":
            specific_date = (datetime.now() + timedelta(1)).strftime('%Y-%m-%d')  # Calculer la date de demain

        # Si aucun patient n'est spécifié
        if not patient:
            # Si aucune requête de période mensuelle n'a été construite
            if "rendez_vous.date" not in query:
                if specific_date:
                    query["rendez_vous.date"] = specific_date  # Rechercher dans les rendez-vous
                elif time_constraint and time_constraint != "ALL":
                    current_date = datetime.now().strftime('%Y-%m-%d')
                    if time_constraint == "LAST":
                        query["rendez_vous.date"] = {"$lt": current_date}  # Avant aujourd'hui
                    elif time_constraint == "NEXT":
                        query["rendez_vous.date"] = {"$gte": current_date}  # À partir d'aujourd'hui
            return {
                "query": query,
                "projection": projection,
                "intent": "RENDEZ_VOUS",
                "time_constraint": time_constraint,
                "specific_date": specific_date,
                "all_patients": True,
                "original_text": original_text,
                "expect_multiple": True
            }

        # Si un patient est spécifié
        else:
            name_parts = patient.split()

            if len(name_parts) > 1:
                # Cas avec prénom et nom
                first_name = name_parts[0]
                last_name = name_parts[1]

                query["$or"] = [
                    # Correspondance exacte prénom ET nom (case-insensitive)
                    {"$and": [
                        {"prenom": {"$regex": f"^{first_name}$", "$options": "i"}},
                        {"nom": {"$regex": f"^{last_name}$", "$options": "i"}}
                    ]},
                    # Correspondance exacte nom ET prénom inversés (case-insensitive)
                    {"$and": [
                        {"nom": {"$regex": f"^{first_name}$", "$options": "i"}},
                        {"prenom": {"$regex": f"^{last_name}$", "$options": "i"}}
                    ]},
                    # Correspondance de nom composé
                    {"prenom": {"$regex": f"^{patient}$", "$options": "i"}},
                    {"nom": {"$regex": f"^{patient}$", "$options": "i"}}
                ]
            else:
                # Cas simple avec un seul mot (prénom ou nom)
                query["$or"] = [
                    # Correspondance exacte case-insensitive
                    {"nom": {"$regex": f"^{patient}$", "$options": "i"}},
                    {"prenom": {"$regex": f"^{patient}$", "$options": "i"}}
                ]

            # Ajouter les contraintes de temps si spécifiées
            if specific_date:
                query["rendez_vous"] = {
                    "$elemMatch": {
                        "date": specific_date
                    }
                }
            elif time_constraint and time_constraint != "ALL":
                current_date = datetime.now().strftime('%Y-%m-%d')
                if time_constraint == "LAST":
                    query["rendez_vous"] = {
                        "$elemMatch": {
                            "date": {"$lt": current_date}
                        }
                    }
                elif time_constraint == "NEXT":
                    query["rendez_vous"] = {
                        "$elemMatch": {
                            "date": {"$gte": current_date}
                        }
                    }

            return {
                "query": query,
                "projection": projection,
                "intent": "RENDEZ_VOUS",
                "time_constraint": time_constraint,
                "specific_date": specific_date,
                "is_month_period": (time_constraint == "MONTH_PERIOD"),
                "all_patients": not bool(patient),
                "original_text": original_text,
                "expect_multiple": True
            }

    def build_patient_info_query(self, entities):
        patient = entities.get("patient")

        if not patient:
            return {
                "query": {},
                "projection": None,
                "intent": "DOSSIER_PATIENT",
                "expect_multiple": True
            }

        patient_parts = patient.strip().split()
        query = {"$or": []}

        if len(patient_parts) == 1:
            query["$or"].extend([
                {"nom": {"$regex": f"^{patient_parts[0]}$", "$options": "i"}},
                {"prenom": {"$regex": f"^{patient_parts[0]}$", "$options": "i"}}
            ])
        elif len(patient_parts) >= 2:
            query["$or"].extend([
                {"$and": [
                    {"prenom": {"$regex": f"^{patient_parts[0]}$", "$options": "i"}},
                    {"nom": {"$regex": f"^{patient_parts[1]}$", "$options": "i"}}
                ]},
                {"$and": [
                    {"nom": {"$regex": f"^{patient_parts[0]}$", "$options": "i"}},
                    {"prenom": {"$regex": f"^{patient_parts[1]}$", "$options": "i"}}
                ]}
            ])

        projection = None

        return {
            "query": query,
            "projection": projection,
            "intent": "DOSSIER_PATIENT",
            "expect_multiple": True
        }

    def build_prescription_query(self, entities, time_constraint, specific_date, original_text):

        # S'assurer que entities est toujours un dictionnaire, même vide
        entities = entities or {}

        # Correction des faux positifs temporels
        patient = entities.get("patient")
        if patient and patient.lower() in ["demain", "aujourd'hui", "hier", "next", "tomorrow", "today", "yesterday"]:
            patient = None

        # Initialisation de la requête
        query = {}
        projection = {
            "nom": 1,
            "prenom": 1,
            "dateNaissance": 1,
            "prescriptions": 1,
            "image": 1
        }

        # Date courante
        current_date = datetime.now()

        # Nouvelle gestion des mois en français
        if "mois" in original_text.lower():
            # Dictionnaire des mois en français
            months_fr = {
                "janvier": "01", "février": "02", "mars": "03", "avril": "04",
                "mai": "05", "juin": "06", "juillet": "07", "août": "08",
                "septembre": "09", "octobre": "10", "novembre": "11", "décembre": "12"
            }

            # Extraire le mois du texte original
            for month_name, month_num in months_fr.items():
                if month_name in original_text.lower():
                    # Extraire l'année (par défaut l'année en cours si non spécifiée)
                    year = datetime.now().year
                    for year_str in [str(y) for y in range(2020, 2030)]:
                        if year_str in original_text:
                            year = int(year_str)
                            break

                    # Définir les dates de début et de fin du mois
                    start_date = f"{year}-{month_num}-01"
                    _, last_day = monthrange(year, int(month_num))
                    end_date = f"{year}-{month_num}-{last_day}"

                    # Mettre à jour la requête pour couvrir toute la période du mois
                    query["prescriptions.date"] = {
                        "$gte": start_date,  # À partir du 1er jour du mois
                        "$lte": end_date  # Jusqu'au dernier jour du mois
                    }

                    # Mettre à jour specific_date et time_constraint
                    specific_date = f"{year}-{month_num}"
                    time_constraint = "MONTH_PERIOD"
                    break

        # Gestion du mois prochain et des périodes mensuelles
        if time_constraint in ["prochain", "next"] or time_constraint == "MONTH_PERIOD":
            try:
                if time_constraint in ["prochain", "next"]:
                    # Définir le premier et le dernier jour du mois prochain
                    if current_date.month == 12:
                        first_day_next_month = date(current_date.year + 1, 1, 1)
                        last_day_next_month = date(current_date.year + 1, 1, 31)
                    else:
                        first_day_next_month = date(current_date.year, current_date.month + 1, 1)
                        last_day_next_month = date(current_date.year, current_date.month + 1,
                                                   monthrange(current_date.year, current_date.month + 1)[1])

                    query["prescriptions.date"] = {
                        "$gte": first_day_next_month.strftime('%Y-%m-%d'),
                        "$lte": last_day_next_month.strftime('%Y-%m-%d')
                    }

                elif specific_date and time_constraint == "MONTH_PERIOD":
                    # Extraire le mois et l'année du texte spécifique
                    year, month = map(int, specific_date.split('-'))

                    # Premier et dernier jour du mois
                    start_date = date(year, month, 1)
                    _, last_day = monthrange(year, month)
                    end_date = date(year, month, last_day)

                    query["prescriptions.date"] = {
                        "$gte": start_date.strftime('%Y-%m-%d'),
                        "$lte": end_date.strftime('%Y-%m-%d')
                    }

            except Exception as e:
                print(f"Erreur lors du traitement de la période mensuelle : {e}")

        # Gestion des dates relatives
        if specific_date:
            relative_dates = {
                "hier": "yesterday",
                "today": "aujourd'hui",
                "tomorrow": "demain"
            }

            if specific_date.lower() in relative_dates or specific_date.lower() in relative_dates.values():
                if specific_date.lower() in ["hier", "yesterday"]:
                    specific_date = (current_date - timedelta(1)).strftime('%Y-%m-%d')
                elif specific_date.lower() in ["aujourd'hui", "today"]:
                    specific_date = current_date.strftime('%Y-%m-%d')
                elif specific_date.lower() in ["demain", "tomorrow"]:
                    specific_date = (current_date + timedelta(1)).strftime('%Y-%m-%d')

        # Requête de base si aucune contrainte spécifique n'a été définie
        # Requête de base si aucune contrainte spécifique n'a été définie
        if not query:
            if specific_date:
                query = {
                    "prescriptions": {
                        "$elemMatch": {
                            "date": specific_date
                        }
                    }
                }
            elif time_constraint and time_constraint != "ALL":
                current_date = datetime.now().strftime('%Y-%m-%d')
                if time_constraint == "LAST":
                    query = {
                        "prescriptions": {
                            "$elemMatch": {
                                "date": {"$lt": current_date}
                            }
                        }
                    }
                elif time_constraint == "NEXT":
                    query = {
                        "prescriptions": {
                            "$elemMatch": {
                                "date": {"$gte": current_date}
                            }
                        }
                    }
                elif time_constraint == "PRESENT":
                    query = {
                        "prescriptions": {
                            "$elemMatch": {
                                "date": current_date
                            }
                        }
                    }

        # Gestion du patient
        if patient:
            name_parts = patient.split()

            if len(name_parts) > 1:
                # Cas avec prénom et nom
                query["$or"] = [
                    # Prénom = premier mot, Nom = deuxième mot
                    {"$and": [
                        {"prenom": {"$regex": f"^{name_parts[0]}$", "$options": "i"}},
                        {"nom": {"$regex": f"^{name_parts[1]}$", "$options": "i"}}
                    ]},
                    # Nom = premier mot, Prénom = deuxième mot
                    {"$and": [
                        {"nom": {"$regex": f"^{name_parts[0]}$", "$options": "i"}},
                        {"prenom": {"$regex": f"^{name_parts[1]}$", "$options": "i"}}
                    ]},
                    # Prénom composé
                    {"prenom": {"$regex": f"^{patient}$", "$options": "i"}},
                    # Nom composé
                    {"nom": {"$regex": f"^{patient}$", "$options": "i"}}
                ]
            else:
                # Cas simple avec un seul mot (prénom ou nom)
                query["$or"] = [
                    {"nom": {"$regex": patient, "$options": "i"}},
                    {"prenom": {"$regex": patient, "$options": "i"}}
                ]

        return {
            "query": query,
            "projection": projection,
            "intent": "PRESCRIPTION",
            "time_constraint": time_constraint,
            "specific_date": specific_date,
            "is_month_period": (time_constraint == "MONTH_PERIOD"),
            "all_patients": not bool(patient),
            "original_text": original_text,
            "expect_multiple": True
        }