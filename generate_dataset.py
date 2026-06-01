"""
Usage:
    
    python generate_dataset_faker.py --size small --friends 5
    python generate_dataset_faker.py --size medium --friends 5
    python generate_dataset_faker.py --size small --friends 20
    python generate_dataset_faker.py --size medium --friends 20

"""

import csv, random, argparse, time
from faker import Faker

fake = Faker()
random.seed(42)
Faker.seed(42)

SIZES = {"small": 1_000, "medium": 10_000}

AVG_POSTS_PER_PERSON  = 3
AVG_COMMENTS_PER_POST = 2
AVG_LIKES_PER_POST    = 4

def random_date(start_year=2018, end_year=2024):
    from datetime import datetime, timedelta
    start = datetime(start_year, 1, 1)
    end   = datetime(end_year, 12, 31)
    delta = end - start
    return (start + timedelta(days=random.randint(0, delta.days))).date()

def generate_persons(n):
    return [
        {
            "id":        i,
            "name":      fake.name(),
            "age":       random.randint(18, 70),
            "city":      fake.city(),
            "join_date": random_date(),
        }
        for i in range(1, n + 1)
    ]

def generate_friendships(n, avg_friends):
    edges = set()
    for pid in range(1, n + 1):
        k = max(1, min(avg_friends * 3, int(random.gauss(avg_friends, avg_friends // 3 + 1))))
        for _ in range(k):
            fid = random.randint(1, n)
            if fid != pid:
                edges.add((min(pid, fid), max(pid, fid)))
    return [{"person_id": a, "friend_id": b} for a, b in edges]

def generate_posts(n):
    posts = []
    post_id = 1
    for pid in range(1, n + 1):
        for _ in range(max(0, int(random.gauss(AVG_POSTS_PER_PERSON, 1)))):
            posts.append({
                "id":         post_id,
                "person_id":  pid,
                "content":    fake.sentence(nb_words=random.randint(6, 20)),
                "created_at": random_date(),
                "likes":      random.randint(0, 500),
            })
            post_id += 1
    return posts

def generate_comments(posts, n):
    comments = []
    cid = 1
    for post in posts:
        for _ in range(max(0, int(random.gauss(AVG_COMMENTS_PER_POST, 1)))):
            comments.append({
                "id":         cid,
                "post_id":    post["id"],
                "person_id":  random.randint(1, n),
                "text":       fake.sentence(nb_words=random.randint(4, 15)),
                "created_at": random_date(),
            })
            cid += 1
    return comments

def generate_likes(posts, n):
    rows = []
    for post in posts:
        k = max(0, int(random.gauss(AVG_LIKES_PER_POST, 2)))
        seen = set()
        for _ in range(k * 2):
            liker = random.randint(1, n)
            if liker != post["person_id"] and liker not in seen:
                seen.add(liker)
                rows.append({"person_id": liker, "post_id": post["id"]})
                if len(seen) >= k:
                    break
    return rows

def write_csv(filename, fieldnames, rows):
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Wrote {len(rows):>8,} rows  ->  {filename}")

def main():
    parser = argparse.ArgumentParser(description="Generate small/medium datasets using Faker")
    parser.add_argument("--size", choices=SIZES.keys(), default="small",
                        help="Dataset size: small (1k) or medium (10k)")
    parser.add_argument("--friends", type=int, default=5,
                        help="Average number of friends per person (default: 5)")
    args = parser.parse_args()

    n           = SIZES[args.size]
    avg_friends = args.friends
    prefix      = f"data_{args.size}_{avg_friends}_"

    print(f"\nGenerating '{args.size}' dataset ({n:,} persons, ~{avg_friends} friends) using Faker ...\n")
    t0 = time.time()

    persons     = generate_persons(n)
    posts       = generate_posts(n)
    comments    = generate_comments(posts, n)
    friendships = generate_friendships(n, avg_friends)
    likes       = generate_likes(posts, n)

    write_csv(f"{prefix}persons.csv",     ["id","name","age","city","join_date"],            persons)
    write_csv(f"{prefix}posts.csv",       ["id","person_id","content","created_at","likes"], posts)
    write_csv(f"{prefix}comments.csv",    ["id","post_id","person_id","text","created_at"],  comments)
    write_csv(f"{prefix}friendships.csv", ["person_id","friend_id"],                          friendships)
    write_csv(f"{prefix}likes.csv",       ["person_id","post_id"],                            likes)

    print(f"\nDone in {time.time()-t0:.1f}s")
    print(f"\nSummary:")
    for label, data in [("Persons", persons), ("Friendships", friendships),
                        ("Posts", posts), ("Comments", comments), ("Likes", likes)]:
        print(f"  {label:<15} {len(data):>8,}")

if __name__ == "__main__":
    main()