"""NAS에 마운트할 애플리케이션과 Python 의존성을 준비합니다."""

import os
from pathlib import Path
import shutil
import subprocess
import sys


def prepare_sources(source: Path, destination: Path) -> None:
    """환경변수와 로컬 데이터 없이 실행 소스만 복사합니다."""
    destination.mkdir(parents=True, exist_ok=False)
    shutil.copytree(
        source / "app",
        destination / "app",
        ignore=shutil.ignore_patterns(
            "__pycache__", "*.pyc", ".env*", "*.db", "*.sqlite*", "*.log"
        ),
    )
    for name in ("requirements.txt", "alembic.ini"):
        shutil.copy2(source / name, destination / name)


def main() -> None:
    """동일한 Python 컨테이너에서 의존성 설치와 비실행 검증을 수행합니다."""
    if len(sys.argv) != 2:
        raise SystemExit("사용법: python scripts/package-nas-build.py <새 출력 경로>")
    destination = Path(sys.argv[1]).resolve()
    prepare_sources(Path(__file__).resolve().parents[1], destination)
    for source_file in (destination / "app").rglob("*.py"):
        compile(source_file.read_bytes(), str(source_file), "exec")
    packages = destination / ".packages"
    subprocess.run(
        [
            sys.executable, "-m", "pip", "install", "--no-cache-dir", "--no-compile",
            "--target", str(packages), "-r", str(destination / "requirements.txt"),
        ],
        check=True,
    )
    environment = {
        **os.environ,
        "PYTHONPATH": str(packages),
        "PYTHONDONTWRITEBYTECODE": "1",
        "AWS_EC2_METADATA_DISABLED": "true",
    }
    subprocess.run(
        [sys.executable, "-m", "pip", "check"],
        cwd=destination, env=environment, check=True,
    )
    # 소켓을 열거나 DB에 연결하지 않고 실행 진입점과 ORM 매핑을 확인합니다.
    subprocess.run(
        [
            sys.executable, "-B", "-c",
            "from app.main import app; import uvicorn; "
            "from sqlalchemy.orm import configure_mappers; configure_mappers(); "
            "assert any(route.path == '/health' for route in app.routes); "
            "print('FastAPI runtime import OK (server not started)')",
        ],
        cwd=destination, env=environment, check=True,
    )


if __name__ == "__main__":
    main()
