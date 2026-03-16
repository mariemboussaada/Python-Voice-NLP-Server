# train_model.py
from TunisianModelTrainer import TunisianModelTrainer

if __name__ == "__main__":
    print("Entraînement du modèle de traduction tunisien...")
    trainer = TunisianModelTrainer()
    model = trainer.train("dictTN.txt", "nomTN.txt")
    print(f"Entraînement terminé. Modèle sauvegardé avec {len(model)} entrées.")