# Part 2 — Real-Time Leaderboard Design & Implementation

## Overview

A real-time leaderboard system for a gaming company supporting **~1,000 concurrent users** with constantly updating scores, maintaining the **Top 10 players** at all times.

- **Language:** Python 3
- **Redis Target:** Redis Enterprise DB `migration-target` (Server B, port 12000)
- **Demo Type:** Terminal-based CLI dashboard + utility commands

---

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                      Leaderboard System                          │
│                                                                  │
│  ┌─────────────┐    ZINCRBY (score update)   ┌────────────────┐ │
│  │  Simulated  │ ──────────────────────────► │  Redis Sorted  │ │
│  │  ~1000      │                             │  Set           │ │
│  │  Players    │ ◄─────────────────────────  │  (global_      │ │
│  └─────────────┘    ZREVRANGE (top 10)        │  leaderboard)  │ │
│                     ZREVRANK + ZSCORE          └────────────────┘ │
│                     (player rank/score)                           │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │               CLI Dashboard (terminal)                   │   │
│  │   Real-time Top 10 │ VIP tracker │ Avg Read Latency      │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

---

## Assumptions & Scale Targets

| Parameter | Value |
|-----------|-------|
| Concurrent Users | ~1,000 (players `p:1` to `p:1000`) |
| Score Update Frequency | Configurable — default 50 writes/cycle |
| Leaderboard Size (Top-N) | Top 10 (configurable via `--n`) |
| Refresh Interval | Configurable — default 0.5s |
| Latency Target | < 5ms per operation |
| Redis Target | Redis Enterprise DB (port 12000) |
| Leaderboard Key | `global_leaderboard` (configurable via `--key`) |

---

## Data Model

### Redis Data Structure
**Sorted Set** — ideal for leaderboard use cases due to O(log N) inserts and O(log N + M) range queries.

### Key Design

| Key | Type | Description |
|-----|------|-------------|
| `global_leaderboard` | Sorted Set | Member = `p:<id>` (e.g. `p:500`), Score = cumulative player score |

### Redis Commands Used

| Operation | Command | Complexity |
|-----------|---------|------------|
| Update / increment player score | `ZINCRBY global_leaderboard <increment> <player_id>` | O(log N) |
| Get Top-N players (highest first) | `ZREVRANGE global_leaderboard 0 N-1 WITHSCORES` | O(log N + M) |
| Get player rank (1-indexed) | `ZREVRANK global_leaderboard <player_id>` | O(log N) |
| Get player score | `ZSCORE global_leaderboard <player_id>` | O(1) |
| Get total players | `ZCARD global_leaderboard` | O(1) |

### Example Commands

```bash
# Increment player p:500 score by 75
ZINCRBY global_leaderboard 75 p:500

# Get Top 10 players (highest scores first)
ZREVRANGE global_leaderboard 0 9 WITHSCORES

# Get player rank (0-indexed from Redis, displayed as 1-indexed in app)
ZREVRANK global_leaderboard p:500

# Get player score
ZSCORE global_leaderboard p:500

# Total players on leaderboard
ZCARD global_leaderboard
```

### Why Redis Sorted Sets?

| Feature | Benefit |
|---------|---------|
| O(log N) inserts/updates | Handles high-frequency score updates efficiently |
| Automatic ranking | No manual sorting — Redis maintains order by score |
| Atomic operations | `ZINCRBY` is atomic — safe for 1,000 concurrent users |
| Range queries | `ZREVRANGE` retrieves Top-N in O(log N + M) |
| Built-in rank retrieval | `ZREVRANK` gives instant player rank without scanning |
| Pipeline support | Rank + score fetched in a single round-trip via `pipeline()` |

### Alternatives Considered

| Alternative | Pros | Cons |
|-------------|------|------|
| SQL `ORDER BY` | Familiar, flexible | Slow for high-frequency writes + reads at scale |
| Redis Hash + Sort | Flexible schema | Requires manual sort — not atomic |
| Redis List | Simple | No built-in scoring or ranking |
| Redis Sorted Set ✅ | Atomic, O(log N), built-in rank | Best fit for this use case |

---

## Project Structure

