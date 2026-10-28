"""Autoriza o robo a enviar videos para o SEU canal do YouTube (OAuth). Uma vez so. So biblioteca padrao + httpx. Nunca imprime segredos.

Antes: no Google Cloud Console crie o projeto, ative a "YouTube Data API v3", configure a tela de consentimento e crie uma credencial OAuth do tipo
"App para computador"; baixe o JSON e salve como  data/youtube/youtube_client.json  (docs/03, passo 12).

Uso (no servidor):   venv/bin/python ferramentas/youtube_conectar.py
  - O script mostra um LINK. Abra no navegador do SEU computador, entre na conta dona do canal e autorize.
  - O Google devolve para http://127.0.0.1:8765 : como o servidor nao tem navegador, abra ANTES um tunel no seu computador:
        ssh -L 8765:127.0.0.1:8765 usuario@IP-DO-SERVIDOR
    (assim o 127.0.0.1:8765 do seu computador chega ao servidor).
Resultado: data/youtube/youtube_token.json (chmod 600) com o refresh token. O robo passa a enviar um Short para cada Reel da fila."""
import json
import os
import secrets
import sys
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import httpx

PASTA = Path(os.getenv("PROMOBOT_DATA", "/opt/promobot/data")) / "youtube"
PORTA = int(os.getenv("YT_PORTA", "8765"))
ESCOPOS = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly"


def main() -> None:
    arq = PASTA / "youtube_client.json"
    if not arq.exists():
        print(f"\n  ERRO: faltou {arq}\n  Baixe o JSON da credencial OAuth (tipo 'App para computador') e salve nesse caminho (docs/03, passo 12).")
        sys.exit(1)
    cli = json.loads(arq.read_text(encoding="utf-8")).get("installed") or {}
    if not cli.get("client_id") or not cli.get("client_secret"):
        print("\n  ERRO: o JSON nao parece uma credencial do tipo 'App para computador' (sem client_id/client_secret).")
        sys.exit(1)
    redir = f"http://127.0.0.1:{PORTA}"
    estado = secrets.token_urlsafe(16)
    url = "https://accounts.google.com/o/oauth2/auth?" + urllib.parse.urlencode({"client_id": cli["client_id"], "redirect_uri": redir, "response_type": "code", "scope": ESCOPOS,
                                                                                    "access_type": "offline", "prompt": "consent", "state": estado})
    resultado: dict = {}

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if q.get("state", [""])[0] == estado and "code" in q:
                resultado["code"] = q["code"][0]
                msg = "Autorizado. Pode fechar esta aba e voltar ao terminal."
            else:
                resultado["erro"] = q.get("error", ["sem codigo"])[0]
                msg = "Falhou: " + resultado["erro"]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(msg.encode("utf-8"))

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", PORTA), H)
    srv.timeout = 5
    print(f"\n  1) No SEU computador, abra o tunel (se o servidor nao tem navegador):  ssh -L {PORTA}:127.0.0.1:{PORTA} usuario@IP-DO-SERVIDOR")
    print("  2) Abra este link no navegador, entre na conta DONA DO CANAL e autorize:\n\n" + url + "\n")
    print("  Aguardando a autorizacao (ate 10 minutos)...")
    limite = time.time() + 600
    while not resultado and time.time() < limite:
        srv.handle_request()
    if "code" not in resultado:
        print(f"\n  ERRO: a autorizacao nao foi concluida ({resultado.get('erro', 'tempo esgotado')}).")
        sys.exit(1)
    r = httpx.post(cli.get("token_uri", "https://oauth2.googleapis.com/token"), timeout=60, data={"code": resultado["code"], "client_id": cli["client_id"], "client_secret": cli["client_secret"],
                                                                                                   "redirect_uri": redir, "grant_type": "authorization_code"}).json()
    if not r.get("refresh_token"):
        print(f"\n  ERRO: o Google nao devolveu o refresh token ({str(r.get('error_description', r))[:160]}).\n  Dica: remova o acesso do app em myaccount.google.com/permissions e rode de novo.")
        sys.exit(1)
    os.umask(0o077)
    (PASTA / "youtube_token.json").write_text(json.dumps({"refresh_token": r["refresh_token"], "scope": r.get("scope")}), encoding="utf-8")
    os.chmod(PASTA / "youtube_token.json", 0o600)
    print("\n  OK: YouTube autorizado. Proximo passo: ferramentas/social_verificar.py")


if __name__ == "__main__":
    main()
