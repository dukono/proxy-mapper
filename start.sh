#!/bin/bash
cd "$(dirname "$0")"
SCRIPT_DIR="$(pwd)"

# Crear venv si no existe
if [ ! -d "venv" ]; then
    python3 -m venv venv
    venv/bin/pip install -r requirements.txt
fi

# Instalar / actualizar entrada en el launcher de escritorio
DESKTOP_FILE="$HOME/.local/share/applications/proxymonitor.desktop"
mkdir -p "$HOME/.local/share/applications"
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Proxy Monitor
Comment=Interceptación y manipulación de tráfico HTTP/HTTPS
Exec=$SCRIPT_DIR/start.sh
Icon=$SCRIPT_DIR/ico.png
Terminal=false
Categories=Development;Network;
StartupNotify=true
StartupWMClass=main.py
EOF
chmod +x "$DESKTOP_FILE"

venv/bin/python3 main.py
