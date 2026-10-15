import os
from flask import Flask, request, render_template_string, redirect, url_for

app = Flask(__name__)

# In-memory database storing channel messages and active users
channels = {
    "general": [],
    "lounge": []
}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>IRC Lightweight Chat</title>
    <!-- Auto-refreshes every 6 seconds for regular browsers -->
    <meta http-equiv="refresh" content="6">
</head>
<body style="font-family: monospace; padding: 10px; background-color: #f4f4f4;">
    <h2>Minimal IRC Chat</h2>
    <p>
        <strong>Channels:</strong> 
        <a href="/channel/general">[ #general ]</a> | 
        <a href="/channel/lounge">[ #lounge ]</a>
    </p>
    <p><a href="/channel/{{ current_channel }}">[ Refresh Messages ]</a></p>
    <hr>

    <h3>Active Channel: #{{ current_channel }}</h3>

    <!-- Chat Output Box -->
    <div style="background-color: #fff; border: 1px solid #ccc; padding: 10px; min-height: 200px;">
        {% for msg in messages %}
            <p style="margin: 3px 0;">
                <span style="color: #888;">[{{ msg.time }}]</span> 
                <strong>&lt;{{ msg.sender }}&gt;</strong> {{ msg.text }}
            </p>
        {% else %}
            <p><em>No messages in #{{ current_channel }} yet. Say hi!</em></p>
        {% endfor %}
    </div>

    <hr>

    <!-- Message Form (No JavaScript Needed) -->
    <form action="/send" method="POST">
        <input type="hidden" name="channel" value="{{ current_channel }}">
        <p>
            <label><strong>Nickname:</strong></label><br>
            <input type="text" name="sender" value="{{ default_sender }}" placeholder="User123" required>
        </p>
        <p>
            <label><strong>Message:</strong></label><br>
            <input type="text" name="text" placeholder="Type a message..." required style="width: 80%;">
        </p>
        <p>
            <input type="submit" value="[ Send Message ]">
        </p>
    </form>
</body>
</html>
"""

@app.route('/')
def index():
    return redirect(url_for('view_channel', channel_name='general'))

@app.route('/channel/<channel_name>')
def view_channel(channel_name):
    if channel_name not in channels:
        channels[channel_name] = []
    
    sender_cookie = request.args.get('sender', 'Guest')
    
    return render_template_string(
        HTML_TEMPLATE, 
        current_channel=channel_name, 
        messages=channels[channel_name],
        default_sender=sender_cookie
    )

@app.route('/send', methods=['POST'])
def send():
    channel = request.form.get('channel', 'general')
    sender = request.form.get('sender', 'Anonymous').strip()
    text = request.form.get('text', '').strip()

    if text and channel in channels:
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M")
        
        # Keep channel buffer lightweight (last 20 messages)
        channels[channel].append({
            'time': timestamp,
            'sender': sender,
            'text': text
        })
        if len(channels[channel]) > 20:
            channels[channel].pop(0)

    return redirect(url_for('view_channel', channel_name=channel, sender=sender))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)