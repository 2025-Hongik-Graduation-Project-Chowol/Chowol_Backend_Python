from flask import Blueprint, request, jsonify
from services.inpaint_service import inpaint_image

inpaint_bp = Blueprint("inpaint", __name__, url_prefix="/api/inpaint")

@inpaint_bp.route("", methods=["POST"])
def inpaint():
    try:
        data = request.get_json()

        original_url = data.get("image_url")
        mask_url = data.get("mask_url")

        if not original_url or not mask_url:
            return jsonify({"message": "image_url, mask_url required"}), 400

        output_url = inpaint_image(original_url, mask_url)

        return jsonify({
            "message": "success",
            "output_url": output_url
        }), 200

    except Exception as e:
        return jsonify({"message": str(e)}), 500
