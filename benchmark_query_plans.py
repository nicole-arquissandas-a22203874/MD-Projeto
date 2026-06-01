"""
Query Plan Analysis Script
Runs EXPLAIN ANALYZE on PostgreSQL and PROFILE on Neo4j for selected queries.
This gives insight into HOW each database executes the query, not just how long it takes.

Usage:
    python query_plan_analysis.py

Make sure the correct large dataset is loaded before running.
Run twice: once with --friends 5 (for Q1a and Q2d) and once with --friends 20 (for Q2c).
Results are saved to query_plan_results.txt
"""

import psycopg2
from neo4j import GraphDatabase



PG_CONFIG = {
    "host":     "localhost",
    "port":     5432,
    "dbname":   "benchmark_db",
    "user":     "postgres",
    "password": "postgres",   # change to your PostgreSQL password
}

NEO4J_URI      = "bolt://localhost:7687"
NEO4J_USER     = "neo4j"
NEO4J_PASSWORD = "neoPass"   

# ── Queries to analyse ────────────────────────────────────────────────────────
# Three cases chosen based on benchmark results (large dataset):
# 1. Q2d with 5 friends  -> Neo4j wins by 115x  (best Neo4j result)
# 2. Q2c with 20 friends -> PostgreSQL wins by 393x (most counter-intuitive)
# 3. Q1a with 5 friends  -> PostgreSQL wins by 258x (simple lookup overhead)
# Make sure large dataset is loaded before running:
#   python load_neo4j.py --size large --friends 5   (for cases 1 and 3)
#   python load_neo4j.py --size large --friends 20  (for case 2)