```
redis-assignment-SA/
├── README-Part1.md
├── README-Part2.md
├── PROJECT_CONTEXT.md
├── leaderboard_redis.py      ← Part 2 implementation
├── requirements.txt          ← Python dependencies (redis>=5.0.0)
└── images/
    └── ...
```

---

## Prerequisites

### Step 1 — Verify Python is installed

```bash
python3 --version
# Expected: Python 3.7.x or higher
```

### Step 2 — (Optional but recommended) Create a virtual environment

```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate   # macOS / Linux
# .venv\Scripts\activate    # Windows
```

> Using a virtual environment keeps dependencies isolated from your system Python.

### Step 3 — Install dependencies

```bash
pip install -r requirements.txt
```

**`requirements.txt`:**
```
redis>=5.0.0
```

---

## Usage

### Connection Flags (Global — all commands)

| Flag | Default | Description |
|------|---------|-------------|
| `--host` | `YOUR_SERVER_B_IP` | Redis host |
| `--port` | `12000` | Redis port |
| `--db` | `0` | Redis database index |
| `--key` | `global_leaderboard` | Leaderboard sorted set key name |

---

### Command 1 — `dashboard` (Real-time live leaderboard)

Simulates ~1,000 concurrent players updating scores and displays a live-refreshing Top 10 leaderboard in the terminal.

```bash
python leaderboard_redis.py \
  --host <SERVER_B_IP> \
  --port 12000 \
  dashboard \
  --updates 50 \
  --interval 0.5 \
  --vip p:500
```

**Dashboard flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `--updates` | `50` | Number of random score writes per refresh cycle |
| `--interval` | `0.5` | Seconds between leaderboard refreshes |
| `--vip` | `p:500` | Player to track (highlighted with `<--` marker) |

**What the dashboard shows:**
- Live Top 10 players with scores, refreshed every `--interval` seconds
- VIP player rank and score tracked in real time
- Average `ZREVRANGE` read latency (rolling 20-sample window)
- Current config (writes/cycle, refresh interval)

**Sample output:**
```
=== LEADERBOARD: global_leaderboard (DB: 0) ===
#1   p:742           98432
#2   p:118           97891
#3   p:500           97203 <--
#4   p:33            96540
#5   p:881           95102
#6   p:212           94870
#7   p:456           93210
#8   p:99            92048
#9   p:300           91337
#10  p:667           90122
=============================================
VIP p:500: Rank #3 | Score: 97203
AVG READ LATENCY: 0.842 ms
CONFIG: 50 writes/cycle | 0.5s refresh
```

Press `Ctrl+C` to exit.

---

### Command 2 — `update` (Increment a player's score)

```bash
python leaderboard_redis.py \
  --host <SERVER_B_IP> \
  --port 12000 \
  update p:500 150
```

**Output:**
```
Update: p:500 | New Score: 97353 | Key: global_leaderboard | Latency: 0.812ms
```

---

### Command 3 — `get` (Get a player's rank and score)

```bash
python leaderboard_redis.py \
  --host <SERVER_B_IP> \
  --port 12000 \
  get p:500
```

**Output:**
```
Stats: p:500 | Rank: #3 | Score: 97353 | Key: global_leaderboard | Latency: 0.654ms
```

> Uses Redis `pipeline()` to fetch rank (`ZREVRANK`) and score (`ZSCORE`) in a single round-trip.

---

### Command 4 — `top` (Show Top-N players)

```bash
python leaderboard_redis.py \
  --host <SERVER_B_IP> \
  --port 12000 \
  top --n 10
```

**Output:**
```
--- TOP 10 PLAYERS (Key: global_leaderboard) ---
#1  p:742           98432
#2  p:118           97891
#3  p:500           97353
...
Command Latency: 0.731ms
```

---

## Demo — Run & Verification Steps

### Step 1 — Install dependencies on local machine or Server B

```bash
pip install redis
```

### Step 2 — Seed the leaderboard (run dashboard for a few seconds)

```bash
python leaderboard_redis.py --host <SERVER_B_IP> --port 12000 dashboard --updates 100 --interval 1 --vip p:1
# Let it run for 5–10 seconds, then Ctrl+C
```

### Step 3 — Verify correctness

