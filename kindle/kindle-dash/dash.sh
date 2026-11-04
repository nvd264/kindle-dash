#!/bin/sh
# Weather dashboard for Kindle PW4 (jailbroken), launched by the scriptlets in documents/.
#   diag  - dump device info to the log (read it over USB)
#   once  - fetch and show the dashboard once, UI keeps running
#   start - stop the Kindle UI and refresh forever, suspending in between.
#   start screen - second screen for the PC (run pc/screen.py there first).
#           To exit either: hold the power button ~15s to reboot.
URL="https://nvd264.github.io/kindle-dash/dash.png" # fallback; GH cron on a public repo is delayed by hours
# shortcut: PC's LAN IP is hardcoded; reserve it in the router or edit here if it changes
SCREEN_URL="http://192.168.1.170:8765/screen.png"
LAN_URL="http://192.168.1.170:8766/dash.png" # pc/dashboard.py renders this every 5 min
INTERVAL=300 # seconds, matches the GitHub Actions cron (5 min)
LOG=/mnt/us/kindle-dash.log
IMG=/tmp/dash.png
PENDING=/tmp/kindle-dash.pending # lines written while /mnt/us is unmountable (USB drive mode)

# Buffer each line and flush to /mnt/us when it is writable: during USB drive mode the
# device has no /mnt/us, and silently lost log lines are what made the last crash invisible.
log() {
    echo "$(date '+%F %T') $*" >>"$PENDING"
    if [ -w /mnt/us ]; then
        cat "$PENDING" >>"$LOG" 2>/dev/null && : >"$PENDING"
    fi
}

wait_wifi() {
    lipc-set-prop com.lab126.cmd wirelessEnable 1
    i=0
    while [ "$(lipc-get-prop com.lab126.wifid cmState)" != CONNECTED ]; do
        i=$((i + 1))
        # wifid sometimes sticks in READY forever; bouncing the radio recovers it
        if [ $i -eq 15 ]; then
            log "wifi stuck at $(lipc-get-prop com.lab126.wifid cmState), bouncing radio"
            lipc-set-prop com.lab126.cmd wirelessEnable 0
            sleep 3
            lipc-set-prop com.lab126.cmd wirelessEnable 1
        fi
        [ $i -gt 45 ] && return 1
        sleep 1
    done
}

show() {
    log "show: waiting for wifi ($(lipc-get-prop com.lab126.wifid cmState))"
    # cmState is only advisory: probe with curl, since that is what we actually need
    wait_wifi || log "show: wifi $(lipc-get-prop com.lab126.wifid cmState), trying anyway"
    # LAN first (fresh every 5 min), Pages as fallback when the PC is unreachable
    src=""
    if curl -fsSL --max-time 10 -o "$IMG.new" "$LAN_URL"; then
        src=LAN
    # Pages' CDN caches for 10 min, so bust it or we re-show a stale frame
    elif curl -fsSL --max-time 45 -H 'Cache-Control: no-cache' -o "$IMG.new" "$URL?t=$(date +%s)"; then
        src=Pages
    fi
    if [ -n "$src" ]; then
        mv "$IMG.new" "$IMG"
        log "fetched via $src"
        eips -f -g "$IMG" || log "eips failed ($?)"
    else
        log "fetch failed (wifi: $(lipc-get-prop com.lab126.wifid cmState))"
        # never leave the panel blank: keep whatever frame is already on it
        [ -f "$IMG" ] && eips -f -g "$IMG"
    fi
    bat=$(lipc-get-prop com.lab126.powerd battLevel)
    log "battery $bat%"
    [ "$bat" -lt 20 ] && eips 0 0 "Pin yeu ($bat%) - hay sac"
}

suspend_until_next() {
    # shortcut: arms every RTC since we don't know which one wakes PW4; diag log tells
    for r in /sys/class/rtc/rtc*/wakealarm; do
        echo 0 >"$r"
        echo "+$INTERVAL" >"$r"
    done
    echo mem >/sys/power/state
}

case "$1" in
diag)
    {
        echo "== diag $(date)"
        id
        cat /etc/prettyversion.txt
        uname -a
        for r in /sys/class/rtc/rtc*; do echo "$r name=$(cat "$r/name") wakealarm=$(cat "$r/wakealarm")"; done
        for c in curl eips lipc-get-prop setsid initctl; do echo "$c: $(command -v $c)"; done
        echo "battery=$(lipc-get-prop com.lab126.powerd battLevel) wifi=$(lipc-get-prop com.lab126.wifid cmState)"
        initctl list | grep -i -E 'gui|framework|powerd'
        curl -sSI --max-time 30 "$URL" | head -1
    } >>"$LOG" 2>&1
    eips 0 0 "diag xong, xem kindle-dash.log"
    ;;
once)
    show
    ;;
start)
    mode=${2:-loop}
    # nohup keeps the loop alive when the GUI that launched it is stopped
    if command -v setsid >/dev/null; then
        setsid nohup sh "$0" "$mode" >>"$LOG" 2>&1 </dev/null &
    else
        nohup sh "$0" "$mode" >>"$LOG" 2>&1 </dev/null &
    fi
    ;;
loop)
    log "loop: start"
    lipc-set-prop com.lab126.powerd preventScreenSaver 1
    stop lab126_gui
    log "loop: gui stopped"
    sleep 5
    # draw something at once: stopping the GUI blanks the panel, and a crash in the
    # first fetch used to leave it blank for good
    [ -f "$IMG" ] || eips 0 0 "Dashboard: dang tai..."
    while true; do
        show
        sleep 10 # let the screen finish refreshing before suspend
        suspend_until_next
        log "loop: woke up"
    done
    ;;
screen)
    log "second screen started"
    lipc-set-prop com.lab126.powerd preventScreenSaver 1
    stop lab126_gui
    sleep 5
    n=0
    while true; do
        if curl -fs --max-time 5 -o "$IMG.new" "$SCREEN_URL" && ! cmp -s "$IMG.new" "$IMG"; then
            mv "$IMG.new" "$IMG"
            n=$((n + 1))
            # partial refreshes are fast but ghost; flash a full one every 30 frames
            if [ $((n % 30)) -eq 0 ]; then eips -f -g "$IMG"; else eips -g "$IMG"; fi
        fi
        sleep 1
    done
    ;;
esac
