
import os
import shutil
import tempfile
import threading
from urllib.parse import urlparse

from flask import Flask, request, send_file, render_template_string
from yt_dlp import YoutubeDL

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 4096

# One active download at a time to reduce resource usage.
download_lock = threading.Lock()
MAX_SIZE = 100 * 1024 * 1024

PAGE = """
<!doctype html>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mini Media</title>
<h2>Mini Media Downloader</h2>
<form method="post">
  <input name="url" type="url" required maxlength="2048"
         placeholder="Paste video URL" style="width:95%">
  <p>
  <select name="format">
    <option value="mp3">MP3 Audio</option>
    <option value="mp4">MP4 Video</option>
    <option value="3gp">3GP Video</option>
  </select>
  </p>
  <button type="submit">Download</button>
</form>
<p>{{ message }}</p>
"""

@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "GET":
        return render_template_string(PAGE, message="")

    url = request.form.get("url", "").strip()
    fmt = request.form.get("format", "")

    parsed = urlparse(url)
    if (parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or fmt not in ("mp3", "mp4", "3gp")):
        return render_template_string(
            PAGE, message="Invalid URL or format."
        ), 400

    # Avoid obvious local/private hostnames. For a public deployment,
    # add proper DNS/IP validation and redirect protections too.
    host = parsed.hostname.lower()
    if host in ("localhost",) or host.endswith(".local"):
        return render_template_string(
            PAGE, message="Local addresses are not allowed."
        ), 400

    if not download_lock.acquire(blocking=False):
        return render_template_string(
            PAGE, message="Another download is running. Try later."
        ), 429

    folder = tempfile.mkdtemp(prefix="media_")

    opts = {
        "outtmpl": os.path.join(folder, "%(title).80B.%(ext)s"),
        "noplaylist": True,
        "max_filesize": MAX_SIZE,
        "socket_timeout": 15,
        "retries": 1,
        "fragment_retries": 1,
        "concurrent_fragment_downloads": 1,
        "quiet": True,
        "no_warnings": True,
    }

    if fmt == "mp3":
        opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "128",
            }],
        })
    elif fmt == "mp4":
        opts.update({
            "format":
                "best[ext=mp4][height<=480]/"
                "best[height<=480][ext=mp4]/"
                "best[height<=480]/best",
            "merge_output_format": "mp4",
        })
    else:
        # Only works if the source provides a compatible 3GP format.
        opts.update({
            "format": "best[ext=3gp]/3gp",
        })

    try:
        with YoutubeDL(opts) as ydl:
            ydl.download([url])

        files = [
            os.path.join(folder, f)
            for f in os.listdir(folder)
            if os.path.isfile(os.path.join(folder, f))
        ]

        if not files:
            raise RuntimeError("No output file")

        path = max(files, key=os.path.getsize)

        if os.path.getsize(path) > MAX_SIZE:
            raise RuntimeError("Output exceeds size limit")

        response = send_file(
            path,
            as_attachment=True,
            download_name=os.path.basename(path),
        )

        def cleanup():
            shutil.rmtree(folder, ignore_errors=True)
            download_lock.release()

        response.call_on_close(cleanup)
        return response

    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        download_lock.release()
        return render_template_string(
            PAGE,
            message=(
                "Download failed. The format may be unavailable, "
                "FFmpeg may be missing, or the URL may be unsupported."
            ),
        ), 400


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
    )
    
