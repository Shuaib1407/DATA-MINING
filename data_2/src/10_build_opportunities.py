import pandas as pd
import psycopg2


BASE = r"C:\Users\Shuaib Ahmed\Downloads\data_2\data_2"


# ============================================================
# CONNECT
# ============================================================

conn = psycopg2.connect(
    host="localhost",
    port=5432,
    database="postgres",
    user="admin",
    password="admin123"
)

cur = conn.cursor()

print("Connected to PostgreSQL.")


# ============================================================
# LOAD NOTICES
# ============================================================

print("\nLoading notices...")

cur.execute("""
    SELECT notice_id, published_at
    FROM notices
    ORDER BY published_at, notice_id
""")

notice_rows = cur.fetchall()

notices = pd.DataFrame(
    notice_rows,
    columns=[
        "notice_id",
        "published_at"
    ]
)

print("Notices:", len(notices))


# ============================================================
# LOAD FINAL MATCH PAIRS
# ============================================================

print("\nLoading final match pairs...")

cur.execute("""
    SELECT notice_id_a, notice_id_b, jaccard
    FROM final_match_pairs
    ORDER BY jaccard DESC
""")

match_rows = cur.fetchall()

matches = pd.DataFrame(
    match_rows,
    columns=[
        "notice_id_a",
        "notice_id_b",
        "jaccard"
    ]
)

print("Match pairs:", len(matches))


# ============================================================
# BUILD DIRECT MATCH GRAPH
# ============================================================

neighbors = {}

for _, row in matches.iterrows():

    a = row["notice_id_a"]
    b = row["notice_id_b"]

    neighbors.setdefault(a, []).append(b)
    neighbors.setdefault(b, []).append(a)


# ============================================================
# CREATE STABLE OPPORTUNITIES
# ============================================================

print("\nCreating stable opportunities...")

assigned = {}

created_count = 0
reused_count = 0


# Process deterministically
for notice_id in notices["notice_id"]:

    if notice_id in assigned:
        continue

    # --------------------------------------------------------
    # Check whether this notice already has an opportunity
    # --------------------------------------------------------

    cur.execute("""
        SELECT opportunity_id
        FROM notice_opportunity
        WHERE notice_id = %s
    """, (notice_id,))

    existing = cur.fetchone()

    if existing:

        opportunity_id = existing[0]
        reused_count += 1

    else:

        # PostgreSQL generates UUID exactly ONCE.
        cur.execute("""
            INSERT INTO opportunities (
                canonical_notice_id
            )
            VALUES (%s)
            RETURNING opportunity_id
        """, (notice_id,))

        opportunity_id = cur.fetchone()[0]

        created_count += 1


    # Canonical notice
    assigned[notice_id] = opportunity_id


    # --------------------------------------------------------
    # Assign only direct matches to canonical notice
    # --------------------------------------------------------

    for candidate in neighbors.get(notice_id, []):

        if candidate in assigned:
            continue

        # Check whether candidate already has stable mapping
        cur.execute("""
            SELECT opportunity_id
            FROM notice_opportunity
            WHERE notice_id = %s
        """, (candidate,))

        candidate_existing = cur.fetchone()

        if candidate_existing:

            # Existing persistent mapping wins.
            assigned[candidate] = candidate_existing[0]

        else:

            assigned[candidate] = opportunity_id


# ============================================================
# INSERT NOTICE → OPPORTUNITY MAPPINGS
# ============================================================

print("\nSaving notice mappings...")

inserted = 0

for notice_id, opportunity_id in assigned.items():

    cur.execute("""
        INSERT INTO notice_opportunity (
            notice_id,
            opportunity_id
        )
        VALUES (%s, %s)
        ON CONFLICT (notice_id)
        DO NOTHING
    """, (
        notice_id,
        opportunity_id
    ))

    inserted += cur.rowcount


conn.commit()


# ============================================================
# RESULTS
# ============================================================

cur.execute("""
    SELECT COUNT(*)
    FROM opportunities
""")

opportunity_count = cur.fetchone()[0]


cur.execute("""
    SELECT COUNT(*)
    FROM notice_opportunity
""")

mapping_count = cur.fetchone()[0]


print("\n==========================================")
print("STABLE OPPORTUNITY ASSIGNMENT COMPLETE")
print("==========================================")

print(
    "Opportunities:",
    opportunity_count
)

print(
    "Notice mappings:",
    mapping_count
)

print(
    "New opportunity UUIDs created:",
    created_count
)

print(
    "Existing opportunities reused:",
    reused_count
)


cur.close()
conn.close()