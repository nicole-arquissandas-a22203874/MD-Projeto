"""
Benchmark script for PostgreSQL vs Neo4j performance comparison.

Usage:
    python benchmark.py --size small --friends 5
    python benchmark.py --size medium --friends 5
    python benchmark.py --size large --friends 5
    python benchmark.py --size small --friends 20
    python benchmark.py --size medium --friends 20
    python benchmark.py --size large --friends 20

Results saved to: results_{size}_{friends}.csv
"""

import time, csv, argparse
import psycopg2
from neo4j import GraphDatabase



PG_CONFIG = {
    "host":     "localhost",
    "port":     5432,
    "dbname":   "benchmark_db",
    "user":     "postgres",
    "password": "postgres",  
}

NEO4J_URI      = "bolt://localhost:7687"
NEO4J_USER     = "neo4j"
NEO4J_PASSWORD = "neoPass"

RUNS = 5   # number of times each query is run , so the result will be the average 



QUERIES = [

    # Q1: Simple lookups
    (
        "Q1a - lookup person by id",
        "SELECT * FROM persons WHERE id = 1",
        "MATCH (p:Person {id: 1}) RETURN p",
    ),
    (
        "Q1b - filter persons by age range",
        "SELECT * FROM persons WHERE age BETWEEN 20 AND 30",
        "MATCH (p:Person) WHERE p.age >= 20 AND p.age <= 30 RETURN p",
    ),
    (
        "Q1c - find persons in a city",
        "SELECT * FROM persons WHERE city = 'Lisbon'",
        "MATCH (p:Person) WHERE p.city = 'Lisbon' RETURN p",
    ),

    # Q2: Multihop traversals
    (
        "Q2a - friends of person (1 hop)",
        """
        SELECT p2.id, p2.name
        FROM persons p1
        JOIN friendships f ON p1.id = f.person_id
        JOIN persons p2    ON f.friend_id = p2.id
        WHERE p1.id = 1
        """,
        """
        MATCH (p:Person {id: 1})-[:KNOWS]->(friend:Person)
        RETURN friend.id, friend.name
        """,
    ),
    (
        "Q2b - friends of friends (2 hops)",
        """
        SELECT DISTINCT p3.id, p3.name
        FROM persons p1
        JOIN friendships f1 ON p1.id = f1.person_id
        JOIN persons p2     ON f1.friend_id = p2.id
        JOIN friendships f2 ON p2.id = f2.person_id
        JOIN persons p3     ON f2.friend_id = p3.id
        WHERE p1.id = 1 AND p3.id <> p1.id
        """,
        """
        MATCH (p:Person {id: 1})-[:KNOWS*2]->(fof:Person)
        WHERE fof.id <> 1
        RETURN DISTINCT fof.id, fof.name
        """,
    ),
    (
        "Q2c - friends of friends of friends (3 hops)",
        """
        SELECT DISTINCT p4.id, p4.name
        FROM persons p1
        JOIN friendships f1 ON p1.id = f1.person_id
        JOIN persons p2     ON f1.friend_id = p2.id
        JOIN friendships f2 ON p2.id = f2.person_id
        JOIN persons p3     ON f2.friend_id = p3.id
        JOIN friendships f3 ON p3.id = f3.person_id
        JOIN persons p4     ON f3.friend_id = p4.id
        WHERE p1.id = 1 AND p4.id <> p1.id
        """,
        """
        MATCH (p:Person {id: 1})-[:KNOWS*3]->(fofof:Person)
        WHERE fofof.id <> 1
        RETURN DISTINCT fofof.id, fofof.name
        """,
    ),
    (
        "Q2d - posts liked by friends",
        """
        SELECT DISTINCT po.id, po.content
        FROM persons p
        JOIN friendships f  ON p.id = f.person_id
        JOIN likes l        ON f.friend_id = l.person_id
        JOIN posts po       ON l.post_id = po.id
        WHERE p.id = 1
        """,
        """
        MATCH (p:Person {id: 1})-[:KNOWS]->(friend:Person)-[:LIKES]->(post:Post)
        RETURN DISTINCT post.id, post.content
        """,
    ),

    # Q3: Aggregations
    (
        "Q3a - count persons per city",
        """
        SELECT city, COUNT(*) AS total
        FROM persons
        GROUP BY city
        ORDER BY total DESC
        """,
        """
        MATCH (p:Person)
        RETURN p.city AS city, count(p) AS total
        ORDER BY total DESC
        """,
    ),
    (
        "Q3b - average likes per person",
        """
        SELECT p.id, p.name, AVG(po.likes) AS avg_likes
        FROM persons p
        JOIN posts po ON p.id = po.person_id
        GROUP BY p.id, p.name
        ORDER BY avg_likes DESC
        LIMIT 10
        """,
        """
        MATCH (p:Person)-[:POSTED]->(post:Post)
        RETURN p.id, p.name, avg(post.likes) AS avg_likes
        ORDER BY avg_likes DESC
        LIMIT 10
        """,
    ),
    (
        "Q3c - most connected persons (friend count)",
        """
        SELECT p.id, p.name, COUNT(f.friend_id) AS friend_count
        FROM persons p
        JOIN friendships f ON p.id = f.person_id
        GROUP BY p.id, p.name
        ORDER BY friend_count DESC
        LIMIT 10
        """,
        """
        MATCH (p:Person)-[:KNOWS]->(friend:Person)
        RETURN p.id, p.name, count(friend) AS friend_count
        ORDER BY friend_count DESC
        LIMIT 10
        """,
    ),
    (
        "Q3d - total comments per post (top 10)",
        """
        SELECT po.id, po.content, COUNT(c.id) AS comment_count
        FROM posts po
        JOIN comments c ON po.id = c.post_id
        GROUP BY po.id, po.content
        ORDER BY comment_count DESC
        LIMIT 10
        """,
        """
        MATCH (post:Post)-[:HAS_COMMENT]->(c:Comment)
        RETURN post.id, post.content, count(c) AS comment_count
        ORDER BY comment_count DESC
        LIMIT 10
        """,
    ),
]

