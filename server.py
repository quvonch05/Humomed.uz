import requests
from datetime import datetime

FIREBASE_URL = "https://humomed-a5f76-default-rtdb.firebaseio.com"

def save_lab_to_firebase(code, patient, test_type, doctor, summary, file_url=""):
    clean_code = code.strip().upper().replace(" ", "")
    data = {
        "id": int(datetime.now().timestamp() * 1000),
        "code": clean_code,
        "patient": patient,
        "testType": test_type,
        "doctor": doctor,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "summary": summary,
        "fileUrl": file_url
    }
    # To'g'ridan-to'g'ri Firebase'ga yozish
    url = f"{FIREBASE_URL}/lab_results/{clean_code}.json"
    response = requests.put(url, json=data)
    return response.status_code == 200
