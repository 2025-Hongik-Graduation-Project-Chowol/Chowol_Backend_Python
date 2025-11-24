from flask import Blueprint, request, jsonify
from services.reinsert_service import generate_boxes_only

reinsert_bp = Blueprint("reinsert", __name__, url_prefix="/api/reinsert")


@reinsert_bp.route("", methods=["POST"])
def reinsert():
    try:
        data = request.get_json()

        ocr_url = data.get("ocr_json_url")
        translated_url = data.get("translated_json_url")

        if not ocr_url or not translated_url:
            return jsonify({
                "message": "ocr_json_url and translated_json_url are required"
            }), 400

        boxes = generate_boxes_only(ocr_url, translated_url)

        return jsonify({
            "message": "success",
            "boxes": boxes
        }), 200

    except Exception as e:
        return jsonify({"message": str(e)}), 500