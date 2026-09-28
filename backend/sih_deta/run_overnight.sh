#!/bin/bash
# ==============================================================================
# SIH-DETA: Autonomous Overnight Historical Delay Crawler Launcher
# Backed by Beacon Supervisor with Auto-Heal & Deadlock-Killing Watchdog
# ==============================================================================

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/Historical-Delay-Records"
cd "$DIR" || exit 1

# Ensure logs and data directories exist
mkdir -p logs data

# Kill any existing stale supervisor or crawler processes cleanly
pkill -f "python3.*supervisor.py" 2>/dev/null
pkill -f "python3.*main.py --mode batch" 2>/dev/null
sleep 1

# Launch the Beacon Supervisor detached in the background
nohup python3 -u supervisor.py --phase auto > logs/supervisor_launch.log 2>&1 &
SUPERVISOR_PID=$!

echo "================================================================================"
echo "  🚀 AUTONOMOUS BEACON SUPERVISOR LAUNCHED IN BACKGROUND (PID: $SUPERVISOR_PID)"
echo "================================================================================"
echo "  • Crawling Mode:      Phase 1 (90-Day ?d=3m) -> Phase 2 (1-Year ?d=1y)"
echo "  • Beacon Heartbeat:   Historical-Delay-Records/data/crawler_beacon.json"
echo "  • Activity Log:       Historical-Delay-Records/logs/crawler.log"
echo "  • Supervisor Log:     Historical-Delay-Records/logs/supervisor.log"
echo "  • Checkpoint State:   Historical-Delay-Records/data/checkpoint.json"
echo "================================================================================"
echo "  🛡️  MURPHY'S LAW PROTECTIONS ACTIVE:"
echo "      - Network drop auto-pause & resume"
echo "      - 90s stall deadlock kill & respawn"
echo "      - Non-interactive /dev/null stdin clamp"
echo "      - SQLite WAL mode 60s busy timeout"
echo "================================================================================"
echo "  You may now safely close your laptop or disconnect SSH."
echo "================================================================================"