# Timing helpers

def time_pg_query(conn, sql, runs=RUNS):
    times = []
    cur = conn.cursor()
    for _ in range(runs):
        t0 = time.perf_counter()
        cur.execute(sql)
        cur.fetchall()
        times.append(time.perf_counter() - t0)
    cur.close()
    return sum(times) / len(times)


def time_neo4j_query(driver, cypher, runs=RUNS):
    times = []
    with driver.session() as session:
        for _ in range(runs):
            t0 = time.perf_counter()
            result = session.run(cypher)
            result.data()
            times.append(time.perf_counter() - t0)
    return sum(times) / len(times)



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", choices=["small", "medium", "large"], default="small")
    parser.add_argument("--friends", type=int, default=5,
                        help="Average friends per person used when loading (default: 5)")
    args = parser.parse_args()

    print(f"\nRunning benchmark on '{args.size}' dataset (~{args.friends} friends) ...\n")
    print(f"Each query averaged over {RUNS} runs.\n")
    print(f"{'Query':<45} {'PostgreSQL (s)':>15} {'Neo4j (s)':>12} {'Winner':>10}")
    print("-" * 88)

    pg_conn      = psycopg2.connect(**PG_CONFIG)
    neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    results = []

    for name, sql, cypher in QUERIES:
        pg_time    = time_pg_query(pg_conn, sql.strip())
        neo4j_time = time_neo4j_query(neo4j_driver, cypher.strip())
        winner     = "PostgreSQL" if pg_time < neo4j_time else "Neo4j"

        print(f"{name:<45} {pg_time:>15.4f} {neo4j_time:>12.4f} {winner:>10}")

        results.append({
            "size":       args.size,
            "friends":    args.friends,
            "query":      name,
            "pg_time":    round(pg_time, 6),
            "neo4j_time": round(neo4j_time, 6),
            "winner":     winner,
        })

    pg_conn.close()
    neo4j_driver.close()

    output_file = f"results_{args.size}_{args.friends}.csv"
    with open(output_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["size","friends","query","pg_time","neo4j_time","winner"])
        writer.writeheader()
        writer.writerows(results)

    print(f"\nResults saved to {output_file}")


if __name__ == "__main__":
    main()