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

> **데이터 연결 방식**  
> Flask 앱은 `supabase-py` SDK를 통해 **Supabase Data API**를 사용합니다.

---

## 주요 기능

| 영역 | 기능 |
|---|---|
| 학습 기록 | 날짜·과목·공부 시간·메모를 추가, 수정, 삭제하고 과목 또는 메모를 검색 |
| 학습 상태 | 기록별로 `진행 중` 또는 `공부 완료` 상태를 저장하고 목록과 대시보드에서 확인 |
| 대시보드 | 오늘의 공부 시간, 하루 목표 진행률, 이번 주 요약과 최근 기록 확인 |
| 주간 리포트 | 월요일부터 일요일까지 날짜별 학습 시간, 주간 합계·평균·목표 달성률 비교 |
| 목표와 설정 | 표시 이름, 하루·주간 공부 목표, 브라우저 공부 알림 설정 |
| 계정 보안 | 현재 비밀번호 확인 후 비밀번호 변경, 가입 이메일과 현재 비밀번호 재입력 후 회원탈퇴 |
| 공부 친구 | 7일 동안 유효한 초대 링크 생성, 초대 수락·거절·취소 및 친구 연결 |
| 선택 공유 | 공부 기록마다 공유할 친구를 직접 선택하고, 공유 기록 화면에서 내가 받은 기록 확인 |
| 알림 | 친구 연결 알림과 브라우저가 열려 있을 때 표시하는 공부 알림 |

친구로 연결되는 것만으로 학습 기록이 공개되지는 않습니다. 각 기록에서 공유할 친구를 직접 선택해야 해당 친구에게 표시됩니다.

---

## 기술 구성

- **서버:** Python 3.12, Flask
- **화면:** Jinja 템플릿, CSS, 브라우저 JavaScript
- **데이터:** Supabase Data API (`supabase-py`)
- **배포 진입점:** Vercel Python Function (`api/index.py`)

```text
브라우저
  └─ Flask 화면과 정적 파일
       └─ Flask 앱 (app.py)
            └─ supabase-py → Supabase Data API
                 └─ 앱 전용 ongyeol 스키마
```

회원가입과 로그인은 Supabase Auth가 아니라 Flask 앱이 `ongyeol.users` 테이블을 이용해 처리합니다. 비밀번호는 해시로 저장됩니다.

---

## 시작하기

### 준비물

- Python 3.12 권장 (`.python-version` 기준)
- 사용할 Supabase 프로젝트
- Windows PowerShell 또는 macOS/Linux 터미널

### 1. 가상 환경과 의존성 설치

프로젝트 루트에서 실행합니다.

**Windows PowerShell**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install Flask Flask-WTF python-dotenv supabase
```

**macOS / Linux**

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install Flask Flask-WTF python-dotenv supabase
```

### 2. 로컬 환경 파일 준비

예시 파일을 루트의 `.env`로 복사합니다. 이미 `.env`가 있다면 덮어쓰지 말고 필요한 항목만 보완하세요.

**Windows PowerShell**

```powershell
if (-not (Test-Path .\.env)) { Copy-Item .\supabase\env.example .\.env }
```

**macOS / Linux**

```bash
[ -f .env ] || cp supabase/env.example .env
```

`.env`에서 다음 항목을 본인의 Supabase 프로젝트 값으로 바꿉니다.

```dotenv
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_SECRET_KEY=<서버용 Secret key>
SUPABASE_SCHEMA=ongyeol
```

기존 `service_role` 키를 사용하는 경우 `SUPABASE_SECRET_KEY` 대신 `SUPABASE_SERVICE_ROLE_KEY`를 지정합니다. 둘 중 하나만 사용하세요. 로컬 Flask 세션 키는 지정하지 않으면 `instance/flask_secret_key`에 생성·저장됩니다.

### 3. 앱 실행

```powershell
python app.py
```

브라우저에서 <http://127.0.0.1:5000>을 엽니다. 이 명령은 로컬 개발 서버를 실행합니다. Vercel 배포 환경은 별도로 설정해야 합니다.

---

## Supabase 프로젝트 준비

