"""검증된 TOML 설정으로 API 로그 출력과 롤링 수명주기를 관리한다."""
import logging
import tomllib
from collections.abc import Iterator
from contextlib import contextmanager
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path
from queue import SimpleQueue
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class LoggingConfig(BaseModel):
    """알 수 없는 키와 잘못된 정책은 서버 시작 시 오류로 알린다."""

    model_config = ConfigDict(extra="forbid")
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    console_enabled: bool = True
    file_enabled: bool = True
    file_path: str = Field(default="logs/api-access.log", min_length=1)
    rotation: Literal["size", "time"] = "size"
    max_bytes: int = Field(default=10485760, gt=0)
    backup_count: int = Field(default=14, ge=1)
    when: Literal["S", "M", "H", "D", "midnight", "W0", "W1", "W2", "W3", "W4", "W5", "W6"] = "midnight"
    interval: int = Field(default=1, ge=1)
    utc: bool = True


def load_logging_config(config_path: str) -> LoggingConfig:
    """상대 설정 경로를 프로젝트 루트에 고정한다."""
    path = Path(config_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    with path.open("rb") as source:
        return LoggingConfig.model_validate(tomllib.load(source))


@contextmanager
def configure_api_logging(config: LoggingConfig) -> Iterator[None]:
    """큐에서 파일 I/O를 처리하고 종료 시 남은 로그를 배출한다."""
    logger = logging.getLogger("gwiteem.api_access")
    outputs: list[logging.Handler] = []
    listener: QueueListener | None = None
    previous = (logger.handlers[:], logger.level, logger.propagate)
    try:
        if config.console_enabled:
            outputs.append(logging.StreamHandler())
        if config.file_enabled:
            path = Path(config.file_path)
            if not path.is_absolute():
                path = PROJECT_ROOT / path
            path.parent.mkdir(parents=True, exist_ok=True)
            if config.rotation == "size":
                outputs.append(RotatingFileHandler(
                    path, maxBytes=config.max_bytes, backupCount=config.backup_count,
                    encoding="utf-8",
                ))
            else:
                outputs.append(TimedRotatingFileHandler(
                    path, when=config.when, interval=config.interval,
                    backupCount=config.backup_count, encoding="utf-8", utc=config.utc,
                ))
        for handler in outputs:
            handler.setFormatter(logging.Formatter("%(message)s"))
        logger.setLevel(config.level)
        logger.propagate = False
        if outputs:
            queue: SimpleQueue[logging.LogRecord] = SimpleQueue()
            logger.handlers = [QueueHandler(queue)]
            listener = QueueListener(queue, *outputs)
            listener.start()
        else:
            logger.handlers = [logging.NullHandler()]
        yield
    finally:
        if listener is not None:
            listener.stop()
        logger.handlers, logger.level, logger.propagate = previous
        for handler in outputs:
            handler.close()
