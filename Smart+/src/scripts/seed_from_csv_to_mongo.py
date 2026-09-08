import pandas as pd
from pymongo import MongoClient
from src.config import CFG

cli = MongoClient(CFG.mongo_uri)
db = cli[CFG.db_name]

def seed(path, coll):
    df = pd.read_csv(path)
    recs = df.to_dict(orient="records")
    if "_id" in df.columns:
        from bson.objectid import ObjectId
        for r in recs:
            r["_id"] = str(r["_id"])
    if recs:
        db[coll].insert_many(recs)
        print(f"Seeded {len(recs)} into {coll}")

seed("metrics.csv", CFG.raw_coll)
seed("students.csv", CFG.students_coll)
seed("doctors.csv", CFG.doctors_coll)
print("Done.")
