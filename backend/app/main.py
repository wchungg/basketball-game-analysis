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

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from schemas import AnalyzeSampleRequest, AnalysisResponse, HealthResponse, VideoAsset
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


@app.post("/api/v1/analyze/sample", response_model=AnalysisResponse)
def analyze_sample_video(request: AnalyzeSampleRequest) -> AnalysisResponse:
    try:
        return analysis_service.analyze_sample_video(
            video_name=request.video_name,
            use_stubs=request.use_stubs,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/analyze/upload", response_model=AnalysisResponse)
async def analyze_uploaded_video(
    file: UploadFile = File(...),
    use_stubs: bool = Query(default=False),
) -> AnalysisResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Uploaded file must have a filename.")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".mp4", ".avi", ".mov", ".mkv"}:
        raise HTTPException(status_code=400, detail="Unsupported video format.")

    try:
        file_bytes = await file.read()
        return analysis_service.analyze_uploaded_video(
            filename=file.filename,
            file_bytes=file_bytes,
            use_stubs=use_stubs,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/v1/results/{job_id}", response_model=AnalysisResponse)
def get_analysis_result(job_id: str) -> AnalysisResponse:
    result = analysis_service.get_result(job_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Analysis result not found.")

    return result


@app.get("/api/v1/results/{job_id}/video")
def download_result_video(job_id: str) -> FileResponse:
    result = analysis_service.get_result(job_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Analysis result not found.")

    output_path = Path(result.output_video_path)
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="Output video file not found.")

    return FileResponse(
        path=output_path,
        media_type="video/mp4",
        filename=output_path.name,
    )
