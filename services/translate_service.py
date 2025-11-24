from utils.s3_1 import load_json_from_s3, save_json_to_s3
from utils.ocr import detect_language_from_ocr, extract_lines_from_ocr
from utils.papago import papago_translate

def process_translation(body):
    ocr_url = body["ocrJsonUrl"]
    img_url = body["originalImageUrl"]
    forced_source = body.get("forcedSource")
    target = body.get("target", "ko")

    full_json = load_json_from_s3(ocr_url)

    lang = detect_language_from_ocr(full_json)
    source = forced_source or lang or "auto"

    print(source)
    print (target)
    if source == target:
        if source == "ko":
            target = "en"
        else:
            target = "ko"
    print(source)
    print (target)

    lines = extract_lines_from_ocr(full_json)
    if len(lines) == 0:
        return {"message": "줄 추출 실패"}

    # Papago 번역
    # result = []
    # for line in lines:
    #     trimmed = line.strip()

    #     translated = papago_translate(line, source, target)
    #     result.append({
    #         "original": line,
    #         "translated": translated
    #     })
    result = []
    for line in lines:
        trimmed = line.strip()

        if not any(ch.isalnum() for ch in trimmed):  
            result.append({
                "original": line,
                "translated": line
            })
            continue

        try:
            translated = papago_translate(line, source, target)
        except Exception as e:
            print(f"번역 실패: {e}")
            translated = line

        result.append({
            "original": line,
            "translated": translated
        })

    translated_url = save_json_to_s3(result, img_url)

    return {
        "message": "번역 완료",
        "source": source,
        "target": target,
        "translatedUrl": translated_url
    }
