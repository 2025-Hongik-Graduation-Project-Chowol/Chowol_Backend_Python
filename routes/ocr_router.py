from flask import Blueprint, request, jsonify, send_file
from services.ocr_service import process_ocr
from services.ocr_service import process_ocr_select, download_ocr_json_file

ocr_bp = Blueprint("ocr", __name__)

@ocr_bp.post("/auto")
def ocr_auto():
    data = request.get_json()
    projectId = data.get("projectId")
    image_url = data.get("image_url")

    result = process_ocr(projectId, image_url)
    return jsonify(result)


@ocr_bp.post("/select")
def ocr_select():
    data = request.get_json()
    projectId = data.get("projectId")  
    image_url = data.get("image_url")
    bbox = data.get("bbox")          

    result = process_ocr_select(projectId, image_url, bbox)
    return jsonify(result)        


@ocr_bp.post("/download-json")
def ocr_download_json():
    """
    Body로 받은 image_url 기준으로
    ocr_results/{filename}.json 파일을 '다운로드' 시켜주는 엔드포인트
    """
    data = request.get_json()
    image_url = data.get("image_url")

    file_obj, filename = download_ocr_json_file(image_url)

    return send_file(
        file_obj,
        mimetype="application/json",
        as_attachment=True,          # ← 이게 있어야 '다운로드'로 동작
        download_name=filename,      # 브라우저/클라이언트에서 보일 파일 이름
    )