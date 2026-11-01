import os
import json
import base64
import requests

DIR_NAME = os.path.dirname(os.path.abspath(__file__))

def get_gemini_api_key():
    env_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if env_key:
        return env_key
    config_file = os.path.join(DIR_NAME, "gemini_config.json")
    if not os.path.exists(config_file):
        config_file = os.path.join(os.path.dirname(DIR_NAME), "gemini_config.json")
    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                return json.load(f).get("gemini_api_key", "").strip()
        except Exception:
            pass
    return ""

def transcribe_audio_bytes(audio_bytes, mime_type="audio/ogg"):
    """Sử dụng Gemini 3.5 Flash Lite nhận diện giọng nói tiếng Việt tức thì"""
    api_key = get_gemini_api_key()
    if not api_key:
        print("[Voice STT] Không tìm thấy GEMINI_API_KEY")
        return None
        
    b64_audio = base64.b64encode(audio_bytes).decode("utf-8")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={api_key}"
    payload = {
        "contents": [{
            "parts": [
                {"inline_data": {"mime_type": mime_type, "data": b64_audio}},
                {"text": "Bạn là bộ phận nhận diện giọng nói tiếng Việt cho hệ thống Logistics GHN Miền Tây. Hãy nghe đoạn âm thanh này và chuyển đổi thành văn bản tiếng Việt chính xác 100%. Chỉ trả về nội dung người nói, không thêm bất kỳ lời dẫn hay ngoặc kép nào."}
            ]
        }],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 300
        }
    }
    try:
        r = requests.post(url, json=payload, timeout=25)
        if r.status_code == 200:
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            return text
        else:
            print(f"[Voice STT Error] {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"[Voice STT Exception] {e}")
    return None

def download_and_transcribe_telegram_voice(file_id, bot_token):
    """Tải file ghi âm từ Telegram và dịch thành văn bản"""
    try:
        get_file_url = f"https://api.telegram.org/bot{bot_token}/getFile?file_id={file_id}"
        r = requests.get(get_file_url, timeout=10)
        if r.status_code != 200 or not r.json().get("ok"):
            print(f"[Voice Download Error] Không lấy được thông tin file: {r.text}")
            return None
        file_path = r.json()["result"]["file_path"]
        download_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
        audio_res = requests.get(download_url, timeout=20)
        if audio_res.status_code == 200:
            return transcribe_audio_bytes(audio_res.content, mime_type="audio/ogg")
    except Exception as e:
        print(f"[Voice STT Telegram Error] {e}")
    return None

if __name__ == "__main__":
    print("Voice STT service ready. API Key available:", bool(get_gemini_api_key()))
