from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[2]
APP_DIR = BACKEND_DIR / "app"
MODELS_DIR = BACKEND_DIR / "models"
IMAGES_DIR = BACKEND_DIR / "images"
SAMPLE_VIDEOS_DIR = BACKEND_DIR / "video_data"
STUBS_DEFAULT_PATH = BACKEND_DIR / "stubs"
OUTPUT_VIDEOS_DIR = BACKEND_DIR / "output_videos"
TEMP_UPLOADS_DIR = BACKEND_DIR / "temp_uploads"

PLAYER_DETECTOR_PATH = str(MODELS_DIR / "player_detector.pt")
BALL_DETECTOR_PATH = str(MODELS_DIR / "ball_detector_model.pt")
COURT_KEYPOINT_DETECTOR_PATH = str(MODELS_DIR / "court_keypoint_detector.pt")
COURT_IMAGE_PATH = IMAGES_DIR / "basketball_court.png"
OUTPUT_VIDEO_PATH = str(OUTPUT_VIDEOS_DIR / "output_video.avi")
