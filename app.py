from __future__ import annotations

import hashlib
import os
import re
import secrets
from datetime import date, datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urljoin, urlparse

from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_wtf.csrf import CSRFProtect
from supabase import create_client
from werkzeug.security import check_password_hash, generate_password_hash


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=BASE_DIR / ".env", override=False)
INSTANCE_DIR = BASE_DIR / "instance"


def load_secret_key() -> str:
    """Use an explicit deployment key and a persistent local key in development."""
    configured_key = os.environ.get("FLASK_SECRET_KEY") or os.environ.get("SESSION_SECRET")
    if configured_key:
        return configured_key
    if os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV"):
        raise RuntimeError(
            "FLASK_SECRET_KEY (or SESSION_SECRET) must be set in the Vercel project environment variables."
        )

    key_path = INSTANCE_DIR / "flask_secret_key"
    try:
        if key_path.is_file():
            saved_key = key_path.read_text(encoding="utf-8").strip()
            if saved_key:
                return saved_key
        INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
        new_key = secrets.token_hex(32)
        key_path.write_text(new_key, encoding="utf-8")
        try:
            key_path.chmod(0o600)
        except OSError:
            pass
        return new_key
    except OSError:
        return secrets.token_hex(32)


def _resource_path(*parts: str) -> Path:
    """Locate source resources in a checkout or in the Vercel function bundle."""
    direct_path = BASE_DIR.joinpath(*parts)
    if direct_path.exists():
        return direct_path
    bundled_path = BASE_DIR / "api" / Path(*parts)
    if bundled_path.exists():
        return bundled_path
    return direct_path


