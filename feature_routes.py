"""Account security, study status, and friend-selected sharing routes."""
from __future__ import annotations

from datetime import date
from typing import Any

from flask import abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from app import (
    _first_response_row,
    _response_rows,
    app,
    get_current_user,
    get_db,
    login_required,
    utc_now,
)


def _user_friend_ids(user_id: int) -> list[int]:
    rows = _response_rows(
        get_db().table("friendships")
        .select("user_a,user_b")
        .or_(f"user_a.eq.{user_id},user_b.eq.{user_id}")
        .execute()
    )
    return sorted({
        int(row["user_b"] if int(row["user_a"]) == user_id else row["user_a"])
        for row in rows
    })


def _record_form_values(record: dict[str, Any] | None = None) -> dict[str, str]:
    if record is None:
        return {
            "study_date": date.today().isoformat(),
            "subject": "",
            "duration_minutes": "60",
            "memo": "",
            "study_status": "completed",
        }
    stored_date = record.get("study_date", date.today().isoformat())
    return {
        "study_date": stored_date.isoformat() if isinstance(stored_date, date) else str(stored_date)[:10],
        "subject": str(record.get("subject", "")),
        "duration_minutes": str(record.get("duration_minutes", "60")),
        "memo": str(record.get("memo", "")),
        "study_status": str(record.get("study_status") or "completed"),
    }