QUERIES_TO_ANALYSE = [
    {
        "name": "Q1a - Lookup person by ID (large, 5 friends) — PostgreSQL wins 258x",
        "sql": "SELECT * FROM persons WHERE id = 1",
        "cypher": "MATCH (p:Person {id: 1}) RETURN p",
        "note": "Load large 5 friends dataset before running this query."
    },
    {
        "name": "Q2d - Posts liked by friends (large, 5 friends) — Neo4j wins 115x",
        "sql": """
            SELECT DISTINCT po.id, po.content
            FROM persons p
            JOIN friendships f  ON p.id = f.person_id
            JOIN likes l        ON f.friend_id = l.person_id
            JOIN posts po       ON l.post_id = po.id
            WHERE p.id = 1
        """,
        "cypher": """
            MATCH (p:Person {id: 1})-[:KNOWS]->(friend:Person)-[:LIKES]->(post:Post)
            RETURN DISTINCT post.id, post.content
        """,
        "note": "Load large 5 friends dataset before running this query."
    },
    {
        "name": "Q2c - Friends of friends of friends (large, 20 friends) — PostgreSQL wins 393x",
        "sql": """
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
        "cypher": """
            MATCH (p:Person {id: 1})-[:KNOWS*3]->(fofof:Person)
            WHERE fofof.id <> 1
            RETURN DISTINCT fofof.id, fofof.name
        """,
        "note": "Load large 20 friends dataset before running this query."
    },
]

# PostgreSQL plan analysis 

def analyse_pg(conn, sql, query_name):
    cur = conn.cursor()

    # EXPLAIN ANALYZE BUFFERS shows:
    # - actual execution time
    # - shared hit = pages served from cache (fast)
    # - shared read = pages read from disk (slow)
    # - whether it used Index Scan or Seq Scan
    explain_sql = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) {sql.strip()}"
    cur.execute(explain_sql)
    plan_rows = cur.fetchall()
    plan_text = "\n".join(row[0] for row in plan_rows)

    # Extract key metrics from plan
    total_time = None
    scan_types = []
    shared_hits = 0
    shared_reads = 0

    for line in plan_text.split("\n"):
        if "Execution Time:" in line:
            total_time = line.strip()
        if "Index Scan" in line or "Index Only Scan" in line:
            scan_types.append("Index Scan")
        if "Seq Scan" in line:
            scan_types.append("Seq Scan")
        if "Buffers:" in line and "shared hit=" in line:
            parts = line.strip().replace("Buffers: ", "")
            for part in parts.split():
                if part.startswith("hit="):
                    shared_hits += int(part.replace("hit=", "").replace(",",""))
                if part.startswith("read="):
                    shared_reads += int(part.replace("read=", "").replace(",",""))

    cur.close()
    return {
        "plan": plan_text,
        "total_time": total_time,
        "scan_types": list(set(scan_types)),
        "shared_hits": shared_hits,
        "shared_reads": shared_reads,
        "cache_ratio": round(shared_hits / (shared_hits + shared_reads) * 100, 1) if (shared_hits + shared_reads) > 0 else "N/A"
    }


# Neo4j plan analysis 

def analyse_neo4j(driver, cypher, query_name):
    # PROFILE prepended to a Cypher query returns the execution plan
    # with DbHits (number of graph records touched) and rows produced
    # at each step of the plan
    profile_cypher = f"PROFILE {cypher.strip()}"

    with driver.session() as session:
        result = session.run(profile_cypher)
        # Consume all results to get the profile summary
        records = list(result)
        summary = result.consume()

        # Extract plan information
        plan = summary.profile

        def extract_plan_info(node, depth=0):
            indent = "  " * depth
            if isinstance(node, dict):
                operator = node.get("operatorType", node.get("operator_type", "Unknown"))
                db_hits  = node.get("dbHits", node.get("db_hits", 0))
                rows     = node.get("rows", 0)
                children = node.get("children", [])
            else:
                operator = node.operator_type
                db_hits  = node.db_hits
                rows     = node.rows
                children = node.children
            info = f"{indent}{operator} | db_hits={db_hits} | rows={rows}"
            children_info = [extract_plan_info(c, depth + 1) for c in children]
            return info + ("\n" + "\n".join(children_info) if children_info else "")

        plan_text = extract_plan_info(plan)

        def total_db_hits(node):
            if isinstance(node, dict):
                hits     = node.get("dbHits", node.get("db_hits", 0))
                children = node.get("children", [])
            else:
                hits     = node.db_hits
                children = node.children
            return hits + sum(total_db_hits(c) for c in children)

        total_hits = total_db_hits(plan)

    return {
        "plan": plan_text,
        "total_db_hits": total_hits,
    }


# Main 

def main():
  


    pg_conn      = psycopg2.connect(**PG_CONFIG)
    neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    output_lines = []
    output_lines.append("QUERY PLAN ANALYSIS — Large Dataset")
    output_lines.append("=" * 70)

    for q in QUERIES_TO_ANALYSE:
        print(f"\n{'=' * 70}")
        print(f"Query: {q['name']}")
        print(f"{'=' * 70}")
        output_lines.append(f"\n{'=' * 70}")
        output_lines.append(f"Query: {q['name']}")
        output_lines.append(f"{'=' * 70}")

        # PostgreSQL analysis
        print("\n--- PostgreSQL EXPLAIN ANALYZE ---")
        pg_result = analyse_pg(pg_conn, q["sql"], q["name"])

        pg_summary = (
            f"  Execution time : {pg_result['total_time']}\n"
            f"  Scan types     : {', '.join(pg_result['scan_types']) if pg_result['scan_types'] else 'None detected'}\n"
            f"  Cache hits     : {pg_result['shared_hits']} pages\n"
            f"  Disk reads     : {pg_result['shared_reads']} pages\n"
            f"  Cache ratio    : {pg_result['cache_ratio']}%"
        )
        print(pg_summary)
        print("\nFull plan:")
        print(pg_result["plan"])

        output_lines.append("\n--- PostgreSQL EXPLAIN ANALYZE ---")
        output_lines.append(pg_summary)
        output_lines.append("\nFull plan:")
        output_lines.append(pg_result["plan"])

        # Neo4j analysis
        print("\n--- Neo4j PROFILE ---")
        neo4j_result = analyse_neo4j(neo4j_driver, q["cypher"], q["name"])

        neo4j_summary = (
            f"  Total DbHits   : {neo4j_result['total_db_hits']}\n"
            f"  (DbHits = number of graph records the engine touched)"
        )
        print(neo4j_summary)
        print("\nExecution plan:")
        print(neo4j_result["plan"])

        output_lines.append("\n--- Neo4j PROFILE ---")
        output_lines.append(neo4j_summary)
        output_lines.append("\nExecution plan:")
        output_lines.append(neo4j_result["plan"])

    pg_conn.close()
    neo4j_driver.close()

    # Save to file
    with open("query_plan_results.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))

    print(f"\n{'=' * 70}")
    print("Results saved to query_plan_results.txt")
    print("Use these results to discuss query internals in your report.")


if __name__ == "__main__":
    main()