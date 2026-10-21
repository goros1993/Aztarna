"""Sirve la interfaz (web/) y la API de Aztarna por HTTP, para hacer las capturas del manual en un navegador.

En la aplicación, la interfaz habla con Python por el puente de pywebview;
aquí, `capturar.js` sustituye ese puente por llamadas HTTP a este servidor.

Uso: python servidor.py <repo> <puerto> <destino> [carpeta inicial]
Borra <destino>, copia allí los ejemplos y prepara los documentos de importar
(documentos.py). Los ajustes del PC van a un archivo temporal.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
puerto = int(sys.argv[2])
destino = Path(sys.argv[3])
inicial = sys.argv[4] if len(sys.argv) > 4 else "yaml"
os.environ["AZTARNA_AJUSTES"] = str(Path(tempfile.mkdtemp(prefix="ajustes-")) / "ajustes.json")
if destino.exists():
    shutil.rmtree(destino)
shutil.copytree(repo / "ejemplos", destino)
subprocess.run([sys.executable, str(Path(__file__).with_name("documentos.py")), str(repo), str(destino)], check=True)
sys.path.insert(0, str(repo))
from app.importacion_api import EditorImportacionApi  # noqa: E402

api = EditorImportacionApi(destino / inicial)


class Manejador(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(repo / "web"), **k)

    def log_message(self, *a):
        pass

    def do_POST(self):
        nombre = self.path.rsplit("/", 1)[-1]
        largo = int(self.headers.get("Content-Length") or 0)
        args = json.loads(self.rfile.read(largo) or b"[]")
        metodo = getattr(api, nombre, None)
        r = metodo(*args) if metodo else {"ok": False, "error": f"sin método {nombre}"}
        cuerpo = json.dumps(r, default=str).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)


print("LISTO", flush=True)
ThreadingHTTPServer(("127.0.0.1", puerto), Manejador).serve_forever()
