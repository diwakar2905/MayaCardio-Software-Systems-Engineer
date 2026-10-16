import json, sqlite3, time
from pathlib import Path

class Store:
    def __init__(self, path):
        self.path = Path(path); self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("PRAGMA busy_timeout=30000")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS samples(session_id TEXT NOT NULL,sensor INTEGER NOT NULL,idx INTEGER NOT NULL,values_json TEXT NOT NULL,received REAL NOT NULL,synced INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(session_id,sensor,idx));
        CREATE TABLE IF NOT EXISTS losses(id INTEGER PRIMARY KEY,session_id TEXT NOT NULL,sensor INTEGER NOT NULL,start_idx INTEGER NOT NULL,end_idx INTEGER,reason TEXT NOT NULL,created REAL NOT NULL,synced INTEGER NOT NULL DEFAULT 0,UNIQUE(session_id,sensor,start_idx,end_idx,reason));
        CREATE TABLE IF NOT EXISTS sessions(session_id TEXT PRIMARY KEY,first_seen REAL NOT NULL,last_seen REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS results(session_id TEXT NOT NULL,window_idx INTEGER NOT NULL,mode TEXT NOT NULL,result_json TEXT NOT NULL,PRIMARY KEY(session_id,window_idx,mode));
        CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        """)
    def close(self): self.db.close()
    def save_samples(self, sid, sensor, first, data):
        now=time.time(); self.db.execute("BEGIN IMMEDIATE")
        try:
            self.db.execute("INSERT INTO sessions VALUES(?,?,?) ON CONFLICT(session_id) DO UPDATE SET last_seen=excluded.last_seen",(sid,now,now))
            n=0
            for j,values in enumerate(data):
                n += self.db.execute("INSERT OR IGNORE INTO samples(session_id,sensor,idx,values_json,received) VALUES(?,?,?,?,?)",(sid,sensor,first+j,json.dumps(values,separators=(",",":")),now)).rowcount
            self.db.execute("COMMIT"); return n
        except: self.db.execute("ROLLBACK"); raise
    def add_loss(self,sid,sensor,start,end,reason):
        self.db.execute("INSERT OR IGNORE INTO losses(session_id,sensor,start_idx,end_idx,reason,created) VALUES(?,?,?,?,?,?)",(sid,sensor,start,end,reason,time.time()))
    def set_meta(self,key,value):
        self.db.execute("INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(key,str(value)))
    def get_meta(self,key,default=None):
        row=self.db.execute("SELECT value FROM meta WHERE key=?",(key,)).fetchone()
        return row[0] if row else default
    def latest_index(self,sid,sensor):
        return self.db.execute("SELECT MAX(idx) FROM samples WHERE session_id=? AND sensor=?",(sid,sensor)).fetchone()[0]
    def sessions(self): return [r[0] for r in self.db.execute("SELECT session_id FROM sessions")]
    def samples(self,sid,sensor,start=None,end=None):
        q="SELECT idx,values_json FROM samples WHERE session_id=? AND sensor=?"; a=[sid,sensor]
        if start is not None: q+=" AND idx>=?"; a.append(start)
        if end is not None: q+=" AND idx<?"; a.append(end)
        q+=" ORDER BY idx"
        return [{"index":r["idx"],"values":json.loads(r["values_json"])} for r in self.db.execute(q,a)]
    def pending(self,limit=500):
        s=[{"session_id":r["session_id"],"sensor":r["sensor"],"index":r["idx"],"values":json.loads(r["values_json"])} for r in self.db.execute("SELECT session_id,sensor,idx,values_json FROM samples WHERE synced=0 ORDER BY received LIMIT ?",(limit,))]
        l=[{"id":r["id"],"session_id":r["session_id"],"sensor":r["sensor"],"from_index":r["start_idx"],"to_index":r["end_idx"],"reason":r["reason"]} for r in self.db.execute("SELECT * FROM losses WHERE synced=0 ORDER BY id LIMIT ?",(limit,))]
        return s,l
    def mark_synced(self,samples,losses):
        self.db.executemany("UPDATE samples SET synced=1 WHERE session_id=? AND sensor=? AND idx=?",[(x["session_id"],x["sensor"],x["index"]) for x in samples])
        self.db.executemany("UPDATE losses SET synced=1 WHERE id=?",[(x["id"],) for x in losses])
    def counts(self):
        return {"samples_saved":self.db.execute("SELECT COUNT(*) FROM samples").fetchone()[0],
                "samples_in_cloud":self.db.execute("SELECT COUNT(*) FROM samples WHERE synced=1").fetchone()[0],
                "backlog":self.db.execute("SELECT (SELECT COUNT(*) FROM samples WHERE synced=0)+(SELECT COUNT(*) FROM losses WHERE synced=0)").fetchone()[0]}
    def export(self,sid):
        samples=[{"sensor":r["sensor"],"index":r["idx"],"values":json.loads(r["values_json"])} for r in self.db.execute("SELECT * FROM samples WHERE session_id=? ORDER BY sensor,idx",(sid,))]
        losses=[{"sensor":r["sensor"],"from_index":r["start_idx"],"to_index":r["end_idx"],"reason":r["reason"]} for r in self.db.execute("SELECT * FROM losses WHERE session_id=? ORDER BY sensor,start_idx",(sid,))]
        return samples,losses
    def save_result(self,sid,w,mode,obj):
        self.db.execute("INSERT INTO results VALUES(?,?,?,?) ON CONFLICT(session_id,window_idx,mode) DO UPDATE SET result_json=excluded.result_json",(sid,w,mode,json.dumps(obj,separators=(",",":"))))
    def results(self,sid):
        return [json.loads(r[0]) for r in self.db.execute("SELECT result_json FROM results WHERE session_id=? ORDER BY window_idx,mode",(sid,))]
