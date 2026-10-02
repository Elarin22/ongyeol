<div align="center">
  <p><strong>STUDY JOURNAL</strong></p>
  <h1>온결</h1>
  <p><strong>매일의 작은 집중을 기록하고, 나만의 학습 흐름을 돌아보는 학습 저널</strong></p>
  <p>하루씩 쌓이는 공부 시간을 살펴보고, 나에게 맞는 목표를 꾸준히 이어가 보세요.</p>
</div>

---

## 프로젝트 소개

온결은 공부 습관을 만들고 싶은 학생을 위한 학습 기록 웹앱입니다. 공부한 시간과 내용을 날짜별로 남기고, 하루 목표와 주간 학습 결과를 확인할 수 있습니다.

**완성 기준:** 5일 동안 실제로 공부 기록을 남기고 주간 학습 결과를 확인합니다.

> Flask 앱은 `supabase-py` SDK를 통해 **Supabase Data API**를 사용합니다.

## 주요 기능

| 영역 | 기능 |
|---|---|
| 학습 기록 | 날짜·과목·공부 시간·메모 추가, 수정, 삭제 및 검색 |
| 학습 상태 | 각 기록에 `진행 중` 또는 `공부 완료` 표시 |
| 대시보드·리포트 | 오늘과 이번 주 공부 시간, 날짜별 합계, 목표 달성률 확인 |
| 계정 보안 | 현재 비밀번호 확인 후 비밀번호 변경, 이메일과 현재 비밀번호 확인 후 회원탈퇴 |
| 공부 친구 | 초대 링크 생성·수락·거절·취소, 친구 목록과 친구 삭제 |
| 선택 공유 | 공부 기록을 선택한 친구와 공유, 받은 기록과 내가 공유한 기록 확인 및 공유 해제 |
| 알림·설정 | 앱 알림, 표시 이름, 학습 목표 및 브라우저 알림 설정 |

공부 친구가 되어도 기록은 기본 비공개입니다. 각 기록에서 공유할 친구를 직접 선택합니다. 친구 연결을 삭제하면 서로 공유했던 기록도 제거되어 과거 공유 권한이 나중에 되살아나지 않습니다.

## 기술 구성

- Python 3.12, Flask, Jinja, CSS, 브라우저 JavaScript
- 데이터: Supabase Data API (`supabase-py`)
- 배포: Vercel Python Function (`api/index.py`)

회원가입 및 로그인은 Flask 앱의 `ongyeol.users` 테이블로 처리합니다. 비밀번호는 해시로 저장합니다.

