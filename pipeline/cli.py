import argparse,json,os,logging,signal
from .store import Store
from .engine import Engine

def main():
    p=argparse.ArgumentParser(prog="pipeline");sp=p.add_subparsers(dest="cmd",required=True)
    sp.add_parser("run");sp.add_parser("status")
    e=sp.add_parser("export");e.add_argument("--session",required=True);e.add_argument("--from",dest="source",choices=["device","cloud"],default="device")
    r=sp.add_parser("results");r.add_argument("--session",required=True)
    a=p.parse_args();s=Store(os.getenv("PIPELINE_DB","./data/pipeline.db"))
    if a.cmd=="status":
        print(json.dumps({"mode":s.get_meta("mode","offline"),**s.counts(),"current_session":s.get_meta("current_session")},separators=(",",":")));return
    if a.cmd=="export":
        if a.source=="cloud":
            import httpx
            url=os.getenv("CLOUD_URL","").rstrip("/")
            if not url:raise SystemExit("Set CLOUD_URL first")
            x=httpx.get(f"{url}/sessions/{a.session}/export",timeout=15);x.raise_for_status();obj=x.json()
            for row in obj["samples"]+obj["losses"]:print(json.dumps(row,separators=(",",":")))
        else:
            samples,losses=s.export(a.session)
            for row in samples+losses:print(json.dumps(row,separators=(",",":")))
        return
    if a.cmd=="results":
        for row in s.results(a.session):print(json.dumps(row,separators=(",",":")))
        return
    logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s")
    eng=Engine(s)
    def stop(*_):eng.stop=True
    signal.signal(signal.SIGINT,stop)
    if hasattr(signal,"SIGTERM"):signal.signal(signal.SIGTERM,stop)
    try:eng.run()
    finally:s.close()
if __name__=="__main__":main()
