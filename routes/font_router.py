# routes/font_router.py
from flask import Blueprint, request, jsonify
from services.font_service import process_font_recommend

font_bp = Blueprint("font", __name__)

# 최종 엔드포인트: POST /api/font-recommend
@font_bp.post("")
def font_recommend():
    data = request.get_json()
    project_id = data.get("projectId")   # 지금 로직에선 안 써도 됨
    image_url = data["image_url"]

    result = process_font_recommend(project_id, image_url)
    return jsonify(result)
