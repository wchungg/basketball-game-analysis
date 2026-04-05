import hashlib
from datetime import datetime
from pathlib import Path
import re
import sys
import threading
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
from schemas import AnalysisJobResponse, DrawerOptions, StubOptions, UploadHistoryItem, VideoAsset
from speed_and_distance_calculator import SpeedAndDistanceCalculator
from tactical_view_converter import TacticalViewConverter
from team_assigner import TeamAssigner
from trackers import BallTracker, PlayerTracker
from utils import read_video, save_video


class AnalysisCancelledError(Exception):
    pass


class VideoAnalysisService:
    def __init__(self):
        self.jobs: dict[str, AnalysisJobResponse] = {}
        self.cancel_requests: set[str] = set()
        self.lock = threading.Lock()

        TEMP_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        OUTPUT_VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
        STUBS_DEFAULT_PATH.mkdir(parents=True, exist_ok=True)

    def list_sample_videos(self) -> list[VideoAsset]:
        return [
            VideoAsset(name=path.name, path=str(path))
            for path in sorted(SAMPLE_VIDEOS_DIR.glob("*"))
            if path.is_file()
        ]

    def list_upload_history(self, limit: int = 20) -> list[UploadHistoryItem]:
        files = [
            path for path in OUTPUT_VIDEOS_DIR.glob("*")
            if path.is_file() and path.suffix.lower() in {".mp4", ".avi", ".mov", ".mkv"}
        ]
        files.sort(key=lambda path: path.stat().st_mtime, reverse=True)

        jobs_by_output_path = {
            job.output_video_path: job
            for job in self.jobs.values()
            if job.output_video_path
        }

        history: list[UploadHistoryItem] = []
        for path in files[:limit]:
            stat = path.stat()
            matched_job = jobs_by_output_path.get(str(path))

            history.append(
                UploadHistoryItem(
                    file_name=path.name,
                    file_path=str(path),
                    file_size_bytes=stat.st_size,
                    created_at=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    video_url=matched_job.output_video_url if matched_job else f"/api/v1/history/video/{path.name}",
                    job_id=matched_job.job_id if matched_job else None,
                    input_video_name=matched_job.input_video_name if matched_job else None,
                    status=matched_job.status if matched_job else None,
                    frame_count=matched_job.frame_count if matched_job else None,
                    passes_team_1=matched_job.passes_team_1 if matched_job else None,
                    passes_team_2=matched_job.passes_team_2 if matched_job else None,
                    steals_team_1=matched_job.steals_team_1 if matched_job else None,
                    steals_team_2=matched_job.steals_team_2 if matched_job else None,
                )
            )

        return history

    def get_history_video_path(self, file_name: str) -> Path | None:
        safe_name = Path(file_name).name
        candidate = OUTPUT_VIDEOS_DIR / safe_name
        if candidate.exists() and candidate.is_file():
            return candidate
        return None

    def get_result(self, job_id: str) -> AnalysisJobResponse | None:
        with self.lock:
            return self.jobs.get(job_id)

    def cancel_job(self, job_id: str) -> AnalysisJobResponse | None:
        with self.lock:
            job = self.jobs.get(job_id)
            if job is None:
                return None

            if job.status in {"completed", "failed", "cancelled"}:
                return job

            self.cancel_requests.add(job_id)
            updated_job = job.model_copy(
                update={
                    "status": "cancelling",
                    "message": "Cancellation requested. The pipeline will stop at the next safe checkpoint.",
                }
            )
            self.jobs[job_id] = updated_job
            return updated_job

    def analyze_sample_video(self, video_name: str, use_stubs: bool = True) -> AnalysisJobResponse:
        video_path = SAMPLE_VIDEOS_DIR / video_name
        if not video_path.exists():
            raise FileNotFoundError(f"Sample video '{video_name}' was not found.")

        return self._analyze_video_file(
            job_id=uuid.uuid4().hex,
            video_path=video_path,
            display_name=video_path.name,
            stub_prefix=video_path.stem,
            drawer_options=DrawerOptions(),
            stub_options=StubOptions(
                player_tracks=use_stubs,
                ball_tracks=use_stubs,
                court_keypoints=use_stubs,
                player_assignment=use_stubs,
            ),
        )

    def start_uploaded_video_analysis(
        self,
        filename: str,
        file_bytes: bytes,
        drawer_options: DrawerOptions,
        stub_options: StubOptions,
    ) -> AnalysisJobResponse:
        if not file_bytes:
            raise ValueError("Uploaded video is empty.")

        safe_name = self._slugify(Path(filename).stem)
        file_hash = hashlib.sha256(file_bytes).hexdigest()[:16]
        job_id = uuid.uuid4().hex
        upload_key = f"{safe_name}_{file_hash}"
        upload_path = TEMP_UPLOADS_DIR / f"{upload_key}{Path(filename).suffix.lower() or '.mp4'}"
        upload_path.write_bytes(file_bytes)

        queued_job = AnalysisJobResponse(
            job_id=job_id,
            status="queued",
            message="Upload complete. Waiting for the analysis pipeline to start.",
            input_video_name=filename,
        )
        with self.lock:
            self.jobs[job_id] = queued_job

        worker = threading.Thread(
            target=self._run_uploaded_analysis,
            kwargs={
                "job_id": job_id,
                "video_path": upload_path,
                "display_name": filename,
                "stub_prefix": upload_key,
                "drawer_options": drawer_options,
                "stub_options": stub_options,
            },
            daemon=True,
        )
        worker.start()

        return queued_job

    def _run_uploaded_analysis(
        self,
        job_id: str,
        video_path: Path,
        display_name: str,
        stub_prefix: str,
        drawer_options: DrawerOptions,
        stub_options: StubOptions,
    ) -> None:
        try:
            self._analyze_video_file(
                job_id=job_id,
                video_path=video_path,
                display_name=display_name,
                stub_prefix=stub_prefix,
                drawer_options=drawer_options,
                stub_options=stub_options,
            )
        except AnalysisCancelledError:
            self._update_job(
                job_id,
                status="cancelled",
                message="Analysis was cancelled before completion.",
            )
        except Exception as exc:
            self._update_job(
                job_id,
                status="failed",
                message=str(exc),
            )

    def _analyze_video_file(
        self,
        job_id: str,
        video_path: Path,
        display_name: str,
        stub_prefix: str,
        drawer_options: DrawerOptions,
        stub_options: StubOptions,
    ) -> AnalysisJobResponse:
        self._update_job(job_id, status="in_progress", message="Loading video frames...")
        video_frames = read_video(str(video_path))
        if not video_frames:
            raise ValueError("No frames were read from the video.")
        self._ensure_not_cancelled(job_id)

        player_tracker = PlayerTracker(PLAYER_DETECTOR_PATH)
        ball_tracker = BallTracker(BALL_DETECTOR_PATH)
        court_keypoint_detector = CourtKeypointDetector(COURT_KEYPOINT_DETECTOR_PATH)
        team_assigner = TeamAssigner()
        ball_acquisition_detector = BallAcquisitionDetector()
        pass_and_steal_detector = PassAndStealDetector()
        tactical_view_converter = TacticalViewConverter(court_image_path=str(COURT_IMAGE_PATH))

        stub_paths = self._build_stub_paths(stub_prefix)

        self._update_job(job_id, message="Running player tracking...")
        player_tracks = player_tracker.get_object_tracks(
            video_frames,
            read_from_stub=stub_options.player_tracks,
            stub_path=stub_paths["player_tracks"],
        )
        self._ensure_not_cancelled(job_id)

        self._update_job(job_id, message="Running ball tracking...")
        ball_tracks = ball_tracker.get_object_tracks(
            video_frames,
            read_from_stub=stub_options.ball_tracks,
            stub_path=stub_paths["ball_tracks"],
        )
        ball_tracks = ball_tracker.remove_wrong_detections(ball_tracks)
        ball_tracks = ball_tracker.interpolate_ball_positions(ball_tracks)
        self._ensure_not_cancelled(job_id)

        self._update_job(job_id, message="Detecting court keypoints...")
        court_keypoints = court_keypoint_detector.get_court_keypoints(
            video_frames,
            read_from_stub=stub_options.court_keypoints,
            stub_path=stub_paths["court_keypoints"],
        )
        self._ensure_not_cancelled(job_id)

        self._update_job(job_id, message="Assigning teams...")
        player_assignment = team_assigner.get_player_teams_across_frames(
            video_frames,
            player_tracks,
            load_from_stub=stub_options.player_assignment,
            stub_path=stub_paths["player_assignment"],
        )
        self._ensure_not_cancelled(job_id)

        self._update_job(job_id, message="Computing possession, passes, and steals...")
        ball_acquisition = ball_acquisition_detector.detect_ball_possession(player_tracks, ball_tracks)
        passes = pass_and_steal_detector.detect_pass(ball_acquisition, player_assignment)
        steals = pass_and_steal_detector.detect_steal(ball_acquisition, player_assignment)
        self._ensure_not_cancelled(job_id)

        self._update_job(job_id, message="Projecting players to tactical view...")
        court_keypoints = tactical_view_converter.validate_keypoints(court_keypoints)
        tactical_player_positions = tactical_view_converter.transform_players_to_tactical_view(
            court_keypoints,
            player_tracks,
        )
        self._ensure_not_cancelled(job_id)

        self._update_job(job_id, message="Calculating speed and distance...")
        speed_distance_calculator = SpeedAndDistanceCalculator(
            tactical_view_converter.width,
            tactical_view_converter.height,
            tactical_view_converter.actual_width_in_meters,
            tactical_view_converter.actual_height_in_meters,
        )
        player_distance_per_frame = speed_distance_calculator.calculate_distance(tactical_player_positions)
        player_speed_per_frame = speed_distance_calculator.calculate_speed(player_distance_per_frame)
        self._ensure_not_cancelled(job_id)

        self._update_job(job_id, message="Drawing output video...")
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
            tactical_view_converter=tactical_view_converter,
            drawer_options=drawer_options,
        )
        self._ensure_not_cancelled(job_id)

        self._update_job(job_id, message="Saving annotated video...")
        output_path = OUTPUT_VIDEOS_DIR / f"{Path(display_name).stem}_{job_id}.mp4"
        save_video(output_video_frames, str(output_path))
        self._ensure_not_cancelled(job_id)

        result = AnalysisJobResponse(
            job_id=job_id,
            status="completed",
            message="Analysis complete. Your annotated video is ready.",
            input_video_name=display_name,
            output_video_name=output_path.name,
            output_video_path=str(output_path),
            output_video_url=f"/api/v1/results/{job_id}/video",
            frame_count=len(video_frames),
            passes_team_1=sum(1 for item in passes if item == 1),
            passes_team_2=sum(1 for item in passes if item == 2),
            steals_team_1=sum(1 for item in steals if item == 1),
            steals_team_2=sum(1 for item in steals if item == 2),
        )
        with self.lock:
            self.jobs[job_id] = result
            self.cancel_requests.discard(job_id)
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
        tactical_view_converter,
        drawer_options: DrawerOptions,
    ):
        output_video_frames = video_frames

        if drawer_options.player_tracks:
            output_video_frames = PlayerTracksDrawer().draw(
                output_video_frames,
                player_tracks,
                player_assignment,
                ball_acquisition,
            )
        if drawer_options.ball_tracks:
            output_video_frames = BallTracksDrawer().draw(output_video_frames, ball_tracks)
        if drawer_options.team_ball_control:
            output_video_frames = TeamBallControlDrawer().draw(
                output_video_frames,
                player_assignment,
                ball_acquisition,
            )
        if drawer_options.passes_steals:
            output_video_frames = PassStealDrawer().draw(output_video_frames, passes, steals)
        if drawer_options.court_keypoints:
            output_video_frames = CourtKeypointDrawer().draw(output_video_frames, court_keypoints)
        if drawer_options.tactical_view:
            output_video_frames = TacticalViewDrawer().draw(
                output_video_frames,
                str(COURT_IMAGE_PATH),
                tactical_view_converter.width,
                tactical_view_converter.height,
                tactical_view_converter.key_points,
                tactical_player_positions,
                player_assignment,
                ball_acquisition,
            )
        if drawer_options.speed_distance:
            output_video_frames = SpeedAndDistanceDrawer().draw(
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

    def _update_job(self, job_id: str, **updates) -> None:
        with self.lock:
            current = self.jobs.get(job_id)
            if current is None:
                current = AnalysisJobResponse(job_id=job_id, status="queued")
            self.jobs[job_id] = current.model_copy(update=updates)

    def _ensure_not_cancelled(self, job_id: str) -> None:
        with self.lock:
            is_cancelled = job_id in self.cancel_requests
        if is_cancelled:
            raise AnalysisCancelledError()

    def _slugify(self, value: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", value).strip("_")
        return slug or "upload"
