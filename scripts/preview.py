"""Loopback-only text preview for the running Cresta draft (no alternate model)."""
import json
import os
import secrets
import shutil
import socketserver
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = shutil.which("cresta") or str(Path.home() / ".local/bin/cresta")
TOKEN = secrets.token_urlsafe(32)
LOCK = threading.Lock()
CONVERSATIONS = set()
PORT = int(os.environ.get("MARINA_PREVIEW_PORT", "9138"))


def command(*args):
    result = subprocess.run([CLI, "agent", "chat", *args, "--output", "json"],
                            cwd=ROOT, capture_output=True, text=True, timeout=100)
    if result.returncode:
        raise RuntimeError("O rascunho não respondeu. Verifique a sessão da Cresta no terminal.")
    return json.loads(result.stdout)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass  # Passenger details and conversation text are never logged here.

    def reply(self, status, body, content_type="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'nonce-" + TOKEN + "'; style-src 'unsafe-inline'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode())

    def valid_host(self):
        return self.headers.get("Host") in {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}

    def do_GET(self):
        if not self.valid_host():
            return self.reply(403, {"error": "Origem inválida."})
        if self.path != "/":
            return self.reply(404, {"error": "Página não encontrada."})
        page = (ROOT / "preview/index.html").read_text().replace("__TOKEN__", TOKEN)
        self.reply(200, page.encode(), "text/html")

    def do_POST(self):
        if not self.valid_host() or not secrets.compare_digest(self.headers.get("X-Preview-Token", ""), TOKEN):
            return self.reply(403, {"error": "Reabra a página de teste."})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 16000:
                return self.reply(400, {"error": "Mensagem inválida."})
            payload = json.loads(self.rfile.read(length))
            with LOCK:
                if self.path == "/new":
                    result = command("new", str(ROOT / "ai-agent-51"))
                    CONVERSATIONS.add(result["convID"])
                elif self.path == "/message":
                    conversation = payload.get("conversation")
                    message = payload.get("message")
                    if conversation not in CONVERSATIONS or not isinstance(message, str) or not message.strip() or len(message) > 8000:
                        return self.reply(400, {"error": "Inicie uma conversa e escreva uma mensagem."})
                    result = command(str(ROOT / "ai-agent-51"), "--conversation", conversation, "-m", message)
                else:
                    return self.reply(404, {"error": "Ação inválida."})
            self.reply(200, {"conversation": result.get("convID"), "text": result.get("greeting", result.get("text", "")),
                             "tools": [x.get("toolDisplayName", "") for x in result.get("toolCalls", [])],
                             "empty": result.get("emptyReply", False)})
        except subprocess.TimeoutExpired:
            self.reply(504, {"error": "A resposta demorou demais. Não reenvie uma confirmação de reserva; inicie uma nova conversa para continuar o teste."})
        except (ValueError, TypeError, KeyError):
            self.reply(400, {"error": "Resposta ou mensagem inválida. Inicie uma nova conversa."})
        except RuntimeError as error:
            self.reply(502, {"error": str(error)})


class LocalServer(ThreadingHTTPServer):
    def server_bind(self):
        # No reverse DNS lookup is necessary for a loopback preview.
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address


if __name__ == "__main__":
    server = LocalServer(("127.0.0.1", PORT), Handler)
    print(f"Marina draft preview: http://127.0.0.1:{PORT}", flush=True)
    server.serve_forever()
