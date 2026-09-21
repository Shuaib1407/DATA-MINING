import pandas as pd
import psycopg2


BASE = r"C:\Users\Shuaib Ahmed\Downloads\data_2\data_2"

INPUT_FILE = BASE + r"\results\scored_candidates.csv"


print("Loading scored candidates...")

df = pd.read_csv(INPUT_FILE)

print(
    "Total scored candidates:",
    len(df)
)


# ------------------------------------------------------------
# FINAL MERGE THRESHOLD
# ------------------------------------------------------------

threshold = 0.50

matches = df[
    df["jaccard"] >= threshold
].copy()

print(
    "Matches at Jaccard >= 0.50:",
    len(matches)
)


# ------------------------------------------------------------
# CONNECT TO POSTGRES
# ------------------------------------------------------------

conn = psycopg2.connect(
    host="localhost",
    port=5432,
    database="postgres",
    user="admin",
    password="admin123"
)

cur = conn.cursor()

print("Connected to PostgreSQL.")


# ------------------------------------------------------------
# INSERT FINAL MATCH PAIRS
# ------------------------------------------------------------

print("Loading final match pairs...")

rows = [
    (
        str(row["notice_id_a"]),
        str(row["notice_id_b"]),
        float(row["jaccard"])
    )
    for _, row in matches.iterrows()
]

cur.executemany(
    """
    INSERT INTO final_match_pairs
        (notice_id_a, notice_id_b, jaccard)
    VALUES
        (%s, %s, %s)
    ON CONFLICT DO NOTHING
    """,
    rows
)

conn.commit()

print(
    "Inserted:",
    cur.rowcount
)


# ------------------------------------------------------------
# VERIFY
# ------------------------------------------------------------

cur.execute(
    "SELECT COUNT(*) FROM final_match_pairs"
)

count = cur.fetchone()[0]

print(
    "Final match pairs in PostgreSQL:",
    count
)


cur.close()
conn.close()

print("\nFINAL MATCH LOAD COMPLETE")