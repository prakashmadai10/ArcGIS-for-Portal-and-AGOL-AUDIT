# config_context.py
import datetime
import uuid
from dataclasses import dataclass, field

import pytz


@dataclass
class Config:
    """Central configuration with validation"""
    TEST_MODE: bool =False
    TEST_ITEM_ID: str = "370db127e0d8424ba4fb1e2c53b96814"
    MAX_ITEMS: int = 1000
    MAX_WORKERS: int = 10
    BATCH_SIZE: int = 2000
    FIRST_RUN: bool = True
    TIMEZONE: pytz.timezone = pytz.timezone("America/Chicago")
    LOG_RETENTION_DAYS: int = 7
    EXPORT_RETENTION_DAYS: int = 7

    def __post_init__(self):
        if self.MAX_WORKERS < 1:
            self.MAX_WORKERS = 1
        if self.BATCH_SIZE < 1:
            self.BATCH_SIZE = 100


CONFIG = Config()


@dataclass
class RunContext:
    """Manages current run metadata with lazy initialization."""
    utc_now: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @property
    def local_now(self) -> datetime.datetime:
        return self.utc_now.astimezone(CONFIG.TIMEZONE)

    @property
    def run_label(self) -> str:
        return self.local_now.strftime("%Y-%m-%d %I:%M %p %Z")

    @property
    def run_timestamp(self) -> int:
        return int(self.local_now.timestamp() * 1000)

    def print_header(self):
        mode = 'TEST (Single Item)' if CONFIG.TEST_MODE else 'PRODUCTION (All Items)'
        print(f"{'='*60}")
        print(f"🚀 Edit Audit Run: {self.run_label}")
        print(f"🔹 Run ID: {self.run_id}")
        print(f"🔹 Mode: {mode}")
        print(f"{'='*60}\n")
