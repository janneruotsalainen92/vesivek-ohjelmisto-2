from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, send_from_directory, url_for

from vesivek.config import DEFAULT_STICK_M, IMAGE_SUFFIXES, default_output_dir, repo_root
from vesivek.pipeline import RunRequest, list_site_facades, run_measurement

UPLOAD_ROOT = repo_root() / ".web-uploads"


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["MAX_CONTENT_LENGTH"] = 250 * 1024 * 1024
    app.secret_key = "vesivek-local-mvp-not-a-secret"

    @app.get("/")
    def index():
        return render_template("index.html", mittatikku=DEFAULT_STICK_M)

    @app.post("/julkisivut")
    def julkisivut():
        osoite = (request.form.get("osoite") or "").strip()
        wfs_mode = request.form.get("wfs") or "auto"
        if not osoite:
            flash("Anna katuosoite.")
            return redirect(url_for("index"))
        try:
            site, facades = list_site_facades(osoite, wfs_mode=wfs_mode)
        except Exception as exc:
            flash(str(exc))
            return redirect(url_for("index"))
        compass = [f for f in facades if not f.key.startswith("reuna-")]
        return render_template(
            "julkisivut.html",
            osoite=osoite,
            wfs_mode=wfs_mode,
            site=site,
            facades=compass,
            mittatikku=DEFAULT_STICK_M,
        )

    @app.post("/mittaa")
    def mittaa():
        osoite = (request.form.get("osoite") or "").strip()
        wfs_mode = request.form.get("wfs") or "auto"
        julkisivu = request.form.get("julkisivu") or "auto"
        try:
            mittatikku = float(request.form.get("mittatikku") or DEFAULT_STICK_M)
        except ValueError:
            mittatikku = DEFAULT_STICK_M
        leveys_raw = (request.form.get("kaistan_leveys") or "").strip()
        try:
            leveys = float(leveys_raw) if leveys_raw else None
        except ValueError:
            flash("Kaistan leveys ei ole luku.")
            return redirect(url_for("index"))

        batch = UPLOAD_ROOT / uuid.uuid4().hex
        batch.mkdir(parents=True, exist_ok=True)
        saved = 0
        for storage in request.files.getlist("kuvat"):
            if not storage or not storage.filename:
                continue
            suffix = Path(storage.filename).suffix.lower()
            if suffix not in IMAGE_SUFFIXES:
                continue
            dest = batch / f"{saved:04d}_{Path(storage.filename).name}"
            storage.save(dest)
            saved += 1

        req = RunRequest(
            osoite=osoite,
            kuvat=[batch] if saved else [],
            julkisivu=julkisivu,
            mittatikku_m=mittatikku,
            kaistan_leveys_m=leveys,
            wfs_mode=wfs_mode,
            output_dir=default_output_dir(),
        )
        try:
            result = run_measurement(req)
        except Exception as exc:
            shutil.rmtree(batch, ignore_errors=True)
            flash(str(exc))
            return redirect(url_for("index"))

        token = result.output_dir.name
        return render_template("tulos.html", result=result, token=token)

    @app.get("/tulokset/<token>/<name>")
    def download(token: str, name: str):
        if name not in {"julkisivukaista.png", "mittaus.xlsx", "julkisivukaista.geojson", "huomiot.txt"}:
            return "Ei sallittu", 404
        folder = default_output_dir() / token
        return send_from_directory(folder, name, as_attachment=name.endswith((".xlsx", ".geojson")))

    return app


def serve(host: str = "127.0.0.1", port: int = 5050) -> None:
    app = create_app()
    print(f"Vesivek Ohjelma bot-kokeilu  →  http://{host}:{port}")
    app.run(host=host, port=port, debug=False)
