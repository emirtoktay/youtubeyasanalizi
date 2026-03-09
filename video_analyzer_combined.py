# video_analyzer_combined.py
from ultralytics import YOLO
from pytubefix import YouTube
import cv2
import os

# Modeli bir kez yükleyelim
try:
    # Senin yeni modelin
    model = YOLO("knife_gun_best.pt")
except Exception as e:
    print(f"❌ YOLO Kombine Model yükleme hatası: {e}")
    model = None


def download_video(url):
    try:
        yt = YouTube(url)
        video_id = yt.video_id
        path = f"downloads/{video_id}.mp4"
        if not os.path.exists("downloads"):
            os.makedirs("downloads")
        if os.path.exists(path):
            return path
        stream = yt.streams.filter(progressive=True, file_extension="mp4").first()
        stream.download(output_path="downloads", filename=f"{video_id}.mp4")
        return path
    except Exception as e:
        print(f"❌ Video indirme hatası: {e}")
        return None


def analyze_visual_content(video_path):
    if model is None:
        return {"gun_safety": 100, "knife_safety": 100, "gun_det": 0, "knife_det": 0}

    # Senin kodundaki gibi Class ID'leri otomatik bulalım
    pistol_ids = []
    knife_ids = []
    for cls_id, name in model.names.items():
        n = name.lower()
        if any(word in n for word in ["pistol", "gun", "weapon"]):
            pistol_ids.append(cls_id)
        if any(word in n for word in ["knife", "blade"]):
            knife_ids.append(cls_id)

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0: fps = 30

    check_interval = int(fps * 15)  # 15 saniyede bir kontrol
    frame_count = 0
    total_analyzed = 0

    # Sayaçlar
    pistol_frames = 0
    knife_frames = 0
    total_pistol = 0
    total_knife = 0

    while True:
        ret, frame = cap.read()
        if not ret: break

        frame_count += 1
        if frame_count % check_interval != 0:
            continue

        total_analyzed += 1
        results = model(frame, verbose=False)

        pistol_in_frame = False
        knife_in_frame = False

        for r in results:
            for box in r.boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])

                if conf > 0.40:
                    if cls_id in pistol_ids:
                        pistol_in_frame = True
                        total_pistol += 1
                    elif cls_id in knife_ids:
                        knife_in_frame = True
                        total_knife += 1

        if pistol_in_frame: pistol_frames += 1
        if knife_in_frame: knife_frames += 1

    cap.release()

    # Güvenlik Yüzdeleri
    gun_safety = 100.0
    knife_safety = 100.0
    if total_analyzed > 0:
        gun_safety = ((total_analyzed - pistol_frames) / total_analyzed) * 100
        knife_safety = ((total_analyzed - knife_frames) / total_analyzed) * 100

    return {
        "gun_safety": round(gun_safety, 2),
        "knife_safety": round(knife_safety, 2),
        "gun_det": total_pistol,
        "knife_det": total_knife
    }