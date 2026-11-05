"""실제 파일 출력, 롤링, 보관 개수와 설정 검증을 검사한다."""
import logging
import time
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.core.logging_config import LoggingConfig, configure_api_logging, load_logging_config


def test_size_rotation_and_shutdown_flush(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "api.log"
    config = LoggingConfig(console_enabled=False, file_path=str(path), max_bytes=100, backup_count=2)
    with configure_api_logging(config):
        for index in range(20):
            logging.getLogger("gwiteem.api_access").info("%s %s", index, "인증 로그" * 10)
    assert len(list(path.parent.glob("api.log*"))) == 3
    assert "19 인증 로그" in path.read_text(encoding="utf-8")


def test_level_filter_and_restart(tmp_path: Path) -> None:
    path = tmp_path / "api.log"
    config = LoggingConfig(console_enabled=False, file_path=str(path), level="WARNING")
    for _ in range(2):
        with configure_api_logging(config):
            logger = logging.getLogger("gwiteem.api_access")
            logger.info("success")
            logger.warning("failed")
    assert path.read_text(encoding="utf-8").splitlines() == ["failed", "failed"]


def test_time_rotation(tmp_path: Path) -> None:
    path = tmp_path / "api.log"
    path.write_text("old\n", encoding="utf-8")
    handler = TimedRotatingFileHandler(path, when="midnight", backupCount=2, utc=True, encoding="utf-8")
    handler.rolloverAt = int(time.time()) - 1
    with patch("app.core.logging_config.TimedRotatingFileHandler", return_value=handler) as factory:
        with configure_api_logging(LoggingConfig(console_enabled=False, file_path=str(path), rotation="time", backup_count=2)):
            logging.getLogger("gwiteem.api_access").info("new")
        assert factory.call_args.kwargs["when"] == "midnight"
        assert factory.call_args.kwargs["utc"] is True
    assert path.read_text(encoding="utf-8") == "new\n"
    assert len(list(tmp_path.glob("api.log.*"))) == 1


def test_config_validation_and_disabled_output(tmp_path: Path) -> None:
    config_path = tmp_path / "logging.toml"
    config_path.write_text('level = "WARNING"\nfile_enabled = false\nconsole_enabled = false\n', encoding="utf-8")
    config = load_logging_config(str(config_path))
    with configure_api_logging(config):
        assert isinstance(logging.getLogger("gwiteem.api_access").handlers[0], logging.NullHandler)
    for values in ({"rotation": "typo"}, {"backup_count": 0}, {"max_bytes": 0}, {"unknown": True}):
        with pytest.raises(ValidationError):
            LoggingConfig.model_validate(values)


def test_app_lifespan_loads_config(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient
    from app.main import app

    path = tmp_path / "api.log"
    config = LoggingConfig(console_enabled=False, file_path=str(path))
    with patch("app.main.load_logging_config", return_value=config):
        with TestClient(app) as client:
            assert client.get("/api/not-found").status_code == 404
    assert "[public], GET, /api/not-found, failed" in path.read_text(encoding="utf-8")