"""
Neo4j loader for the benchmark project.

Usage:
    python load_neo4j.py --size small --friends 5
    python load_neo4j.py --size medium --friends 5
    python load_neo4j.py --size large --friends 20

"""

import csv, time, argparse
from neo4j import GraphDatabase

NEO4J_URI      = "bolt://localhost:7687"
NEO4J_USER     = "neo4j"
NEO4J_PASSWORD = "neoPass"   # change to your Neo4j password

BATCH_SIZE = 500

def read_csv(filename):
    with open(filename, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def batches(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def run_batch(session, query, rows):
    session.run(query, rows=rows)

def clear_database(session):
    """Remove everything in batches to avoid memory issues."""
    while True:
        result = session.run(
            "MATCH (n) WITH n LIMIT 10000 DETACH DELETE n RETURN count(n) AS deleted"
        )
        deleted = result.single()["deleted"]
        print(f"  Deleted {deleted} nodes...")
        if deleted == 0:
            break
    print("  Cleared existing data")

def create_constraints(session):
    constraints = [
        "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Person)  REQUIRE p.id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Post)    REQUIRE p.id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Comment) REQUIRE c.id IS UNIQUE",
    ]
    for c in constraints:
        session.run(c)
    indexes = [
        "CREATE INDEX IF NOT EXISTS FOR (p:Person) ON (p.city)",
        "CREATE INDEX IF NOT EXISTS FOR (p:Person) ON (p.name)",
        "CREATE INDEX IF NOT EXISTS FOR (p:Post)   ON (p.created_at)",
    ]
    for idx in indexes:
        session.run(idx)
    print("  Constraints and indexes created")

def load_persons(session, rows):
    query = """
    UNWIND $rows AS row
    MERGE (p:Person {id: toInteger(row.id)})
    SET p.name      = row.name,
        p.age       = toInteger(row.age),
        p.city      = row.city,
        p.join_date = row.join_date
    """
    total = 0
    for batch in batches(rows, BATCH_SIZE):
        run_batch(session, query, batch)
        total += len(batch)
    print(f"  Loaded {total:>8,} Person nodes")

def load_posts(session, rows):
    query = """
    UNWIND $rows AS row
    MATCH (p:Person {id: toInteger(row.person_id)})
    MERGE (post:Post {id: toInteger(row.id)})
    SET post.content    = row.content,
        post.created_at = row.created_at,
        post.likes      = toInteger(row.likes)
    MERGE (p)-[:POSTED]->(post)
    """
    total = 0
    for batch in batches(rows, BATCH_SIZE):
        run_batch(session, query, batch)
        total += len(batch)
    print(f"  Loaded {total:>8,} Post nodes + POSTED relationships")

def load_comments(session, rows):
    query = """
    UNWIND $rows AS row
    MATCH (person:Person {id: toInteger(row.person_id)})
    MATCH (post:Post     {id: toInteger(row.post_id)})
    MERGE (c:Comment {id: toInteger(row.id)})
    SET c.text       = row.text,
        c.created_at = row.created_at
    MERGE (person)-[:COMMENTED]->(c)
    MERGE (post)-[:HAS_COMMENT]->(c)
    """
    total = 0
    for batch in batches(rows, BATCH_SIZE):
        run_batch(session, query, batch)
        total += len(batch)
    print(f"  Loaded {total:>8,} Comment nodes + relationships")

def load_friendships(session, rows):
    query = """
    UNWIND $rows AS row
    MATCH (a:Person {id: toInteger(row.person_id)})
    MATCH (b:Person {id: toInteger(row.friend_id)})
    MERGE (a)-[:KNOWS]->(b)
    MERGE (b)-[:KNOWS]->(a)
    """
    total = 0
    for batch in batches(rows, BATCH_SIZE):
        run_batch(session, query, batch)
        total += len(batch)
    print(f"  Loaded {total:>8,} KNOWS relationships")

def load_likes(session, rows):
    query = """
    UNWIND $rows AS row
    MATCH (p:Person {id: toInteger(row.person_id)})
    MATCH (post:Post {id: toInteger(row.post_id)})
    MERGE (p)-[:LIKES]->(post)
    """
    total = 0
    for batch in batches(rows, BATCH_SIZE):
        run_batch(session, query, batch)
        total += len(batch)
    print(f"  Loaded {total:>8,} LIKES relationships")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", choices=["small", "medium", "large"], default="small")
    parser.add_argument("--friends", type=int, default=5)
    args = parser.parse_args()

    prefix = f"data_{args.size}_{args.friends}_"
    print(f"\nLoading '{args.size}' dataset (~{args.friends} friends) into Neo4j ...\n")

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    with driver.session() as session:
        print("Setting up ...")
        clear_database(session)
        create_constraints(session)

        t0 = time.time()

        print("\nLoading nodes ...")
        load_persons(session,  read_csv(f"{prefix}persons.csv"))
        load_posts(session,    read_csv(f"{prefix}posts.csv"))
        load_comments(session, read_csv(f"{prefix}comments.csv"))

        print("\nLoading relationships ...")
        load_friendships(session, read_csv(f"{prefix}friendships.csv"))
        load_likes(session,       read_csv(f"{prefix}likes.csv"))

        print(f"\nDone in {time.time()-t0:.1f}s")

        print("\nNode counts:")
        for label in ["Person", "Post", "Comment"]:
            result = session.run(f"MATCH (n:{label}) RETURN count(n) AS c")
            print(f"  {label:<10} {result.single()['c']:>8,}")

        print("\nRelationship counts:")
        for rel in ["KNOWS", "POSTED", "HAS_COMMENT", "COMMENTED", "LIKES"]:
            result = session.run(f"MATCH ()-[r:{rel}]->() RETURN count(r) AS c")
            print(f"  {rel:<15} {result.single()['c']:>8,}")

    driver.close()

if __name__ == "__main__":
    main()
