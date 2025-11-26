import boto3
import json
import os
import math
import uuid
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

S3_BUCKET = os.environ.get("S3_BUCKET")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

s3 = boto3.client(
    "s3",
    region_name=AWS_REGION,
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY")
)


def extract_s3_key(url: str):
    after = url.split(".amazonaws.com/", 1)[1]
    return after.split("?", 1)[0]


def load_json_from_s3_url(url: str):
    key = extract_s3_key(url)
    obj = s3.get_object(Bucket=S3_BUCKET, Key=key)
    body = obj["Body"].read().decode("utf-8")
    return json.loads(body)


def compute_raw_angle(vertices):
    clean = [v for v in vertices if "x" in v and "y" in v]
    if len(clean) < 4:
        return 0
    pts = [(v["x"], v["y"]) for v in clean]
    edges = [(pts[0], pts[1]), (pts[1], pts[2]), (pts[2], pts[3]), (pts[3], pts[0])]
    max_len, longest = -1, None

    for p1, p2 in edges:
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        length = dx * dx + dy * dy
        if length > max_len:
            max_len = length
            longest = (p1, p2)

    (x1, y1), (x2, y2) = longest
    return math.degrees(math.atan2(y2 - y1, x2 - x1))


def decide_orientation(vertices):
    xs = [v["x"] for v in vertices if "x" in v]
    ys = [v["y"] for v in vertices if "y" in v]

    w = max(xs) - min(xs)
    h = max(ys) - min(ys)
    raw = compute_raw_angle(vertices)

    if w > h * 1.3:
        return 0, "horizontal"
    if h > w * 1.3:
        return -90, "vertical"

    ang = raw
    if ang < -90:
        ang += 180
    if ang > 90:
        ang -= 180
    return ang, "diagonal"


def compute_symbol_height(symbol_vertices_list):
    heights = []
    for verts in symbol_vertices_list:
        clean = [v for v in verts if "x" in v and "y" in v]
        if len(clean) < 2:
            continue
        ys = [v["y"] for v in clean]
        heights.append(max(ys) - min(ys))
    return int((sum(heights) / len(heights)) * 0.9) if heights else 20



def generate_boxes_only(ocr_json_url, translated_json_url):


    ocr = load_json_from_s3_url(ocr_json_url)
    translated = load_json_from_s3_url(translated_json_url)

    lines = []
    buf_text, buf_vertices, buf_symbols = "", [], []

    for page in ocr["pages"]:
        for block in page.get("blocks", []):
            for para in block.get("paragraphs", []):
                for word in para.get("words", []):
                    for sym in word.get("symbols", []):
                        buf_text += sym["text"]
                        buf_vertices += sym["boundingBox"]["vertices"]
                        buf_symbols.append(sym["boundingBox"]["vertices"])

                        br = sym.get("property", {}).get("detectedBreak", {})
                        if br.get("type") == "LINE_BREAK":
                            if buf_text.strip():
                                lines.append({
                                    "text": buf_text.strip(),
                                    "vertices": buf_vertices.copy(),
                                    "symbols": [s.copy() for s in buf_symbols]
                                })
                            buf_text, buf_vertices, buf_symbols = "", [], []

    if buf_text.strip():
        lines.append({
            "text": buf_text.strip(),
            "vertices": buf_vertices.copy(),
            "symbols": [s.copy() for s in buf_symbols]
        })

    boxes = []
    count = min(len(lines), len(translated))
    font_path = "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"

    for i in range(count):
        original = lines[i]["text"]
        translated_text = translated[i]["translated"]
        verts = lines[i]["vertices"]
        symbols = lines[i]["symbols"]

        xs = [v["x"] for v in verts if "x" in v]
        ys = [v["y"] for v in verts if "y" in v]
        cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)

        angle, orientation = decide_orientation(verts)
        font_size = max(12, compute_symbol_height(symbols))
        if orientation == "vertical":
            font_size = int(font_size * 0.85)

        x = min(xs)
        y = min(ys)
        width = max(xs) - min(xs)
        height = max(ys) - min(ys)

        boxes.append({
            "id": str(uuid.uuid4()),
            "original_text": original,
            "translated_text": translated_text,
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "angle": angle,
            "fontSize": font_size,
            "color": "#000000"
        })

    manual_items = ocr.get("manualTexts", [])
    manual_index = 0  # 실제 번역 index 맞추기 위해 필요

    for item in manual_items:
        manual_text = (item.get("text") or "").strip()
        bbox = item.get("bbox", [])

        # 빈 문자열이면 skip
        if not manual_text:
            continue

        # 번역 index = auto_count + manual_index
        translated_idx = count + manual_index
        if translated_idx < len(translated):
            translated_text = translated[translated_idx]["translated"]
        else:
            translated_text = manual_text  # 혹시 번역이 없으면 원본 유지

        manual_index += 1  # 다음 manualTexts 라인으로 진행

        # bbox → x/y/width/height 계산
        xs = [p["x"] for p in bbox if "x" in p]
        ys = [p["y"] for p in bbox if "y" in p]
        if not xs or not ys:
            continue

        x = min(xs)
        y = min(ys)
        width = max(xs) - min(xs)
        height = max(ys) - min(ys)

        angle = 0  # manualTexts는 모두 직사각형
        font_size = max(12, int(height * 0.9))

        boxes.append({
            "id": str(uuid.uuid4()),
            "original_text": manual_text,
            "translated_text": translated_text,
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "angle": angle,
            "fontSize": font_size,
            "color": "#000000"
        })

    return boxes
