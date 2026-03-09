import cv2
import numpy as np
import tensorflow as tf

# Modeli yüklüyoruz
try:
    print("🎰 Kumar Tespit Modeli (Keras) yükleniyor...")
    model = tf.keras.models.load_model('kumar_tespit_modeli.h5')
    print("✅ Kumar Modeli başarıyla yüklendi!")
except Exception as e:
    print(f"❌ Kumar Modeli yükleme hatası: {e}")
    model = None


def analyze_visual_content(video_path):
    if model is None:
        return {"gambling_safety": 100.0, "gambling_det": 0}

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print("HATA: Video okunamadı!")
        return {"gambling_safety": 100.0, "gambling_det": 0}

    kesin_kumar_sayaci = 0
    toplam_taranan_kare = 0
    su_anki_saniye = 0
    KONTROL_ARALIGI_SN = 15

    while True:
        # Işık hızında tarama (15 sn atlayarak)
        cap.set(cv2.CAP_PROP_POS_MSEC, su_anki_saniye * 1000)
        ret, frame = cap.read()

        if not ret:
            break

        toplam_taranan_kare += 1

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        resized_frame = cv2.resize(rgb_frame, (224, 224))
        input_array = np.expand_dims(resized_frame, axis=0)

        prediction = model.predict(input_array, verbose=0)
        anlik_skor = prediction[0][0]

        # 🚀 SENİN ORİJİNAL KURALIN: Sadece oran %99.9 ve üzeriyse say!
        if anlik_skor < 0.5:
            oran = (1 - anlik_skor) * 100
            if oran >= 99.9:
                kesin_kumar_sayaci += 1

        su_anki_saniye += KONTROL_ARALIGI_SN

    cap.release()

    gambling_safety = 100.0
    if toplam_taranan_kare > 0:
        gambling_safety = ((toplam_taranan_kare - kesin_kumar_sayaci) / toplam_taranan_kare) * 100

    return {
        "gambling_safety": round(gambling_safety, 2),
        "gambling_det": kesin_kumar_sayaci
    }