온결은 기존 Supabase 프로젝트 안에 앱 전용 **`ongyeol` 스키마**를 사용합니다. 초기화 SQL은 기존 `public` 스키마의 다른 실습 테이블을 대상으로 하지 않습니다.

1. Supabase Dashboard에서 사용할 프로젝트를 엽니다.
2. **SQL Editor**에서 [`supabase/schema.sql`](supabase/schema.sql) 전체를 실행합니다.
3. **Project Settings → API / Data API → Exposed schemas**에 `ongyeol`을 추가합니다. 이미 등록된 `public` 등 기존 스키마는 필요한 경우 그대로 둡니다.
4. 앱의 `SUPABASE_SCHEMA`는 `ongyeol`로 둡니다. 코드의 기본값도 `ongyeol`입니다.

초기화 SQL은 앱 실행이나 Vercel 배포 중 자동으로 실행되지 않습니다. Supabase SQL Editor에서 직접 적용해야 합니다. 파일에는 앱 테이블, 권한·RLS 설정과 친구 초대 응답을 처리하는 RPC 함수가 포함되어 있습니다.

| 테이블 | 용도 |
|---|---|
| `ongyeol.users` | 앱 계정, 비밀번호 해시, 프로필, 목표와 알림 설정 |
| `ongyeol.study_records` | 날짜별 학습 내용, 공부 시간과 메모 |
| `ongyeol.friend_invites` | 초대 토큰 해시, 상태와 만료 시각 |
| `ongyeol.friendships` | 수락된 공부 친구 관계 |
| `ongyeol.app_notifications` | 친구 연결 관련 앱 알림 |
| `ongyeol.study_record_shares` | 기록 소유자와 선택된 공유 친구의 연결 |

---

## 환경 변수

| 변수 | 필수 여부 | 값과 용도 |
|---|---|---|
| `SUPABASE_URL` | 필수 | Supabase Dashboard의 **Project URL**. `https://<project-ref>.supabase.co` 형식이며 `/rest/v1/`은 붙이지 않습니다. |
| `SUPABASE_SECRET_KEY` | 필수 중 하나 | 서버에서만 보관하는 Supabase Secret key입니다. |
| `SUPABASE_SERVICE_ROLE_KEY` | 대체 변수 | 기존 `service_role` 키를 쓸 때 지정합니다. 위 키와 둘 다 설정하지 말고 하나만 사용합니다. |
| `SUPABASE_SCHEMA` | 선택 | 앱 스키마 이름. 기본값은 `ongyeol`입니다. |
| `FLASK_SECRET_KEY` | 배포 필수 | Flask 세션과 CSRF 보호용 별도 비밀 키입니다. 기존 `SESSION_SECRET`도 호환됩니다. |

`FLASK_SECRET_KEY`는 Supabase에서 복사하는 값이 아닙니다. 새 값을 만들려면 로컬 터미널에서 실행합니다.

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Vercel에서는 **Settings → Environment Variables**에 서버 환경 변수로 등록합니다. 사용할 배포 환경(Production, 필요하면 Preview)을 선택한 뒤 재배포해야 합니다. 로컬 `.env`와 비밀 키는 코드, 브라우저, Git 저장소, 채팅이나 스크린샷에 공개하지 마세요.

---

## 테스트와 사용 점검

프로젝트 루트에서 단위 테스트를 실행합니다.

```powershell
python -m unittest discover -s tests -v
```

테스트는 실제 Supabase 프로젝트에 접속하지 않고 입력 검증, Data API 설정, 주간 합계 등의 로직을 점검하도록 작성되어 있습니다. 실제 Supabase 스키마 적용과 브라우저 동작은 별도로 확인해야 합니다.

5일 사용 점검 예시:

1. **1일 차:** 계정을 만들고 첫 공부 기록을 저장합니다.
2. **2일 차:** 다시 접속해 기록이 남아 있는지 확인하고 새 기록을 추가합니다.
3. **3일 차:** 기록을 수정하거나 삭제하고 목록과 합계에 반영되는지 확인합니다.
4. **4일 차:** 날짜별 시간, 하루 목표와 알림 설정을 확인합니다.
5. **5일 차:** 주간 합계와 목표 달성률을 확인하고 사용 결과를 정리합니다.

