# NAS 백엔드 실행 파일 배치

`.github/workflows/transfer-nas.yml`은 `main` push 또는 Actions의 **Run workflow**로 실행합니다.
`hodo_admin@kimjihodo.synology.me:22`에 접속해 `/volume1/docker/gwiteem/product/be`에 Python 앱과 설치된 의존성을 배치합니다.
배치가 끝나면 이 경로를 Python 컨테이너의 `/app`에 마운트하고 Uvicorn 실행 명령으로 FastAPI 서버를 시작할 수 있습니다.
Actions는 NAS의 컨테이너나 서버를 시작·재시작하거나 DB 마이그레이션을 실행하지 않습니다.

## GitHub 설정

백엔드 저장소 **Settings → Secrets and variables → Actions → New repository secret**에서 다음 항목 하나를 등록합니다.

| Name | Secret |
| --- | --- |
| `NAS_SSH_PASSWORD` | NAS `hodo_admin` 계정의 로그인 비밀번호 |

Actions는 저장된 비밀번호를 `sshpass`의 환경변수로 읽습니다. 실행 중 비밀번호 입력창은 뜨지 않습니다.
`NAS_SSH_PRIVATE_KEY`, `NAS_KNOWN_HOSTS`, NAS 공개키 등록은 필요하지 않습니다.

각 Actions 실행은 첫 SSH 접속에서 받은 호스트 키를 자동으로 신뢰하고 임시 `known_hosts` 파일에 저장합니다(`StrictHostKeyChecking=accept-new`). 같은 실행에서 이후 접속의 호스트 키가 달라지면 거부합니다. 새 실행마다 처음 받은 키를 신뢰하므로 최초 접속 대상의 신원을 사전에 검증하지는 않습니다.

NAS에서 SSH 비밀번호 인증이 허용되어야 하며 해당 계정에 대상 디렉터리 생성·쓰기 권한이 필요합니다.
NAS에 `sh`, SSH, SCP, `sha256sum`, `tar`가 있어야 하고 외부 GitHub hosted runner에서 SSH 22번 포트에 연결할 수 있어야 합니다.
Synology 호환성을 위해 SCP의 기존 프로토콜(`-O`)을 사용합니다.

## 빌드와 파일 배치

1. Actions에서 `python:3.12-slim-bookworm`의 Linux amd64 컨테이너로 `scripts/package-nas-build.py`를 실행합니다.
2. `app/`, `requirements.txt`, `alembic.ini`만 복사하고 환경변수 파일, 로컬 데이터, 캐시를 제외합니다. `pip --target`으로 의존성을 배포 디렉터리의 `.packages/`에 설치합니다.
3. Python 구문과 `app.main`, Uvicorn import를 검사합니다. 검사 시 `AWS_EC2_METADATA_DISABLED=true`를 설정하며 서버를 시작하거나 DB·Redis·외부 API에 연결하지 않습니다.
4. `gwiteem-be.tar.gz`와 SHA-256 파일을 NAS의 `.transfers/<commit SHA>-<run ID>-<attempt>/`에 전송합니다.
5. `scripts/install-nas-build.sh`를 SSH 표준입력으로 실행합니다. 스크립트가 체크섬을 확인하고 `runtime/`에 압축을 푼 뒤 실행 파일을 `be` 루트로 옮깁니다.

배치 결과는 다음과 같습니다. `.packages`와 `.transfers`는 숨김 디렉터리이므로 NAS 터미널에서 `ls -a`로 확인할 수 있습니다.

```text
/volume1/docker/gwiteem/product/be/
├── app/
├── .packages/
├── requirements.txt
├── alembic.ini
├── TRANSFER_COMPLETE
└── .transfers/
    └── <commit SHA>-<run ID>-<attempt>/
        ├── gwiteem-be.tar.gz
        ├── gwiteem-be.tar.gz.sha256
        ├── runtime/
        └── previous/
```

`app`, `.packages`, `requirements.txt`, `alembic.ini`, `TRANSFER_COMPLETE`만 교체합니다.
기존 파일은 해당 전송 디렉터리의 `previous/`에 보관하고, 교체 중 명령이 실패하면 이전 파일로 복구하도록 구성합니다. 전원 차단 등으로 복구 처리 자체가 중단되는 경우까지 보장하지는 않습니다.
루트의 `.env`, `data/` 등 별도 운영 파일과 예전 방식의 실행별 디렉터리는 유지합니다.
`TRANSFER_COMPLETE`는 배치한 실행 식별자가 담긴 **파일**입니다. 실패하면 기존 배치의 완료 파일이 남을 수 있으므로 현재 Actions 실행 식별자와 비교합니다.
Actions 실행 요약에도 배치 경로를 기록합니다. 전송 파일과 이전 버전은 자동 삭제하지 않습니다.
이미 실행 중인 서버가 있다면 파일 교체 중 무중단 운영은 보장하지 않으며, 배치 후 사용자가 재시작해야 새 버전이 적용됩니다.

