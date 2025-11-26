from flask import Blueprint, request, jsonify
import os
import boto3
import json
from dotenv import load_dotenv
load_dotenv()

signed_bp = Blueprint("prefix", __name__, url_prefix="/api/prefix")

# 🔥 s3 클라이언트 생성 (여기 추가해야 함)
s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION")
)

@signed_bp.route("", methods=["POST"])
def get_signed_url():
    data = request.get_json()
    url = data.get("url")

    if not url:
        return jsonify({"message": "url is required"}), 400

    # URL에서 key 추출
    # 예: https://bucket.s3.amazonaws.com/output/xxx.png → output/xxx.png
    try:
        key = url.split(".amazonaws.com/")[1]
    except:
        return jsonify({"message": "Invalid S3 URL format"}), 400

    bucket = os.getenv("S3_BUCKET")

    try:
        signed_url = s3.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=3600  # 1시간 유효
        )

        return jsonify({"signed_url": signed_url})

    except Exception as e:
        return jsonify({"message": str(e)}), 500
