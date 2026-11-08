#!/bin/sh
set -e
mkdir -p /data/logs
cat > /data/ckpool.conf <<CONF
{
"btcd": [{"url": "${BTC_HOST}:${BTC_PORT}", "auth": "${BTC_USER}", "pass": "${BTC_PASS}", "notify": false}],
"btcsolo": true,
"btcsig": "Mined by a solo miner on Umbrel",
"blockpoll": 100,
"update_interval": 30,
"serverurl": ["0.0.0.0:3333"],
"mindiff": 1,
"startdiff": 42,
"maxdiff": 0,
"logdir": "/data/logs"
}
CONF
ckpool -c /data/ckpool.conf &
sleep 3
exec python3 /app/server.py
