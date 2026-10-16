import json,zlib
from pipeline.mock_client import validate,MockError
from pipeline.store import Store
from pipeline.processing import compute_window

def test_crc():
    data='[[1,2,3]]';crc=f"{zlib.crc32(data.encode())&0xffffffff:08x}"
    raw=(f'{{"session_id":"s","sensor":1,"first_index":0,"count":1,"lost":[],"crc32":"{crc}","data":{data}}}').encode()
    assert validate(raw)["data"]==[[1,2,3]]
def test_bad_crc():
    data='[[1,2,3]]';raw=(f'{{"session_id":"s","sensor":1,"first_index":0,"count":1,"lost":[],"crc32":"deadbeef","data":{data}}}').encode()
    try:validate(raw);assert False
    except MockError:pass
def test_store_dedupe(tmp_path):
    s=Store(tmp_path/"d.db")
    assert s.save_samples("s",1,0,[[1,2,3]])==1
    assert s.save_samples("s",1,0,[[1,2,3]])==0
    assert s.samples("s",1)[0]["values"]==[1,2,3];s.close()
def test_window_missing():
    r=compute_window("s",0,[{"index":i,"values":[1,2,3]} for i in range(399)],[{"index":i,"values":[3,4]} for i in range(400)],"offline")
    assert r["missing_1"]==1 and r["missing_2"]==0 and not r["complete"]
