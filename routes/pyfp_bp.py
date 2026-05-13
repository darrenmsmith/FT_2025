from flask import Blueprint, jsonify

pyfp_bp = Blueprint("pyfp", __name__, url_prefix="/pyfp")


@pyfp_bp.route("/healthz")
def healthz():
    return jsonify({"ok": True})
