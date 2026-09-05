"""HTTP entry point: signup, login, and the work-order board behind a session."""
from __future__ import annotations

import os
from typing import Optional

from flask import Flask, jsonify, request

from dispatch.models import LoginRequest, SignupRequest, ValidationError, WorkOrder
from dispatch.sessions import SessionStore
from dispatch.work_orders import DispatchError, WorkOrderBoard, seed_board
from infrai_captcha import CaptchaRejected, verify_captcha

COOKIE_NAME = "fs_session"


def demo_orders() -> WorkOrderBoard:
    return seed_board([
        WorkOrder(order_id="WO-4471", site="Bakersfield cold room", problem="compressor short-cycling"),
        WorkOrder(order_id="WO-4472", site="Fresno depot", problem="dock leveller stuck"),
    ])


def create_app(store: Optional[SessionStore] = None, board: Optional[WorkOrderBoard] = None) -> Flask:
    app = Flask(__name__)
    app.config["STORE"] = store or SessionStore()
    app.config["BOARD"] = board or demo_orders()

    def current_email() -> Optional[str]:
        session = app.config["STORE"].resolve(request.cookies.get(COOKIE_NAME))
        return session.email if session else None

    @app.post("/signup")
    def signup():
        try:
            payload = SignupRequest.parse(request.get_json(silent=True) or {})
        except ValidationError as exc:
            return jsonify({"error": str(exc)}), 400

        try:
            verify_captcha(payload.captcha_token, ip=request.remote_addr, action="signup")
        except CaptchaRejected as exc:
            # A rejected token is a decision about this signup, so it stays a 4xx.
            return jsonify({"error": exc.code, "message": exc.message}), 403

        try:
            tech = app.config["STORE"].create_technician(
                payload.email, payload.password, payload.full_name
            )
        except KeyError as exc:
            return jsonify({"error": str(exc)}), 409

        session = app.config["STORE"].open_session(tech.email)
        response = jsonify({"email": tech.email, "status": "signed_up"})
        response.set_cookie(COOKIE_NAME, session.session_id, httponly=True, samesite="Lax")
        return response, 201

    @app.post("/login")
    def login():
        try:
            payload = LoginRequest.parse(request.get_json(silent=True) or {})
        except ValidationError as exc:
            return jsonify({"error": str(exc)}), 400
        if not app.config["STORE"].check_password(payload.email, payload.password):
            return jsonify({"error": "email or password did not match"}), 401
        session = app.config["STORE"].open_session(payload.email)
        response = jsonify({"email": payload.email, "status": "signed_in"})
        response.set_cookie(COOKIE_NAME, session.session_id, httponly=True, samesite="Lax")
        return response

    @app.post("/logout")
    def logout():
        sid = request.cookies.get(COOKIE_NAME)
        if sid:
            app.config["STORE"].close_session(sid)
        return jsonify({"status": "signed_out"})

    @app.get("/work-orders")
    def list_orders():
        email = current_email()
        if not email:
            return jsonify({"error": "sign in first"}), 401
        board: WorkOrderBoard = app.config["BOARD"]
        return jsonify({"orders": [o.to_json() for o in board.for_technician(email)]})

    @app.post("/work-orders/<order_id>/claim")
    def claim(order_id: str):
        email = current_email()
        if not email:
            return jsonify({"error": "sign in first"}), 401
        try:
            order = app.config["BOARD"].dispatch(order_id, email)
        except DispatchError as exc:
            return jsonify({"error": str(exc)}), 409
        return jsonify(order.to_json())

    @app.post("/work-orders/<order_id>/photos")
    def add_photo(order_id: str):
        if not current_email():
            return jsonify({"error": "sign in first"}), 401
        body = request.get_json(silent=True) or {}
        try:
            order = app.config["BOARD"].attach_photo(
                order_id, str(body.get("key", "")), str(body.get("caption", ""))
            )
        except DispatchError as exc:
            return jsonify({"error": str(exc)}), 409
        return jsonify(order.to_json())

    @app.post("/work-orders/<order_id>/close")
    def close(order_id: str):
        if not current_email():
            return jsonify({"error": "sign in first"}), 401
        body = request.get_json(silent=True) or {}
        try:
            order = app.config["BOARD"].close(order_id, body.get("follow_up_note"))
        except DispatchError as exc:
            return jsonify({"error": str(exc)}), 409
        return jsonify(order.to_json())

    return app


if __name__ == "__main__":
    create_app().run(port=int(os.environ.get("PORT", "5000")))
