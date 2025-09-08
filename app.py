from __future__ import annotations
from altcha import create_challenge, verify_solution
from dotenv import load_dotenv
from flask import abort, flash, Flask, redirect, render_template, request, url_for
from urllib.parse import quote
import datetime, json, os, shutil, tempfile

load_dotenv()

app = Flask(__name__)

app.secret_key = os.environ.get("SECRET_KEY")
ALTCHA_HMAC_KEY = os.environ.get("ALTCHA_HMAC_KEY")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
ANIMES_JSON = os.path.join(DATA_DIR, "animes.json")
REQUESTS_JSON = os.path.join(DATA_DIR, "requests.json")
FEEDBACKS_JSON = os.path.join(DATA_DIR, "feedbacks.json")
COVERS_DIR = os.path.join(BASE_DIR, "static", "covers")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(COVERS_DIR, exist_ok=True)

@app.after_request
def after_request(response):
    if request.path.startswith('/static/'):
        if request.path.endswith(('.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg')):
            response.cache_control.max_age = 86400
            response.cache_control.public = True
        elif request.path.endswith(('.css', '.js')):
            response.cache_control.max_age = 3600
            response.cache_control.public = True
    return response

@app.after_request
def after_request(response):
    if request.endpoint == 'static':
        if request.view_args and 'filename' in request.view_args:
            filename = request.view_args['filename']
            if filename.endswith(('.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg')):
                response.cache_control.max_age = 86400
                response.cache_control.public = True
            elif filename.endswith(('.css', '.js')):
                response.cache_control.max_age = 3600
                response.cache_control.public = True
    return response

@app.template_filter('pct')
def percent_encode(s):
    return quote(str(s), safe='')

def load_animes() -> dict:
    if not os.path.exists(ANIMES_JSON):
        return {}
    with open(ANIMES_JSON, "r", encoding="utf-8") as f:
        return json.load(f)

