# TunisianModelTrainer.py
import pickle
import os


class TunisianModelTrainer:
    def __init__(self):
        self.words_dict = {}
        self.names_dict = {}
        self.combined_dict = {}

    def train(self, words_file, names_file, output_model_path="tunisian_model.pkl"):
        """Entraîne le modèle et le sauvegarde"""
        # Charger les mots
        self.words_dict = self._load_dictionary(words_file)

        # Charger les noms
        self.names_dict = self._load_dictionary(names_file)

        # Combiner les dictionnaires
        self.combined_dict = {**self.words_dict, **self.names_dict}

        # Sauvegarder le modèle
        with open(output_model_path, 'wb') as f:
            pickle.dump(self.combined_dict, f)

        print(f"Modèle entraîné et sauvegardé: {len(self.combined_dict)} entrées au total")
        return self.combined_dict

    def _load_dictionary(self, file_path):
        dictionary = {}
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                for line in file:
                    if '|' in line:
                        ar, fr = line.strip().split('|')
                        dictionary[ar] = fr
            print(f"Dictionnaire chargé: {len(dictionary)} entrées depuis {file_path}")
        except Exception as e:
            print(f"Erreur lors du chargement du dictionnaire {file_path}: {e}")
        return dictionary