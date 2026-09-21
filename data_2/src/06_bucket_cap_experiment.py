import pandas as pd
import psycopg2


CAPS = [50, 100, 150, 200, 300]

conn = psycopg2.connect(
    host="localhost",
    port=5432,
    database="postgres",
    user="admin",
    password="admin123"
)

cur = conn.cursor()

print("Loading filtered LSH buckets...")

cur.execute("""
    SELECT band, bucket_hash, notice_id
    FROM lsh_buckets_filtered
""")

rows = cur.fetchall()

buckets = {}

for band, bucket_hash, notice_id in rows:
    key = (band, bucket_hash)

    if key not in buckets:
        buckets[key] = []

    buckets[key].append(notice_id)

print("Buckets:", len(buckets))

# Build notice -> buckets mapping
notice_buckets = {}

for key, notice_ids in buckets.items():
    for notice_id in notice_ids:
        notice_buckets.setdefault(notice_id, []).append(key)

# Load trusted labelled pairs
pairs = pd.read_csv("labelled_pairs.csv")

print("Labelled pairs:", len(pairs))


def is_candidate(a, b, cap):
    keys_a = notice_buckets.get(a, [])
    keys_b = notice_buckets.get(b, [])

    shared = set(keys_a).intersection(keys_b)

    for key in shared:
        if len(buckets[key]) <= cap:
            return True

    return False


print("\n==============================================")
print("BUCKET CAP EXPERIMENT")
print("==============================================")

for cap in CAPS:

    same_total = 0
    same_retrieved = 0

    different_total = 0
    different_retrieved = 0

    for _, row in pairs.iterrows():

        a = row["notice_id_a"]
        b = row["notice_id_b"]
        label = row["label"]

        candidate = is_candidate(a, b, cap)

        if label == "same":

            same_total += 1

            if candidate:
                same_retrieved += 1

        elif label == "different":

            different_total += 1

            if candidate:
                different_retrieved += 1

    same_recall = (
        same_retrieved / same_total
        if same_total else 0
    )

    different_survival = (
        different_retrieved / different_total
        if different_total else 0
    )

    print(
        f"\nCAP = {cap}"
    )

    print(
        f"Same pairs retrieved: "
        f"{same_retrieved}/{same_total}"
    )

    print(
        f"Same-pair recall: "
        f"{same_recall:.4f}"
    )

    print(
        f"Different pairs retrieved: "
        f"{different_retrieved}/{different_total}"
    )

    print(
        f"Different-pair survival: "
        f"{different_survival:.4f}"
    )


cur.close()
conn.close()