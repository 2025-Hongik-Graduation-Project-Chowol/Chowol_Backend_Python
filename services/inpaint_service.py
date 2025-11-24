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
import string
from dotenv import load_dotenv
load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LAMA_DIR = os.path.join(BASE_DIR, "lama")
if LAMA_DIR not in sys.path:
    sys.path.insert(0, LAMA_DIR)

MODEL_PATH = os.path.join(LAMA_DIR, "big-lama", "models")

INPUT_DIR = os.path.join(BASE_DIR, "inputs")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

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


# presigned 생성
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

    image_key = extract_s3_key(image_url)
    mask_key = extract_s3_key(mask_url)

    original_filename = image_key.split("/")[-1]
    base = original_filename.rsplit(".", 1)[0]
    output_filename = f"{base}_inpaint.png"

    temp = make_temp()
    workdir = os.path.join(INPUT_DIR, temp)
    outdir = os.path.join(OUTPUT_DIR, temp)
    os.makedirs(workdir, exist_ok=True)
    os.makedirs(outdir, exist_ok=True)

    # original_path = os.path.join(workdir, "input.png")
    # mask_path = os.path.join(workdir, "mask.png")
    original_path = os.path.join(workdir, "image.png")     
    mask_path = os.path.join(workdir, "image_mask.png")


    try:
        presigned_original = create_presigned(image_key)
        presigned_mask = create_presigned(mask_key)

        download_image(presigned_original, original_path, "RGB")
        download_image(presigned_mask, mask_path, "L")

        # lama_python = os.path.abspath("lama_env/Scripts/python.exe")
        lama_python = sys.executable
        env = os.environ.copy()
        env["PYTHONPATH"] = LAMA_DIR


        cmd = [
            lama_python,
            os.path.join(LAMA_DIR, "bin", "predict.py"),
            f"model.path={MODEL_PATH}",
            f"indir={workdir}",
            f"outdir={outdir}",
            # "dataset.img_suffix=.png",
        ]

        # result = subprocess.run(
        #     [lama_python, os.path.join(LAMA_DIR, "bin", "predict.py"),
        #      f"model.path={MODEL_PATH}",
        #      f"indir={workdir}",
        #      f"outdir={outdir}",
        #      "dataset.img_suffix=.png"],
        #     stdout=subprocess.PIPE,
        #     stderr=subprocess.STDOUT,
        #     text=True,
        #     env=env
        # )
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env
        )

        if result.returncode != 0:
            print("--- LaMa Error Log ---") 
            print(result.stdout)
            raise Exception("LaMa 실행 오류: " + result.stdout)

        files = [f for f in os.listdir(outdir) if f.endswith(".png")]
        if not files:
            raise Exception("인페인팅 결과 이미지 없음")

        output_local = os.path.join(outdir, files[0])

        output_key = f"output/{output_filename}"
        upload_to_s3(output_local, output_key)


        return f"https://{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{output_key}"

    finally:
        # cleanup(workdir)
        # cleanup(outdir)
        pass

