
import os
import re
import shutil
import tempfile
import threading
import subprocess

from flask import Flask, request, send_file, render_template_string
from yt_dlp import YoutubeDL

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 4096

lock = threading.Lock()
MAX_SIZE = 100 * 1024 * 1024

PAGE = """
<!doctype html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MiniTube</title>
</head>
<body>
<h2>MiniTube</h2>

<form method="get">
<input name="q" maxlength="150" required
 value="{{ q }}" placeholder="Search YouTube"
 style="width:95%">
<button>Search</button>
</form>

<p>{{ message }}</p>

{% for v in results %}
<hr>
<b>{{ v.title }}</b><br>
{% if v.duration %}Duration: {{ v.duration }} sec<br>{% endif %}
<form method="post">
<input type="hidden" name="id" value="{{ v.id }}">
<select name="format">
<option value="mp3">MP3</option>
<option value="mp4">MP4 (480p max)</option>
<option value="3gp">3GP</option>
</select>
<button>Download</button>
</form>
{% endfor %}
</body>
</html>
"""


def page(q="", results=None, message=""):
    return render_template_string(
        PAGE, q=q, results=results or [], message=message
    )


@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "GET":
        q = request.args.get("q", "").strip()[:150]
        if not q:
            return page()

        try:
            opts = {
                "quiet": True,
                "no_warnings": True,
                "extract_flat": True,
                "playlistend": 5,
                "socket_timeout": 10,
            }
            with YoutubeDL(opts) as ydl:
                data = ydl.extract_info(
                    "ytsearch5:" + q, download=False
                )

            results = []
            for v in data.get("entries", []):
                if not v:
                    continue
                vid = v.get("id", "")
                if not re.fullmatch(r"[A-Za-z0-9_-]{11}", vid):
                    continue
                results.append({
                    "id": vid,
                    "title": v.get("title", "Untitled"),
                    "duration": v.get("duration"),
                })

            return page(q, results, "No results found."
                        if not results else "")
        except Exception:
            return page(q, message="Search failed. Try again.")

    vid = request.form.get("id", "")
    fmt = request.form.get("format", "")

    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", vid):
        return page(message="Invalid video ID."), 400

    if fmt not in ("mp3", "mp4", "3gp"):
        return page(message="Invalid format."), 400

    if not lock.acquire(blocking=False):
        return page(message="Another download is running."), 429

    folder = tempfile.mkdtemp(prefix="mini_")
    url = "https://www.youtube.com/watch?v=" + vid

    opts = {
        "outtmpl": os.path.join(folder, "media.%(ext)s"),
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
                "preferredquality": "96",
            }],
        })
    elif fmt == "mp4":
        opts.update({
            "format":
                "best[ext=mp4][height<=480]/"
                "best[height<=480][ext=mp4]/"
                "best[height<=480]/best",
        })
    else:
        # Download a small source, then convert to 3GP.
        opts["format"] = (
            "best[height<=144][ext=mp4]/"
            "best[height<=144]/best"
        )

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

        path = files[0]

        if fmt == "3gp":
            converted = os.path.join(folder, "media.3gp")
            subprocess.run(
                [
                    "ffmpeg", "-nostdin", "-y",
                    "-i", path,
                    "-vf", "scale=320:240:force_original_aspect_ratio=decrease",
                    "-c:v", "mpeg4", "-q:v", "8",
                    "-c:a", "aac", "-b:a", "32k",
                    "-threads", "1",
                    "-fs", str(MAX_SIZE),
                    converted,
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=90,
            )
            os.remove(path)
            path = converted

        if os.path.getsize(path) > MAX_SIZE:
            raise RuntimeError("File too large")

        response = send_file(
            path,
            as_attachment=True,
            download_name=os.path.basename(path),
        )

        def cleanup():
            shutil.rmtree(folder, ignore_errors=True)
            lock.release()

        response.call_on_close(cleanup)
        return response

    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        lock.release()
        return page(
            message="Download failed. Check FFmpeg and format availability."
        ), 400


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
  )
          
