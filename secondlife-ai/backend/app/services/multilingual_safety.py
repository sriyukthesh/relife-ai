"""Safety keywords for English, Tamil, Hindi, and common transliterations."""
import re
import unicodedata

KEYWORDS = [
    "mains", "220v", "230v", "high voltage", "smoke", "burning", "burnt", "swollen", "explode", "sparking",
    "மின்சாரம்", "மெயின்ஸ்", "புகை", "எரிந்த", "எரிகிறது", "வீங்கிய", "வெடி", "தீப்பொறி", "அதிக மின்னழுத்தம்",
    "बिजली का झटका", "मेन्स", "धुआं", "धुआँ", "जल गया", "जला हुआ", "फूला हुआ", "फट", "चिंगारी", "हाई वोल्टेज", "220 वोल्ट",
    "pugai", "dhuan", "dhuaan", "bijli ka jhatka", "mins", "minsaram",
]
_PATTERN = re.compile("|".join(re.escape(keyword) for keyword in KEYWORDS), re.IGNORECASE)

SAFETY_REPLY = {
    "en": "Stop and unplug everything. Do not touch the part. Mains power, smoke or swollen batteries are not safe for hobby work. Ask a qualified electrician.",
    "ta": "நிறுத்துங்கள், அனைத்தையும் துண்டியுங்கள். அந்தப் பாகத்தைத் தொடாதீர்கள். இது பாதுகாப்பற்றது. தகுதியான மின்பணியாளரிடம் கேளுங்கள்.",
    "hi": "रुकिए और सब कुछ अनप्लग कर दीजिए। उस पुर्जे को मत छुइए। यह सुरक्षित नहीं है। किसी योग्य इलेक्ट्रीशियन से पूछिए।",
}


def detect_language(text: str) -> str:
    for char in text:
        name = unicodedata.name(char, "")
        if "TAMIL" in name:
            return "ta"
        if "DEVANAGARI" in name:
            return "hi"
    return "en"


def is_unsafe(text: str) -> bool:
    return bool(_PATTERN.search(unicodedata.normalize("NFC", text or "")))


def safety_message(text: str) -> str:
    return SAFETY_REPLY[detect_language(text or "")]
