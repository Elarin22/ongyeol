"""Re-authenticated password change and account deletion handlers."""
from __future__ import annotations

from typing import Any

from flask import flash, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from app import _response_rows, app, get_current_user, get_db, login_required


def register_account_security_routes(flask_app: Any = app) -> None:
    """Replace the account-security endpoints after feature routes are added."""

    @login_required
    def change_password() -> Any:
        user = get_current_user()
        assert user is not None

        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not check_password_hash(user["password_hash"], current_password):
            flash("현재 비밀번호가 올바르지 않아요.", "error")
        elif not 8 <= len(new_password) <= 128:
            flash("새 비밀번호는 8자 이상 128자 이하로 입력해 주세요.", "error")
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
                flash("비밀번호를 변경하지 못했어요. 다시 시도해 주세요.", "error")
            else:
                flash("비밀번호를 안전하게 변경했어요.", "success")

        return redirect(url_for("settings") + "#password-settings")

    @login_required
    def delete_account() -> Any:
        user = get_current_user()
        assert user is not None
        user_id = int(user["id"])
        typed_email = request.form.get("confirm_email", "").strip().lower()
        current_password = request.form.get("current_password", "")

        if typed_email != str(user["email"]).strip().lower():
            flash("가입한 이메일 주소가 일치하지 않아요. 계정은 삭제되지 않았어요.", "error")
            return redirect(url_for("settings") + "#account-settings")
        if not check_password_hash(user["password_hash"], current_password):
            flash("현재 비밀번호가 올바르지 않아요. 계정은 삭제되지 않았어요.", "error")
            return redirect(url_for("settings") + "#account-settings")

        try:
            # Delete the account row once. The Supabase schema's ON DELETE
            # rules should cascade owned records, friendships, notifications,
            # invitations and shares; a restrictive FK safely rejects deletion.
            deleted = _response_rows(
                get_db().table("users").delete().eq("id", user_id).select("id").execute()
            )
        except Exception:
            app.logger.exception("Account deletion failed for user id %s", user_id)
            flash(
                "회원탈퇴를 완료하지 못했어요. 연결 데이터의 삭제 권한이나 외래 키 설정을 확인해 주세요.",
                "error",
            )
            return redirect(url_for("settings") + "#account-settings")

        if not deleted:
            flash("회원탈퇴를 완료하지 못했어요. 다시 로그인한 뒤 시도해 주세요.", "error")
            return redirect(url_for("settings") + "#account-settings")

        session.clear()
        flash("회원탈퇴가 완료되었어요. 이용해 주셔서 감사합니다.", "success")
        return redirect(url_for("login"))

    # feature_routes.py registers these endpoint names first. Replacing the
    # handlers keeps the existing URLs while applying the stricter checks.
    for endpoint, view in (
        ("change_password", change_password),
        ("delete_account", delete_account),
    ):
        if endpoint not in flask_app.view_functions:
            raise RuntimeError(f"Missing account security endpoint: {endpoint}")
        flask_app.view_functions[endpoint] = view


__all__ = ["register_account_security_routes"]
