import hashlib
from pathlib import Path
import re
import sys
import uuid

APP_DIR = Path(__file__).resolve().parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from ball_acquisition import BallAcquisitionDetector
from configs.config import (
    BALL_DETECTOR_PATH,
    COURT_IMAGE_PATH,
    COURT_KEYPOINT_DETECTOR_PATH,
    OUTPUT_VIDEOS_DIR,
    PLAYER_DETECTOR_PATH,
    SAMPLE_VIDEOS_DIR,
    STUBS_DEFAULT_PATH,
    TEMP_UPLOADS_DIR,
)
from court_keypoint_detector import CourtKeypointDetector
from drawers import (
    BallTracksDrawer,
    CourtKeypointDrawer,
    PassStealDrawer,
    PlayerTracksDrawer,
    SpeedAndDistanceDrawer,
    TacticalViewDrawer,
    TeamBallControlDrawer,
)
from pass_steal_detector import PassAndStealDetector
from schemas import AnalysisResponse, VideoAsset
from speed_and_distance_calculator import SpeedAndDistanceCalculator
from tactical_view_converter import TacticalViewConverter
from team_assigner import TeamAssigner
from trackers import BallTracker, PlayerTracker
from utils import read_video, save_video


class VideoAnalysisService:
    def __init__(self):
        self.player_tracker = PlayerTracker(PLAYER_DETECTOR_PATH)
        self.ball_tracker = BallTracker(BALL_DETECTOR_PATH)
        self.court_keypoint_detector = CourtKeypointDetector(COURT_KEYPOINT_DETECTOR_PATH)
        self.team_assigner = TeamAssigner()
        self.ball_acquisition_detector = BallAcquisitionDetector()
        self.pass_and_steal_detector = PassAndStealDetector()
        self.tactical_view_converter = TacticalViewConverter(court_image_path=str(COURT_IMAGE_PATH))
        self.results: dict[str, AnalysisResponse] = {}

        TEMP_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        OUTPUT_VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
        STUBS_DEFAULT_PATH.mkdir(parents=True, exist_ok=True)

    def list_sample_videos(self) -> list[VideoAsset]:
        return [
            VideoAsset(name=path.name, path=str(path))
            for path in sorted(SAMPLE_VIDEOS_DIR.glob("*"))
            if path.is_file()
        ]

    def analyze_sample_video(self, video_name: str, use_stubs: bool = True) -> AnalysisResponse:
        video_path = SAMPLE_VIDEOS_DIR / video_name
        if not video_path.exists():
            raise FileNotFoundError(f"Sample video '{video_name}' was not found.")

        return self._analyze_video_file(
            video_path=video_path,
            display_name=video_path.name,
            use_stubs=use_stubs,
            stub_prefix=video_path.stem,
        )

    def analyze_uploaded_video(
        self,
        filename: str,
        file_bytes: bytes,
        use_stubs: bool = True,
    ) -> AnalysisResponse:
        if not file_bytes:
            raise ValueError("Uploaded video is empty.")

        safe_name = self._slugify(Path(filename).stem)
        file_hash = hashlib.sha256(file_bytes).hexdigest()[:16]
        job_id = uuid.uuid4().hex
        upload_key = f"{safe_name}_{file_hash}"
        upload_path = TEMP_UPLOADS_DIR / f"{upload_key}{Path(filename).suffix.lower() or '.mp4'}"
        upload_path.write_bytes(file_bytes)

        return self._analyze_video_file(
            video_path=upload_path,
            display_name=filename,
            use_stubs=use_stubs,
            stub_prefix=upload_key,
            job_id=job_id,
        )

    def get_result(self, job_id: str) -> AnalysisResponse | None:
        return self.results.get(job_id)

    def _analyze_video_file(
        self,
        video_path: Path,
        display_name: str,
        use_stubs: bool,
        stub_prefix: str,
        job_id: str | None = None,
    ) -> AnalysisResponse:
        video_frames = read_video(str(video_path))
        if not video_frames:
            raise ValueError("No frames were read from the video.")

        stub_paths = self._build_stub_paths(stub_prefix) if use_stubs else {}

        player_tracks = self.player_tracker.get_object_tracks(
            video_frames,
            read_from_stub=use_stubs,
            stub_path=stub_paths.get("player_tracks"),
        )
        ball_tracks = self.ball_tracker.get_object_tracks(
            video_frames,
            read_from_stub=use_stubs,
            stub_path=stub_paths.get("ball_tracks"),
        )
        court_keypoints = self.court_keypoint_detector.get_court_keypoints(
            video_frames,
            read_from_stub=use_stubs,
            stub_path=stub_paths.get("court_keypoints"),
        )

        ball_tracks = self.ball_tracker.remove_wrong_detections(ball_tracks)
        ball_tracks = self.ball_tracker.interpolate_ball_positions(ball_tracks)

        player_assignment = self.team_assigner.get_player_teams_across_frames(
            video_frames,
            player_tracks,
            load_from_stub=use_stubs,
            stub_path=stub_paths.get("player_assignment"),
        )

        ball_acquisition = self.ball_acquisition_detector.detect_ball_possession(player_tracks, ball_tracks)
        passes = self.pass_and_steal_detector.detect_pass(ball_acquisition, player_assignment)
        steals = self.pass_and_steal_detector.detect_steal(ball_acquisition, player_assignment)

        court_keypoints = self.tactical_view_converter.validate_keypoints(court_keypoints)
        tactical_player_positions = self.tactical_view_converter.transform_players_to_tactical_view(
            court_keypoints,
            player_tracks,
        )

        speed_distance_calculator = SpeedAndDistanceCalculator(
            self.tactical_view_converter.width,
            self.tactical_view_converter.height,
            self.tactical_view_converter.actual_width_in_meters,
            self.tactical_view_converter.actual_height_in_meters,
        )
        player_distance_per_frame = speed_distance_calculator.calculate_distance(tactical_player_positions)
        player_speed_per_frame = speed_distance_calculator.calculate_speed(player_distance_per_frame)

        output_video_frames = self._draw_output_frames(
            video_frames=video_frames,
            player_tracks=player_tracks,
            player_assignment=player_assignment,
            ball_acquisition=ball_acquisition,
            ball_tracks=ball_tracks,
            passes=passes,
            steals=steals,
            court_keypoints=court_keypoints,
            tactical_player_positions=tactical_player_positions,
            player_distance_per_frame=player_distance_per_frame,
            player_speed_per_frame=player_speed_per_frame,
        )

        analysis_job_id = job_id or uuid.uuid4().hex
        output_path = OUTPUT_VIDEOS_DIR / f"{Path(display_name).stem}_{analysis_job_id}.mp4"
        save_video(output_video_frames, str(output_path))

        result = AnalysisResponse(
            job_id=analysis_job_id,
            status="completed",
            input_video_name=display_name,
            output_video_name=output_path.name,
            output_video_path=str(output_path),
            output_video_url=f"/api/v1/results/{analysis_job_id}/video",
            frame_count=len(video_frames),
            passes_team_1=sum(1 for item in passes if item == 1),
            passes_team_2=sum(1 for item in passes if item == 2),
            steals_team_1=sum(1 for item in steals if item == 1),
            steals_team_2=sum(1 for item in steals if item == 2),
        )
        self.results[analysis_job_id] = result
        return result

    def _draw_output_frames(
        self,
        video_frames,
        player_tracks,
        player_assignment,
        ball_acquisition,
        ball_tracks,
        passes,
        steals,
        court_keypoints,
        tactical_player_positions,
        player_distance_per_frame,
        player_speed_per_frame,
    ):
        player_tracks_drawer = PlayerTracksDrawer()
        ball_tracks_drawer = BallTracksDrawer()
        team_ball_control_drawer = TeamBallControlDrawer()
        passes_steals_drawer = PassStealDrawer()
        court_keypoint_drawer = CourtKeypointDrawer()
        tactical_view_drawer = TacticalViewDrawer()
        speed_and_distance_drawer = SpeedAndDistanceDrawer()

        output_video_frames = player_tracks_drawer.draw(
            video_frames,
            player_tracks,
            player_assignment,
            ball_acquisition,
        )
        output_video_frames = ball_tracks_drawer.draw(output_video_frames, ball_tracks)
        output_video_frames = team_ball_control_drawer.draw(
            output_video_frames,
            player_assignment,
            ball_acquisition,
        )
        output_video_frames = passes_steals_drawer.draw(output_video_frames, passes, steals)
        output_video_frames = court_keypoint_drawer.draw(output_video_frames, court_keypoints)
        output_video_frames = tactical_view_drawer.draw(
            output_video_frames,
            str(COURT_IMAGE_PATH),
            self.tactical_view_converter.width,
            self.tactical_view_converter.height,
            self.tactical_view_converter.key_points,
            tactical_player_positions,
            player_assignment,
            ball_acquisition,
        )
        output_video_frames = speed_and_distance_drawer.draw(
            output_video_frames,
            player_tracks,
            player_distance_per_frame,
            player_speed_per_frame,
        )

        return output_video_frames

    def _build_stub_paths(self, stub_prefix: str) -> dict[str, str]:
        return {
            "player_tracks": str(STUBS_DEFAULT_PATH / f"{stub_prefix}_player_tracks.pkl"),
            "ball_tracks": str(STUBS_DEFAULT_PATH / f"{stub_prefix}_ball_tracks.pkl"),
            "court_keypoints": str(STUBS_DEFAULT_PATH / f"{stub_prefix}_court_keypoints.pkl"),
            "player_assignment": str(STUBS_DEFAULT_PATH / f"{stub_prefix}_player_assignment.pkl"),
        }

    def _slugify(self, value: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", value).strip("_")
        return slug or "upload"
