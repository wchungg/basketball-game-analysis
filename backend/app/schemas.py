from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str


class VideoAsset(BaseModel):
    name: str
    path: str


class DrawerOptions(BaseModel):
    player_tracks: bool = True
    ball_tracks: bool = True
    team_ball_control: bool = True
    passes_steals: bool = True
    court_keypoints: bool = True
    tactical_view: bool = True
    speed_distance: bool = True


class StubOptions(BaseModel):
    player_tracks: bool = True
    ball_tracks: bool = True
    court_keypoints: bool = True
    player_assignment: bool = True


class AnalyzeSampleRequest(BaseModel):
    video_name: str = Field(..., description="Name of a video inside backend/video_data.")
    use_stubs: bool = Field(default=True, description="Reuse cached detections when available.")


class AnalysisJobResponse(BaseModel):
    job_id: str
    status: str
    message: str | None = None
    input_video_name: str | None = None
    output_video_name: str | None = None
    output_video_path: str | None = None
    output_video_url: str | None = None
    frame_count: int | None = None
    passes_team_1: int | None = None
    passes_team_2: int | None = None
    steals_team_1: int | None = None
    steals_team_2: int | None = None
