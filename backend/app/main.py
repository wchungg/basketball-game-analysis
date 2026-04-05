from pathlib import Path
import os
import sys

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

CACHE_DIR = APP_DIR.parent / ".cache"
os.makedirs(CACHE_DIR, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(CACHE_DIR / "matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(CACHE_DIR))
os.makedirs(Path(os.environ["MPLCONFIGDIR"]), exist_ok=True)

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from schemas import (
    AnalyzeSampleRequest,
    AnalysisJobResponse,
    DrawerOptions,
    HealthResponse,
    StubOptions,
    UploadHistoryItem,
    VideoAsset,
)
from services.video_analysis_service import VideoAnalysisService


app = FastAPI(
    title="NBA Game Analysis API",
    version="1.0.0",
    description="REST API for basketball video analysis and annotated video generation.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

analysis_service = VideoAnalysisService()


@app.get("/api/v1/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/api/v1/videos", response_model=list[VideoAsset])
def list_sample_videos() -> list[VideoAsset]:
    return analysis_service.list_sample_videos()


@app.get("/api/v1/history", response_model=list[UploadHistoryItem])
def list_upload_history(limit: int = Query(default=20, ge=1, le=100)) -> list[UploadHistoryItem]:
    return analysis_service.list_upload_history(limit=limit)


@app.get("/api/v1/history/video/{file_name}")
def download_history_video(file_name: str) -> FileResponse:
    output_path = analysis_service.get_history_video_path(file_name)
    if output_path is None:
        raise HTTPException(status_code=404, detail="History video file not found.")

    media_types = {
        ".mp4": "video/mp4",
        ".avi": "video/x-msvideo",
        ".mov": "video/quicktime",
        ".mkv": "video/x-matroska",
    }

    return FileResponse(
        path=output_path,
        media_type=media_types.get(output_path.suffix.lower(), "application/octet-stream"),
        filename=output_path.name,
    )


@app.post("/api/v1/analyze/sample", response_model=AnalysisJobResponse)
def analyze_sample_video(request: AnalyzeSampleRequest) -> AnalysisJobResponse:
    try:
        return analysis_service.analyze_sample_video(
            video_name=request.video_name,
            use_stubs=request.use_stubs,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/analyze/upload", response_model=AnalysisJobResponse)
async def analyze_uploaded_video(
    file: UploadFile = File(...),
    draw_player_tracks: bool = Form(default=True),
    draw_ball_tracks: bool = Form(default=True),
    draw_team_ball_control: bool = Form(default=True),
    draw_passes_steals: bool = Form(default=True),
    draw_court_keypoints: bool = Form(default=True),
    draw_tactical_view: bool = Form(default=True),
    draw_speed_distance: bool = Form(default=True),
    stub_player_tracks: bool = Form(default=True),
    stub_ball_tracks: bool = Form(default=True),
    stub_court_keypoints: bool = Form(default=True),
    stub_player_assignment: bool = Form(default=True),
) -> AnalysisJobResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Uploaded file must have a filename.")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".mp4", ".avi", ".mov", ".mkv"}:
        raise HTTPException(status_code=400, detail="Unsupported video format.")

    try:
        file_bytes = await file.read()
        return analysis_service.start_uploaded_video_analysis(
            filename=file.filename,
            file_bytes=file_bytes,
            drawer_options=DrawerOptions(
                player_tracks=draw_player_tracks,
                ball_tracks=draw_ball_tracks,
                team_ball_control=draw_team_ball_control,
                passes_steals=draw_passes_steals,
                court_keypoints=draw_court_keypoints,
                tactical_view=draw_tactical_view,
                speed_distance=draw_speed_distance,
            ),
            stub_options=StubOptions(
                player_tracks=stub_player_tracks,
                ball_tracks=stub_ball_tracks,
                court_keypoints=stub_court_keypoints,
                player_assignment=stub_player_assignment,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/v1/results/{job_id}", response_model=AnalysisJobResponse)
def get_analysis_result(job_id: str) -> AnalysisJobResponse:
    result = analysis_service.get_result(job_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Analysis result not found.")

    return result


@app.post("/api/v1/results/{job_id}/cancel", response_model=AnalysisJobResponse)
def cancel_analysis(job_id: str) -> AnalysisJobResponse:
    result = analysis_service.cancel_job(job_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Analysis result not found.")

    return result


@app.get("/api/v1/results/{job_id}/video")
def download_result_video(job_id: str) -> FileResponse:
    result = analysis_service.get_result(job_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Analysis result not found.")

    if result.status != "completed" or not result.output_video_path:
        raise HTTPException(status_code=409, detail="Output video is not ready yet.")

    output_path = Path(result.output_video_path)
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="Output video file not found.")

    return FileResponse(
        path=output_path,
        media_type="video/mp4",
        filename=output_path.name,
    )
