from __future__ import annotations

from dataclasses import dataclass


@dataclass
class UploadFormData:
    notes: str = ""
    processing_type: str = "automatico_local"
