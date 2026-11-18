"""
一鍵啟動「一二壘有人：封殺三壘決策模擬器」本機伺服器
先重新由最新資料匯出模型 JSON，再於 http://127.0.0.1:8765 啟動靜態伺服器。
"""
import http.server
import socketserver
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.force_3b_model import export_web_bundle

PORT = int(os.environ.get("PORT", "8765"))


def main():
    export_web_bundle()
    web_dir = BASE_DIR / "web"
    os.chdir(web_dir)
    handler = http.server.SimpleHTTPRequestHandler
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", PORT), handler) as httpd:
        print(f"=== 封殺三壘決策模擬器已啟動：http://127.0.0.1:{PORT} ===", flush=True)
        print("按 Ctrl+C 可停止伺服器", flush=True)
        httpd.serve_forever()


if __name__ == "__main__":
    main()
