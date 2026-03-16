from utils import read_video, save_video
from trackers import PlayerTracker, BallTracker
from drawers import PlayerTracksDrawer, BallTracksDrawer

def main():
    print("hello world")

    # read video
    video_frames = read_video("video_data/block.mp4")

    # init tracker
    player_tracker = PlayerTracker("models/player_detector.pt")
    ball_tracker = BallTracker("models/ball_detector_model.pt")

    # run trackers
    player_tracks = player_tracker.get_object_tracks(video_frames, read_from_stub=True, stub_path="stubs/player_track_stubs.pkl")
    ball_tracks = ball_tracker.get_object_tracks(video_frames, read_from_stub=True, stub_path="stubs/ball_track_stubs.pkl")

    # remove wrong ball detections
    ball_tracks = ball_tracker.remove_wrong_detections(ball_tracks)
    # interpolate ball tracks
    ball_tracks = ball_tracker.interpolate_ball_positions(ball_tracks)

    # draw output
    # init drawers
    player_tracks_drawer = PlayerTracksDrawer()
    ball_tracks_drawer = BallTracksDrawer()

    # draw object tracks
    output_video_frames = player_tracks_drawer.draw(video_frames, player_tracks)
    output_video_frames = ball_tracks_drawer.draw(output_video_frames, ball_tracks)

    # save video
    save_video(output_video_frames, "output_videos/output_video.avi")

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