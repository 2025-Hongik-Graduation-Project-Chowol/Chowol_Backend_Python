# services/font_service.py
import os
import io
from io import BytesIO
from glob import glob
from urllib.parse import urlparse

import boto3
from PIL import Image

import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.transforms as T
from torchvision.models import resnet18
from google.cloud import vision
from dotenv import load_dotenv
load_dotenv()


# --- 공통 설정 ---
s3 = boto3.client("s3")
BUCKET_NAME = os.environ.get("S3_BUCKET")
vision_client = vision.ImageAnnotatorClient()
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _extract_filename(url: str) -> str:
    parsed = urlparse(url)
    return os.path.basename(parsed.path)


# ----------------- 폰트 모델 정의 ----------------- #
class FontStyleNet(nn.Module):
    def __init__(self, num_fonts, emb_dim=256):
        super().__init__()
        backbone = resnet18(weights="IMAGENET1K_V1")
        backbone.fc = nn.Identity()  # 마지막 FC 제거 → 512-dim
        self.backbone = backbone
        self.fc_emb = nn.Linear(512, emb_dim)
        self.fc_cls = nn.Linear(emb_dim, num_fonts)

    def forward(self, x):
        feat = self.backbone(x)       # (B, 512)
        emb = self.fc_emb(feat)       # (B, emb_dim)
        emb = F.normalize(emb, dim=1) # L2 정규화
        logits = self.fc_cls(emb)     # (B, num_fonts)
        return emb, logits


def _load_font_model_and_gallery():
    # 프로젝트 루트 = flask_server/ 기준 잡기
    base_dir = os.path.dirname(os.path.dirname(__file__))
    model_path = os.path.join(base_dir, "font_models", "font_style_resnet18.pth")
    font_data_root = os.path.join(base_dir, "font_dataset")

    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Font model checkpoint not found: {model_path}")
    if not os.path.exists(font_data_root):
        raise FileNotFoundError(f"Font dataset root not found: {font_data_root}")

    checkpoint = torch.load(model_path, map_location=device)

    font_ids = checkpoint["font_ids"]
    num_fonts = len(font_ids)

    model = FontStyleNet(num_fonts=num_fonts, emb_dim=256).to(device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    # --- 폰트 갤러리 생성 ---
    gallery = {}
    with torch.no_grad():
        for font_id in sorted(font_ids):
            folder = os.path.join(font_data_root, font_id)
            if not os.path.isdir(folder):
                continue

            img_paths = glob(os.path.join(folder, "*.png"))
            if len(img_paths) == 0:
                continue

            embs = []
            # 폰트당 최대 5장만 사용 (속도용)
            for p in img_paths[:5]:
                img = Image.open(p).convert("L")
                img_t = T.ToTensor()(img)         # (1, H, W)
                img_t = img_t.repeat(3, 1, 1)     # (3, H, W)
                img_t = T.Resize((128, 128))(img_t)
                img_t = img_t.unsqueeze(0).to(device)  # (1, 3, 128, 128)

                emb, _ = model(img_t)
                embs.append(emb.squeeze(0).cpu())

            if not embs:
                continue

            embs = torch.stack(embs, dim=0)   # (N, D)
            mean_emb = embs.mean(dim=0)       # (D,)
            mean_emb = F.normalize(mean_emb, dim=0)
            gallery[font_id] = mean_emb

    font_ids_gallery = sorted(gallery.keys())
    gallery_embs = torch.stack(
        [gallery[fid] for fid in font_ids_gallery], dim=0
    ).to(device)  # (F, D)

    return model, font_ids_gallery, gallery_embs


# 모듈 import 시점에 한 번만 로드 (실패해도 서버 죽지 않게 try/except)
try:
    FONT_MODEL, FONT_IDS_GALLERY, GALLERY_EMBS = _load_font_model_and_gallery()
    print(f"[font_service] loaded font model, num_fonts={len(FONT_IDS_GALLERY)}")
except Exception as e:
    print("[font_service] WARNING: failed to load font model:", e)
    FONT_MODEL = None
    FONT_IDS_GALLERY = []
    GALLERY_EMBS = None


def _extract_embedding_from_pil(pil_img: Image.Image) -> torch.Tensor:
    pil_img = pil_img.convert("L")
    img_t = T.ToTensor()(pil_img)          # (1, H, W)
    img_t = img_t.repeat(3, 1, 1)          # (3, H, W)
    img_t = T.Resize((128, 128))(img_t)
    img_t = img_t.unsqueeze(0).to(device)  # (1, 3, 128, 128)

    with torch.no_grad():
        emb, _ = FONT_MODEL(img_t)
        emb = F.normalize(emb, dim=1)      # (1, D)
    return emb.squeeze(0)                  # (D,)


def _download_original_image_from_s3(image_url: str) -> Image.Image:
    filename = _extract_filename(image_url)          # e.g. "abc.png" 또는 "abc_inpainted.png"
    # 지금은 파일명이 같다고 가정. 필요하면 여기서 규칙 조금 바꿔도 됨.
    key = f"images/{filename}"

    obj = s3.get_object(Bucket=BUCKET_NAME, Key=key)
    img_bytes = obj["Body"].read()
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    return img


def _crop_text_region_with_vision(img: Image.Image) -> Image.Image:
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    image = vision.Image(content=buf.getvalue())
    response = vision_client.text_detection(image=image)
    annotations = response.text_annotations

    if not annotations or len(annotations) <= 1:
        return img

    xs, ys = [], []
    for txt in annotations[1:]:
        for v in txt.bounding_poly.vertices:
            xs.append(v.x)
            ys.append(v.y)

    if not xs or not ys:
        return img

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    min_x = max(0, min_x)
    min_y = max(0, min_y)
    max_x = min(img.width,  max_x)
    max_y = min(img.height, max_y)

    if max_x <= min_x or max_y <= min_y:
        return img

    return img.crop((min_x, min_y, max_x, max_y))



def process_font_recommend(project_id: str, image_url: str) -> dict:
    if FONT_MODEL is None or GALLERY_EMBS is None:
        return {
            "recommended_fonts": [],
            "error": "font model is not loaded on server"
        }

    # 1) 원본 이미지 가져오기 (images/{filename})
    img = _download_original_image_from_s3(image_url)

    # 2) 텍스트 영역 crop
    text_region = _crop_text_region_with_vision(img)

    # 3) 임베딩 추출
    q_emb = _extract_embedding_from_pil(text_region).to(device)  # (D,)

    # 4) 갤러리와 유사도 계산
    sims = torch.matmul(GALLERY_EMBS, q_emb)  # (F,)
    topk_vals, topk_idx = torch.topk(sims, k=min(3, sims.shape[0]))

    recommended = []
    for i in range(topk_vals.shape[0]):
        fid = FONT_IDS_GALLERY[topk_idx[i].item()]
        score = float(topk_vals[i].item())
        recommended.append({
            "name": fid,
            "similarity": round(score, 4)
        })

    return {
        "recommended_fonts": recommended
    }
