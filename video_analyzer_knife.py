# video_analyzer_knife.py
from ultralytics import YOLO
from pytubefix import YouTube
import cv2
import os

try:
    model = YOLO("knife_best.pt")
except Exception as e:
    print(f"❌ YOLO Bıçak Modeli yükleme hatası: {e}")
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
        return {"knife_safety_percent": 0, "knife_detections": 0}

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0: fps = 30

    check_interval = int(fps * 15)  # 15 saniyede bir kare kontrol
    frame_count = 0
    dangerous_frames = 0
    total_analyzed = 0
    total_detections = 0

    # 💡 İŞTE BURAYI SENİN ÇALIŞAN KODUNA GÖRE DÜZELTTİK:
    target_classes = [1, 4, 5]

    while True:
        ret, frame = cap.read()
        if not ret: break

        frame_count += 1
        if frame_count % check_interval != 0:
            continue

        total_analyzed += 1
        results = model(frame, verbose=False)

        found_in_frame = False
        for r in results:
            for box in r.boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])

                if cls_id in target_classes and conf > 0.40:
                    found_in_frame = True
                    total_detections += 1

        if found_in_frame:
            dangerous_frames += 1

    cap.release()

    safety_ratio = 100.0
    if total_analyzed > 0:
        safety_ratio = ((total_analyzed - dangerous_frames) / total_analyzed) * 100

    return {
        "knife_safety_percent": round(safety_ratio, 2),
        "knife_detections": total_detections
    }