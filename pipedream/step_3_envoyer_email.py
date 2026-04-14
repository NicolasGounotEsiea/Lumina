"""
PIPEDREAM — Étape 3 : Envoyer l'email de licence via Gmail SMTP
"""
import json
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

_EMAIL_TEMPLATE = """\
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Votre licence Lumina Control</title>
  <style>
    body { margin:0;padding:0;background-color:#141414;font-family:'Segoe UI',Arial,sans-serif;color:#D0D0D0;-webkit-font-smoothing:antialiased; }
    .wrapper { max-width:600px;margin:40px auto;border-radius:12px;overflow:hidden;border:1px solid rgba(255,255,255,0.08); }
    .header { background:#1E1E1E;padding:32px 40px 28px;border-bottom:2px solid #60CDFF; }
    .logo { font-size:20px;font-weight:700;color:#60CDFF;letter-spacing:0.04em; }
    .logo span { color:#FFFFFF; }
    .tagline { font-size:12px;color:#666;margin-top:4px;letter-spacing:0.06em;text-transform:uppercase; }
    .body { background:#181818;padding:36px 40px; }
    .greeting { font-size:22px;font-weight:600;color:#FFFFFF;margin:0 0 8px; }
    .intro { font-size:14px;color:#999;line-height:1.6;margin:0 0 32px; }
    .intro strong { color:#60CDFF; }
    .plan-badge { display:inline-block;background:rgba(96,205,255,0.12);border:1px solid rgba(96,205,255,0.35);color:#60CDFF;font-size:11px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;padding:4px 12px;border-radius:20px;margin-bottom:28px; }
    .key-section { margin-bottom:32px; }
    .key-label { font-size:11px;font-weight:700;letter-spacing:0.10em;text-transform:uppercase;color:#60CDFF;margin-bottom:10px; }
    .key-box { background:#111111;border:1px solid rgba(96,205,255,0.25);border-radius:8px;padding:18px 20px;font-family:'Cascadia Code','Consolas','Courier New',monospace;font-size:12px;color:#A8E6FF;word-break:break-all;line-height:1.6; }
    .key-hint { font-size:11px;color:#555;margin-top:8px; }
    .steps-title { font-size:13px;font-weight:700;color:#CCCCCC;margin:0 0 16px;text-transform:uppercase;letter-spacing:0.06em; }
    .steps { list-style:none;padding:0;margin:0 0 32px; }
    .steps li { display:flex;align-items:flex-start;gap:14px;margin-bottom:14px;font-size:13px;color:#AAAAAA;line-height:1.5; }
    .step-num { flex-shrink:0;width:24px;height:24px;background:rgba(96,205,255,0.15);border:1px solid rgba(96,205,255,0.30);border-radius:50%;color:#60CDFF;font-size:11px;font-weight:700;display:flex;align-items:center;justify-content:center; }
    .sep { border:none;border-top:1px solid rgba(255,255,255,0.06);margin:0 0 28px; }
    .support { font-size:12px;color:#555;line-height:1.7; }
    .support a { color:#60CDFF;text-decoration:none; }
    .footer { background:#141414;padding:20px 40px;border-top:1px solid rgba(255,255,255,0.05);font-size:11px;color:#444;line-height:1.6; }
    .footer a { color:#555;text-decoration:none; }
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="header">
      <div class="logo">Lumina<span>Control</span></div>
      <div class="tagline">Contrôle avancé de la luminosité</div>
    </div>
    <div class="body">
      <p class="greeting">Bonjour {{customer_name}} 👋</p>
      <p class="intro">Merci pour votre achat de <strong>{{product_name}}</strong> !<br />Voici votre clé de licence personnelle. Conservez cet email en lieu sûr.</p>
      <div class="plan-badge">Licence {{plan_label}}</div>
      <div class="key-section">
        <div class="key-label">🔑 Votre clé de licence</div>
        <div class="key-box">{{license_key}}</div>
        <div class="key-hint">Sélectionnez tout le texte ci-dessus et copiez-le (Ctrl+A puis Ctrl+C)</div>
      </div>
      <p class="steps-title">Comment activer</p>
      <ul class="steps">
        <li><div class="step-num">1</div><div>Lancez <strong>Lumina Control</strong> — le dialog d'activation s'ouvre automatiquement.</div></li>
        <li><div class="step-num">2</div><div>Collez votre clé dans le champ prévu à cet effet.</div></li>
        <li><div class="step-num">3</div><div>Cliquez sur <strong>Activer</strong> — c'est tout, aucune connexion internet requise.</div></li>
      </ul>
      <hr class="sep" />
      <div class="support">Un problème ? Répondez à cet email ou écrivez à <a href="mailto:{{gmail_user}}">{{gmail_user}}</a>.<br />Clé associée à : <strong>{{customer_email}}</strong></div>
    </div>
    <div class="footer">Lumina Control · Cette clé est personnelle et ne peut être partagée.</div>
  </div>
</body>
</html>"""


def _render(template: str, **kwargs: str) -> str:
    for key, value in kwargs.items():
        template = template.replace("{{" + key + "}}", value)
    return template


def handler(pd: "pipedream"):
    prev_verify  = pd.steps["code"]["$return_value"]
    prev_license = pd.steps["code1"]["$return_value"]

    if prev_verify.get("skip") or prev_license.get("skip"):
        return {"skip": True}

    customer_email = prev_verify["email"]
    customer_name  = prev_verify["name"]
    product_name   = prev_verify["product_name"]
    license_key    = prev_license["license_key"]
    plan           = prev_license["plan"]
    plan_label     = "À vie" if plan == "lifetime" else "Pro"

    gmail_user     = os.environ["GMAIL_USER"]
    gmail_password = os.environ["GMAIL_APP_PASSWORD"]

    html_body = _render(
        _EMAIL_TEMPLATE,
        customer_name  = customer_name,
        customer_email = customer_email,
        product_name   = product_name,
        license_key    = license_key,
        plan_label     = plan_label,
        gmail_user     = gmail_user,
    )

    # Construction du message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🔑 Votre licence {product_name}"
    msg["From"]    = f"Lumina Control <{gmail_user}>"
    msg["To"]      = customer_email
    msg.attach(MIMEText(
        f"Bonjour {customer_name},\n\nMerci pour votre achat ({plan_label}) !\n\n"
        f"Votre clé :\n\n{license_key}\n\n"
        "Lancez Lumina Control → collez la clé → cliquez Activer.",
        "plain", "utf-8",
    ))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    # Envoi via Gmail SMTP
    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(gmail_user, gmail_password)
        smtp.sendmail(gmail_user, customer_email, msg.as_bytes())

    return {"sent": True, "to": customer_email, "from": gmail_user}
