class EnglishTranslator:
    def __init__(self):
        """
        Initialise le traducteur anglais-français.
        Chargez ici votre modèle de traduction ou vos API.
        """
        print("Initialisation du traducteur anglais")
        # Si vous utilisez une API comme Google Translate, DeepL, etc.
        # importez les bibliothèques nécessaires ici

        # Exemple avec une bibliothèque comme transformers pour un modèle local
        try:
            from transformers import pipeline
            self.translator = pipeline("translation_en_to_fr", model="Helsinki-NLP/opus-mt-en-fr")
            self.api_translation = False
            print("✅ Modèle de traduction anglais-français chargé")
        except Exception as e:
            print(f"⚠️ Erreur lors du chargement du modèle de traduction: {str(e)}")
            print("⚠️ Passage au mode API")
            # Fallback sur une API si le modèle local ne fonctionne pas
            self.api_translation = True

            # Vous pourriez utiliser une API comme DeepL ou Google Translate
            # Exemple avec googletrans qui ne nécessite pas de clé API
            try:
                from googletrans import Translator
                self.api_translator = Translator()
                print("✅ API de traduction Google initialisée")
            except Exception as e:
                print(f"❌ Erreur d'initialisation de l'API de traduction: {str(e)}")

    def translate_text(self, text):
        """
        Traduit le texte anglais en français.

        Args:
            text (str): Le texte en anglais à traduire

        Returns:
            str: Le texte traduit en français
        """
        if not text:
            return ""

        try:
            if hasattr(self, 'api_translation') and self.api_translation:
                # Utilisation de l'API
                translated = self.api_translator.translate(text, src='en', dest='fr')
                return translated.text
            else:
                # Utilisation du modèle local
                result = self.translator(text)
                if isinstance(result, list) and len(result) > 0:
                    return result[0]['translation_text']
                return result['translation_text']
        except Exception as e:
            print(f"❌ Erreur de traduction: {str(e)}")
            # En cas d'erreur, retourner le texte original
            return text