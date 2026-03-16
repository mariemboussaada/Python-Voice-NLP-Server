# SimpleTestTranslator.py
import os
from TunisianModelTrainer import TunisianModelTrainer
from TunisianTranslator import TunisianTranslator


def train_if_needed():
    """Entraîne le modèle s'il n'existe pas déjà"""
    model_path = "tunisian_model.pkl"

    if not os.path.exists(model_path):
        print("Le modèle n'existe pas. Entraînement en cours...")
        trainer = TunisianModelTrainer()
        trainer.train("dictTN.txt", "nomTN.txt", model_path)
        print("Modèle entraîné avec succès!")
    else:
        print("Modèle existant trouvé.")


def translate_phrases(phrases):
    """Affiche la traduction des phrases arabes"""
    translator = TunisianTranslator()

    print("\n===== TRADUCTIONS =====\n")

    for i, phrase in enumerate(phrases):
        translation = translator.translate_text(phrase)

        print(f"Phrase #{i + 1}:")
        print(f"Original: {phrase}")
        print(f"Traduction: {translation}")
        print("-" * 50)


if __name__ == "__main__":
    # S'assurer que le modèle est entraîné
    train_if_needed()

    # Phrases de test en arabe tunisien
    test_phrases = [
        "أناليز",
]


    # Traduire les phrases
    translate_phrases(test_phrases)