import os,time,logging,httpx
from .mock_client import read
from .processing import compute_windows
from .store import Store

log=logging.getLogger("pipeline")
class Engine:
    def __init__(self,store):
        self.store=store; self.host=os.getenv("MOCK_HOST","127.0.0.1"); self.port=int(os.getenv("MOCK_PORT","7100"))
        self.cloud=os.getenv("CLOUD_URL","").rstrip("/"); self.timeout=float(os.getenv("REQUEST_TIMEOUT","1"))
        self.stop=False; self.current=None; self.online=False
    def record(self,sensor,o):
        sid=o["session_id"]
        if self.current and self.current!=sid:
            for sn in (1,2):
                last=self.store.latest_index(self.current,sn)
                if last is not None:self.store.add_loss(self.current,sn,last+1,None,"mock_restarted_old_session_end_unknown")
        self.current=sid; self.store.set_meta("current_session",sid)
        for loss in o.get("lost",[]): self.store.add_loss(sid,sensor,int(loss["from_index"]),loss.get("to_index"),str(loss.get("reason","mock_reported_loss")))
        first=int(o["first_index"]); last=self.store.latest_index(sid,sensor)
        if last is not None and first>last+1:self.store.add_loss(sid,sensor,last+1,first-1,"index_gap_detected")
        self.store.save_samples(sid,sensor,first,o["data"])
    def process(self):
        for sid in self.store.sessions():
            s1=self.store.samples(sid,1);s2=self.store.samples(sid,2)
            for r in compute_windows(sid,s1,s2,"offline"):self.store.save_result(sid,r["window"],"offline",r)
    def sync(self):
        if not self.cloud:return False
        try:
            h=httpx.get(self.cloud+"/health",timeout=2);h.raise_for_status()
            while True:
                samples,losses=self.store.pending(500)
                if not samples and not losses:break
                body={"samples":samples,"losses":[{k:v for k,v in l.items() if k!="id"} for l in losses]}
                r=httpx.post(self.cloud+"/ingest",json=body,timeout=10);r.raise_for_status()
                self.store.mark_synced(samples,losses)
            # Mirror cloud-produced results locally so `pipeline results` shows both modes.
            for sid in self.store.sessions():
                rr=httpx.get(f"{self.cloud}/sessions/{sid}/results",timeout=10); rr.raise_for_status()
                for result in rr.json().get("results",[]): self.store.save_result(sid,result["window"],"online",result)
            return True
        except (httpx.HTTPError, OSError, ValueError) as e:
            log.warning("cloud unavailable; backlog retained: %s",e)
            return False
    def run(self):
        while not self.stop:
            for sensor in (1,2):
                if self.stop:break
                try:self.record(sensor,read(self.host,self.port,sensor,self.timeout))
                except Exception as e:log.warning("sensor %s read failed: %s",sensor,e)
            self.online=self.sync()
            self.store.set_meta("mode", "online" if self.online else "offline")
            self.process()
            time.sleep(float(os.getenv("POLL_INTERVAL","0.05")))
