import re
import os
import time
import gc
import threading  # Eşzamanlı istekleri engellemek için
from flask import Flask, request, jsonify
from flask_cors import CORS

# Kendi oluşturduğumuz modüller
import subtitle_analyzer
import video_analyzer_gun
import video_analyzer_knife
import video_analyzer_combined
import video_analyzer_gambling
import db_manager

app = Flask(__name__)
CORS(app)

# ===================================================
# 🔹 KİLİT MEKANİZMASI (Aynı anda aynı videoyu analiz etmeyi önler)
# ===================================================
active_analyses = set()
analysis_lock = threading.Lock()


# ===================================================
# 🔹 YARDIMCI FONKSİYONLAR
# ===================================================
def extract_video_id(link: str):
    pattern = r"(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})"
    match = re.search(pattern, link)
    if match: return match.group(1)
    raise ValueError("Geçersiz YouTube bağlantısı.")


def get_canonical_url(video_id: str):
    return f"https://www.youtube.com/watch?v={video_id}"


# YENİ: Gelişmiş Yaş Sınırı Hesaplama Fonksiyonu
def calculate_age_rating(text_scores, visual_scores):
    # ---------------------------------------------------------
    # 1. METİN (ALTYAZI) ANALİZİ YAŞ HESAPLAMASI
    # ---------------------------------------------------------
    lstm = text_scores.get('lstm', 100.0)
    bert = text_scores.get('bert', 100.0)
    svc = text_scores.get('svc', 100.0)

    t_scores = [lstm, bert, svc]

    if sum(1 for s in t_scores if s >= 90) >= 2:
        text_age = 7
    elif sum(1 for s in t_scores if s >= 85) >= 2:  # +9 eklendi
        text_age = 9
    elif sum(1 for s in t_scores if s >= 75) >= 2:
        text_age = 13
    elif sum(1 for s in t_scores if s >= 60) >= 2:
        text_age = 15
    else:
        text_age = 18

        # ---------------------------------------------------------
    # 2. GÖRSEL ANALİZ YAŞ HESAPLAMASI
    # ---------------------------------------------------------
    gun_pct = 100.0 - visual_scores.get('gun_safety', 100.0)
    comb_gun_pct = 100.0 - visual_scores.get('combined_gun_safety', 100.0)

    knife_pct = 100.0 - visual_scores.get('knife_safety', 100.0)
    comb_knife_pct = 100.0 - visual_scores.get('combined_knife_safety', 100.0)

    gambling_pct = 100.0 - visual_scores.get('gambling_safety', 100.0)

    visual_age = 7

    if gambling_pct > 75:
        visual_age = 18
    elif gun_pct > 10 and comb_gun_pct > 30:
        visual_age = 18
    elif knife_pct > 20 and comb_knife_pct > 7:
        visual_age = 18

    # ---------------------------------------------------------
    # 3. FİNAL YAŞ SINIRI KARARI
    # ---------------------------------------------------------
    final_age = max(text_age, visual_age)

    if final_age == 18:
        return "+18"
    elif final_age == 15:
        return "+15"
    elif final_age == 13:
        return "+13"
    elif final_age == 9:
        return "+9"
    else:
        return "Genel İzleyici (7+)"


