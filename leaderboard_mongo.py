import pymongo
import random
import time
import sys
import argparse
from collections import deque

# --- Default Connection Configuration ---
DEFAULT_URI = 'mongodb+srv://'
DEFAULT_DB = 'gaming_platform'
DEFAULT_COLL = 'global_leaderboard'

def get_client(uri):
    try:
        client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=2000)
        client.admin.command('ping') # Verify connection
        return client
    except Exception as e:
        print(f"CRITICAL: Connection Failed to {uri}\nError: {e}")
        sys.exit(1)

# --- Helper Logic ---

def get_rank(coll, score):
    """Simulates Redis ZREVRANK by counting docs with higher scores."""
    if score is None: return "N/A"
    # Rank = (Count of players with score > current) + 1
    count = coll.count_documents({"score": {"$gt": score}})
    return count + 1

# --- Logic Functions ---

def update_score(coll, player_id, increment):
    start_time = time.perf_counter()
    # Atomic increment using upsert
    res = coll.find_one_and_update(
        {"_id": player_id},
        {"$inc": {"score": increment}},
        upsert=True,
        return_document=pymongo.ReturnDocument.AFTER
    )
    duration = (time.perf_counter() - start_time) * 1000
    print(f"Update: {player_id} | New Score: {int(res['score'])} | Latency: {duration:.3f}ms")

def get_stats(coll, player_id):
    start_time = time.perf_counter()
    doc = coll.find_one({"_id": player_id})
    
    score = doc['score'] if doc else None
    rank = get_rank(coll, score)
    
    duration = (time.perf_counter() - start_time) * 1000
    print(f"Stats: {player_id} | Rank: #{rank} | Score: {int(score or 0)} | Latency: {duration:.3f}ms")

def show_top(coll, n=10):
    start_time = time.perf_counter()
    top_n = list(coll.find().sort("score", -1).limit(n))
    duration = (time.perf_counter() - start_time) * 1000
    
    print(f"\n--- TOP {n} PLAYERS (MongoDB) ---")
    for i, doc in enumerate(top_n, 1):
        print(f"#{i:<3} {doc['_id']:<15} {int(doc['score'])}")
    print(f"Command Latency: {duration:.3f}ms\n")

def run_dashboard(coll, updates, interval, vip_id):
    latency_history = deque(maxlen=20)
    # Ensure index exists for performance
    coll.create_index([("score", -1)])
    
    try:
        while True:
            # Simulation Load
            for _ in range(updates):
                p_id = f"p:{random.randint(1, 1000)}"
                coll.update_one({"_id": p_id}, {"$inc": {"score": random.randint(1, 100)}}, upsert=True)

            # Data Retrieval & Latency Tracking
            start_time = time.perf_counter()
            top_10 = list(coll.find().sort("score", -1).limit(10))
            cmd_latency = (time.perf_counter() - start_time) * 1000
            latency_history.append(cmd_latency)
            
            # Fetch VIP status
            v_doc = coll.find_one({"_id": vip_id})
            v_score = v_doc['score'] if v_doc else None
            v_rank = get_rank(coll, v_score)

            # UI Render
            print("\033[H\033[J") # Clear terminal screen
            print(f"=== MONGO LEADERBOARD: {coll.name} ===")
            for i, doc in enumerate(top_10, 1):
                marker = " <--" if doc["_id"] == vip_id else ""
                print(f"#{i:<4} {doc['_id']:<15} {int(doc['score'])}{marker}")
            print("=" * 45)
            print(f"VIP {vip_id}: Rank #{v_rank} | Score: {int(v_score or 0)}")
            print(f"AVG READ LATENCY: {sum(latency_history)/len(latency_history):.3f} ms")
            print(f"CONFIG: {updates} writes/cycle | {interval}s refresh")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nExiting...")

# --- Main CLI Entry ---

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MongoDB Leaderboard Tool")
    
    parser.add_argument('--uri', type=str, default=DEFAULT_URI)
    parser.add_argument('--db', type=str, default=DEFAULT_DB)
    parser.add_argument('--coll', type=str, default=DEFAULT_COLL)

    subparsers = parser.add_subparsers(dest="command", help="Available sub-commands")

    dash = subparsers.add_parser('dashboard')
    dash.add_argument('--updates', type=int, default=50)
    dash.add_argument('--interval', type=float, default=0.5)
    dash.add_argument('--vip', type=str, default='p:500')

    upd = subparsers.add_parser('update')
    upd.add_argument('id', type=str)
    upd.add_argument('value', type=int)

    get = subparsers.add_parser('get')
    get.add_argument('id', type=str)

    top = subparsers.add_parser('top')
    top.add_argument('--n', type=int, default=10)

    args = parser.parse_args()
    
    m_client = get_client(args.uri)
    m_coll = m_client[args.db][args.coll]

    if args.command == 'dashboard':
        run_dashboard(m_coll, args.updates, args.interval, args.vip)
    elif args.command == 'update':
        update_score(m_coll, args.id, args.value)
    elif args.command == 'get':
        get_stats(m_coll, args.id)
    elif args.command == 'top':
        show_top(m_coll, args.n)
    else:
        parser.print_help()