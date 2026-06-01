"""

Usage:
    
    python analyse_results.py


Outputs:
    chart1_scaling_by_size.png       - How each DB scales with dataset size
    chart2_traversal_vs_friends.png  - Q2 performance vs connectivity
    chart3_query_heatmap.png         - Winner heatmap across all scenarios
    chart4_q2d_crossover.png         - Q2d crossover point analysis
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import os



SIZES   = ["small", "medium", "large"]
FRIENDS = [5, 10, 15, 20]
SIZE_LABELS = {"small": "Small\n(1k)", "medium": "Medium\n(10k)", "large": "Large\n(100k)"}

def load_all():
    dfs = []
    for size in SIZES:
        for f in FRIENDS:
            fname = f"results_{size}_{f}.csv"
            if os.path.exists(fname):
                df = pd.read_csv(fname)
                dfs.append(df)
    return pd.concat(dfs, ignore_index=True)

df = load_all()
print(f"Loaded {len(df)} result rows from {df.groupby(['size','friends']).ngroups} files\n")

# Clean query names for charts
df["query_short"] = df["query"].str.replace(r"Q\d+\w? - ", "", regex=True)

# Size order
size_order   = ["small", "medium", "large"]
size_n       = {"small": "1k", "medium": "10k", "large": "100k"}

PG_COLOR    = "#534AB7"
NEO_COLOR   = "#1D9E75"
GRAY        = "#888780"

plt.rcParams.update({
    "font.family":  "sans-serif",
    "font.size":    11,
    "axes.spines.top":   False,
    "axes.spines.right": False,
})

# Chart 1: Scaling by dataset size (5 friends, Q2 queries)

fig, axes = plt.subplots(1, 3, figsize=(15, 5), sharey=False)
fig.suptitle("Chart 1 — Traversal Query Scaling by Dataset Size (5 friends)", 
             fontsize=14, fontweight="bold", y=1.02)

traversal_queries = ["Q2b - friends of friends (2 hops)",
                     "Q2c - friends of friends of friends (3 hops)",
                     "Q2d - posts liked by friends"]

for ax, query in zip(axes, traversal_queries):
    data = df[(df["friends"] == 5) & (df["query"] == query)]
    data = data.set_index("size").reindex(size_order)

    x = np.arange(len(size_order))
    width = 0.35

    bars_pg  = ax.bar(x - width/2, data["pg_time"],    width, label="PostgreSQL", color=PG_COLOR,  alpha=0.85)
    bars_neo = ax.bar(x + width/2, data["neo4j_time"], width, label="Neo4j",      color=NEO_COLOR, alpha=0.85)

    ax.set_xticks(x)
    ax.set_xticklabels([size_n[s] for s in size_order])
    ax.set_xlabel("Dataset size (people)")
    ax.set_ylabel("Avg execution time (s)")
    ax.set_title(query.split(" - ")[1].capitalize(), fontsize=10, fontweight="bold")
    ax.legend(fontsize=9)

plt.tight_layout()
plt.savefig("chart1_scaling_by_size.png", dpi=150, bbox_inches="tight")
plt.close()
print("Saved chart1_scaling_by_size.png")

#Chart 2: Q2 traversal performance vs connectivity (large dataset)

fig, axes = plt.subplots(1, 3, figsize=(15, 5), sharey=False)
fig.suptitle("Chart 2 — Traversal Performance vs Graph Connectivity (Large dataset, 100k people)",
             fontsize=14, fontweight="bold", y=1.02)

for ax, query in zip(axes, traversal_queries):
    data = df[(df["size"] == "large") & (df["query"] == query)]
    data = data.sort_values("friends")

    ax.plot(data["friends"], data["pg_time"],    "o-", color=PG_COLOR,  linewidth=2, 
            markersize=8, label="PostgreSQL")
    ax.plot(data["friends"], data["neo4j_time"], "s-", color=NEO_COLOR, linewidth=2, 
            markersize=8, label="Neo4j")

    ax.set_xlabel("Avg friends per person")
    ax.set_ylabel("Avg execution time (s)")
    ax.set_title(query.split(" - ")[1].capitalize(), fontsize=10, fontweight="bold")
    ax.set_xticks(FRIENDS)
    ax.legend(fontsize=9)
    ax.axvspan(5, 10, alpha=0.08, color=NEO_COLOR, label="Neo4j wins")

plt.tight_layout()
plt.savefig("chart2_traversal_vs_friends.png", dpi=150, bbox_inches="tight")
plt.close()
print("Saved chart2_traversal_vs_friends.png")

#  Chart 3: Winner map

fig, axes = plt.subplots(1, 3, figsize=(18, 6))
fig.suptitle("Chart 3 — Winner Heatmap: PostgreSQL vs Neo4j Across All Scenarios",
             fontsize=14, fontweight="bold", y=1.02)

query_order = df["query"].unique().tolist()
query_short = [q.split(" - ")[1].capitalize() for q in query_order]

for ax, size in zip(axes, size_order):
    matrix = []
    for query in query_order:
        row = []
        for f in FRIENDS:
            subset = df[(df["size"] == size) & 
                       (df["friends"] == f) & 
                       (df["query"] == query)]
            if len(subset) > 0:
                winner = subset["winner"].values[0]
                row.append(0 if winner == "PostgreSQL" else 1)
            else:
                row.append(-1)
        matrix.append(row)

    matrix = np.array(matrix)
    cmap = plt.cm.colors.ListedColormap([PG_COLOR, NEO_COLOR])
    im = ax.imshow(matrix, cmap=cmap, vmin=0, vmax=1, aspect="auto")

    ax.set_xticks(range(len(FRIENDS)))
    ax.set_xticklabels([f"{f} friends" for f in FRIENDS], fontsize=9)
    ax.set_yticks(range(len(query_short)))
    ax.set_yticklabels(query_short, fontsize=8)
    ax.set_title(f"{size.capitalize()} ({size_n[size]} people)", 
                fontweight="bold", fontsize=11)

    # Add text labels
    for i in range(len(query_order)):
        for j in range(len(FRIENDS)):
            text = "PG" if matrix[i,j] == 0 else "Neo4j"
            color = "white"
            ax.text(j, i, text, ha="center", va="center", 
                   fontsize=8, color=color, fontweight="bold")

pg_patch  = mpatches.Patch(color=PG_COLOR,  label="PostgreSQL wins")
neo_patch = mpatches.Patch(color=NEO_COLOR, label="Neo4j wins")
fig.legend(handles=[pg_patch, neo_patch], loc="lower center", 
          ncol=2, fontsize=11, bbox_to_anchor=(0.5, -0.02))

plt.tight_layout()
plt.savefig("chart3_winner_heatmap.png", dpi=150, bbox_inches="tight")
plt.close()
print("Saved chart3_winner_heatmap.png")

# Chart 4: Q2d crossover point 

fig, axes = plt.subplots(1, 3, figsize=(15, 5), sharey=False)
fig.suptitle("Chart 4 — Q2d (Posts Liked by Friends) Crossover Point Across Dataset Sizes",
             fontsize=14, fontweight="bold", y=1.02)

for ax, size in zip(axes, size_order):
    data = df[(df["size"] == size) & 
              (df["query"] == "Q2d - posts liked by friends")].sort_values("friends")

    ax.plot(data["friends"], data["pg_time"],    "o-", color=PG_COLOR,  
            linewidth=2, markersize=8, label="PostgreSQL")
    ax.plot(data["friends"], data["neo4j_time"], "s-", color=NEO_COLOR, 
            linewidth=2, markersize=8, label="Neo4j")

    ax.set_xlabel("Avg friends per person")
    ax.set_ylabel("Avg execution time (s)")
    ax.set_title(f"{size.capitalize()} ({size_n[size]} people)", 
                fontweight="bold", fontsize=11)
    ax.set_xticks(FRIENDS)
    ax.legend(fontsize=9)

plt.tight_layout()
plt.savefig("chart4_q2d_crossover.png", dpi=150, bbox_inches="tight")
plt.close()
print("Saved chart4_q2d_crossover.png")

print("\nAll charts saved! Use them in your report.")
