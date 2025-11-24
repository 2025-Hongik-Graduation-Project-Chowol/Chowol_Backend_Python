import boto3
import io
import json
import os
from dotenv import load_dotenv
load_dotenv()

s3 = boto3.client("s3")
BUCKET_NAME = os.environ.get("S3_BUCKET")

def upload_json_to_s3(data, key):
    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=key,
        Body=json.dumps(data, ensure_ascii=False, indent=2),
        ContentType="application/json"
    )
    return f"https://{BUCKET_NAME}.s3.amazonaws.com/{key}"

def upload_mask_to_s3(mask_image, key):
    buffer = io.BytesIO()
    mask_image.save(buffer, format="PNG")
    buffer.seek(0)

    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=key,
        Body=buffer,
        ContentType="image/png"
    )
    
    return f"https://{BUCKET_NAME}.s3.amazonaws.com/{key}"
