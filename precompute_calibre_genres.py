import json
import pandas as pd
from Projects.genre_classifier.genre_classifier import GenreClassifier

# 1. Load Calibre metadata (adapt path/source as needed)
calibre_df = pd.read_json("calibre_metadata.json")  # or from their DB

# 2. Load your trained classifier
clf = GenreClassifier("Projects/genre_classifier/genre_model")

# 3. Classify each book
def classify_row(row):
    title = row.get("title", "")
    description = row.get("comments", "")
    return clf.predict_labels(title, description, threshold=0.5, top_k=3)

calibre_df["predicted_genres"] = calibre_df.apply(classify_row, axis=1)

# 4. Save for fast use in MCP
calibre_df.to_json("calibre_with_genres.json", orient="records", force_ascii=False)
print("Saved calibre_with_genres.json with predicted_genres")
