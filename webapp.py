import os
import logging
import subprocess
import sys
import threading
import urllib.request
from datetime import datetime
from io import BytesIO
from pathlib import Path

from flask import Flask, render_template, jsonify, request, send_file

import db
from commercial_strategy import build_commercial_strategy
from knowledge_engine import load_knowledge
from matcher import load_profile
from pdf_generator import create_proposal_pdf
from pricing_engine import calculate_pricing
from project_validation import validate_project_output
from proposal_generator_v2 import generate_proposal
from proposal_intelligence import build_proposal_intelligence

WEBAPP_HOST = os.getenv("WEBAPP_HOST", "0.0.0.0")
WEBAPP_PORT = int(os.getenv("WEBAPP_PORT", "5050"))

app = Flask(__name__)
BASE_DIR = Path(__file__).parent
logger = logging.getLogger(__name__)

scan_lock = threading.Lock()
scan_state = {
    "running": False,
    "lines": [],
    "process": None,
    "returncode": None,
}

STATUS_LABELS = {
    "proposta_gerada": "Pendentes",
    "enviado": "Enviados",
    "respondeu": "Responderam",
    "em_andamento": "Em andamento",
    "finalizado": "Finalizados",
    "perdido": "Perdidos",
    "descartado": "Descartados",
}

STATUS_PERMITIDOS = set(STATUS_LABELS.keys())

# Score a partir do qual um projeto é destacado como "quente" na interface.
HOT_SCORE_THRESHOLD = 45.0

# Onde o Chrome escuta em modo debug (mesma porta usada pelo scraper do 99Freelas).
CHROME_CDP_URL = os.getenv("CHROME_CDP_URL", "http://127.0.0.1:9222")
CHROME_DEBUG_PROFILE = BASE_DIR / ".chrome_cdp_profile"

