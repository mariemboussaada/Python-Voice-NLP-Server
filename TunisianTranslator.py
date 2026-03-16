# TunisianTranslator.py
import pickle


class TunisianTranslator:
    def __init__(self, model_path="tunisian_model.pkl"):
        # Charger le modèle pré-entraîné
        self.translation_dict = self._load_model(model_path)

    def _load_model(self, model_path):
        try:
            with open(model_path, 'rb') as f:
                model = pickle.load(f)
            print(f"Modèle chargé: {len(model)} entrées")
            return model
        except Exception as e:
            print(f"Erreur lors du chargement du modèle: {e}")
            return {}

    def translate_text(self, arabic_text):
        """Traduit un texte arabe tunisien en français"""
        if not arabic_text:
            return ""

        # Découper le texte en mots
        words = arabic_text.split()
        translated_words = []

        for word in words:
            # Vérifier si le mot est dans notre dictionnaire de traduction
            if word in self.translation_dict:
                translated_words.append(self.translation_dict[word])
            else:
                # Conserver le mot original si aucune traduction n'est trouvée
                translated_words.append(word)

        return " ".join(translated_words)