from flask import Flask, request, jsonify, abort, render_template
from flask_cors import CORS
from google import genai
from dotenv import load_dotenv
from sqlmodel import SQLModel, Session, create_engine, select
from models import User, Conversation
import os, json, re, datetime, requests
import threading
import time
import hmac

load_dotenv()
API_KEY = os.getenv("TOKEN")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
PING_URL = os.getenv("PING_URL", "http://localhost:5000/ping")
app = Flask(__name__)
app.config["DASHBOARD_TOKEN"] = os.getenv("DASHBOARD_TOKEN")
CORS(app, origins=["http://localhost:3000", os.getenv("FRONTEND_URL", "*")])
engine = create_engine("sqlite:///database.db")
SQLModel.metadata.create_all(engine)
try:
    client = genai.Client(api_key=API_KEY)
except Exception as e:
    print(f"Erro ao inicializar o Gemini: {e}")
    client = None

def clean_text(text):
    return re.sub(r"[*_]", "", text)

def get_or_create_user(ip):
    with Session(engine) as session:
        user = session.exec(select(User).where(User.ip_address == ip)).first()
        if not user:
            user = User(ip_address=ip)
            session.add(user)
            session.commit()
            session.refresh(user)
        return user

def log_to_discord(user_msg, ai_reply, ip):
    if not DISCORD_WEBHOOK_URL:
        return
    embed = {
        "title": "Nova Interação com a IA",
        "color": 0x5865F2,
        "fields": [
            {"name": "Mensagem do Usuário", "value": user_msg[:1000], "inline": False},
            {"name": "Resposta da IA", "value": ai_reply[:1000], "inline": False},
            {"name": "IP", "value": ip, "inline": True},
        ],
        "footer": {"text": f"Data: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"}
    }
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]}, timeout=5)
    except:
        pass

def keep_alive():
    def run():
        while True:
            time.sleep(300)
            try:
                response = requests.get(PING_URL, timeout=10)
                print(f"[KEEP-ALIVE] Ping enviado → {PING_URL} | Status: {response.status_code}")
            except Exception as e:
                print(f"[KEEP-ALIVE] Erro no ping: {e}")
    thread = threading.Thread(target=run)
    thread.daemon = True
    thread.start()
    print(f"[KEEP-ALIVE] Self-ping ativado: {PING_URL}")

@app.route("/ping")
def ping():
    return "pong", 200

@app.route("/health")
def health():
    return jsonify({"status": "API rodando!", "time": datetime.datetime.now().isoformat()})

@app.route("/api/chat", methods=["POST"])
def chat():
    if not client:
        return jsonify({"reply": "Serviço de IA indisponível."}), 503
    try:
        data = request.get_json(silent=True) or {}
        user_message = data.get("message", "").strip()
        user_ip = request.remote_addr
        if not user_message:
            return jsonify({"reply": "Envie uma mensagem válida."}), 400
        user = get_or_create_user(user_ip)
        prompt = f"""
Você é Vitor Emanuel, um jovem de 15 anos, comunicativo, educado e muito profissional.
Está em busca de oportunidades de emprego na área de tecnologia, principalmente com Python e desenvolvimento web.
Responda de forma humana e natural, como se estivesse realmente conversando.
Se alguém mencionar vaga, emprego, oportunidade, currículo ou recrutador, fale de forma gentil e profissional, informando seus contatos:
- WhatsApp: +55 82 98756-5699
- Email: vitorvzp722@gmail.com
Fale com educação e clareza, sempre demonstrando maturidade e boa comunicação.
Mensagem recebida:
\"\"\"{user_message}\"\"\"
"""
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        reply = clean_text(response.text)
        with Session(engine) as session:
            conv = Conversation(
                user_id=user.id,
                user_message=user_message,
                ai_response=reply
            )
            session.add(conv)
            session.commit()
        log_to_discord(user_message, reply, user_ip)
        return jsonify({"reply": reply})
    except Exception as e:
        print(f"Erro durante o chat: {e}")
        return jsonify({"reply": "Erro interno no servidor."}), 500

@app.route("/dashboard")
def dashboard():
    expected_token = app.config.get("DASHBOARD_TOKEN")
    if not expected_token or not expected_token.strip():
        abort(404)
    authorization = request.headers.get("Authorization", "")
    scheme, separator, supplied_token = authorization.partition(" ")
    if (
        not separator
        or scheme.lower() != "bearer"
        or not hmac.compare_digest(
            supplied_token.encode("utf-8"), expected_token.encode("utf-8")
        )
    ):
        abort(401)

    ip_filter = request.args.get("ip")
    with Session(engine) as session:
        if ip_filter:
            conversations = session.exec(
                select(Conversation).join(User).where(User.ip_address == ip_filter)
            ).all()
        else:
            conversations = session.exec(select(Conversation)).all()
        all_ips = session.exec(select(User.ip_address)).all()
        return render_template(
            "dashboard.html",
            conversations=conversations,
            all_ips=all_ips,
            ip_filter=ip_filter,
        )


@app.after_request
def protect_dashboard_response(response):
    if request.endpoint == "dashboard":
        if response.status_code == 401:
            response.headers["WWW-Authenticate"] = 'Bearer realm="dashboard"'
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; style-src 'unsafe-inline'; "
            "form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
        )
        response.vary.add("Authorization")
    return response

@app.route("/api/faq")
def get_faq():
    try:
        with open("faq.json", "r", encoding="utf-8") as f:
            faq_data = json.load(f)
        return jsonify(faq_data)
    except FileNotFoundError:
        return jsonify({"error": "FAQ not found"}), 404

keep_alive()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
