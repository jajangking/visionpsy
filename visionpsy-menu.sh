#!/data/data/com.termux/files/usr/bin/bash
# VisionPsy launcher menu - TUI untuk Qwen3-VL-2B
DIR=~/visionpsy
HOST=127.0.0.1
API_PORT=8090
WEB_PORT=8091
LAN_IP=$(ip -4 addr show 2>/dev/null | grep -oP 'inet \K[\d.]+' | grep -v '^127\.' | head -1)
[ -z "$LAN_IP" ] && LAN_IP=$(ifconfig 2>/dev/null | grep -oP 'inet \K[\d.]+' | grep -v '^127\.' | head -1)
[ -z "$LAN_IP" ] && LAN_IP=127.0.0.1

GREEN="\033[32m"; RED="\033[31m"; YELLOW="\033[33m"; CYAN="\033[36m"; MAGENTA="\033[35m"
BOLD="\033[1m"; DIM="\033[2m"; RESET="\033[0m"

# --- Layout ---
W=44
if command -v tput >/dev/null 2>&1; then
    C=$(tput cols 2>/dev/null)
    if [ -n "$C" ] && [ "$C" -ge 36 ] && [ "$C" -le 72 ]; then W=$((C-4)); fi
fi
LINE="$(printf '═%.0s' $(seq 1 "$W"))"
SP=$(printf ' %.0s' $(seq 1 "$W"))

health() { curl -s -m 3 "http://$HOST:$API_PORT/health" 2>/dev/null | grep -q '"ok"'; }

kill_port() {
    local port=$1
    lsof -ti ":$port" 2>/dev/null | xargs -r kill 2>/dev/null \
        || fuser -k "${port}/tcp" 2>/dev/null
}

slot_info() {
    curl -s -m 3 "http://$HOST:$API_PORT/slots" 2>/dev/null | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    tot=len(d); busy=sum(1 for s in d if s.get('state')!='idle')
    proc=next((s for s in d if s.get('state')!='idle'),None)
    if proc:
        print(f'{busy}/{tot} memproses {proc.get(\"n_prompt_tokens_processed\",0)}/{proc.get(\"n_prompt_tokens\",\"?\")} token')
    else:
        print(f'{tot} slot siap')
except Exception:
    print('-')
" 2>/dev/null || echo "-"
}

sys_stats() {
    local memtotal memavail
    read -r memtotal memavail <<< "$(awk '/MemTotal|MemAvailable/{print $2}' /proc/meminfo | tr '\n' ' ')"
    local memu=$(( (memtotal - memavail) / 1024 )) memt=$(( memtotal / 1024 ))
    local load
    load=$(cut -d' ' -f1 /proc/loadavg 2>/dev/null || echo "-")
    local disk
    disk=$(df -h / 2>/dev/null | awk 'NR==2{printf "%s / %s", $3, $2}')
    echo "RAM ${memu}/${memt}G  ·  CPU ${load}  ·  Disk ${disk}"
}

server_status() {
    if health; then echo -e "${GREEN}● Server online${RESET}"; else echo -e "${RED}● Server offline${RESET}"; fi
}

start() {
    if health; then server_status; return 0; fi
    bash "$DIR/vision_server.sh" start
}

stop() {
    bash "$DIR/vision_server.sh" stop
}

web() {
    if health; then
        bash "$DIR/vision_server.sh" web
    else
        echo -e "${YELLOW}Server belum jalan.${RESET}"
        read -p "enter..."
    fi
}

cli() {
    if health; then
        python3 "$DIR/web/cli.py"
    else
        echo -e "${YELLOW}Server belum jalan.${RESET}"
    fi
}

query() {
    if [ -z "$1" ]; then echo "Usage: $(basename $0) query <gambar> [prompt]"; return 1; fi
    bash "$DIR/vision_server.sh" query "$1" "${2:-Apa isi gambar ini? Jelaskan secara detail.}"
}

