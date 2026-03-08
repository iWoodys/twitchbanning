from flask import Flask, Response
import os
import requests

app = Flask(__name__)

TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID", "")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET", "")
TWITCH_REFRESH_TOKEN = os.getenv("TWITCH_REFRESH_TOKEN", "")
BROADCASTER_ID = os.getenv("TWITCH_BROADCASTER_ID", "")
MODERATOR_ID = os.getenv("TWITCH_MODERATOR_ID", "")


def refresh_access_token() -> str:
    if not all([TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET, TWITCH_REFRESH_TOKEN]):
        raise RuntimeError("Faltan variables de entorno de Twitch.")

    response = requests.post(
        "https://id.twitch.tv/oauth2/token",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "refresh_token",
            "refresh_token": TWITCH_REFRESH_TOKEN,
            "client_id": TWITCH_CLIENT_ID,
            "client_secret": TWITCH_CLIENT_SECRET,
        },
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()

    access_token = payload.get("access_token")
    if not access_token:
        raise RuntimeError("No se recibió access_token de Twitch.")

    return access_token


def get_banned_users():
    if not all([BROADCASTER_ID, MODERATOR_ID]):
        raise RuntimeError("Faltan BROADCASTER_ID o MODERATOR_ID.")

    access_token = refresh_access_token()
    url = "https://api.twitch.tv/helix/moderation/banned"

    params = {
        "broadcaster_id": BROADCASTER_ID,
        "moderator_id": MODERATOR_ID,
        "first": 100,
    }

    all_rows = []
    cursor = None

    while True:
        page_params = params.copy()
        if cursor:
            page_params["after"] = cursor

        response = requests.get(
            url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Client-Id": TWITCH_CLIENT_ID,
            },
            params=page_params,
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()

        all_rows.extend(payload.get("data", []))
        cursor = payload.get("pagination", {}).get("cursor")

        if not cursor:
            break

    return all_rows


@app.get("/")
def home():
    return Response("API Twitch baneados online", mimetype="text/plain")


@app.get("/bans_count")
def bans_count():
    try:
        rows = get_banned_users()
        permanent = [r for r in rows if not r.get("end_time")]
        timed_out = [r for r in rows if r.get("end_time")]
        text = f"Baneados permanentes: {len(permanent)} | Timeouts activos: {len(timed_out)} | Total: {len(rows)}"
        return Response(text[:400], mimetype="text/plain")
    except Exception as e:
        return Response(f"Error: {str(e)}"[:400], mimetype="text/plain", status=500)


@app.get("/bans_list")
def bans_list():
    try:
        rows = get_banned_users()
        permanent = [r.get("user_login", "?") for r in rows if not r.get("end_time")]

        if not permanent:
            text = "No tenés usuarios baneados permanentemente."
        else:
            text = "Baneados: " + ", ".join(permanent[:20])
            if len(permanent) > 20:
                text += f" ... y {len(permanent) - 20} más"

        return Response(text[:400], mimetype="text/plain")
    except Exception as e:
        return Response(f"Error: {str(e)}"[:400], mimetype="text/plain", status=500)


@app.get("/bans_last")
def bans_last():
    try:
        rows = get_banned_users()
        permanent = [r for r in rows if not r.get("end_time")]
        permanent.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        if not permanent:
            text = "No hay baneos permanentes para mostrar."
        else:
            names = [r.get("user_login", "?") for r in permanent[:10]]
            text = "Últimos baneados: " + ", ".join(names)

        return Response(text[:400], mimetype="text/plain")
    except Exception as e:
        return Response(f"Error: {str(e)}"[:400], mimetype="text/plain", status=500)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)