## Docker 컨테이너 설정

NAS Container Manager 등에서 아래 값으로 컨테이너를 구성합니다.

| 항목 | 값 |
| --- | --- |
| 이미지 | `python:3.12-slim-bookworm` |
| 플랫폼 | `linux/amd64` |
| 호스트 경로 | `/volume1/docker/gwiteem/product/be` |
| 컨테이너 마운트 경로 | `/app` |
| 작업 디렉터리 | `/app` |
| 컨테이너 포트 | `8000` |
| 실행 명령 | `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000` |

빌드 시 설치한 의존성에는 Linux용 바이너리가 포함됩니다. 실행 환경도 같은 Python 3.12·Debian Bookworm·amd64 조합을 사용합니다.
ARM NAS라면 빌드와 실행 플랫폼을 함께 변경해야 합니다.
호스트에서 사용할 포트를 컨테이너의 `8000`번 포트에 연결합니다.
컨테이너 사용자를 따로 지정하면 NAS 마운트 경로의 읽기·탐색 권한도 확인합니다.

컨테이너 환경변수에는 다음 값을 설정합니다.

| 이름 | 값 또는 설정 내용 |
| --- | --- |
| `PYTHONPATH` | `/app/.packages` — 설치된 의존성을 읽기 위해 필수 |
| `PYTHONDONTWRITEBYTECODE` | `1` |
| `PYTHONUNBUFFERED` | `1` |
| `APP_ENV` | `production` |
| `DEBUG` | `false` |
| `AWS_EC2_METADATA_DISABLED` | `true` — NAS에서 AWS EC2 메타데이터 자격증명 탐색 제외 |
| `DATABASE_URL` | 컨테이너에서 접근 가능한 PostgreSQL 접속 URL. `postgresql+asyncpg://` 형식 사용 |
| `REDIS_URL` | 컨테이너에서 접근 가능한 Redis 접속 URL |
| `JWT_SECRET_KEY` | 운영용 JWT 서명 비밀값 |

`DATABASE_URL`, `REDIS_URL` 등 앱 설정은 NAS의 `/volume1/docker/gwiteem/product/be/.env`에 직접 준비해도 됩니다.
작업 디렉터리가 `/app`이면 앱이 이 파일을 읽으며, 컨테이너 환경변수가 같은 이름의 `.env` 값보다 우선합니다.
`PYTHONPATH` 등 Python 실행 환경변수는 컨테이너 설정에 넣어야 합니다. 앱의 `.env`만으로 설정되지 않습니다.
`.env`는 GitHub Actions에서 전송하지 않으며 재배치할 때 기존 파일을 보존합니다.

DB와 Redis를 별도 컨테이너에서 실행한다면 같은 Docker 네트워크의 해당 서비스 이름이나 실제 접근 가능한 주소를 사용합니다.
앱 기본값인 `localhost`는 Python 컨테이너 자체를 가리키므로 별도 DB·Redis에 연결할 수 없습니다.
이메일 인증에는 AWS SES 설정, 소셜 로그인에는 해당 공급자의 OAuth 설정도 필요합니다. 설정 이름은 `app/core/config.py`를 따릅니다.
DB 스키마 준비와 마이그레이션은 별도 운영 단계이며 이 워크플로에서 실행하지 않습니다.

이 설정이 준비되면 별도 `pip install`이나 빌드 없이 위 Uvicorn 명령으로 실행할 수 있습니다.
`package-nas-build.py`와 `install-nas-build.sh`는 Actions의 배포 도구이며 서버 실행 시 직접 호출할 필요가 없습니다.

## 검증 범위

현재 로컬 환경에는 Docker가 없어 실제 Linux 컨테이너에서의 의존성 설치·import 검증은 GitHub Actions 실행에서 확인해야 합니다.
Windows의 독립된 Python 3.12 환경에서는 의존성 설치, `pip check`, FastAPI import와 ORM 매핑 검증을 통과했습니다.
Actions의 패키징 단계가 이를 검사하며, 실제 NAS 전송과 운영 DB 연결 여부는 해당 실행 결과와 운영 설정으로 확인합니다.