def _is_vercel_runtime() -> bool:
    return bool(os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV"))


app = Flask(__name__, template_folder=str(_resource_path("templates")))
app.static_folder = str(_resource_path("static"))
app.config.update(
    SECRET_KEY=load_secret_key(),
    SUPABASE_URL=os.environ.get("SUPABASE_URL", "").strip(),
    SUPABASE_SCHEMA=os.environ.get("SUPABASE_SCHEMA", "ongyeol").strip() or "ongyeol",
    # Prefer a server-side Secret key; keep compatibility with legacy service_role keys.
    SUPABASE_SECRET_KEY=os.environ.get("SUPABASE_SECRET_KEY", "").strip(),
    SUPABASE_SERVICE_ROLE_KEY=os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip(),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=_is_vercel_runtime() or os.environ.get("FLASK_COOKIE_SECURE") == "1",
    PERMANENT_SESSION_LIFETIME=timedelta(days=14),
    WTF_CSRF_TIME_LIMIT=3600,
)
CSRFProtect(app)

_SUPABASE_CLIENT: Any = None
_SUPABASE_CLIENT_CONFIG: tuple[str, str] | None = None


def connect_to_supabase_api() -> Any:
    """Create or reuse a server-side supabase-py Data API client."""
    global _SUPABASE_CLIENT, _SUPABASE_CLIENT_CONFIG

    project_url = str(app.config.get("SUPABASE_URL") or "").strip().rstrip("/")
    api_key = str(
        app.config.get("SUPABASE_SECRET_KEY")
        or app.config.get("SUPABASE_SERVICE_ROLE_KEY")
        or ""
    ).strip()
    if not project_url or not api_key:
        raise RuntimeError(
            "Set SUPABASE_URL and a server-side SUPABASE_SECRET_KEY "
            "(or legacy SUPABASE_SERVICE_ROLE_KEY) in the environment."
        )

    parsed_url = urlparse(project_url)
    if (
        parsed_url.scheme not in {"https", "http"}
        or not parsed_url.hostname
        or parsed_url.path not in {"", "/"}
        or parsed_url.query
        or parsed_url.fragment
    ):
        raise RuntimeError(
            "SUPABASE_URL must be the Supabase project URL, such as https://<project-ref>.supabase.co, "
            "not a REST endpoint such as /rest/v1/."
        )
    if parsed_url.scheme == "http" and parsed_url.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise RuntimeError("Use HTTPS for a non-local SUPABASE_URL.")

    config_key = (project_url, api_key)
    if _SUPABASE_CLIENT is None or _SUPABASE_CLIENT_CONFIG != config_key:
        _SUPABASE_CLIENT = create_client(project_url, api_key)
        _SUPABASE_CLIENT_CONFIG = config_key
    return _SUPABASE_CLIENT


def get_db() -> Any:
    """Return the Supabase Data API client scoped to the app's custom schema."""
    if "db" not in g:
        client = connect_to_supabase_api()
        schema_name = str(app.config.get("SUPABASE_SCHEMA") or "ongyeol").strip()
        g.db = client.schema(schema_name)
    return g.db


def _response_rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if data is None:
        return []
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    return []


def _first_response_row(response: Any) -> dict[str, Any] | None:
    rows = _response_rows(response)
    return rows[0] if rows else None


def create_user_account(email: str, display_name: str, password: str) -> int | None:
    """Create an account through Supabase Data API; return None for an existing email."""
    users = get_db().table("users")
    existing_user = _first_response_row(users.select("id").eq("email", email).limit(1).execute())
    if existing_user is not None:
        return None

    try:
        created_rows = _response_rows(
            users.insert(
                {
                    "email": email,
                    "display_name": display_name,
                    "password_hash": generate_password_hash(password),
                }
            )
            .select("id")
            .execute()
        )
    except Exception as insert_error:
        # A concurrent registration can claim this email after the availability check.
        try:
            existing_user = _first_response_row(
                users.select("id").eq("email", email).limit(1).execute()
            )
        except Exception:
            raise insert_error
        if existing_user is not None:
            return None
        raise insert_error

    if not created_rows:
        raise RuntimeError("Supabase did not return the new user ID.")
    return int(created_rows[0]["id"])


def _as_utc_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def utc_now() -> datetime:
    """Return an aware UTC timestamp for Supabase timestamp fields."""
    return datetime.now(timezone.utc).replace(microsecond=0)


def hash_invite_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def safe_redirect_target(target: str | None) -> str | None:
    if not target:
        return None
    base = urlparse(request.host_url)
    candidate = urlparse(urljoin(request.host_url, target))
    if candidate.scheme in {"http", "https"} and candidate.netloc == base.netloc:
        suffix = f"?{candidate.query}" if candidate.query else ""
        fragment = f"#{candidate.fragment}" if candidate.fragment else ""
        return candidate.path + suffix + fragment
    return None


def get_current_user() -> dict[str, Any] | None:
    user_id = session.get("user_id")
    if not user_id:
        return None
    if not getattr(g, "current_user_loaded", False):
        g.current_user = _first_response_row(
            get_db().table("users").select("*").eq("id", user_id).limit(1).execute()
        )
        g.current_user_loaded = True
    return g.current_user


def login_required(view: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(view)
    def wrapped_view(*args: Any, **kwargs: Any) -> Any:
        if get_current_user() is None:
            if request.endpoint == "open_invite" and request.view_args:
                session["pending_invite_token"] = request.view_args.get("token", "")
            else:
                next_path = request.full_path if request.query_string else request.path
                if next_path.startswith("/") and not next_path.startswith("//"):
                    session["next_after_login"] = next_path
            flash("계속하려면 먼저 로그인해 주세요.", "info")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped_view


def after_login_redirect() -> Any:
    pending_token = session.pop("pending_invite_token", None)
    next_path = safe_redirect_target(session.pop("next_after_login", None))
    if pending_token:
        return redirect(url_for("open_invite", token=pending_token))
    if next_path:
        return redirect(next_path)
    return redirect(url_for("dashboard"))


def build_week_summary(user_id: int, user: dict[str, Any], week_offset: int = 0) -> dict[str, Any]:
    today = date.today()
    monday = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    sunday = monday + timedelta(days=6)
    rows = _response_rows(
        get_db()
        .table("study_records")
        .select("study_date,duration_minutes")
        .eq("user_id", user_id)
        .gte("study_date", monday.isoformat())
        .lte("study_date", sunday.isoformat())
        .execute()
    )
    totals: dict[str, int] = {}
    for row in rows:
        stored_date = row["study_date"]
        date_key = stored_date.isoformat() if isinstance(stored_date, date) else str(stored_date)[:10]
        totals[date_key] = totals.get(date_key, 0) + int(row["duration_minutes"] or 0)
    total_minutes = sum(totals.values())
    weekly_goal = int(user["weekly_goal_minutes"])
    # The chart's goal line is labelled as the daily goal, so use that target.
    daily_goal_line = int(user["daily_goal_minutes"])
    chart_scale = max([daily_goal_line, 60, *totals.values()])

    weekdays = ("월", "화", "수", "목", "금", "토", "일")
    days = []
    for index in range(7):
        day = monday + timedelta(days=index)
        minutes = totals.get(day.isoformat(), 0)
        days.append(
            {
                "date": day.isoformat(),
                "date_label": day.strftime("%m/%d"),
                "weekday": weekdays[index],
                "minutes": minutes,
                "bar_percent": min(100, round(minutes / chart_scale * 100)),
                "is_today": day == today,
            }
        )
    best_day = max(days, key=lambda item: item["minutes"]) if total_minutes else None
    return {
        "days": days,
        "start": monday,
        "end": sunday,
        "week_title": f"{monday:%Y.%m.%d} – {sunday:%Y.%m.%d}",
        "total_minutes": total_minutes,
        "average_minutes": round(total_minutes / 7),
        "weekly_goal": weekly_goal,
        "progress_percent": min(100, round(total_minutes / weekly_goal * 100)) if weekly_goal else 0,
        "goal_reached": total_minutes >= weekly_goal,
        "daily_goal_line_percent": min(100, round(daily_goal_line / chart_scale * 100)),
        "best_day": best_day,
        "week_offset": week_offset,
        "is_current_week": week_offset == 0,
    }


@app.template_filter("duration")
def format_duration(value: Any) -> str:
    minutes = max(0, int(value or 0))
    hours, remainder = divmod(minutes, 60)
    if hours and remainder:
        return f"{hours}시간 {remainder}분"
    if hours:
        return f"{hours}시간"
    return f"{remainder}분"


@app.template_filter("date_label")
def format_date_label(value: Any) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y.%m.%d")
    if isinstance(value, date):
        return value.strftime("%Y.%m.%d")
    try:
        return date.fromisoformat(str(value)[:10]).strftime("%Y.%m.%d")
    except (TypeError, ValueError):
        return str(value or "")


@app.context_processor
def inject_shared_template_data() -> dict[str, Any]:
    user = get_current_user()
    unread_count = 0
    if user is not None:
        unread_count = len(
            _response_rows(
                get_db()
                .table("app_notifications")
                .select("id")
                .eq("user_id", user["id"])
                .is_("read_at", "null")
                .execute()
            )
        )
    return {"current_user": user, "unread_count": unread_count, "today_iso": date.today().isoformat()}


@app.get("/")
def index() -> Any:
    return redirect(url_for("dashboard" if get_current_user() is not None else "login"))


@app.route("/register", methods=["GET", "POST"])
def register() -> Any:
    if get_current_user() is not None:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        display_name = request.form.get("display_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not display_name or len(display_name) > 40:
            flash("이름은 1자 이상 40자 이하로 입력해 주세요.", "error")
        elif len(email) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            flash("올바른 이메일 주소를 입력해 주세요.", "error")
        elif len(password) < 8:
            flash("비밀번호는 8자 이상 입력해 주세요.", "error")
        else:
            created_user_id = create_user_account(email, display_name, password)
            if created_user_id is None:
                flash("이 이메일은 이미 가입되어 있어요. 로그인해 주세요.", "error")
            else:
                pending_token = session.get("pending_invite_token")
                next_path = session.get("next_after_login")
                session.clear()
                session.permanent = True
                session["user_id"] = created_user_id
                if pending_token:
                    session["pending_invite_token"] = pending_token
                if next_path:
                    session["next_after_login"] = next_path
                flash("온결에 오신 걸 환영해요. 첫 공부 기록을 남겨 보세요.", "success")
                return after_login_redirect()
    return render_template("auth.html", mode="register", page_title="회원가입")


@app.route("/login", methods=["GET", "POST"])
def login() -> Any:
    if get_current_user() is not None:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = _first_response_row(
            get_db().table("users").select("*").eq("email", email).limit(1).execute()
        )
        if user is None or not check_password_hash(user["password_hash"], password):
            flash("이메일 또는 비밀번호를 확인해 주세요.", "error")
        else:
            pending_token = session.get("pending_invite_token")
            next_path = session.get("next_after_login")
            session.clear()
            session.permanent = True
            session["user_id"] = user["id"]
            if pending_token:
                session["pending_invite_token"] = pending_token
            if next_path:
                session["next_after_login"] = next_path
            flash("다시 만나 반가워요.", "success")
            return after_login_redirect()
    return render_template("auth.html", mode="login", page_title="로그인")


@app.post("/logout")
@login_required
def logout() -> Any:
    session.clear()
    flash("로그아웃했어요.", "info")
    return redirect(url_for("login"))


@app.get("/dashboard")
@login_required
def dashboard() -> Any:
    user = get_current_user()
    assert user is not None
    summary = build_week_summary(user["id"], user)
    today_total = next((day["minutes"] for day in summary["days"] if day["is_today"]), 0)
    daily_goal = int(user["daily_goal_minutes"])
    recent_records = _response_rows(
        get_db()
        .table("study_records")
        .select("*")
        .eq("user_id", user["id"])
        .order("study_date", desc=True)
        .order("created_at", desc=True)
        .limit(5)
        .execute()
    )
    return render_template(
        "dashboard.html", page_title="오늘의 기록",
        page_description="하루씩 쌓아가는 나만의 학습 흐름이에요.", summary=summary,
        today_total=today_total,
        today_percent=min(100, round(today_total / daily_goal * 100)) if daily_goal else 0,
        recent_records=recent_records,
    )


def read_record_form() -> tuple[dict[str, str], str | None]:
    values = {
        "study_date": request.form.get("study_date", "").strip(),
        "subject": request.form.get("subject", "").strip(),
        "duration_minutes": request.form.get("duration_minutes", "").strip(),
        "memo": request.form.get("memo", "").strip(),
    }
    try:
        date.fromisoformat(values["study_date"])
    except ValueError:
        return values, "학습 날짜를 올바르게 선택해 주세요."
    if not values["subject"] or len(values["subject"]) > 80:
        return values, "학습 내용은 1자 이상 80자 이하로 입력해 주세요."
    try:
        duration = int(values["duration_minutes"])
    except ValueError:
        return values, "공부 시간을 분 단위 숫자로 입력해 주세요."
    if not 1 <= duration <= 1440:
        return values, "공부 시간은 1분 이상 24시간 이하로 입력해 주세요."
    if len(values["memo"]) > 500:
        return values, "메모는 500자 이하로 입력해 주세요."
    return values, None


def record_values(record: dict[str, Any] | None = None) -> dict[str, str]:
    if record is None:
        return {"study_date": date.today().isoformat(), "subject": "", "duration_minutes": "60", "memo": ""}
    study_date = record["study_date"]
    if isinstance(study_date, date):
        study_date = study_date.isoformat()
    return {
        "study_date": str(study_date), "subject": record["subject"],
        "duration_minutes": str(record["duration_minutes"]), "memo": record["memo"],
    }


@app.get("/records")
@login_required
def records() -> Any:
    user = get_current_user()
    assert user is not None
    search = request.args.get("q", "").strip()[:100]
    rows = _response_rows(
        get_db()
        .table("study_records")
        .select("*")
        .eq("user_id", user["id"])
        .order("study_date", desc=True)
        .order("created_at", desc=True)
        .execute()
    )
    if search:
        search_key = search.casefold()
        rows = [
            row for row in rows
            if search_key in str(row.get("subject", "")).casefold()
            or search_key in str(row.get("memo", "")).casefold()
        ]
    return render_template(
        "records.html", page_title="공부 기록",
        page_description="배운 시간과 작은 생각들을 모아 보세요.", records=rows,
        search=search, record_count=len(rows),
        total_minutes=sum(int(row["duration_minutes"]) for row in rows),
    )


@app.route("/records/new", methods=["GET", "POST"])
@login_required
def new_record() -> Any:
    user = get_current_user()
    assert user is not None
    if request.method == "POST":
        values, error = read_record_form()
        if error:
            flash(error, "error")
            return render_template("record_form.html", page_title="기록 추가", record=None, values=values), 400
        get_db().table("study_records").insert(
            {
                "user_id": user["id"],
                "study_date": date.fromisoformat(values["study_date"]).isoformat(),
                "subject": values["subject"],
                "duration_minutes": int(values["duration_minutes"]),
                "memo": values["memo"],
            }
        ).execute()
        flash("공부 기록을 저장했어요.", "success")
        return redirect(url_for("records"))
    initial = record_values()
    try:
        initial["study_date"] = date.fromisoformat(request.args.get("date", "")).isoformat()
    except ValueError:
        pass
    return render_template("record_form.html", page_title="기록 추가", record=None, values=initial)


@app.route("/records/<int:record_id>/edit", methods=["GET", "POST"])
@login_required
def edit_record(record_id: int) -> Any:
    user = get_current_user()
    assert user is not None
    record = _first_response_row(
        get_db()
        .table("study_records")
        .select("*")
        .eq("id", record_id)
        .eq("user_id", user["id"])
        .limit(1)
        .execute()
    )
    if record is None:
        abort(404)
    if request.method == "POST":
        values, error = read_record_form()
        if error:
            flash(error, "error")
            return render_template("record_form.html", page_title="기록 수정", record=record, values=values), 400
        updated_rows = _response_rows(
            get_db()
            .table("study_records")
            .update(
                {
                    "study_date": date.fromisoformat(values["study_date"]).isoformat(),
                    "subject": values["subject"],
                    "duration_minutes": int(values["duration_minutes"]),
                    "memo": values["memo"],
                    "updated_at": utc_now().isoformat(),
                }
            )
            .eq("id", record_id)
            .eq("user_id", user["id"])
            .select("id")
            .execute()
        )
        if not updated_rows:
            abort(404)
        flash("공부 기록을 수정했어요.", "success")
        return redirect(url_for("records"))
    return render_template("record_form.html", page_title="기록 수정", record=record, values=record_values(record))


@app.post("/records/<int:record_id>/delete")
@login_required
def delete_record(record_id: int) -> Any:
    user = get_current_user()
    assert user is not None
    deleted_rows = _response_rows(
        get_db()
        .table("study_records")
        .delete()
        .eq("id", record_id)
        .eq("user_id", user["id"])
        .select("id")
        .execute()
    )
    if not deleted_rows:
        abort(404)
    flash("공부 기록을 삭제했어요.", "success")
    return redirect(url_for("records"))


@app.get("/report")
@login_required
def report() -> Any:
    user = get_current_user()
    assert user is not None
    try:
        week_offset = int(request.args.get("week", "0"))
    except ValueError:
        week_offset = 0
    summary = build_week_summary(user["id"], user, max(-104, min(0, week_offset)))
    return render_template(
        "report.html", page_title="주간 리포트",
        page_description="이번 주의 공부 흐름을 천천히 돌아봐요.", summary=summary,
    )


@app.get("/friends")
@login_required
def friends() -> Any:
    user = get_current_user()
    assert user is not None
    connection = get_db()
    user_id = int(user["id"])
    friendship_rows = _response_rows(
        connection.table("friendships")
        .select("user_a,user_b,created_at")
        .or_(f"user_a.eq.{user_id},user_b.eq.{user_id}")
        .execute()
    )
    friend_ids = sorted(
        {
            int(row["user_b"] if int(row["user_a"]) == user_id else row["user_a"])
            for row in friendship_rows
        }
    )
    if friend_ids:
        friend_users = _response_rows(
            connection.table("users").select("id,display_name").in_("id", friend_ids).execute()
        )
    else:
        friend_users = []
    friends_by_id = {int(row["id"]): row for row in friend_users}
    friend_rows = []
    for friendship in friendship_rows:
        friend_id = int(
            friendship["user_b"] if int(friendship["user_a"]) == user_id else friendship["user_a"]
        )
        friend = friends_by_id.get(friend_id)
        if friend is not None:
            friend_rows.append(
                {
                    "id": friend_id,
                    "display_name": friend["display_name"],
                    "friends_since": friendship.get("created_at"),
                }
            )
    friend_rows.sort(key=lambda row: str(row["display_name"]).casefold())

    outgoing_invites = _response_rows(
        connection.table("friend_invites")
        .select("id,status,expires_at,created_at")
        .eq("inviter_id", user["id"])
        .order("created_at", desc=True)
        .limit(12)
        .execute()
    )
    for invite in outgoing_invites:
        invite["expires_at"] = _as_utc_datetime(invite["expires_at"])

    invite_token = request.args.get("invite", "").strip()[:128]
    invite_preview = None
    invite_error = None
    if invite_token:
        invite_preview = _first_response_row(
            connection.table("friend_invites")
            .select("id,inviter_id,expires_at")
            .eq("token_hash", hash_invite_token(invite_token))
            .eq("status", "pending")
            .gt("expires_at", utc_now().isoformat())
            .limit(1)
            .execute()
        )
        if invite_preview is None:
            invite_error = "초대 링크가 만료되었거나 이미 처리되었어요."
        else:
            invite_preview["expires_at"] = _as_utc_datetime(invite_preview["expires_at"])
            inviter = _first_response_row(
                connection.table("users")
                .select("display_name")
                .eq("id", invite_preview["inviter_id"])
                .limit(1)
                .execute()
            )
            invite_preview["inviter_name"] = inviter["display_name"] if inviter else "알 수 없는 사용자"
            if int(invite_preview["inviter_id"]) == user_id:
                invite_preview = None
                invite_error = "자신이 만든 초대 링크는 수락할 수 없어요."
    return render_template(
        "friends.html", page_title="공부 친구",
        page_description="연결은 함께, 학습 기록은 각자의 공간에.",
        friends=friend_rows, outgoing_invites=outgoing_invites,
        invite_token=invite_token, invite_preview=invite_preview, invite_error=invite_error,
        latest_invite_url=session.pop("latest_invite_url", None), now_utc=utc_now(),
    )


@app.post("/friends/invites/new")
@login_required
def create_friend_invite() -> Any:
    user = get_current_user()
    assert user is not None
    token = secrets.token_urlsafe(32)
    now = utc_now()
    get_db().table("friend_invites").insert(
        {
            "inviter_id": user["id"],
            "token_hash": hash_invite_token(token),
            "status": "pending",
            "expires_at": (now + timedelta(days=7)).isoformat(),
        }
    ).execute()
    session["latest_invite_url"] = url_for("open_invite", token=token, _external=True)
    flash("친구 초대 링크를 만들었어요. 친구에게 공유해 보세요.", "success")
    return redirect(url_for("friends"))


@app.get("/invite/<token>")
@login_required
def open_invite(token: str) -> Any:
    if len(token) > 128:
        abort(404)
    return redirect(url_for("friends", invite=token))


@app.post("/friends/invites/<int:invite_id>/cancel")
@login_required
def cancel_friend_invite(invite_id: int) -> Any:
    user = get_current_user()
    assert user is not None
    changed_rows = _response_rows(
        get_db()
        .table("friend_invites")
        .update({"status": "cancelled", "updated_at": utc_now().isoformat()})
        .eq("id", invite_id)
        .eq("inviter_id", user["id"])
        .eq("status", "pending")
        .select("id")
        .execute()
    )
    flash(
        "친구 초대를 취소했어요." if changed_rows else "이미 처리되었거나 취소할 수 없는 초대예요.",
        "success" if changed_rows else "error",
    )
    return redirect(url_for("friends"))


@app.post("/friends/invites/respond")
@login_required
def respond_to_invite() -> Any:
    user = get_current_user()
    assert user is not None
    token = request.form.get("token", "").strip()
    action = request.form.get("action", "").strip()
    if action not in {"accept", "decline"} or not token or len(token) > 128:
        flash("초대 요청을 확인할 수 없어요.", "error")
        return redirect(url_for("friends"))

    result = _first_response_row(
        get_db()
        .rpc(
            "respond_to_friend_invite",
            {
                "p_token_hash": hash_invite_token(token),
                "p_user_id": int(user["id"]),
                "p_action": action,
            },
        )
        .execute()
    )
    if not result or not result.get("success"):
        reason = result.get("reason") if result else None
        if reason == "self_invite":
            flash("자신이 만든 초대 링크는 수락할 수 없어요.", "error")
        elif reason == "user_not_found":
            flash("사용자 정보를 확인할 수 없어요. 다시 로그인해 주세요.", "error")
        else:
            flash("초대 링크가 만료되었거나 이미 처리되었어요.", "error")
        return redirect(url_for("friends"))

    if action == "accept":
        flash(f"{result['inviter_name']}님과 공부 친구가 되었어요.", "success")
    else:
        flash("친구 초대를 거절했어요.", "info")
    return redirect(url_for("friends"))


@app.get("/notifications")
@login_required
def notifications() -> Any:
    user = get_current_user()
    assert user is not None
    rows = _response_rows(
        get_db()
        .table("app_notifications")
        .select("*")
        .eq("user_id", user["id"])
        .order("created_at", desc=True)
        .limit(100)
        .execute()
    )
    return render_template(
        "notifications.html", page_title="알림",
        page_description="친구 초대와 학습 소식을 확인해요.",
        notifications=rows, unread=sum(1 for row in rows if row.get("read_at") is None),
    )


@app.post("/notifications/<int:notification_id>/read")
@login_required
def mark_notification_read(notification_id: int) -> Any:
    user = get_current_user()
    assert user is not None
    get_db().table("app_notifications").update({"read_at": utc_now().isoformat()}).eq(
        "id", notification_id
    ).eq("user_id", user["id"]).is_("read_at", "null").execute()
    return redirect(url_for("notifications"))


@app.post("/notifications/read-all")
@login_required
def mark_all_notifications_read() -> Any:
    user = get_current_user()
    assert user is not None
    get_db().table("app_notifications").update({"read_at": utc_now().isoformat()}).eq(
        "user_id", user["id"]
    ).is_("read_at", "null").execute()
    flash("알림을 모두 읽음 처리했어요.", "success")
    return redirect(url_for("notifications"))


def settings_values(user: dict[str, Any]) -> dict[str, Any]:
    reminder_time = user["reminder_time"]
    if hasattr(reminder_time, "strftime"):
        reminder_time = reminder_time.strftime("%H:%M")
    else:
        reminder_time = str(reminder_time or "20:00").strip()[:5]
    return {
        "display_name": user["display_name"],
        "daily_goal_minutes": str(user["daily_goal_minutes"]),
        "weekly_goal_minutes": str(user["weekly_goal_minutes"]),
        "reminder_time": reminder_time,
        "reminder_enabled": bool(user["reminder_enabled"]),
    }


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings() -> Any:
    user = get_current_user()
    assert user is not None
    values = settings_values(user)
    if request.method == "POST":
        reminder_time = request.form.get("reminder_time", "").strip()
        if not reminder_time:
            reminder_time = "20:00"
        values = {
            "display_name": request.form.get("display_name", "").strip(),
            "daily_goal_minutes": request.form.get("daily_goal_minutes", "").strip(),
            "weekly_goal_minutes": request.form.get("weekly_goal_minutes", "").strip(),
            "reminder_time": reminder_time,
            "reminder_enabled": request.form.get("reminder_enabled") == "on",
        }
        error = None
        if not values["display_name"] or len(values["display_name"]) > 40:
            error = "표시 이름은 1자 이상 40자 이하로 입력해 주세요."
        try:
            daily_goal = int(values["daily_goal_minutes"])
            weekly_goal = int(values["weekly_goal_minutes"])
        except ValueError:
            daily_goal = weekly_goal = 0
            error = error or "하루와 주간 목표를 분 단위 숫자로 입력해 주세요."
        if error is None and not 1 <= daily_goal <= 1440:
            error = "하루 목표는 1분 이상 24시간 이하로 입력해 주세요."
        if error is None and not 1 <= weekly_goal <= 10080:
            error = "주간 목표는 1분 이상 168시간 이하로 입력해 주세요."
        if error is None and not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", values["reminder_time"]):
            error = "알림 시각을 올바르게 선택해 주세요."
        if error:
            flash(error, "error")
            return render_template(
                "settings.html", page_title="설정",
                page_description="나에게 맞는 이름과 학습 목표를 정해요.", values=values,
            ), 400
        get_db().table("users").update(
            {
                "display_name": values["display_name"],
                "daily_goal_minutes": daily_goal,
                "weekly_goal_minutes": weekly_goal,
                "reminder_time": values["reminder_time"],
                "reminder_enabled": values["reminder_enabled"],
            }
        ).eq("id", user["id"]).execute()
        flash("설정을 저장했어요.", "success")
        return redirect(url_for("settings"))
    return render_template(
        "settings.html", page_title="설정",
        page_description="나에게 맞는 이름과 학습 목표를 정해요.", values=values,
    )


@app.errorhandler(404)
def not_found(_error: Any) -> tuple[str, int]:
    return render_template("404.html", page_title="페이지를 찾을 수 없어요."), 404


if __name__ == "__main__":
    app.run(
        host="127.0.0.1", port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG") == "1",
    )
