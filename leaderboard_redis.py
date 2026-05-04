import redis
import random
import time
import sys
import argparse
from collections import deque

# --- Default Connection Configuration ---
# These act as fallbacks if flags are not provided
DEFAULT_HOST = 'YOUR_SERVER_B_IP'
DEFAULT_PORT = 12000
DEFAULT_DB = 0
DEFAULT_KEY = 'global_leaderboard'

def get_client(host, port, db):
    try:
        client = redis.Redis(host=host, port=port, db=db, decode_responses=True)
        client.ping()
        return client
    except Exception as e:
        print(f"CRITICAL: Connection Failed to {host}:{port} DB:{db}\nError: {e}")
        sys.exit(1)

# --- Logic Functions ---

def update_score(client, key, player_id, increment):
    start_time = time.perf_counter()
    new_score = client.zincrby(key, increment, player_id)
    duration = (time.perf_counter() - start_time) * 1000
    print(f"Update: {player_id} | New Score: {int(new_score)} | Key: {key} | Latency: {duration:.3f}ms")

def get_stats(client, key, player_id):
    start_time = time.perf_counter()
    pipe = client.pipeline()
    pipe.zrevrank(key, player_id)
    pipe.zscore(key, player_id)
    res = pipe.execute()
    duration = (time.perf_counter() - start_time) * 1000
    
    rank = res[0] + 1 if res[0] is not None else "N/A"
    score = res[1] if res[1] is not None else 0
    print(f"Stats: {player_id} | Rank: #{rank} | Score: {int(score)} | Key: {key} | Latency: {duration:.3f}ms")

def show_top(client, key, n=10):
    start_time = time.perf_counter()
    top_n = client.zrevrange(key, 0, n-1, withscores=True)
    duration = (time.perf_counter() - start_time) * 1000
    
    print(f"\n--- TOP {n} PLAYERS (Key: {key}) ---")
    for i, (player, score) in enumerate(top_n, 1):
        print(f"#{i:<3} {player:<15} {int(score)}")
    print(f"Command Latency: {duration:.3f}ms\n")

def run_dashboard(client, key, updates, interval, vip_id):
    latency_history = deque(maxlen=20)
    try:
        while True:
            # Simulation Load
            for _ in range(updates):
                client.zincrby(key, random.randint(1, 100), f"p:{random.randint(1, 1000)}")

            # Data Retrieval & Latency Tracking
            start_time = time.perf_counter()
            top_10 = client.zrevrange(key, 0, 9, withscores=True)
            cmd_latency = (time.perf_counter() - start_time) * 1000
            latency_history.append(cmd_latency)
            
            # Silent fetch for VIP status
            res = client.pipeline().zrevrank(key, vip_id).zscore(key, vip_id).execute()
            v_rank = res[0] + 1 if res[0] is not None else "N/A"
            v_score = res[1] if res[1] is not None else 0

            # UI Render
            sys.stdout.write("\033[H\033[J") 
            print(f"=== LEADERBOARD: {key} (DB: {client.connection_pool.connection_kwargs['db']}) ===")
            for i, (p, s) in enumerate(top_10, 1):
                marker = " <--" if p == vip_id else ""
                print(f"#{i:<4} {p:<15} {int(s)}{marker}")
            print("=" * 45)
            print(f"VIP {vip_id}: Rank #{v_rank} | Score: {int(v_score)}")
            print(f"AVG READ LATENCY: {sum(latency_history)/len(latency_history):.3f} ms")
            print(f"CONFIG: {updates} writes/cycle | {interval}s refresh")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nExiting...")

# --- Main CLI Entry ---

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Redis Leaderboard Tool")
    
    # Global Connection Arguments
    parser.add_argument('--host', type=str, default=DEFAULT_HOST)
    parser.add_argument('--port', type=int, default=DEFAULT_PORT)
    parser.add_argument('--db', type=int, default=DEFAULT_DB, help="Redis Database Index (default: 0)")
    parser.add_argument('--key', type=str, default=DEFAULT_KEY, help="Leaderboard key name")

    subparsers = parser.add_subparsers(dest="command", help="Available sub-commands")

    # Command: Dashboard
    dash = subparsers.add_parser('dashboard')
    dash.add_argument('--updates', type=int, default=50)
    dash.add_argument('--interval', type=float, default=0.5)
    dash.add_argument('--vip', type=str, default='p:500')

    # Command: Update
    upd = subparsers.add_parser('update')
    upd.add_argument('id', type=str)
    upd.add_argument('value', type=int)

    # Command: Get
    get = subparsers.add_parser('get')
    get.add_argument('id', type=str)

    # Command: Top
    top = subparsers.add_parser('top')
    top.add_argument('--n', type=int, default=10)

    args = parser.parse_args()
    
    # Initialize Client
    r_client = get_client(args.host, args.port, args.db)

    if args.command == 'dashboard':
        run_dashboard(r_client, args.key, args.updates, args.interval, args.vip)
    elif args.command == 'update':
        update_score(r_client, args.key, args.id, args.value)
    elif args.command == 'get':
        get_stats(r_client, args.key, args.id)
    elif args.command == 'top':
        show_top(r_client, args.key, args.n)
    else:
        parser.print_help()