---

## 프로젝트 구조

```text
.
├── api/
│   └── index.py           # Vercel Python 함수 진입점
├── static/
│   ├── app.css            # 앱 스타일
│   ├── layout.css         # 레이아웃과 반응형 스타일
│   ├── app.js             # 메뉴·알림·초대 링크 동작
│   └── favicon.svg
├── templates/             # Flask/Jinja 화면
├── app.py                 # Flask 앱과 라우트
├── feature_routes.py      # 계정 보안·상태·선택 공유 라우트
└── README.md
```

---

## 보안과 데이터 안내

- Supabase Secret key 또는 `service_role` 키는 **서버 전용**입니다. 브라우저 JavaScript나 템플릿에 전달하지 마세요.
- 서버 전용 키는 강한 권한을 가지므로 환경 변수에만 보관하세요. 앱은 사용자별 소유권 확인과 `user_id` 필터를 통해 계정·기록을 처리합니다.
- 앱은 CSRF 보호, 비밀번호 해시, Flask 서명 세션을 사용합니다. 배포 환경에는 반드시 별도의 강한 `FLASK_SECRET_KEY`를 설정하세요.
- 비밀번호 변경은 이메일 인증을 보내지 않습니다. 로그인한 사용자가 현재 비밀번호를 확인한 뒤 새 비밀번호를 설정합니다. 비밀번호를 잊어버렸을 때의 재설정 기능은 포함되지 않습니다.
- 회원탈퇴에는 가입 이메일과 현재 비밀번호를 모두 입력해야 합니다. 실제 데이터 삭제 범위는 Supabase 외래 키의 `ON DELETE CASCADE` 설정에도 의존하므로 스키마를 확인하세요.
- 친구 연결은 학습 기록 공유를 뜻하지 않습니다. 기록 공유는 소유자가 각 기록에서 친구를 직접 선택해야 합니다.
- 공유 기록 메뉴에는 친구가 나와 공유한 기록이 표시됩니다. 친구별 공유 해제는 해당 기록의 공유 설정에서 체크를 해제해 저장합니다.
- 브라우저 공부 알림은 브라우저 알림 API와 사용자의 권한이 필요합니다. 페이지가 열려 있을 때 동작하며, 푸시·이메일·SMS 또는 백그라운드 알림은 제공하지 않습니다.
- `.env`, `instance/`, `.venv/`, `myenv/`, 실제 키 값은 Git에 커밋하지 마세요. `.gitignore`는 이미 Git이 추적 중인 파일을 자동으로 추적 해제하지 않으므로 push 전에 저장소 상태를 확인하세요.
- `instance/ongyeol.sqlite3`의 기존 데이터는 Supabase로 자동 이전되지 않습니다. 필요한 기록은 먼저 백업하고 별도 마이그레이션을 계획하세요.

## 문제 해결

### `permission denied for schema ongyeol`

1. 오류가 난 앱과 같은 Supabase 프로젝트에서 앱 스키마에 필요한 권한을 설정했는지 확인합니다.
2. **Exposed schemas**에 `ongyeol`이 포함되어 있는지 확인합니다.
3. 앱이 `SUPABASE_SCHEMA=ongyeol`과 유효한 서버용 API 키를 사용 중인지 확인합니다.
4. RLS를 끄거나 `anon` 역할에 모든 권한을 부여하는 방식으로 해결하지 마세요.

### `ImportError: cannot import name 'create_client' from 'supabase'`

앱을 실행하는 Python 환경에서 Supabase SDK를 설치합니다.

```powershell
python -m pip install supabase
python -c "from supabase import create_client; print('Supabase SDK import OK')"
```

### Flask에서 500 오류가 발생함

실행 터미널의 traceback에서 첫 번째 앱 코드 오류와 Supabase API 응답을 확인하세요. 환경 변수, 스키마 노출·권한 문제와 CSS 레이아웃 문제는 서로 다른 원인입니다. 오류 로그를 공유할 때는 API 키, 비밀번호, `.env` 전체 내용을 가리세요.
