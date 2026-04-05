from utils import read_video, save_video
import argparse
import os
from trackers import PlayerTracker, BallTracker
from drawers import PlayerTracksDrawer, BallTracksDrawer, TeamBallControlDrawer, PassStealDrawer, CourtKeypointDrawer, TacticalViewDrawer, SpeedAndDistanceDrawer
from team_assigner import TeamAssigner
from ball_acquisition import BallAcquisitionDetector
from pass_steal_detector import PassAndStealDetector
from court_keypoint_detector import CourtKeypointDetector
from tactical_view_converter import TacticalViewConverter
from speed_and_distance_calculator import SpeedAndDistanceCalculator

# from configs import (
#     STUBS_DEFAULT_PATH,
# )

# def parse_args():
#     parser = argparse.ArgumentParser(description='Basketball Video Analysis')
#     parser.add_argument('input_video', type=str, help='Path to input video file')
#     parser.add_argument('--output_video', type=str, default=OUTPUT_VIDEO_PATH, 
#                         help='Path to output video file')
#     parser.add_argument('--stub_path', type=str, default=STUBS_DEFAULT_PATH,
#                         help='Path to stub directory')
#     return parser.parse_args()

def main():
    # args = parse_args()
    print("Loading...")

    # read video
    video_frames = read_video("video_data/turnover.mp4")

    # init tracker
    player_tracker = PlayerTracker("models/player_detector.pt")
    ball_tracker = BallTracker("models/ball_detector_model.pt")
    
    # init court keypoint detector
    court_keypoint_detector = CourtKeypointDetector("models/court_keypoint_detector.pt")

    # run trackers
    player_tracks = player_tracker.get_object_tracks(video_frames, read_from_stub=True, stub_path="stubs/player_track_stubs.pkl")
    ball_tracks = ball_tracker.get_object_tracks(video_frames, read_from_stub=True, stub_path="stubs/ball_track_stubs.pkl")

    # get court keypoints
    court_keypoints = court_keypoint_detector.get_court_keypoints(video_frames,
                                                                  read_from_stub=True,
                                                                  stub_path="stubs/court_key_points_stubs.pkl"
                                                                  )

    # remove wrong ball detections
    ball_tracks = ball_tracker.remove_wrong_detections(ball_tracks)
    # interpolate ball tracks
    ball_tracks = ball_tracker.interpolate_ball_positions(ball_tracks)

    # Assign Player Teams
    team_assigner = TeamAssigner()
    player_assignment = team_assigner.get_player_teams_across_frames(video_frames, 
                                                                player_tracks, 
                                                                load_from_stub=True, 
                                                                stub_path="stubs/player_assignment_stub.pkl"
                                                                # stub_path=os.path.join(args.stub_path, 'player_track_stubs.pkl')
                                                                )

    # Ball Acquisition
    ball_acquisition_detector = BallAcquisitionDetector()
    ball_acquisition = ball_acquisition_detector.detect_ball_possession(player_tracks, ball_tracks)

    # detect passes and steals
    passes_and_steal_detector = PassAndStealDetector()
    passes = passes_and_steal_detector.detect_pass(ball_acquisition, player_assignment)
    steals = passes_and_steal_detector.detect_steal(ball_acquisition, player_assignment)

    # tactical view
    tactical_view_converter = TacticalViewConverter(court_image_path="./images/basketball_court.png")
    court_keypoints = tactical_view_converter.validate_keypoints(court_keypoints)
    tactical_player_positions = tactical_view_converter.transform_players_to_tactical_view(court_keypoints, player_tracks)

    # Speed and distance calculator
    speed_distance_calculator = SpeedAndDistanceCalculator(
        tactical_view_converter.width,
        tactical_view_converter.height,
        tactical_view_converter.actual_width_in_meters,
        tactical_view_converter.actual_height_in_meters
    )
    player_distance_per_frame = speed_distance_calculator.calculate_distance(tactical_player_positions)
    player_speed_per_frame = speed_distance_calculator.calculate_speed(player_distance_per_frame)


    # draw output
    # init drawers
    player_tracks_drawer = PlayerTracksDrawer()
    ball_tracks_drawer = BallTracksDrawer()
    team_ball_control_drawer = TeamBallControlDrawer()
    passes_steals_drawer = PassStealDrawer()
    court_keypoint_drawer = CourtKeypointDrawer()
    tactical_view_drawer = TacticalViewDrawer()
    speed_and_distance_drawer = SpeedAndDistanceDrawer()

    # draw object tracks
    output_video_frames = player_tracks_drawer.draw(video_frames, 
                                                    player_tracks, 
                                                    player_assignment,
                                                    ball_acquisition)
    output_video_frames = ball_tracks_drawer.draw(output_video_frames, ball_tracks)
    
    # draw team ball control
    output_video_frames = team_ball_control_drawer.draw(output_video_frames, 
                                                        player_assignment, 
                                                        ball_acquisition)
    
    # draw passes and steals stats
    output_video_frames = passes_steals_drawer.draw(output_video_frames,
                                                       passes,
                                                       steals)
    
    output_video_frames = court_keypoint_drawer.draw(output_video_frames,
                                                     court_keypoints)
    
    output_video_frames = tactical_view_drawer.draw(output_video_frames, 
                                                    tactical_view_converter.court_image_path,
                                                    tactical_view_converter.width,
                                                    tactical_view_converter.height,
                                                    tactical_view_converter.key_points,
                                                    tactical_player_positions,
                                                    player_assignment,
                                                    ball_acquisition
                                                    )

    # speed and distance drawer
    output_video_frames = speed_and_distance_drawer.draw(output_video_frames,
                                                         player_tracks, 
                                                         player_distance_per_frame, 
                                                         player_speed_per_frame) 

    # save video
    save_video(output_video_frames, "output_videos/output_video.avi")
    print("Done!")
    
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