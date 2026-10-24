#!/bin/sh
# Name: Tăng tốc (CPU tối đa, hết tác dụng khi khởi động lại)
# Author: kindle-dash
LOG=/mnt/us/kindle-dash.log
{
    echo "== speed $(date)"
    top -b -n 1 | head -20
    for c in /sys/devices/system/cpu/cpu*/cpufreq; do
        echo "$c: $(cat "$c/scaling_governor") of [$(cat "$c/scaling_available_governors")] $(cat "$c/scaling_cur_freq")/$(cat "$c/cpuinfo_max_freq") kHz"
        echo performance >"$c/scaling_governor"
    done
} >>"$LOG" 2>&1
eips 0 0 "CPU: $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor)"
