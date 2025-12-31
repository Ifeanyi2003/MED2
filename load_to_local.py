import pandas as pd
from sqlalchemy import create_engine, text

DATABASE_URL = "postgresql://postgres:peter2003$@localhost:5432/drugai"

engine = create_engine(DATABASE_URL)

print("Loading data from drugsCom files...")
df = pd.concat([
    pd.read_csv("drugsComTrain_raw.csv"),
    pd.read_csv("drugsComTest_raw.csv")
])

df['condition'] = df['condition'].astype(str).str.replace(r'<.*?>', '', regex=True).str.strip()
df = df[['drugName', 'condition', 'rating']].dropna()

print(f"Uploading {len(df):,} records to your local PostgreSQL...")
df.to_sql('prescriptions', engine, if_exists='replace', index=False)

print("Creating search index (this makes it super fast)...")
with engine.connect() as conn:
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_condition ON prescriptions(condition);"))
    conn.commit()

print("")
print("SUCCESS! Your DrugAI is 100% ready on your laptop!")
print("Now run: python app.py")
print("Open browser → http://127.0.0.1:5000")