def _read_feature_record_form() -> tuple[dict[str, str], str | None]:
    values = {
        "study_date": request.form.get("study_date", "").strip(),
        "subject": request.form.get("subject", "").strip(),
        "duration_minutes": request.form.get("duration_minutes", "").strip(),
        "memo": request.form.get("memo", "").strip(),
        "study_status": request.form.get("study_status", "completed").strip(),
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
    if values["study_status"] not in {"in_progress", "completed"}:
        return values, "공부 상태를 선택해 주세요."
    return values, None


def register_feature_routes(flask_app: Any = app) -> None:
    """Add feature endpoints once for local and Vercel entry points."""
    if "change_password" in flask_app.view_functions:
        return

    @login_required
    def change_password() -> Any:
        user = get_current_user()
        assert user is not None
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")
        if not check_password_hash(user["password_hash"], current_password):
            flash("현재 비밀번호가 올바르지 않아요.", "error")
        elif len(new_password) < 8:
            flash("새 비밀번호는 8자 이상이어야 해요.", "error")
        elif new_password != confirm_password:
            flash("새 비밀번호 확인이 일치하지 않아요.", "error")
        elif check_password_hash(user["password_hash"], new_password):
            flash("현재와 다른 비밀번호를 입력해 주세요.", "error")
        else:
            changed = _response_rows(
                get_db().table("users")
                .update({"password_hash": generate_password_hash(new_password)})
                .eq("id", user["id"])
                .select("id")
                .execute()
            )
            if not changed:
                abort(409)
            flash("비밀번호를 안전하게 변경했어요.", "success")
        return redirect(url_for("settings") + "#password-settings")

    @login_required
    def delete_account() -> Any:
        user = get_current_user()
        assert user is not None
        typed_email = request.form.get("confirm_email", "").strip().lower()
        current_password = request.form.get("current_password", "")
        if typed_email != str(user["email"]).strip().lower():
            flash("가입한 이메일 주소가 일치하지 않아요. 계정은 삭제되지 않았어요.", "error")
            return redirect(url_for("settings") + "#account-settings")
        if not check_password_hash(user["password_hash"], current_password):
            flash("현재 비밀번호가 올바르지 않아요. 계정은 삭제되지 않았어요.", "error")
            return redirect(url_for("settings") + "#account-settings")
        deleted = _response_rows(
            get_db().table("users").delete().eq("id", user["id"]).select("id").execute()
        )
        if not deleted:
            abort(409)
        session.clear()
        flash("회원탈퇴가 완료되었어요. 이용해 주셔서 감사합니다.", "success")
        return redirect(url_for("login"))

    @login_required
    def new_record_with_status() -> Any:
        user = get_current_user()
        assert user is not None
        if request.method == "POST":
            values, error = _read_feature_record_form()
            if error:
                flash(error, "error")
                return render_template(
                    "record_form.html", page_title="기록 추가", record=None, values=values
                ), 400
            get_db().table("study_records").insert({
                "user_id": user["id"],
                "study_date": date.fromisoformat(values["study_date"]).isoformat(),
                "subject": values["subject"],
                "duration_minutes": int(values["duration_minutes"]),
                "memo": values["memo"],
                "study_status": values["study_status"],
            }).execute()
            flash("공부 기록을 저장했어요.", "success")
            return redirect(url_for("records"))
        values = _record_form_values()
        try:
            values["study_date"] = date.fromisoformat(request.args.get("date", "")).isoformat()
        except ValueError:
            pass
        return render_template("record_form.html", page_title="기록 추가", record=None, values=values)

    @login_required
    def edit_record_with_status(record_id: int) -> Any:
        user = get_current_user()
        assert user is not None
        db = get_db()
        record = _first_response_row(
            db.table("study_records").select("*")
            .eq("id", record_id).eq("user_id", user["id"]).limit(1).execute()
        )
        if record is None:
            abort(404)
        if request.method == "POST":
            values, error = _read_feature_record_form()
            if error:
                flash(error, "error")
                return render_template(
                    "record_form.html", page_title="기록 수정", record=record, values=values
                ), 400
            changed = _response_rows(
                db.table("study_records").update({
                    "study_date": date.fromisoformat(values["study_date"]).isoformat(),
                    "subject": values["subject"],
                    "duration_minutes": int(values["duration_minutes"]),
                    "memo": values["memo"],
                    "study_status": values["study_status"],
                    "updated_at": utc_now().isoformat(),
                }).eq("id", record_id).eq("user_id", user["id"]).select("id").execute()
            )
            if not changed:
                abort(404)
            flash("공부 기록과 상태를 수정했어요.", "success")
            return redirect(url_for("records"))
        return render_template(
            "record_form.html", page_title="기록 수정", record=record,
            values=_record_form_values(record),
        )

    @login_required
    def update_record_status(record_id: int) -> Any:
        user = get_current_user()
        assert user is not None
        next_status = request.form.get("study_status", "").strip()
        if next_status not in {"in_progress", "completed"}:
            flash("공부 상태를 확인해 주세요.", "error")
            return redirect(url_for("records"))
        changed = _response_rows(
            get_db().table("study_records")
            .update({"study_status": next_status, "updated_at": utc_now().isoformat()})
            .eq("id", record_id).eq("user_id", user["id"]).select("id").execute()
        )
        if not changed:
            abort(404)
        flash("공부 상태를 변경했어요.", "success")
        return redirect(request.referrer or url_for("records"))

    @login_required
    def manage_record_shares(record_id: int) -> Any:
        user = get_current_user()
        assert user is not None
        db = get_db()
        record = _first_response_row(
            db.table("study_records").select("*")
            .eq("id", record_id).eq("user_id", user["id"]).limit(1).execute()
        )
        if record is None:
            abort(404)
        friend_ids = _user_friend_ids(int(user["id"]))
        friend_rows = _response_rows(
            db.table("users").select("id,display_name").in_("id", friend_ids).execute()
        ) if friend_ids else []
        friends_by_id = {int(friend["id"]): friend for friend in friend_rows}
        friend_rows = [friends_by_id[friend_id] for friend_id in friend_ids if friend_id in friends_by_id]

        if request.method == "POST":
            try:
                selected_ids = sorted({int(value) for value in request.form.getlist("friend_ids")})
            except ValueError:
                flash("선택한 친구 정보를 확인해 주세요.", "error")
                return redirect(url_for("manage_record_shares", record_id=record_id))
            if any(friend_id not in friend_ids for friend_id in selected_ids):
                flash("공부 친구로 연결된 사람만 기록을 공유할 수 있어요.", "error")
                return redirect(url_for("manage_record_shares", record_id=record_id))
            if selected_ids:
                db.table("study_record_shares").upsert(
                    [{"record_id": record_id, "owner_id": user["id"], "friend_id": friend_id}
                     for friend_id in selected_ids],
                    on_conflict="record_id,friend_id",
                ).execute()
                db.table("study_record_shares").delete().eq(
                    "record_id", record_id
                ).eq("owner_id", user["id"]).not_.in_("friend_id", selected_ids).execute()
            else:
                db.table("study_record_shares").delete().eq(
                    "record_id", record_id
                ).eq("owner_id", user["id"]).execute()
            flash("공유 대상을 저장했어요. 선택한 친구에게만 이 기록이 보여요.", "success")
            return redirect(url_for("records"))

        existing = _response_rows(
            db.table("study_record_shares").select("friend_id")
            .eq("record_id", record_id).eq("owner_id", user["id"]).execute()
        )
        selected_friend_ids = {int(row["friend_id"]) for row in existing}
        return render_template(
            "record_share.html", page_title="기록 공유", record=record,
            friends=friend_rows, selected_friend_ids=selected_friend_ids,
        )

    @login_required
    def shared_records() -> Any:
        user = get_current_user()
        assert user is not None
        current_user_id = int(user["id"])
        friend_ids = _user_friend_ids(current_user_id)
        shares = _response_rows(
            get_db().table("study_record_shares")
            .select("record_id,owner_id,created_at")
            .eq("friend_id", current_user_id).order("created_at", desc=True).execute()
        )
        # A revoked friendship must not leave access to a previously shared record.
        shares = [row for row in shares if int(row["owner_id"]) in friend_ids]
        record_ids = sorted({int(row["record_id"]) for row in shares})
        records = _response_rows(
            get_db().table("study_records").select("*").in_("id", record_ids).execute()
        ) if record_ids else []
        by_id = {int(row["id"]): row for row in records}
        owner_ids = sorted({int(row["owner_id"]) for row in shares})
        owners = _response_rows(
            get_db().table("users").select("id,display_name").in_("id", owner_ids).execute()
        ) if owner_ids else []
        owner_names = {int(row["id"]): row["display_name"] for row in owners}
        shared = []
        for share in shares:
            owner_id = int(share["owner_id"])
            record = by_id.get(int(share["record_id"]))
            if record is not None and owner_id in owner_names:
                shared.append({**record, "owner_name": owner_names[owner_id]})
        shared.sort(key=lambda row: str(row.get("study_date", "")), reverse=True)
        return render_template(
            "shared_records.html", page_title="공유 기록",
            page_description="친구가 직접 나와 공유한 학습 기록이에요.", shared_records=shared,
        )

    routes = (
        ("/settings/password", "change_password", change_password, ["POST"]),
        ("/account/delete", "delete_account", delete_account, ["POST"]),
        ("/records/<int:record_id>/status", "update_record_status", update_record_status, ["POST"]),
        ("/records/<int:record_id>/share", "manage_record_shares", manage_record_shares, ["GET", "POST"]),
        ("/shared", "shared_records", shared_records, ["GET"]),
    )
    for rule, endpoint, view, methods in routes:
        flask_app.add_url_rule(rule, endpoint=endpoint, view_func=view, methods=methods)

    # Replace the existing CRUD views so the selected status is persisted on create/edit.
    flask_app.view_functions["new_record"] = new_record_with_status
    flask_app.view_functions["edit_record"] = edit_record_with_status


__all__ = ["register_feature_routes"]
