import os
import sys
import requests
import subprocess
from io import BytesIO
from PIL import Image
import boto3
import shutil
import time
import random
from dotenv import load_dotenv

load_dotenv()


# LaMa 디렉토리 (EC2 구조 기반)
LAMA_DIR = "/home/ec2-user/lama-server/lama"
PREDICT_PY = f"{LAMA_DIR}/bin/predict.py"

# 모델 경로
MODEL_PATH = f"{LAMA_DIR}/big-lama/models"

# 입력/출력 경로
INPUT_DIR = "/home/ec2-user/lama-server/input"
OUTPUT_DIR = "/home/ec2-user/lama-server/output"

os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# S3 설정
S3_BUCKET = os.environ.get("S3_BUCKET")
AWS_REGION = os.environ.get("AWS_REGION", "ap-northeast-2")

s3 = boto3.client(
    "s3",
    region_name=AWS_REGION,
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY")
)


def extract_s3_key(url: str):
    after = url.split(".amazonaws.com/", 1)[1]
    key = after.split("?", 1)[0]
    return key


def create_presigned(key: str):
    return s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": S3_BUCKET, "Key": key},
        ExpiresIn=3600
    )


def make_temp():
    ts = str(int(time.time() * 1000))
    rand = ''.join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=4))
    return f"temp_{ts}_{rand}"


def download_image(url, save_path, mode):
    res = requests.get(url)
    res.raise_for_status()
    img = Image.open(BytesIO(res.content)).convert(mode)
    img.save(save_path)


def upload_to_s3(local_path, key):
    s3.upload_file(local_path, S3_BUCKET, key)
    return key


def cleanup(path):
    if os.path.exists(path):
        shutil.rmtree(path)



def inpaint_image(image_url: str, mask_url: str) -> str:

    # S3 key 추출
    image_key = extract_s3_key(image_url)
    mask_key = extract_s3_key(mask_url)

    # 기본 파일명 정의
    original_filename = image_key.split("/")[-1]
    base = original_filename.rsplit(".", 1)[0]
    output_filename = f"{base}_inpaint.png"

    # 작업 디렉토리 생성
    temp = make_temp()
    workdir = os.path.join(INPUT_DIR, temp)
    outdir = os.path.join(OUTPUT_DIR, temp)
    os.makedirs(workdir, exist_ok=True)
    os.makedirs(outdir, exist_ok=True)

    # 작업 파일 경로
    original_path = os.path.join(workdir, "image.png")
    mask_path = os.path.join(workdir, "image_mask.png")

    try:
        # presigned URL 생성
        presigned_original = create_presigned(image_key)
        presigned_mask = create_presigned(mask_key)

        # 이미지 다운로드
        download_image(presigned_original, original_path, "RGB")
        download_image(presigned_mask, mask_path, "L")

        # 실행 환경 설정
        lama_python = "/home/ec2-user/lama-server/venv/bin/python"
        env = os.environ.copy()
        env["PYTHONPATH"] = LAMA_DIR


        cmd = [
            lama_python,
            PREDICT_PY,
            f"model.path={MODEL_PATH}",
            f"indir={workdir}",
            f"outdir={outdir}",
        ]

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env
        )

        # 실행 실패 시 에러 출력
        if result.returncode != 0:
            print("--- LaMa Error Log ---")
            print(result.stdout)
            raise Exception("LaMa 실행 오류: " + result.stdout)

        # 출력 파일 찾기
        files = [f for f in os.listdir(outdir) if f.endswith(".png")]
        if not files:
            raise Exception("인페인팅 결과 이미지 없음")

        output_local = os.path.join(outdir, files[0])

        # S3 업로드
        output_key = f"output/{output_filename}"
        upload_to_s3(output_local, output_key)

        # 최종 URL 반환
        return f"https://{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{output_key}"

    finally:
        # 필요하면 정리
        # cleanup(workdir)
        # cleanup(outdir)
        pass
