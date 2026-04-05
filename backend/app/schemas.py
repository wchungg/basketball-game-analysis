from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str


class VideoAsset(BaseModel):
    name: str
    path: str


class AnalyzeSampleRequest(BaseModel):
    video_name: str = Field(..., description="Name of a video inside backend/video_data.")
    use_stubs: bool = Field(default=True, description="Reuse cached detections when available.")


class AnalysisResponse(BaseModel):
    job_id: str
    status: str
    input_video_name: str
    output_video_name: str
    output_video_path: str
    output_video_url: str
    frame_count: int
    passes_team_1: int
    passes_team_2: int
    steals_team_1: int
    steals_team_2: int