switch_model() {
    echo
    echo -e "${BOLD}Model yang tersedia:${RESET}"
    local opts=($(ls -d $DIR/models/*/ 2>/dev/null | xargs -n1 basename))
    local cur=$(cat $DIR/models/current.txt 2>/dev/null)
    local i=1
    for m in "${opts[@]}"; do
        if [ "$m" == "$cur" ]; then echo "  $i) $m ${GREEN}(aktif)${RESET}"; else echo "  $i) $m"; fi
        i=$((i+1))
    done
    echo "  0) batal"
    echo
    read -p "pilih model: " sel
    [ "$sel" -ge 1 ] 2>/dev/null && [ "$sel" -le ${#opts[@]} ] || return 0
    local m=${opts[$((sel-1))]}
    [ "$m" == "$cur" ] && { echo -e "${DIM}masih model yang sama${RESET}"; return 0; }
    echo "$m" > $DIR/models/current.txt
    echo -e "${YELLOW}restart server dengan model $m...${RESET}"
    bash "$DIR/vision_server.sh" stop 2>/dev/null
    sleep 1
    bash "$DIR/vision_server.sh" start || echo "$cur" > $DIR/models/current.txt
}

bar_top() { echo -e "${CYAN}╔${LINE}╗${RESET}"; }
bar_bot() { echo -e "${CYAN}╚${LINE}╝${RESET}"; }
bar_sep() { echo -e "${CYAN}╠${LINE}╣${RESET}"; }

# panjang teks TANPA kode warna, akurat untuk unicode (diitung python3)
vlen() { python3 -c "import sys,re;print(len(re.sub(r'\x1b\[[0-9;]*m','',sys.argv[1])))" "$1"; }

# panj_mid "1" "Web UI"   -> baris menu satu item, rata kiri ke W
panj_mid() {
    local line="  ${BOLD}$1${RESET}) $2"
    printf "${CYAN}║${RESET}%b%*s${CYAN}║${RESET}\n" "$line" "$((W - $(vlen "$line")))" ""
}

# panj_lr "1" "Web UI" "2" "Chat CLI" -> dua item sebaris kiri/kanan
panj_lr() {
    local l="  ${BOLD}$1${RESET}) $2" r="${BOLD}$3${RESET}) $4"
    local pad=$((W - $(vlen "$l") - $(vlen "$r")))
    [ "$pad" -lt 2 ] && pad=2
    printf "${CYAN}║${RESET}%b%*s%b${CYAN}║${RESET}\n" "$l" "$pad" "" "$r"
}

menu() {
    if ! health; then
        echo -e "${YELLOW}Menyiapkan server...${RESET}"
        start
    fi
    while true; do
        clear
        local title=" QWEN3-VL-2B "
        local pad=$(( (W - ${#title}) / 2 ))
        local cur=$(cat $DIR/models/current.txt 2>/dev/null || echo "?")
        local st; st=$(server_status)

        bar_top
        printf "${CYAN}║${RESET}${BOLD}%*s%s%*s${CYAN}║${RESET}\n" "$pad" "" "$title" "$((W-pad-${#title}))" ""
        bar_sep
        local stline="  ${st}  ${DIM}${cur}${RESET}"
        printf "${CYAN}║${RESET}%b%*s${CYAN}║${RESET}\n" "$stline" "$((W - $(vlen "$stline")))" ""
        bar_sep
        panj_mid "1" "Web UI"
        panj_mid "2" "Chat CLI"
        panj_mid "3" "Query gambar"
        panj_mid "4" "Status"
        panj_mid "5" "Ganti model"
        panj_mid "0" "Keluar"
        bar_bot
        echo
        read -p "pilih: " opt
        case "$opt" in
            1) web ;;
            2) cli ;;
            3) read -p "path gambar: " img; query "$img" ;;
            4) server_status; sys_stats; echo -e "${DIM}slot: $(slot_info)${RESET}"
               echo -e "${DIM}web: http://${LAN_IP}:${WEB_PORT}${RESET}"; read -p "enter..." ;;
            5) switch_model;        read -p "enter..." ;;
            0|q) echo -e "${DIM}mematikan server...${RESET}"
                 stop
                 kill_port "$WEB_PORT"
                 echo -e "${DIM}server dimatikan.${RESET}"
                 break ;;
            *) ;;
        esac
    done
}

case "${1:-menu}" in
    start)      start ;;
    stop)       stop ;;
    status)     server_status ;;
    web)        web ;;
    cli)        cli ;;
    query)      query "$2" "$3" ;;
    *)          menu ;;
esac