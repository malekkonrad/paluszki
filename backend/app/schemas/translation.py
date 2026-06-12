from pydantic import BaseModel, Field


class TranslationTask(BaseModel):
    """Task sent to the translation model."""
    meeting_code: str = Field(description="Code of the meeting")
    user_id: str = Field(description="ID of the user whose video is being processed")
    frame_data: bytes = Field(description="Raw frame data from video stream")


class TranslationResult(BaseModel):
    """Result returned from the translation model."""
    meeting_code: str = Field(description="Code of the meeting")
    user_id: str = Field(description="ID of the user whose video was processed")
    gesture_label: str | None = Field(default=None, description="Recognized gesture/sign label")
    confidence: float = Field(default=0.0, description="Confidence score 0-1")
    gesture_accepted: bool | None = Field(
        default=None,
        description="Whether the detected sign passed the confidence threshold (None = no new sign)",
    )
    text: str | None = Field(default=None, description="Translated text of the sign language gesture")
    overlay_frame: bytes | None = Field(default=None, description="Processed frame with overlay (detections drawn)")
