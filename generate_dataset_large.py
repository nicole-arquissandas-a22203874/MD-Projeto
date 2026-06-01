"""

Usage:
    python generate_dataset_fast.py --size large --friends 5
    python generate_dataset_fast.py --size large --friends 20

"""

import csv, random, argparse, time
random.seed(42)

SIZES = {"large": 100_000}

AVG_POSTS_PER_PERSON  = 3
AVG_COMMENTS_PER_POST = 2
AVG_LIKES_PER_POST    = 4

FIRST_NAMES = [
    "Alice","Bob","Carol","David","Emma","Frank","Grace","Hugo","Iris","Jack",
    "Karen","Leo","Mia","Noah","Olivia","Paul","Quinn","Rosa","Sam","Tina",
    "Uma","Victor","Wendy","Xavi","Yara","Zack","Ana","Bruno","Clara","Diego",
    "Elena","Filip","Gina","Hans","Ines","Jorge","Klara","Luis","Maria","Nuno",
    "Oscar","Petra","Rafael","Sofia","Tomas","Ursula","Vasco","Wanda","Xena","Yusuf"
]
LAST_NAMES = [
    "Smith","Jones","Brown","Wilson","Taylor","Davis","White","Clark","Lewis","Hall",
    "Young","King","Wright","Scott","Green","Adams","Baker","Hill","Moore","Lee",
    "Silva","Santos","Ferreira","Costa","Carvalho","Alves","Pereira","Rodrigues",
    "Martins","Sousa","Garcia","Lopez","Martinez","Sanchez","Gonzalez","Hernandez",
    "Müller","Schmidt","Weber","Meyer","Wagner","Becker","Hoffmann","Schulz","Koch"
]
CITIES = [
    "Lisbon","Porto","Madrid","Barcelona","London","Paris","Berlin","Rome",
    "Amsterdam","Vienna","Brussels","Zurich","Stockholm","Oslo","Copenhagen",
    "Warsaw","Prague","Budapest","Athens","Dublin","Helsinki","Riga","Tallinn",
    "Ljubljana","Bratislava","Zagreb","Belgrade","Sofia","Bucharest","Valletta"
]
WORDS = [
    "amazing","beautiful","interesting","important","great","fantastic","wonderful",
    "curious","exciting","surprising","delightful","brilliant","creative","inspiring",
    "thought","moment","life","world","people","things","time","place","day","night",
    "love","hope","dream","journey","story","future","past","change","idea","light",
    "just","really","always","never","sometimes","often","maybe","perhaps","today",
    "shared","posted","found","discovered","thinking","wondering","feeling","believe"
]

def random_sentence(min_w=6, max_w=18):
    words = [random.choice(WORDS) for _ in range(random.randint(min_w, max_w))]
    words[0] = words[0].capitalize()
    return " ".join(words) + "."

def random_date():
    return f"{random.randint(2018,2024)}-{random.randint(1,12):02d}-{random.randint(1,28):02d}"

def generate_persons(n):
    return [
        {
            "id":        i,
            "name":      f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}",
            "age":       random.randint(18, 70),
            "city":      random.choice(CITIES),
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
                "content":    random_sentence(),
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
                "text":       random_sentence(4, 12),
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
    parser = argparse.ArgumentParser(description="Generate large dataset using fast word lists")
    parser.add_argument("--size", choices=SIZES.keys(), default="large",
                        help="Dataset size: large (100k)")
    parser.add_argument("--friends", type=int, default=5,
                        help="Average number of friends per person (default: 5)")
    args = parser.parse_args()

    n           = SIZES[args.size]
    avg_friends = args.friends
    prefix      = f"data_{args.size}_{avg_friends}_"

    print(f"\nGenerating '{args.size}' dataset ({n:,} persons, ~{avg_friends} friends) using fast generator ...\n")
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