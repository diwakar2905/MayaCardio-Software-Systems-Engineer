import json,os,sqlite3,time
from pathlib import Path
from fastapi import FastAPI,HTTPException
from pydantic import BaseModel,Field
from pipeline.processing import compute_windows

DB=Path(os.getenv("CLOUD_DB","./data/cloud.db"))
app=FastAPI(title="MayaCardio Cloud Pipeline")

def conn():
    DB.parent.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(DB,timeout=30); c.row_factory=sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL"); c.execute("PRAGMA synchronous=FULL")
    c.executescript("""CREATE TABLE IF NOT EXISTS samples(session_id TEXT,sensor INTEGER,idx INTEGER,values_json TEXT,received REAL,PRIMARY KEY(session_id,sensor,idx));
    CREATE TABLE IF NOT EXISTS losses(session_id TEXT,sensor INTEGER,start_idx INTEGER,end_idx INTEGER,reason TEXT,PRIMARY KEY(session_id,sensor,start_idx,end_idx,reason));
    CREATE TABLE IF NOT EXISTS results(session_id TEXT,window_idx INTEGER,result_json TEXT,updated REAL,PRIMARY KEY(session_id,window_idx));""")
    return c

class Sample(BaseModel):
    session_id:str
    sensor:int=Field(ge=1,le=2)
    index:int=Field(ge=0)
    values:list[int]
class Loss(BaseModel):
    session_id:str
    sensor:int=Field(ge=1,le=2)
    from_index:int=Field(ge=0)
    to_index:int|None=None
    reason:str
class Batch(BaseModel):
    samples:list[Sample]=[]
    losses:list[Loss]=[]

@app.get("/health")
def health():
    c=conn()
    try: return {"ok":True,"samples":c.execute("SELECT COUNT(*) FROM samples").fetchone()[0]}
    finally:c.close()

@app.post("/ingest")
def ingest(batch:Batch):
    c=conn()
    try:
        with c:
            c.execute("BEGIN IMMEDIATE")
            for s in batch.samples:
                if len(s.values)!=(3 if s.sensor==1 else 2): raise HTTPException(422,"wrong channel count")
                c.execute("INSERT OR IGNORE INTO samples VALUES(?,?,?,?,?)",(s.session_id,s.sensor,s.index,json.dumps(s.values,separators=(",",":")),time.time()))
            for l in batch.losses:
                c.execute("INSERT OR IGNORE INTO losses VALUES(?,?,?,?,?)",(l.session_id,l.sensor,l.from_index,l.to_index,l.reason))
            # Process only windows for which both sensors have advanced beyond the window.
            sessions={s.session_id for s in batch.samples}
            for sid in sessions:
                s1=[{"index":r["idx"],"values":json.loads(r["values_json"])} for r in c.execute("SELECT idx,values_json FROM samples WHERE session_id=? AND sensor=1 ORDER BY idx",(sid,))]
                s2=[{"index":r["idx"],"values":json.loads(r["values_json"])} for r in c.execute("SELECT idx,values_json FROM samples WHERE session_id=? AND sensor=2 ORDER BY idx",(sid,))]
                for result in compute_windows(sid,s1,s2,"online"):
                    c.execute("INSERT INTO results VALUES(?,?,?,?) ON CONFLICT(session_id,window_idx) DO UPDATE SET result_json=excluded.result_json,updated=excluded.updated",(sid,result["window"],json.dumps(result,separators=(",",":")),time.time()))
            return {"accepted":len(batch.samples),"losses_recorded":len(batch.losses)}
    finally:c.close()

@app.get("/sessions/{sid}/export")
def export(sid:str):
    c=conn()
    try:
        ss=[{"sensor":r["sensor"],"index":r["idx"],"values":json.loads(r["values_json"])} for r in c.execute("SELECT * FROM samples WHERE session_id=? ORDER BY sensor,idx",(sid,))]
        ll=[{"sensor":r["sensor"],"from_index":r["start_idx"],"to_index":r["end_idx"],"reason":r["reason"]} for r in c.execute("SELECT * FROM losses WHERE session_id=? ORDER BY sensor,start_idx",(sid,))]
        return {"samples":ss,"losses":ll}
    finally:c.close()

@app.get("/sessions/{sid}/results")
def results(sid:str):
    c=conn()
    try:
        s1=[{"index":r["idx"],"values":json.loads(r["values_json"])} for r in c.execute("SELECT idx,values_json FROM samples WHERE session_id=? AND sensor=1 ORDER BY idx",(sid,))]
        s2=[{"index":r["idx"],"values":json.loads(r["values_json"])} for r in c.execute("SELECT idx,values_json FROM samples WHERE session_id=? AND sensor=2 ORDER BY idx",(sid,))]
        rows=c.execute("SELECT result_json FROM results WHERE session_id=? ORDER BY window_idx",(sid,)).fetchall()
        return {"results":[json.loads(r[0]) for r in rows]}
    finally:c.close()
