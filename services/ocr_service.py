from google.cloud import vision
from google.protobuf.json_format import MessageToDict
from PIL import Image, ImageDraw
import numpy as np
import io, json, os
from io import BytesIO
from urllib.parse import urlparse
from utils.s3 import upload_json_to_s3, upload_mask_to_s3
import boto3
from dotenv import load_dotenv
load_dotenv()

vision_client = vision.ImageAnnotatorClient()
s3 = boto3.client("s3")
BUCKET_NAME = os.environ.get("S3_BUCKET")

def extract_filename(url):
    parsed = urlparse(url)
    return os.path.basename(parsed.path)

def process_ocr(projectId, image_url):
    filename = extract_filename(image_url)

    # 1) S3 이미지 다운로드
    response = s3.get_object(
        Bucket=BUCKET_NAME,
        Key=f"images/{filename}"
    )
    img_bytes = response["Body"].read()

    image = vision.Image(content=img_bytes)

    # 2) Vision OCR
    ocr_response = vision_client.text_detection(image=image)
    annotations = ocr_response.text_annotations
    full_json = MessageToDict(ocr_response.full_text_annotation._pb)

    # 3) OCR JSON 업로드
    json_key = f"ocr_results/{filename}.json"
    json_url = upload_json_to_s3(full_json, json_key)

    # 4) 마스크 생성
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    mask = Image.new('L', img.size, 0)
    draw = ImageDraw.Draw(mask)

    for txt in annotations[1:]:
        vertices = [(v.x, v.y) for v in txt.bounding_poly.vertices]
        draw.polygon(vertices, fill=255)

    # 5) 마스크 S3 업로드
    mask_key = f"mask/{filename}_mask.png"
    mask_url = upload_mask_to_s3(mask, mask_key)

    return {
        "projectId": projectId,
        "image_url": image_url,
        "ocr_json_url": json_url,
        "mask_image_url": mask_url
    }


def _get_ocr_json_key(image_url: str) -> str:
    """auto에서 저장한 OCR 결과 JSON의 S3 key."""
    filename = extract_filename(image_url)
    return f"ocr_results/{filename}.json"


def _append_manual_text_to_json(image_url: str, item: dict):
    """
    S3에 있는 기존 OCR JSON을 읽어서
    manualTexts 배열에 item을 추가한 뒤 다시 저장.
    기존 full_json 구조는 그대로 유지하고 key만 하나 더 붙임.
    """
    json_key = _get_ocr_json_key(image_url)

    try:
        obj = s3.get_object(Bucket=BUCKET_NAME, Key=json_key)
        data_str = obj["Body"].read().decode("utf-8")
        data = json.loads(data_str)
    except s3.exceptions.NoSuchKey:
        # auto를 아직 안 돌렸거나 JSON이 없는 경우
        data = {}

    # manualTexts 배열 없으면 새로 만들기
    if "manualTexts" not in data:
        data["manualTexts"] = []

    data["manualTexts"].append(item)

    # 기존 upload_json_to_s3 재사용 (full_json 저장 방식 그대로 유지)
    upload_json_to_s3(data, json_key)


def process_ocr_select(projectId, image_url, bbox):
    """
    사용자가 지정한 네 꼭짓점(bbox: [{x,y} * 4]) 영역에 대해 OCR 재수행.
    - 해당 영역을 crop해서 Vision OCR 실행
    - 전체 텍스트(annotations[0])를 사용
    - 결과 { text, bbox(4점) } 반환
    - 그리고 S3의 기존 JSON에 manualTexts로 append
    """
    filename = extract_filename(image_url)

    # 1) S3에서 원본 이미지 가져오기
    response = s3.get_object(
        Bucket=BUCKET_NAME,
        Key=f"images/{filename}"
    )
    img_bytes = response["Body"].read()

    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")

    # bbox: [ {x,y}, {x,y}, {x,y}, {x,y} ] 라고 가정
    xs = [p["x"] for p in bbox]
    ys = [p["y"] for p in bbox]

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    # 2) 선택 영역 crop (rectangle)
    left   = min_x
    upper  = min_y
    right  = max_x
    lower  = max_y

    cropped = img.crop((left, upper, right, lower))

    # 3) Vision OCR 실행 (crop된 이미지 기준)
    buf = io.BytesIO()
    cropped.save(buf, format="PNG")
    buf.seek(0)

    image = vision.Image(content=buf.getvalue())
    ocr_response = vision_client.text_detection(image=image)
    annotations = ocr_response.text_annotations

    if annotations:
        selected_text = annotations[0].description.strip()
    else:
        selected_text = ""

    # 결과 아이템
    result_item = {
        "text": selected_text,
        "bbox": bbox   # 4개의 꼭짓점 그대로 저장
    }

    # 4) 기존 JSON에 manualTexts로 추가
    _append_manual_text_to_json(image_url, result_item)

    # 5) API 응답은 스펙대로
    return result_item



def download_ocr_json_file(image_url: str):
    """
    ocr_results/{filename}.json 을 S3에서 가져와서
    Flask send_file로 내려보낼 수 있게 (file-like, filename) 반환
    """
    json_key = _get_ocr_json_key(image_url)  # ocr_results/wow.png.json 이런 형태
    obj = s3.get_object(Bucket=BUCKET_NAME, Key=json_key)
    data_bytes = obj["Body"].read()

    file_obj = BytesIO(data_bytes)
    file_obj.seek(0)

    filename = os.path.basename(json_key)  # wow.png.json
    return file_obj, filename