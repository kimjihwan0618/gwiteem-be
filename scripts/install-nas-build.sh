#!/bin/sh
set -eu

# 파일 배치만 수행합니다. 서버 실행이나 DB 마이그레이션은 하지 않습니다.
cd "$1"
destination="$(pwd -P)"
transfer="$destination/.transfers/$2"
archive="$3"
case "$2" in ''|*[!a-zA-Z0-9-]*) exit 1 ;; esac
case "$archive" in gwiteem-be.tar.gz) ;; *) exit 1 ;; esac

cd "$transfer"
sha256sum -c "$archive.sha256"
mkdir runtime
tar -xzf "$archive" -C runtime
test -f runtime/app/main.py
test -f runtime/requirements.txt
test -f runtime/alembic.ini
test -d runtime/app/db/migrations
test -d runtime/.packages/fastapi
test -d runtime/.packages/uvicorn
test -d runtime/.packages/asyncpg
printf '%s\n' "$2" > runtime/TRANSFER_COMPLETE
mkdir previous

# 교체 도중 실패하면 복구합니다. 루트의 .env와 데이터 디렉터리는 보존합니다.
installed=""
saved=""
restore() {
  result=$?
  trap - 0 HUP INT TERM
  set +e
  for entry in $installed; do
    mv "$destination/$entry" "$transfer/runtime/$entry"
  done
  for entry in $saved; do
    mv "$transfer/previous/$entry" "$destination/$entry"
  done
  exit "$result"
}
trap restore 0
trap 'exit 1' HUP INT TERM
for entry in app .packages requirements.txt alembic.ini TRANSFER_COMPLETE; do
  if [ -e "$destination/$entry" ] || [ -L "$destination/$entry" ]; then
    mv "$destination/$entry" "$transfer/previous/$entry"
    saved="$entry $saved"
  fi
  mv "$transfer/runtime/$entry" "$destination/$entry"
  installed="$entry $installed"
done
trap - 0 HUP INT TERM
printf 'Runtime files ready: %s\n' "$destination"
