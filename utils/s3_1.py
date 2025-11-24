import boto3
import json
import os
from dotenv import load_dotenv
load_dotenv()


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
    key = after.split("?", 1)[0]
    return key

def load_json_from_s3(url: str):
    key = extract_s3_key(url)
    obj = s3.get_object(Bucket=S3_BUCKET, Key=key)
    body = obj["Body"].read().decode("utf-8")
    return json.loads(body)

def save_json_to_s3(data, original_image_url):
    file_name = original_image_url.split("/")[-1]
    base = file_name.rsplit(".", 1)[0]
    new_name = f"{base}_translated.json"
    key = f"translated_json/{new_name}"

    s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=json.dumps(data, ensure_ascii=False, indent=2),
        ContentType="application/json"
    )

    return f"https://{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{key}"