def dump_requests_safely(data: list):
    fd, tmp = tempfile.mkstemp(dir=DATA_DIR, suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    shutil.move(tmp, REQUESTS_JSON)

def cover_path_for(name: str) -> str:
    base = os.path.join("static", "covers", name)
    for ext in (".jpg", ".jpeg", ".png", ".webp", ".avif", ".svg"):
        abs_candidate = os.path.join(BASE_DIR, base + ext)
        if os.path.exists(abs_candidate):
            return f"/{base}{ext}"
    return "/static/placeholder.svg"

def get_client_ip() -> str:
    xff = request.headers.get("X-Forwarded-For", "")
    return xff.split(",")[0].strip() if xff else request.remote_addr or "0.0.0.0"

@app.context_processor
def inject_globals():
    return {
        "CURRENT_YEAR": datetime.datetime.now().year,
        "EMAIL": os.environ.get("EMAIL"),
        "SITE_NAME": os.environ.get("SITE_NAME"),
        "TELEGRAM_USER": os.environ.get("TELEGRAM_USER")
    }

@app.route("/")
def index():
    animes = load_animes()
    sorted_animes = sorted(
        animes.items(),
        key=lambda x: (-int(x[1].get('year', 0)), x[0].lower())
    )
    latest_animes = []
    for name, anime in sorted_animes[:5]:
        latest_animes.append({
            'name': name,
            'anime': anime,
            'cover': cover_path_for(name)
        })
    return render_template("index.html", latest_animes=latest_animes)

@app.route("/animes")
def animes():
    q = (request.args.get("q") or "").strip().lower()
    data = load_animes()
    items = []
    for name, meta in data.items():
        if q and (q not in name.lower() and q not in str(meta.get("year", "")).lower()):
            continue
        items.append({
            "name": name,
            "year": meta.get("year", ""),
            "cover": cover_path_for(name)
        })
    items.sort(key=lambda x: (x["name"].lower()))
    return render_template("animes.html", items=items, query=q)

@app.route("/stream/<path:name>")
def stream(name):
    data = load_animes()
    if name not in data:
        abort(404)

    anime = data[name]
    cover = cover_path_for(name)
    year = anime.get("year", "")
    description = anime.get("description", "")
    content = anime.get("content", {}) or {}

    if not content:
        abort(404)

    episodes = list(content.keys())
    selected = request.args.get("ep") or episodes[0]
    if selected not in content:
        selected = episodes[0]

    embed_url = content[selected]
    return render_template(
        "stream.html",
        name=name,
        cover=cover,
        year=year,
        description=description,
        episodes=episodes,
        selected=selected,
        embed_url=embed_url,
    )

@app.route("/request", methods=["GET", "POST"])
def request_anime():
    ip = get_client_ip()
    MAX_PER_HOUR = 5
    MAX_PER_DAY = 15

    def get_recent_requests(seconds):
        now = datetime.datetime.utcnow()
        if not os.path.exists(REQUESTS_JSON):
            return 0
        with open(REQUESTS_JSON, "r", encoding="utf-8") as f:
            try:
                existing = json.load(f)
            except Exception:
                existing = []
        return sum(
            1 for rec in existing
            if rec.get("ip") == ip and
            (now - datetime.datetime.fromisoformat(rec["timestamp"].replace("Z",""))).total_seconds() <= seconds
        )

    if request.method == "POST":
        altcha_response = request.form.get("altcha")
        if not altcha_response or not verify_solution(altcha_response, ALTCHA_HMAC_KEY):
            flash("Please complete the security verification.", "error")
            return redirect(url_for("request_anime"))
        if get_recent_requests(3600) >= MAX_PER_HOUR:
            flash("You have reached the maximum requests per hour.", "error")
            return redirect(url_for("request_anime"))
        if get_recent_requests(86400) >= MAX_PER_DAY:
            flash("You have reached the maximum requests per day.", "error")
            return redirect(url_for("request_anime"))

        title = (request.form.get("title") or "").strip()

        if not title:
            flash("Please enter an anime name.", "error")
            return redirect(url_for("request_anime"))
        if len(title) > 100:
            flash("Anime name must be no more than 100 characters long.", "error")
            return redirect(url_for("request_anime"))

        record = {
            "title": title,
            "ip": ip,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        }

        existing = []
        if os.path.exists(REQUESTS_JSON):
            try:
                with open(REQUESTS_JSON, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                    if not isinstance(existing, list):
                        existing = []
            except Exception:
                existing = []

        existing.append(record)
        dump_requests_safely(existing)
        flash("Request submitted. Thank you!", "success")
        return redirect(url_for("request_anime"))

    try:
        challenge = create_challenge(hmac_key=ALTCHA_HMAC_KEY, max_number=100000)
        challenge_data = {
            "challenge": challenge.challenge,
            "maxnumber": challenge.max_number,
            "salt": challenge.salt,
            "signature": challenge.signature,
            "algorithm": "SHA-256"
        }
        return render_template("request.html", altcha_challenge=challenge_data)
    except Exception as e:
        print("Challenge generation error:", e)
        return render_template("request.html", altcha_challenge=None)

@app.route("/feedback", methods=["GET", "POST"])
def feedback():
    ip = get_client_ip()
    MAX_PER_HOUR = 5
    MAX_PER_DAY = 15

    def get_recent_feedbacks(seconds):
        now = datetime.datetime.utcnow()
        if not os.path.exists(FEEDBACKS_JSON):
            return 0
        with open(FEEDBACKS_JSON, "r", encoding="utf-8") as f:
            try:
                existing = json.load(f)
            except Exception:
                existing = []
        return sum(
            1 for rec in existing
            if rec.get("ip") == ip and
            (now - datetime.datetime.fromisoformat(rec["timestamp"].replace("Z",""))).total_seconds() <= seconds
        )

    if request.method == "POST":
        altcha_response = request.form.get("altcha")
        if not altcha_response or not verify_solution(altcha_response, ALTCHA_HMAC_KEY):
            flash("Please complete the security verification.", "error")
            return redirect(url_for("feedback"))
        if get_recent_feedbacks(3600) >= MAX_PER_HOUR:
            flash("You have reached the maximum feedback submissions per hour.", "error")
            return redirect(url_for("feedback"))
        if get_recent_feedbacks(86400) >= MAX_PER_DAY:
            flash("You have reached the maximum feedback submissions per day.", "error")
            return redirect(url_for("feedback"))

        feedback_text = (request.form.get("feedback") or "").strip()

        if not feedback_text:
            flash("Please enter your feedback.", "error")
            return redirect(url_for("feedback"))
        if len(feedback_text) < 10:
            flash("Feedback must be at least 10 characters long.", "error")
            return redirect(url_for("feedback"))
        if len(feedback_text) > 500:
            flash("Feedback must be no more than 500 characters long.", "error")
            return redirect(url_for("feedback"))

        record = {
            "feedback": feedback_text,
            "ip": ip,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        }

        existing = []
        if os.path.exists(FEEDBACKS_JSON):
            try:
                with open(FEEDBACKS_JSON, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                    if not isinstance(existing, list):
                        existing = []
            except Exception:
                existing = []

        existing.append(record)
        
        fd, tmp = tempfile.mkstemp(dir=DATA_DIR, suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
        shutil.move(tmp, FEEDBACKS_JSON)
        
        flash("Feedback submitted. Thank you!", "success")
        return redirect(url_for("feedback"))

    try:
        challenge = create_challenge(hmac_key=ALTCHA_HMAC_KEY, max_number=100000)
        challenge_data = {
            "algorithm": "SHA-256",
            "challenge": challenge.challenge,
            "maxnumber": challenge.max_number,
            "salt": challenge.salt,
            "signature": challenge.signature
        }
        return render_template("feedback.html", altcha_challenge=challenge_data)
    except Exception as e:
        print("Challenge generation error:", e)
        return render_template("feedback.html", altcha_challenge=None)

@app.route("/dmca")
def dmca():
    return render_template("dmca.html")

@app.route("/privacy")
def privacy():
    return render_template("privacy.html")

@app.route("/terms")
def terms():
    return render_template("terms.html")

@app.route("/support")
def support():
    return render_template("support.html")

@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0')
