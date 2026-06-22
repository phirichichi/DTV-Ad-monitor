#config.py 
from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "DTV-Ad Monitor API"
    app_env: str = "development"
    app_debug: bool = True
    api_v1_prefix: str = "/api/v1"

    # ---------------------------
    # Database
    # ---------------------------
    db_host: str
    db_port: int = 5432
    db_name: str
    db_user: str
    db_password: str

    # ---------------------------
    # Redis
    # ---------------------------
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_db: int = 0

    # ---------------------------
    # Kafka
    # ---------------------------
    kafka_bootstrap_servers: str = "kafka:9092"
    kafka_frames_topic: str = "dtv.sampled.frames"
    kafka_group_detection: str = "dtv-detection-consumers"

    # ---------------------------
    # Auth
    # ---------------------------
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # ---------------------------
    # CORS
    # ---------------------------
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    cors_origin_regex: Optional[str] = r"^http://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+)(:\d+)?$"

    # ---------------------------
    # Feature Flags
    # ---------------------------
    enable_audio_matching: bool = True
    enable_frame_matching: bool = True
    enable_classifier: bool = False
    enable_watermark_detection: bool = False
    enable_websocket_streaming: bool = False
    enable_auto_verification: bool = False

    # ---------------------------
    # Evidence retention
    # ---------------------------
    evidence_retention_days: int = 30
    auto_delete_old_evidence: bool = False

    # ---------------------------
    # Monitoring config
    # ---------------------------
    frame_sample_interval_seconds: float = 2.0
    audio_chunk_duration_seconds: float = 3.0
    frame_resize_width: int = 320
    preprocess_grayscale: bool = False
    worker_idle_sleep_seconds: float = 3.0
    stream_reconnect_delay_seconds: float = 5.0
    stream_max_retries: int = -1
    clip_duration_seconds: float = 3.0
    duplicate_cooldown_seconds: int = 60

    # ---------------------------
    # Matching thresholds
    # ---------------------------
    frame_match_threshold: float = 0.92
    audio_match_threshold: float = 0.92
    hybrid_match_threshold: float = 0.85

    # ---------------------------
    # Storage
    # ---------------------------
    storage_mode: str = "local"
    local_storage_base_dir: str = "storage"
    local_upload_dir: str = "uploads/advertisements"
    evidence_base_path: str = "evidence"
    screenshot_output_dir: str = "evidence/screenshots"
    clip_output_dir: str = "evidence/clips"
    temp_audio_dir: str = "tmp/audio"

    # ---------------------------
    # Media tools
    # ---------------------------
    ffmpeg_binary_path: str = "ffmpeg"

    # ---------------------------
    # Optional S3
    # ---------------------------
    s3_endpoint: Optional[str] = None
    s3_access_key: Optional[str] = None
    s3_secret_key: Optional[str] = None
    s3_bucket_name: Optional[str] = None
    s3_region: str = "us-east-1"

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


@lru_cache
def get_settings() -> Settings:
    return Settings()