import os
import json
import wave
import subprocess
import re
from flask_cors import CORS
from vosk import Model, KaldiRecognizer
from flask import Flask, request, jsonify
from bson import ObjectId

# Importation des classes NLP
from NLPAnalyzer import NLPAnalyzer
from QueryBuilder import QueryBuilder
from DatabaseConnector import DatabaseConnector
from PatientNameRecognizer import PatientNameRecognizer
from EnglishTranslator import EnglishTranslator
# Importer le traducteur tunisien
from TunisianTranslator import TunisianTranslator

patient_recognizer = PatientNameRecognizer("mongodb://localhost:27017/")

# Initialiser le traducteur tunisien (chargé une seule fois au démarrage)
tunisian_translator = TunisianTranslator()

app = Flask(__name__)


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response


CORS(app, resources={
    r"/transcribe": {
        "origins": ["http://localhost:4200", "http://192.168.1.13:4200", "capacitor://localhost"],
        "methods": ["POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    },
    r"/analyze": {
        "origins": ["http://localhost:4200", "http://192.168.1.13:4200", "capacitor://localhost"],
        "methods": ["POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

UPLOAD_FOLDER = 'uploads'
RESULT_FOLDER = 'result'

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
if not os.path.exists(RESULT_FOLDER):
    os.makedirs(RESULT_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
MODELS = {
    "fr": Model("C:/Users/marie/Desktop/Pfe_speech_to_text/model_fr"),
    "en": Model("C:/Users/marie/Desktop/Pfe_speech_to_text/model_en"),
    "tn": Model("C:/Users/marie/Desktop/Pfe_speech_to_text/model_tn"),
    "ar": Model("C:/Users/marie/Desktop/Pfe_speech_to_text/model_ar")
}

# Initialisation des classes NLP
nlp_analyzer = NLPAnalyzer()
query_builder = QueryBuilder()
db_connector = DatabaseConnector("mongodb://localhost:27017/")
db_connector.db = db_connector.client.PFE  # Définir le nom de votre base de données
english_translator = EnglishTranslator()

def convert_to_wav(input_path, output_path):
    """ Convertit un fichier audio en WAV si nécessaire """
    try:
        subprocess.run(["ffmpeg", "-i", input_path, "-acodec", "pcm_s16le", "-ar", "16000", "-y", output_path],
                       check=True)
        return output_path
    except subprocess.CalledProcessError:
        return None


def speech_to_text(file_path, lang):
    """ Convertit l'audio en texte avec Vosk """
    if lang not in MODELS:
        return "Langue non supportée"

    model = MODELS[lang]

    wf = wave.open(file_path, "rb")
    recognizer = KaldiRecognizer(model, wf.getframerate())

    transcript = ""
    while True:
        data = wf.readframes(4000)
        if len(data) == 0:
            break
        if recognizer.AcceptWaveform(data):
            result = json.loads(recognizer.Result())
            transcript += result["text"] + " "

    result = json.loads(recognizer.FinalResult())
    transcript += result["text"]

    return transcript.strip()

def convert_objectid(obj):
    """Convertit les ObjectId en chaînes pour la sérialisation JSON"""
    if isinstance(obj, dict):
        return {k: convert_objectid(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_objectid(item) for item in obj]
    elif isinstance(obj, ObjectId):
        return str(obj)
    return obj

def process_nlp_query(text, original_arabic_text=None):
    """Version avec gestion des patients inexistants"""
    try:
        print(f"🔍 Traitement de la requête: '{text}'")

        # 1. Analyse avec contexte intelligent
        analysis = nlp_analyzer.analyze(text)

        # 2. 🚨 NOUVEAU: Vérifier si patient inexistant
        context_decision = analysis.get("context_decision", {})
        if context_decision.get("action") == "unknown_patient":
            unknown_patient = context_decision.get("unknown_patient")
            return {
                "success": False,
                "message": f"Le patient '{unknown_patient}' n'existe pas . Veuillez vérifier le nom ou créer ce patient.",
                "data": [],
                "analysis": analysis,
                "original_arabic": original_arabic_text,
                "context_info": nlp_analyzer.smart_context.get_current_context(),
                "context_decision": context_decision,
                "error_type": "unknown_patient"
            }

        # 3. Vérifier si l'intention est reconnue
        if analysis["intent"] == "UNKNOWN":
            return {
                "success": True,
                "message": "Comment puis-je vous aider aujourd'hui avec vos recherches concernant les rendez-vous, les dossiers patients ou les prescriptions?",
                "data": [],
                "analysis": analysis,
                "original_arabic": original_arabic_text,
                "context_info": nlp_analyzer.smart_context.get_current_context()
            }

        # 4. Continuer avec le traitement normal...
        query_spec = query_builder.build_query(analysis)

        if "query" not in query_spec or query_spec.get("query") is None:
            error_msg = query_spec.get("error", "Requête non reconnue")
            return {
                "success": False,
                "message": error_msg,
                "data": [],
                "analysis": analysis,
                "original_arabic": original_arabic_text,
                "context_info": nlp_analyzer.smart_context.get_current_context()
            }

        # 5. Exécuter la requête normalement
        result = db_connector.execute_query(query_spec)

        # 6. Convertir et retourner le résultat
        converted_result = convert_objectid(result)
        converted_result["analysis"] = {
            "intent": analysis.get("intent", "UNKNOWN"),
            "entities": analysis.get("entities", {}),
            "time_constraint": analysis.get("time_constraint", "ALL"),
            "specific_date": analysis.get("specific_date")
        }

        if original_arabic_text:
            converted_result["original_arabic"] = original_arabic_text

        converted_result["context_info"] = nlp_analyzer.smart_context.get_current_context()
        converted_result["context_decision"] = analysis.get("context_decision", {})

        return converted_result

    except Exception as e:
        print(f"❌ Erreur lors du traitement NLP: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": f"Erreur d'analyse: {str(e)}",
            "original_arabic": original_arabic_text,
            "context_info": nlp_analyzer.smart_context.get_current_context() if 'nlp_analyzer' in globals() else {},
            "context_decision": {"action": "error", "reason": str(e)}
        }

@app.before_request
def log_request():
    """ Vérifie les requêtes pour détecter un saut de ligne non souhaité """
    if re.search(r"%0A", request.path):
        return jsonify({"error": "Requête invalide : l'URL contient un saut de ligne"}), 400
    print(f"📢 Requête reçue : '{request.path}'")


@app.route('/transcribe', methods=['POST'])
def transcribe_audio():
    """ Endpoint pour recevoir un fichier audio et retourner le texte transcrit """
    if 'audio' not in request.files:
        return jsonify({'error': 'Aucun fichier audio fourni'}), 400

    audio_file = request.files['audio']
    if audio_file.filename == '':
        return jsonify({'error': 'Fichier audio non sélectionné'}), 400

    lang = request.form.get('lang', 'fr')
    if lang not in MODELS:
        return jsonify({'error': 'Langue non supportée'}), 400

    file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'RecordedFile.wav')
    audio_file.save(file_path)

    converted_path = convert_to_wav(file_path, file_path.replace(".wav", "_converted.wav"))
    if converted_path is None:
        return jsonify({'error': 'Erreur lors de la conversion audio'}), 500

    transcript = speech_to_text(converted_path, lang)

    # Facultatif: Analyser directement la transcription si le paramètre 'analyze' est présent
    analyze_flag = request.form.get('analyze', 'false').lower() == 'true'

    # Vérifier si c'est la langue tunisienne/arabe ou anglaise et traduire si nécessaire
    original_transcript = None

    if lang == "tn" or lang == "ar":
        # Détection de caractères arabes
        has_arabic = any('\u0600' <= c <= '\u06FF' for c in transcript)

        if has_arabic:
            original_transcript = transcript
            # Traduire le texte arabe en français
            transcript = tunisian_translator.translate_text(transcript)
            print(f"Texte original (tunisien): '{original_transcript}'")
            print(f"Texte traduit (français): '{transcript}'")

    elif lang == "en":
        # Sauvegarder le texte original en anglais
        original_transcript = transcript
        # Traduire le texte anglais en français
        transcript = english_translator.translate_text(transcript)
        print(f"Texte original (anglais): '{original_transcript}'")
        print(f"Texte traduit (français): '{transcript}'")

    if transcript:
        response_data = {'transcription': transcript}

        # Ajouter la transcription originale si elle existe
        if original_transcript:
            response_data['original_transcription'] = original_transcript

        if analyze_flag:
            # Analyser directement la transcription traduite
            analysis_result = process_nlp_query(transcript, original_transcript)
            response_data['analysis'] = analysis_result

        return jsonify(response_data)
    else:
        return jsonify({'error': 'Erreur lors de la transcription'}), 500


@app.route('/analyze', methods=['POST'])
def analyze_text():
    try:
        data = request.get_json()
        if 'text' not in data:
            return jsonify({'error': 'Aucun texte fourni'}), 400

        text = data['text']
        print(f"Texte reçu pour analyse: {text}")

        # Obtenir la langue du texte (si fournie)
        lang = data.get('lang', 'auto')
        original_text = None

        # Détection automatique si langue est "auto"
        if lang == "auto":
            # Détection de caractères arabes
            has_arabic = any('\u0600' <= c <= '\u06FF' for c in text)

            # Détection basique pour l'anglais (peut être améliorée)
            # Cette détection est simpliste et pourrait être améliorée avec une bibliothèque de
            # détection de langue comme langdetect ou fasttext
            english_words = ['the', 'a', 'an', 'and', 'or', 'but', 'is', 'are', 'was', 'were',
                             'patient', 'doctor', 'appointment', 'medicine', 'prescription']
            words = text.lower().split()
            english_word_count = sum(1 for word in words if word in english_words)
            is_english = english_word_count > 0 and english_word_count / len(words) > 0.2

            if has_arabic:
                original_text = text
                text = tunisian_translator.translate_text(text)
                print(f"Texte original (tunisien): '{original_text}'")
                print(f"Texte traduit (français): '{text}'")
            elif is_english or lang == "en":
                original_text = text
                text = english_translator.translate_text(text)
                print(f"Texte original (anglais): '{original_text}'")
                print(f"Texte traduit (français): '{text}'")
        elif lang == "en":
            # Si la langue est explicitement spécifiée comme anglais
            original_text = text
            text = english_translator.translate_text(text)
            print(f"Texte original (anglais): '{original_text}'")
            print(f"Texte traduit (français): '{text}'")
        elif lang == "tn" or lang == "ar":
            # Si la langue est explicitement spécifiée comme tunisien/arabe
            original_text = text
            text = tunisian_translator.translate_text(text)
            print(f"Texte original (tunisien): '{original_text}'")
            print(f"Texte traduit (français): '{text}'")

        # Analyser le texte traduit
        result = process_nlp_query(text, original_text)
        print(f"Résultat de l'analyse: {result}")

        return jsonify(result)
    except Exception as e:
        print(f"Erreur lors de l'analyse: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"Erreur serveur: {str(e)}"
        }), 500

@app.route('/analyze/direct', methods=['POST'])
def analyze_audio_direct():
    """ Endpoint pour transcrire et analyser directement un fichier audio """
    if 'audio' not in request.files:
        return jsonify({'error': 'Aucun fichier audio fourni'}), 400

    audio_file = request.files['audio']
    if audio_file.filename == '':
        return jsonify({'error': 'Fichier audio non sélectionné'}), 400

    lang = request.form.get('lang', 'fr')
    if lang not in MODELS:
        return jsonify({'error': 'Langue non supportée'}), 400

    file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'DirectAnalysis.wav')
    audio_file.save(file_path)

    converted_path = convert_to_wav(file_path, file_path.replace(".wav", "_converted.wav"))
    if converted_path is None:
        return jsonify({'error': 'Erreur lors de la conversion audio'}), 500

    transcript = speech_to_text(converted_path, lang)

    if not transcript:
        return jsonify({'error': 'Erreur lors de la transcription'}), 500

    # Traitement pour les langues différentes
    original_transcript = None
    if lang == "tn" or lang == "ar":
        # Détection de caractères arabes
        has_arabic = any('\u0600' <= c <= '\u06FF' for c in transcript)

        if has_arabic:
            original_transcript = transcript
            # Traduire le texte arabe en français
            transcript = tunisian_translator.translate_text(transcript)
            print(f"Texte original (tunisien): '{original_transcript}'")
            print(f"Texte traduit (français): '{transcript}'")
    elif lang == "en":
        # Sauvegarder le texte original en anglais
        original_transcript = transcript
        # Traduire le texte anglais en français
        transcript = english_translator.translate_text(transcript)
        print(f"Texte original (anglais): '{original_transcript}'")
        print(f"Texte traduit (français): '{transcript}'")

    # Analyser la transcription (traduite)
    analysis_result = process_nlp_query(transcript, original_transcript)

    # Structurer la réponse
    response = {
        'success': True,
        'transcription': original_transcript if original_transcript else transcript,
        'intent': analysis_result.get("analysis", {}).get("intent", "UNKNOWN"),
        'message': analysis_result.get("message", ""),
        'multiple_patients': analysis_result.get("multiple_patients", False)
    }

    # Ajouter la transcription traduite
    if original_transcript:
        response['translated_transcription'] = transcript

    if analysis_result.get("multiple_patients"):
        response['patients_info'] = analysis_result.get("patients_info", [])
        response['all_data'] = analysis_result.get("all_data", [])
    else:
        response['data'] = analysis_result.get("data", [])

    return jsonify(response)

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=8100)