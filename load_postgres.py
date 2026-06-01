"""

Usage:
    python load_postgres.py --size small --friends 5
    ython load_postgres.py --size medium --friends 5
    python load_postgres.py --size large --friends 20
"""

import csv, time, argparse
import psycopg2
from psycopg2.extras import execute_batch

DB_CONFIG = {
    "host":     "localhost",
    "port":     5432,
    "dbname":   "benchmark_db",
    "user":     "postgres",
    "password": "postgres",   
}

CREATE_TABLES = """
DROP TABLE IF EXISTS likes       CASCADE;
DROP TABLE IF EXISTS comments    CASCADE;
DROP TABLE IF EXISTS posts       CASCADE;
DROP TABLE IF EXISTS friendships CASCADE;
DROP TABLE IF EXISTS persons     CASCADE;

CREATE TABLE persons (
    id        INTEGER PRIMARY KEY,
    name      TEXT    NOT NULL,
    age       INTEGER,
    city      TEXT,
    join_date DATE
);
CREATE TABLE posts (
    id         INTEGER PRIMARY KEY,
    person_id  INTEGER REFERENCES persons(id),
    content    TEXT,
    created_at DATE,
    likes      INTEGER DEFAULT 0
);
CREATE TABLE comments (
    id         INTEGER PRIMARY KEY,
    post_id    INTEGER REFERENCES posts(id),
    person_id  INTEGER REFERENCES persons(id),
    text       TEXT,
    created_at DATE
);
CREATE TABLE friendships (
    person_id  INTEGER REFERENCES persons(id),
    friend_id  INTEGER REFERENCES persons(id),
    PRIMARY KEY (person_id, friend_id)
);
CREATE TABLE likes (
    person_id  INTEGER REFERENCES persons(id),
    post_id    INTEGER REFERENCES posts(id),
    PRIMARY KEY (person_id, post_id)
);
"""

CREATE_INDEXES = """
CREATE INDEX idx_posts_person       ON posts(person_id);
CREATE INDEX idx_comments_post      ON comments(post_id);
CREATE INDEX idx_comments_person    ON comments(person_id);
CREATE INDEX idx_friendships_friend ON friendships(friend_id);
CREATE INDEX idx_likes_post         ON likes(post_id);
CREATE INDEX idx_persons_city       ON persons(city);
CREATE INDEX idx_persons_name       ON persons(name);
"""

def read_csv(filename):
    with open(filename, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def load_table(cur, table, rows, columns, batch_size=1000):
    placeholders = ", ".join(["%s"] * len(columns))
    col_names    = ", ".join(columns)
    sql  = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
    data = [tuple(row[c] if row[c] != "" else None for c in columns) for row in rows]
    execute_batch(cur, sql, data, page_size=batch_size)
    print(f"  Loaded {len(rows):>8,} rows into {table}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", choices=["small", "medium", "large"], default="small")
    parser.add_argument("--friends", type=int, default=5)
    args = parser.parse_args()

    prefix = f"data_{args.size}_{args.friends}_"
    print(f"\nLoading '{args.size}' dataset (~{args.friends} friends) into PostgreSQL ...\n")

    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False
    cur = conn.cursor()

    print("Creating schema ...")
    cur.execute(CREATE_TABLES)
    conn.commit()

    t0 = time.time()

    load_table(cur, "persons",     read_csv(f"{prefix}persons.csv"),     ["id","name","age","city","join_date"])
    load_table(cur, "posts",       read_csv(f"{prefix}posts.csv"),       ["id","person_id","content","created_at","likes"])
    load_table(cur, "comments",    read_csv(f"{prefix}comments.csv"),    ["id","post_id","person_id","text","created_at"])
    load_table(cur, "friendships", read_csv(f"{prefix}friendships.csv"), ["person_id","friend_id"])
    load_table(cur, "likes",       read_csv(f"{prefix}likes.csv"),       ["person_id","post_id"])
    conn.commit()

    print("\nCreating indexes ...")
    cur.execute(CREATE_INDEXES)
    conn.commit()

    print(f"\nDone in {time.time()-t0:.1f}s")

    print("\nRow counts:")
    for table in ["persons","friendships","posts","comments","likes"]:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        print(f"  {table:<15} {cur.fetchone()[0]:>8,}")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()