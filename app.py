from flask import Flask, request, send_file, render_template, redirect, Response
import requests
from urllib.parse import urlparse, urljoin
import re
import tempfile
import os

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/go")
def go():
    url = request.args.get("url")
    if not url:
        return "Missing URL", 400

    if any(url.lower().endswith(ext) for ext in [".zip", ".exe", ".jar", ".pdf", ".mp4", ".mp3"]):
        return redirect(f"/download?url={url}")

    return redirect(f"/proxy?url={url}")

@app.route("/download")
def download():
    url = request.args.get("url")
    if not url:
        return "Missing 'url' parameter", 400

    try:
        response = requests.get(url, stream=True, timeout=10)
        response.raise_for_status()

        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            for chunk in response.iter_content(chunk_size=8192):
                tmp_file.write(chunk)
            tmp_path = tmp_file.name

        return send_file(tmp_path, as_attachment=True, download_name=os.path.basename(url))

    except requests.RequestException as e:
        return f"Download failed: {e}", 500

    finally:
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.remove(tmp_path)

@app.route("/proxy")
def proxy():
    url = request.args.get("url")
    if not url:
        return "Missing URL", 400

    try:
        r = requests.get(url)
        content_type = r.headers.get("Content-Type", "")
        if "text/html" not in content_type:
            return redirect(f"/download?url={url}")

        html = r.text
        base = url
        html = rewrite_links(html, base)
        return Response(html, content_type="text/html")

    except Exception as e:
        return f"Failed to load page: {e}", 500

def rewrite_links(html, base_url):
    def repl(m):
        original = m.group(2)
        joined = urljoin(base_url, original)
        proxied = f"/proxy?url={joined}"
        return f'{m.group(1)}="{proxied}"'

    pattern = r'(href|src)=["\'](.*?)["\']'
    return re.sub(pattern, repl, html, flags=re.IGNORECASE)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