CHROME_CANDIDATE_PATHS = [
    os.getenv("CHROME_EXE_PATH", ""),
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


def _find_chrome_exe():
    for path in CHROME_CANDIDATE_PATHS:
        if path and Path(path).exists():
            return path
    return None


def _run_scan_subprocess():
    cmd = [sys.executable, "-u", "main.py"]
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    proc = subprocess.Popen(
        cmd,
        cwd=str(BASE_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        env=env,
    )

    with scan_lock:
        scan_state["process"] = proc

    for line in proc.stdout:
        with scan_lock:
            scan_state["lines"].append(line.rstrip("\n"))

    proc.wait()

    with scan_lock:
        scan_state["running"] = False
        scan_state["process"] = None
        scan_state["returncode"] = proc.returncode


def get_stats():
    stats = {}

    with db.get_conn() as conn:
        for status in STATUS_PERMITIDOS:
            stats[status] = conn.execute(
                "SELECT COUNT(*) c FROM projects WHERE status = ?",
                (status,),
            ).fetchone()["c"]

        avg_row = conn.execute(
            "SELECT AVG(match_score) a FROM projects WHERE status = 'proposta_gerada'"
        ).fetchone()

        valor_row = conn.execute(
            """
            SELECT SUM(suggested_price_brl) total
            FROM projects
            WHERE status IN ('proposta_gerada', 'enviado', 'respondeu', 'em_andamento')
            """
        ).fetchone()

    stats["avg_score"] = round(avg_row["a"], 1) if avg_row["a"] else 0.0
    stats["valor_potencial"] = round(valor_row["total"] or 0, 2)

    return stats


def _days_since(timestamp_str):
    if not timestamp_str:
        return None
    try:
        then = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    delta = datetime.utcnow() - then
    return max(delta.days, 0)


def _safe_money(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value):
    try:
        return int(round(float(value or 0)))
    except (TypeError, ValueError):
        return 0


def _timeline_summary(hours, requires_scope_validation=False):
    hours_int = _safe_int(hours)
    if requires_scope_validation:
        return "prazo a validar"
    if hours_int <= 8:
        return "2 a 4 dias úteis"
    if hours_int <= 36:
        return "5 a 8 dias úteis"
    if hours_int <= 90:
        return "2 a 3 semanas"
    return "4 a 8 semanas"


def _legacy_view_model(project):
    price = _safe_money(project.get("suggested_price_brl"))
    hours = _safe_int(project.get("estimated_hours"))
    proposal_text = project.get("proposal_text") or ""
    pricing = {
        "suggested_price_brl": price,
        "minimum_price_brl": price,
        "maximum_price_brl": price,
        "estimated_hours": hours,
        "confidence": 0.0,
        "requires_scope_validation": False,
        "pricing_reason": project.get("ai_reasoning") or "",
        "assumptions": [],
        "adjustments": [],
    }
    proposal = {
        "headline": project.get("title") or "Projeto personalizado",
        "executive_summary": proposal_text[:240],
        "understanding": "",
        "identified_challenges": [],
        "proposed_solution": proposal_text,
        "deliverables": [],
        "work_method": [],
        "timeline": [],
        "technologies": [],
        "relevant_cases": [],
        "proof_points": [],
        "investment_summary": project.get("ai_reasoning") or "",
        "assumptions": [],
        "clarifying_questions": [],
        "next_step": "Validar os detalhes finais para organizar o início.",
        "proposal_text": proposal_text,
        "short_proposal_text": proposal_text[:700],
    }
    return {
        "project": {
            **project,
            "category": "",
            "timeline_summary": _timeline_summary(hours),
            "pricing_confidence": 0.0,
            "requires_scope_validation": False,
        },
        "intelligence": {
            "category": "",
            "complexity": "",
            "scope_confidence": 0.0,
            "problem_summary": "",
            "client_goal": "",
            "risks": [],
            "clarifying_questions": [],
            "relevant_services": [],
            "relevant_technologies": [],
        },
        "strategy": {"relevant_cases": [], "proof_points": []},
        "pricing": pricing,
        "proposal": proposal,
    }


def build_project_view_model(project):
    """Monta dados estruturados para dashboard/PDF sem chamar Groq."""
    try:
        knowledge = load_knowledge()
        intelligence = build_proposal_intelligence(project)
        strategy = build_commercial_strategy(project, intelligence, knowledge)
        pricing = calculate_pricing(project, intelligence, strategy, knowledge)
        if project.get("suggested_price_brl") not in (None, ""):
            pricing["suggested_price_brl"] = _safe_money(project.get("suggested_price_brl"))
        if project.get("estimated_hours") not in (None, ""):
            pricing["estimated_hours"] = _safe_int(project.get("estimated_hours"))
        proposal = generate_proposal(project, intelligence, strategy, pricing, knowledge)
        if project.get("proposal_text"):
            proposal["proposal_text"] = project["proposal_text"]
        try:
            validation = validate_project_output(project, intelligence, strategy, pricing, proposal)
            normalized = validation["normalized"]
            project = normalized["project"]
            intelligence = normalized["intelligence"]
            strategy = normalized["strategy"]
            pricing = normalized["pricing"]
            proposal = normalized["proposal"]
        except Exception as exc:
            logger.exception("Falha ao validar view model estruturado; usando dados originais: %s", exc)
        project_view = {
            **project,
            **proposal,
            "structured_proposal": proposal,
            "category": intelligence.get("category", ""),
            "timeline_summary": _timeline_summary(
                pricing.get("estimated_hours"),
                bool(pricing.get("requires_scope_validation")),
            ),
            "pricing_confidence": pricing.get("confidence", 0.0),
            "requires_scope_validation": bool(pricing.get("requires_scope_validation")),
        }
        return {
            "project": project_view,
            "intelligence": intelligence,
            "strategy": strategy,
            "pricing": pricing,
            "proposal": proposal,
        }
    except Exception as exc:
        logger.exception("Falha ao montar view model estruturado; usando legado: %s", exc)
        return _legacy_view_model(project)


def _enrich(rows):
    projetos = []
    for r in rows:
        p = dict(r)
        p["days_since_status"] = _days_since(p.get("status_changed_at"))
        p["is_hot"] = (p.get("match_score") or 0) >= HOT_SCORE_THRESHOLD
        view = build_project_view_model(p)
        p.update(
            {
                "category": view["intelligence"].get("category", ""),
                "complexity": view["intelligence"].get("complexity", ""),
                "timeline_summary": view["project"].get("timeline_summary", ""),
                "pricing_confidence": view["pricing"].get("confidence", 0.0),
                "requires_scope_validation": view["pricing"].get("requires_scope_validation", False),
            }
        )
        projetos.append(p)
    return projetos


def list_projects(status="proposta_gerada"):
    with db.get_conn() as conn:
        if status == "todos":
            rows = conn.execute(
                """
                SELECT *
                FROM projects
                WHERE status != 'descartado'
                ORDER BY match_score DESC
                """
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT *
                FROM projects
                WHERE status = ?
                ORDER BY match_score DESC
                """,
                (status,),
            ).fetchall()

    return _enrich(rows)


@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/dashboard")
def dashboard():
    db.init_db()
    profile = load_profile()

    status = request.args.get("status", "proposta_gerada")

    if status not in STATUS_PERMITIDOS and status != "todos":
        status = "proposta_gerada"

    projetos = list_projects(status)

    categoria = request.args.get("categoria", "").strip()
    complexidade = request.args.get("complexidade", "").strip()
    plataforma = request.args.get("plataforma", "").strip()
    validacao = request.args.get("validacao", "").strip()
    if categoria:
        projetos = [p for p in projetos if p.get("category") == categoria]
    if complexidade:
        projetos = [p for p in projetos if p.get("complexity") == complexidade]
    if plataforma:
        projetos = [p for p in projetos if p.get("platform") == plataforma]
    if validacao == "1":
        projetos = [p for p in projetos if p.get("requires_scope_validation")]

    with scan_lock:
        running = scan_state["running"]

    return render_template(
        "dashboard.html",
        projetos=projetos,
        stats=get_stats(),
        running=running,
        status_atual=status,
        status_labels=STATUS_LABELS,
        profile=profile,
        filtros={
            "categoria": categoria,
            "complexidade": complexidade,
            "plataforma": plataforma,
            "validacao": validacao,
        },
    )


@app.route("/api/projetos")
def api_projetos():
    status = request.args.get("status", "proposta_gerada")

    if status not in STATUS_PERMITIDOS and status != "todos":
        status = "proposta_gerada"

    return jsonify({
        "ok": True,
        "projetos": list_projects(status),
        "stats": get_stats(),
    })


@app.route("/project/<project_id>")
def project_detail(project_id):
    project = db.get_project(project_id)
    if not project:
        return jsonify({"ok": False, "error": "Projeto não encontrado"}), 404
    view_model = build_project_view_model(project)
    return render_template(
        "project_detail.html",
        view=view_model,
        status_labels=STATUS_LABELS,
    )


@app.route("/api/project/<project_id>/proposal")
def api_project_proposal(project_id):
    project = db.get_project(project_id)
    if not project:
        return jsonify({"ok": False, "error": "Projeto não encontrado"}), 404
    view = build_project_view_model(project)
    return jsonify(
        {
            "ok": True,
            "short_proposal_text": view["proposal"].get("short_proposal_text", ""),
            "proposal_text": view["proposal"].get("proposal_text", ""),
            "pricing": view["pricing"],
            "intelligence": view["intelligence"],
        }
    )


@app.route("/api/scan/start", methods=["POST"])
def start_scan():
    with scan_lock:
        if scan_state["running"]:
            return jsonify({"ok": False, "error": "Varredura já em andamento"}), 409

        scan_state["running"] = True
        scan_state["lines"] = []
        scan_state["returncode"] = None

    threading.Thread(target=_run_scan_subprocess, daemon=True).start()

    return jsonify({"ok": True})


@app.route("/api/scan/poll")
def poll_scan():
    offset = request.args.get("offset", 0, type=int)

    with scan_lock:
        lines = scan_state["lines"][offset:]
        new_offset = len(scan_state["lines"])
        running = scan_state["running"]
        returncode = scan_state["returncode"]

    return jsonify({
        "lines": lines,
        "offset": new_offset,
        "running": running,
        "returncode": returncode,
    })


@app.route("/api/status/<project_id>", methods=["POST"])
def alterar_status(project_id):
    data = request.get_json() or {}
    status = data.get("status")

    if status not in STATUS_PERMITIDOS:
        return jsonify({"ok": False, "error": "Status inválido"}), 400

    db.mark_status(project_id, status)

    return jsonify({"ok": True, "label": STATUS_LABELS[status]})


@app.route("/api/enviar/<project_id>", methods=["POST"])
def marcar_enviado(project_id):
    db.mark_status(project_id, "enviado")
    return jsonify({"ok": True})


@app.route("/api/descartar/<project_id>", methods=["POST"])
def marcar_descartado(project_id):
    db.mark_status(project_id, "descartado")
    return jsonify({"ok": True})


@app.route("/api/chrome/status")
def chrome_status():
    try:
        with urllib.request.urlopen(f"{CHROME_CDP_URL}/json/version", timeout=1.5):
            return jsonify({"connected": True})
    except Exception:
        return jsonify({"connected": False})


@app.route("/api/proposal/<project_id>/pdf")
def download_proposal_pdf(project_id):
    project = db.get_project(project_id)
    if not project:
        return jsonify({"ok": False, "error": "Projeto não encontrado"}), 404

    profile = load_profile()
    view = build_project_view_model(project)
    pdf_bytes = create_proposal_pdf(view["project"], profile)
    return send_file(
        BytesIO(pdf_bytes),
        mimetype="application/pdf",
        download_name=f"proposta_{project_id}.pdf",
        as_attachment=True,
    )


@app.route("/api/db/reset", methods=["POST"])
def reset_database():
    try:
        db.reset_db()
        return jsonify({"ok": True})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/chrome/start", methods=["POST"])
def chrome_start():
    chrome_exe = _find_chrome_exe()
    if not chrome_exe:
        return jsonify({
            "ok": False,
            "error": "Chrome não encontrado. Defina CHROME_EXE_PATH no .env com o caminho do chrome.exe.",
        }), 404

    CHROME_DEBUG_PROFILE.mkdir(parents=True, exist_ok=True)

    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP

    subprocess.Popen(
        [
            chrome_exe,
            "--remote-debugging-port=9222",
            f"--user-data-dir={CHROME_DEBUG_PROFILE}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        **kwargs,
    )

    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host=WEBAPP_HOST, port=WEBAPP_PORT, debug=False, threaded=True, use_reloader=False)
