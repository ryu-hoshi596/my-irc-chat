import os
from flask import Flask, request, render_template_string, redirect, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

# Channels store lists of message dicts: {time, ip, text, target_ip}
channels = {
    "general": [],
    "tech": [],
    "random": []
}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>IP-Chat IRC</title>
    <meta http-equiv="refresh" content="5">
</head>
<body style="font-family: monospace; padding: 10px; background: #111; color: #00ff00;">
    <h2>&gt;&gt; SECURE_IP_CHAT_ROOM</h2>
    
    <!-- Minimal Features / Info Box -->
    <div style="background: #1a1a1a; border: 1px dashed #333; padding: 8px; margin-bottom: 10px; font-size: 11px; color: #aaa;">
        <strong>[ SITE FEATURES ]</strong><br>
        • <b>IP Identification:</b> Your network IP acts as your permanent handle.<br>
        • <b>Location Tracking:</b> Copy any participant's IP and check it via external geo-tools.<br>
        • <b>Whisper Mode:</b> Type <code>/w IP_ADDRESS message</code> for private server-filtered DMs.<br>
        • <b>Zero Bloat:</b> Pure HTML forms, no JS, ultra-fast on JioBharat &amp; mobile.
    </div>

    <p style="color: #fff;">
        <strong>Rooms:</strong> 
        <a href="/channel/general" style="color: #00ffff;">[ #general ]</a> 
        <a href="/channel/tech" style="color: #00ffff;">[ #tech ]</a> 
        <a href="/channel/random" style="color: #00ffff;">[ #random ]</a>
    </p>
    <p>
        <a href="/channel/{{ current_channel }}" style="color: #ffff00;">[ Manual Refresh ]</a> | 
        <span style="color: #ff00ff;">Your IP: {{ viewer_ip }}</span>
    </p>
    <hr style="border-color: #333;">

    <h3>Current Room: #{{ current_channel }}</h3>

    <!-- Chat Box Log -->
    <div style="background: #000; border: 1px solid #333; padding: 10px; min-height: 200px; max-height: 300px; overflow-y: auto;">
        {% for msg in visible_messages %}
            <p style="margin: 4px 0;">
                <span style="color: #777;">[{{ msg.time }}]</span> 
                {% if msg.target_ip %}
                    <span style="color: #ff00ff;">*WHISPER* &lt;{{ msg.ip }}&gt; to &lt;{{ msg.target_ip }}&gt;:</span> 
                    <span style="color: #ff5555;">{{ msg.text }}</span>
                {% else %}
                    <span style="color: #00ffff;">&lt;{{ msg.ip }}&gt;:</span> {{ msg.text }}
                {% endif %}
            </p>
        {% else %}
            <p style="color: #555;"><em>Channel is empty. Drop a payload...</em></p>
        {% endfor %}
    </div>

    <p style="font-size: 11px; color: #888; margin-top: 5px;">
        Syntax tip: <code>/w IP_ADDRESS your message here</code>
    </p>

    <hr style="border-color: #333;">

    <!-- Message Form -->
    <form action="/send" method="POST">
        <input type="hidden" name="channel" value="{{ current_channel }}">
        <p>
            <label><strong>Message / Command:</strong></label><br>
            <input type="text" name="text" placeholder="Type text or /w IP msg..." required style="width: 100%; padding: 8px; background: #222; color: #fff; border: 1px solid #444;">
        </p>
        <p>
            <input type="submit" value="[ TRANSMIT ]" style="background: #00ff00; color: #000; font-weight: bold; padding: 5px 15px; border: none;">
        </p>
    </form>
</body>
</html>
"""

def get_client_ip():
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if not ip:
        return "unknown-ip"
    return ip.split(',')[0].strip()

@app.route('/')
def index():
    return redirect(url_for('view_channel', channel_name='general'))

@app.route('/channel/<channel_name>')
def view_channel(channel_name):
    if channel_name not in channels:
        channels[channel_name] = []
    
    viewer_ip = get_client_ip()
    
    visible_messages = []
    for msg in channels[channel_name]:
        if msg['target_ip'] is None:
            visible_messages.append(msg)
        elif msg['ip'] == viewer_ip or msg['target_ip'] == viewer_ip:
            visible_messages.append(msg)

    return render_template_string(
        HTML_TEMPLATE, 
        current_channel=channel_name, 
        visible_messages=visible_messages,
        viewer_ip=viewer_ip
    )

@app.route('/send', methods=['POST'])
def send():
    channel = request.form.get('channel', 'general')
    text = request.form.get('text', '').strip()
    user_ip = get_client_ip()

    if text and channel in channels:
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        
        target_ip = None
        if text.startswith("/w "):
            parts = text.split(" ", 2)
            if len(parts) >= 3:
                target_ip = parts[1].strip()
                text = parts[2].strip()

        channels[channel].append({
            'time': timestamp,
            'ip': user_ip,
            'text': text,
            'target_ip': target_ip
        })
        
        if len(channels[channel]) > 30:
            channels[channel].pop(0)

    return redirect(url_for('view_channel', channel_name=channel))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
