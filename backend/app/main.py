from utils import read_video, save_video
from trackers import PlayerTracker

def main():
    print("hello world")

    # read video
    video_frames = read_video("video_data/block.mp4")

    # init tracker
    player_tracker = PlayerTracker("models/player_detector.pt")

    # run trackers
    player_tracks = player_tracker.get_object_tracks(video_frames)
    print(player_tracks)

    # save video
    save_video(video_frames, "output_videos/output_video.avi")

if __name__ == "__main__":
    main()








# from fastapi import FastAPI
# import uvicorn
# from ultralytics import YOLO 

# app = FastAPI()

# model = YOLO("models/player_detector.pt")

# results = model.track("video_data/turnover.mp4", save=True)
# print(results)
# print("================")
# for box in results[0].boxes:
#     print(box)

# @app.get("/")
# def read_root():
#     return {"message": "FastAPI YOLO backend running"}


# if __name__ == "__main__":
#     uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)