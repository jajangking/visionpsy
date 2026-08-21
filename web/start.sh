#!/bin/bash
PORT="${1:-8091}"
setsid nohup python3 "$HOME/visionpsy/web/server.py" "$PORT" >> "$HOME/visionpsy-web.log" 2>&1 < /dev/null &
disown
echo "web+search proxy started on :$PORT pid $!"