```bash
# Check total player count
python leaderboard_redis.py --host <SERVER_B_IP> --port 12000 top --n 10

# Check a specific player
python leaderboard_redis.py --host <SERVER_B_IP> --port 12000 get p:500

# Update a player's score manually and verify rank changes
python leaderboard_redis.py --host <SERVER_B_IP> --port 12000 update p:500 999999
python leaderboard_redis.py --host <SERVER_B_IP> --port 12000 get p:500
# Expected: Rank #1
```

### Step 4 — Run the live dashboard

```bash
python leaderboard_redis.py --host <SERVER_B_IP> --port 12000 dashboard --updates 50 --interval 0.5 --vip p:500
```

Observe:
- Top 10 list updates every 0.5 seconds
- Scores incrementing in real time
- VIP player rank changing as scores shift
- Sub-millisecond average read latency

---

## Metrics to Monitor

| Metric | How to Measure | Expected Value |
|--------|---------------|----------------|
| Write latency (`ZINCRBY`) | Printed per `update` command | < 2ms |
| Read latency (`ZREVRANGE`) | Shown in dashboard AVG READ LATENCY | < 2ms |
| Rank + Score latency (pipeline) | Printed per `get` command | < 2ms |
| Ops/sec throughput | `redis-cli INFO stats` → `instantaneous_ops_per_sec` | High |
| Memory usage | `redis-cli INFO memory` → `used_memory_human` | Monitored |
| Connected clients | `redis-cli INFO clients` → `connected_clients` | ~1000 during load |
| Keyspace hits | `redis-cli INFO stats` → `keyspace_hits` | ~100% |

```bash
# Real-time Redis stats on Server B
redis-cli -h <SERVER_B_IP> -p 12000 INFO stats
redis-cli -h <SERVER_B_IP> -p 12000 INFO memory
redis-cli -h <SERVER_B_IP> -p 12000 INFO clients

# Monitor live commands
redis-cli -h <SERVER_B_IP> -p 12000 MONITOR

# Latency check
redis-cli -h <SERVER_B_IP> -p 12000 --latency
```

---

## Validation — Correctness & Performance

### Correctness Checks

```bash
# 1. Total players on leaderboard
redis-cli -h <SERVER_B_IP> -p 12000 ZCARD global_leaderboard

# 2. Top 10 sorted correctly (highest score first)
redis-cli -h <SERVER_B_IP> -p 12000 ZREVRANGE global_leaderboard 0 9 WITHSCORES

# 3. Player rank matches score position
redis-cli -h <SERVER_B_IP> -p 12000 ZREVRANK global_leaderboard p:500
redis-cli -h <SERVER_B_IP> -p 12000 ZSCORE global_leaderboard p:500

# 4. Score increment reflects immediately in rank
redis-cli -h <SERVER_B_IP> -p 12000 ZINCRBY global_leaderboard 9999999 p:500
redis-cli -h <SERVER_B_IP> -p 12000 ZREVRANK global_leaderboard p:500
# Expected: 0 (rank #1)
```

### Performance Validation

```bash
# Benchmark ZADD and ZRANGE against Redis Enterprise
redis-benchmark \
  -h <SERVER_B_IP> \
  -p 12000 \
  -c 50 \
  -n 100000 \
  -t zadd,zrange
```

---

## Redis Value — Why Redis for Leaderboards?

| Requirement | Redis Solution | Alternative |
|-------------|---------------|-------------|
| High-frequency score updates (1K users) | `ZINCRBY` — O(log N), atomic | SQL UPDATE — locks rows, slow at scale |
| Real-time Top-N ranking | `ZREVRANGE` — O(log N + M) | SQL ORDER BY — full table scan |
| Instant player rank lookup | `ZREVRANK` — O(log N) | SQL COUNT(*) — expensive |
| Concurrent safety | All sorted set ops are atomic | SQL needs transactions |
| Sub-millisecond latency | In-memory — < 1ms typical | SQL disk I/O — 5-50ms |

---

## Image References

All images are stored in the [`images/`](images/) folder.

| Image File | Description |
|------------|-------------|
| `images/leaderboard-dashboard.png` | Live dashboard screenshot showing Top 10 + VIP tracker |
| `images/leaderboard-update.png` | `update` command output |
| `images/leaderboard-get.png` | `get` command output showing rank + score |
| `images/leaderboard-top.png` | `top` command output |
