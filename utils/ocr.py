from collections import Counter

def detect_language_from_ocr(full_json):
    try:
        langs = full_json["pages"][0]["property"]["detectedLanguages"]
        if len(langs) > 0:
            return langs[0]["languageCode"]
    except:
        pass

    for page in full_json.get("pages", []):
        for block in page.get("blocks", []):
            for para in block.get("paragraphs", []):
                for word in para.get("words", []):
                    langs = word.get("property", {}).get("detectedLanguages", [])
                    if langs:
                        return langs[0]["languageCode"]

    return "auto"  


def extract_lines_from_ocr(full_json):
    pages = full_json.get("pages") or full_json.get("fullTextAnnotation", {}).get("pages", [])
    lines = []

    for page in pages:
        for block in page.get("blocks", []):
            sentence = ""

            for para in block.get("paragraphs", []):
                for word in para.get("words", []):
                    for sym in word.get("symbols", []):
                        sentence += sym.get("text", "")
                        br = sym.get("property", {}).get("detectedBreak", {})
                        if br.get("type") == "LINE_BREAK":
                            sentence += "\n"

            for line in sentence.split("\n"):
                if line.strip():
                    lines.append(line.strip())

    return lines
