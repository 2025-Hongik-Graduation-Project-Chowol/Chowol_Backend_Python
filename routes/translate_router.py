from flask import Blueprint, request, jsonify
from services.translate_service import process_translation
from utils.papago import papago_translate

translate_bp = Blueprint("translate", __name__, url_prefix="/api/translate")

@translate_bp.route("", methods=["POST"])
def translate():
    body = request.get_json()
    result = process_translation(body)
    return jsonify(result)

@translate_bp.route("/text", methods=["POST"])
def translate_text():
    try:
        data = request.get_json()

        text = data.get("text")
        source = data.get("source_lang", "auto")
        target = data.get("target_lang")

        if not text:
            return jsonify({"message": "text is required"}), 400
        
        if not target:
            return jsonify({"message": "target_lang is required"}), 400
        
        if source == target:
            return jsonify({
                "message": "same_language",
                "translated_text": text   
            }), 200

        translated = papago_translate(text, source, target)

        return jsonify({
            "message": "success",
            "translated_text": translated
        }), 200

    except Exception as e:
        return jsonify({"message": str(e)}), 500