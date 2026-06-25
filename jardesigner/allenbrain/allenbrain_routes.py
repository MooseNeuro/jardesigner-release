##############################################
# allenbrain_routes.py — Flask routes for Allen Brain Cell Types Database
# CORS handled globally in server.py.
##############################################
import traceback
from pathlib import Path

from flask import Blueprint, jsonify, request

from .allenbrain import (
    fetch_species_options,
    search_neurons,
    fetch_swc_for_specimen,
    fetch_morph_thumb,
)

allenbrain_routes = Blueprint("allenbrain", __name__)

USER_UPLOADS_DIR = Path(__file__).resolve().parent.parent / "user_uploads"


@allenbrain_routes.route("/metadata", methods=["GET"])
def get_species_filters():
    """
    GET /allenbrain/metadata?species=<name>
    Returns brain areas, layers, and transgenic lines for the given species.
    """
    species = request.args.get("species", "").strip()
    if not species:
        return jsonify({"error": "species query param required"}), 400
    try:
        return jsonify(fetch_species_options(species))
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@allenbrain_routes.route("/search", methods=["POST"])
def search():
    """
    POST /allenbrain/search
    Body: { species?, brain_area_acronym?, brain_area_parent_acronym?,
            layer?, dendrite_type?, apical?, reconstruction_type?,
            line_name?, page?, size? }
    """
    body = request.get_json(force=True, silent=True) or {}
    try:
        size = max(1, int(body.get("size", 20)))
        page = max(0, int(body.get("page", 0)))
    except (TypeError, ValueError):
        return jsonify({"error": "page and size must be integers"}), 400

    try:
        result = search_neurons(
            species                   = body.get("species") or None,
            sex                       = body.get("sex") or None,
            disease_state             = body.get("disease_state") or None,
            brain_area_acronym        = body.get("brain_area_acronym") or None,
            brain_area_parent_acronym = body.get("brain_area_parent_acronym") or None,
            layer                     = body.get("layer") or None,
            hemisphere                = body.get("hemisphere") or None,
            dendrite_type             = body.get("dendrite_type") or None,
            apical                    = body.get("apical") or None,
            reconstruction_type       = body.get("reconstruction_type") or None,
            reporter_status           = body.get("reporter_status") or None,
            line_name                 = body.get("line_name") or None,
            page                      = page,
            size                      = size,
        )
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    total       = result["total"]
    total_pages = max(1, -(-total // size))

    return jsonify({
        "neurons":     result["neurons"],
        "total":       total,
        "page":        page,
        "total_pages": total_pages,
    })


@allenbrain_routes.route("/thumb/<int:file_id>", methods=["GET"])
def get_thumb(file_id: int):
    """GET /allenbrain/thumb/<file_id> — proxy morphology thumbnail."""
    try:
        img_bytes, content_type = fetch_morph_thumb(file_id)
        return img_bytes, 200, {"Content-Type": content_type}
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


def stage_specimen(specimen_id: int, client_id: str) -> dict:
    """Download SWC for specimen_id and save to the user's session directory.
    Returns {"filename": "<name>.swc"}. Raises on failure."""
    swc_text, filename = fetch_swc_for_specimen(specimen_id)
    dest_dir = USER_UPLOADS_DIR / client_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / filename).write_text(swc_text, encoding="utf-8")
    return {"filename": filename}


@allenbrain_routes.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})