# ===================================================
# 🔹 API UÇ NOKTASI
# ===================================================
@app.route('/analyze_youtube', methods=['POST'])
def analyze_youtube():
    data = request.get_json()
    link = data.get('youtube_link')

    if not link:
        return jsonify({"error": "youtube_link parametresi gerekli."}), 400

    try:
        video_id = extract_video_id(link)
        canonical_url = get_canonical_url(video_id)

        # 1. DB KONTROLÜ
        cached_result = db_manager.check_db_for_result(canonical_url)
        if cached_result:
            text_scores = cached_result.get('safety_percentages', {})
            visual_scores = cached_result.get('safety_percentages', {}).get('visual',
                                                                            cached_result.get('safety_percentages', {}))
            age_rating = calculate_age_rating(text_scores, visual_scores)
            cached_result['age_rating'] = age_rating
            return jsonify(cached_result)

        # ----------------------------------------------------
        # 🛡️ KİLİT MEKANİZMASI KONTROLÜ
        # Aynı video için zaten analiz yapılıyorsa 2. isteği durdur
        # ----------------------------------------------------
        with analysis_lock:
            if video_id in active_analyses:
                return jsonify({"status": "processing", "message": "Bu video zaten şu an analiz ediliyor."})

            # Yeni bir video ise aktif listesine ekle
            active_analyses.add(video_id)

        # Asıl işlem başlıyor (Hata olursa kilit açılsın diye try-finally bloğunda)
        try:
            # --- 2. METİN ANALİZİ ---
            print(f"📝 Altyazı analizi yapılıyor... ({video_id})")
            sub_results = subtitle_analyzer.analyze_subtitles(video_id)
            text_percentages = sub_results["percentages"] if sub_results else {"lstm": 100.0, "bert": 100.0,
                                                                               "svc": 100.0}
            total_lines = sub_results["total_lines"] if sub_results else 0

            # --- 3. GÖRÜNTÜ ANALİZİ ---
            print(f"🎥 Video indiriliyor... ({video_id})")
            video_path = video_analyzer_gun.download_video(link)

            visual_results = {
                "gun_safety": 100.0, "knife_safety": 100.0, "gun_det": 0, "knife_det": 0,
                "combined_gun_safety": 100.0, "combined_knife_safety": 100.0,
                "combined_gun_det": 0, "combined_knife_det": 0,
                "gambling_safety": 100.0, "gambling_det": 0
            }

            if video_path:
                # 1️⃣ Eski Silah Modülü
                gun_res = video_analyzer_gun.analyze_visual_content(video_path)
                visual_results["gun_safety"] = gun_res.get("gun_safety_percent", 100.0)
                visual_results["gun_det"] = gun_res.get("gun_detections", 0)  # <-- EKLENDİ

                # 2️⃣ Eski Bıçak Modülü
                knife_res = video_analyzer_knife.analyze_visual_content(video_path)
                visual_results["knife_safety"] = knife_res.get("knife_safety_percent", 100.0)
                visual_results["knife_det"] = knife_res.get("knife_detections", 0)  # <-- EKLENDİ

                # 3️⃣ Yeni Kombine Modül
                comb_res = video_analyzer_combined.analyze_visual_content(video_path)
                visual_results["combined_gun_safety"] = comb_res.get("gun_safety", 100.0)
                visual_results["combined_knife_safety"] = comb_res.get("knife_safety", 100.0)
                visual_results["combined_gun_det"] = comb_res.get("gun_det", 0)  # <-- EKLENDİ
                visual_results["combined_knife_det"] = comb_res.get("knife_det", 0)  # <-- EKLENDİ

                # 4️⃣ Kumar Modülü
                gambling_res = video_analyzer_gambling.analyze_visual_content(video_path)
                visual_results["gambling_safety"] = gambling_res.get("gambling_safety", 100.0)
                visual_results["gambling_det"] = gambling_res.get("gambling_det", 0)  # <-- EKLENDİ

            # --- 4. DB'ye KAYDETME ---
            try:
                db_manager.save_result_to_db(canonical_url, video_id, total_lines, text_percentages, visual_results)
            except Exception as db_err:
                # Arka arkaya gelen çok hızlı isteklerde veritabanı kilitlenirse sistemi çökertmemek için
                if '2627' in str(db_err) or '23000' in str(db_err):
                    print(f"⚠️ Uyarı: Video zaten veritabanına kaydedilmiş.")
                else:
                    print(f"❌ DB yazma hatası: {db_err}")

            # ----------------------------------------------------
            # 🗑️ VİDEO SİLME MANTIĞI (WinError 32 Çözümü)
            # ----------------------------------------------------
            if video_path and os.path.exists(video_path):
                # Arka planda okuma işlemlerini zorla serbest bırak
                gc.collect()
                # Windows'un kilidi açmasına zaman ver
                time.sleep(1)

                try:
                    os.remove(video_path)
                    print(f"🗑️ Geçici video dosyası başarıyla silindi ({video_id}).")
                except Exception as e:
                    print(f"⚠️ Video silinirken hata oluştu: {e}")

            age_rating = calculate_age_rating(text_percentages, visual_results)

            return jsonify({
                "status": "success",
                "age_rating": age_rating
            })

        finally:
            # ----------------------------------------------------
            # 🔓 İŞLEM BİTTİĞİNDE KİLİDİ AÇ
            # Her şey bitince (veya hata verirse) videoyu aktifler listesinden çıkar
            # ----------------------------------------------------
            with analysis_lock:
                if video_id in active_analyses:
                    active_analyses.remove(video_id)

    except Exception as e:
        print(f"❌ Genel Hata: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)