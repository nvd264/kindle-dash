#!/bin/sh
# Weather dashboard for Kindle PW4 (jailbroken), launched from KUAL.
#   diag  - dump device info to the log (read it over USB)
#   once  - fetch and show the dashboard once, UI keeps running
#   start - stop the Kindle UI and refresh forever, suspending in between.
#           To exit: hold the power button ~15s to reboot.
URL="https://nvd264.github.io/kindle-dash/dash.png"
INTERVAL=1800 # seconds, matches the GitHub Actions cron
LOG=/mnt/us/kindle-dash.log
IMG=/tmp/dash.png

log() { echo "$(date '+%F %T') $*" >>"$LOG"; }

wait_wifi() {
    lipc-set-prop com.lab126.cmd wirelessEnable 1
    i=0
    while [ "$(lipc-get-prop com.lab126.wifid cmState)" != CONNECTED ]; do
        i=$((i + 1))
        [ $i -gt 60 ] && return 1
        sleep 1
    done
}

show() {
    if wait_wifi && curl -fsSL --max-time 60 -o "$IMG.new" "$URL"; then
        mv "$IMG.new" "$IMG"
        eips -f -g "$IMG"
    else
        log "fetch failed (wifi: $(lipc-get-prop com.lab126.wifid cmState))"
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
    if command -v setsid >/dev/null; then setsid sh "$0" loop; else sh "$0" loop; fi >>"$LOG" 2>&1 </dev/null &
    ;;
loop)
    log "dashboard started"
    lipc-set-prop com.lab126.powerd preventScreenSaver 1
    stop lab126_gui
    sleep 5
    while true; do
        show
        sleep 10 # let the screen finish refreshing before suspend
        suspend_until_next
    done
    ;;
esac