## 로컬 실행

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install Flask Flask-WTF python-dotenv supabase
```

프로젝트 루트의 `.env`에 다음을 설정하세요. Supabase에서 Project URL과 서버용 Secret key를 가져오고, 실제 키는 채팅이나 Git에 공개하지 마세요.

```dotenv
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_SECRET_KEY=<서버용 Secret key>
SUPABASE_SCHEMA=ongyeol
```

기존 `service_role` 키를 사용하는 경우 `SUPABASE_SERVICE_ROLE_KEY`를 대신 지정합니다. Flask 비밀 키로 `FLASK_SECRET_KEY`를 설정하거나, 로컬 기본값으로 `instance/flask_secret_key`를 사용합니다.

```powershell
python app.py
```

브라우저에서 <http://127.0.0.1:5000>을 엽니다.

## Supabase 데이터베이스 설정

앱은 기존 Supabase 프로젝트 내 별도의 `ongyeol` 스키마를 대상으로 합니다. 기존 `public` 테이블은 변경하지 마세요.

선택 공유 기능을 사용하려면 기존 `ongyeol.users`, `ongyeol.study_records`, `ongyeol.friendships` 테이블이 준비되어 있어야 합니다. 이후 프로젝트 루트의 [`study_record_shares.sql`](study_record_shares.sql)을 Supabase Dashboard의 **SQL Editor**에서 실행합니다. 이 마이그레이션은 `ongyeol.study_record_shares`와 기록 소유자 검증 트리거를 추가하고, 서버 역할에만 접근 권한을 줍니다. 기반 테이블을 다시 만들거나 기존 테이블을 지울 필요는 없습니다.

**Project Settings → API / Data API → Exposed schemas**에 `ongyeol`이 포함되어 있는지 확인합니다. 이 마이그레이션은 앱 실행 또는 Vercel 배포 때 자동 실행되지 않습니다. Secret/service_role 키는 서버 환경에서만 사용합니다.

## 배포 환경 변수

Vercel의 **Settings → Environment Variables**에 다음을 등록하고 재배포합니다.

| 이름 | 값 |
|---|---|
| `SUPABASE_URL` | Supabase Project URL (`/rest/v1/` 제외) |
| `SUPABASE_SECRET_KEY` 또는 `SUPABASE_SERVICE_ROLE_KEY` | 서버에서만 사용할 키 중 하나 |
| `FLASK_SECRET_KEY` | Flask 세션·CSRF용 별도 비밀 키 (`SESSION_SECRET`도 호환) |
| `SUPABASE_SCHEMA` | 선택 사항, `ongyeol` (기본값) |

Flask 키 생성 예:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

API 키, 실제 `.env`, `instance/`, 가상환경은 저장소에 올리지 마세요.

## 기능 확인 순서

1. Vercel 또는 로컬 앱에서 로그인 후 **함께 응원해요 → 공부 친구**로 이동해 등록된 친구와 `친구 삭제`를 확인합니다.
2. **공부 기록**에서 기록 옆 공유 아이콘을 눌러 친구를 직접 선택하고 저장합니다.
3. **공유 기록 → 내가 공유한 기록**에서 기록과 받는 친구 이름을 확인하고, 공유 해제 또는 친구 삭제 뒤 더 이상 공유되지 않는지 확인합니다.

기본 회귀 테스트는 프로젝트 루트에서 실행합니다.

```powershell
python -m unittest discover -s tests -v
```

## 프로젝트 구조

```text
.
├── api/index.py                 # Vercel 진입점
├── static/                      # CSS와 브라우저 JavaScript
├── templates/                   # Flask/Jinja 화면
├── app.py                       # Flask 앱과 핵심 라우트
├── feature_routes.py            # 계정 보안, 상태 및 친구/공유 기능
├── study_record_shares.sql      # 친구별 기록 공유 테이블 마이그레이션
└── README.md
```

## 보안 및 데이터 유의사항

- 친구 관계는 학습 기록 공개를 뜻하지 않습니다. 기록 소유자가 친구를 지정해야 공유됩니다.
- `내가 공유한 기록`에서 친구별로 공유를 해제할 수 있고, 친구를 삭제하면 양방향 공유 내역도 취소됩니다.
- 공유할 때 기록에 포함된 과목, 날짜, 시간, 메모가 선택한 친구에게 표시될 수 있습니다.
- Supabase Secret/service_role 키는 권한이 강한 서버 전용 비밀입니다. 브라우저 코드, Git, 스크린샷에 공개하지 마세요.
- `.env`, `instance/`, `.venv/`, `myenv/` 등 로컬 파일은 커밋하지 마세요. Git에서 이미 추적 중인 파일은 `.gitignore`만으로 제외되지 않습니다.
- 비밀번호 변경은 현재 비밀번호 확인 방식이며, 이메일 발송 및 분실 비밀번호 재설정 기능은 포함하지 않습니다.
- 회원탈퇴 시 가입 이메일과 현재 비밀번호를 확인합니다. 관련 데이터의 삭제 범위는 Supabase 외래 키 설정도 함께 확인해야 합니다.
- SQLite 데이터가 남아 있더라도 Supabase로 자동 이전되지 않습니다.

## 문제 해결

- **`permission denied for schema ongyeol`**: `ongyeol` 스키마 존재, API Exposed schemas 설정 및 해당 서버 역할의 권한을 확인합니다. RLS를 무작정 끄거나 `anon`에 전체 권한을 부여하지 마세요.
- **`ImportError: cannot import name 'create_client' from 'supabase'`**: 앱 실행 가상환경에서 `python -m pip install supabase`를 실행하고 같은 Python 환경인지 확인합니다.
- **공유 화면에서 500 오류**: Supabase SQL Editor에서 `study_record_shares.sql`을 실행했는지, `ongyeol.study_records`의 `user_id`와 기반 테이블이 맞는지 확인합니다.
- **기타 500 오류**: Flask 터미널 또는 Vercel Runtime Logs의 실제 traceback을 확인합니다. 로그를 공유할 때 키와 비밀번호를 가리세요.
