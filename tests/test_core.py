import json
import math
import zlib

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
def test_crc_uses_exact_data_array_bytes():
    raw_data='[ [1, 2, 3], [4, 5, 6] ]'
    crc=f"{zlib.crc32(raw_data.encode())&0xffffffff:08x}"
    raw=(f'{{"session_id":"s","sensor":1,"first_index":0,"count":2,"lost":[],"crc32":"{crc}","data":{raw_data}}}').encode()
    assert validate(raw)["data"]==[[1,2,3],[4,5,6]]
def test_store_dedupe(tmp_path):
    s=Store(tmp_path/"d.db")
    assert s.save_samples("s",1,0,[[1,2,3]])==1
    assert s.save_samples("s",1,0,[[1,2,3]])==0
    assert s.samples("s",1)[0]["values"]==[1,2,3];s.close()
def test_loss_dedupe(tmp_path):
    s=Store(tmp_path/"d.db")
    s.add_loss("s",1,3,5,"reported")
    s.add_loss("s",1,3,5,"reported")
    assert len(s.export("s")[1])==1
    s.close()
def test_window_missing():
    r=compute_window("s",0,[{"index":i,"values":[1,2,3]} for i in range(399)],[{"index":i,"values":[3,4]} for i in range(400)],"offline")
    assert r["missing_1"]==1 and r["missing_2"]==0 and not r["complete"]
def test_heart_rate_uses_five_second_peak_gaps():
    peaks={900,1167,1434,1701}
    s1=[]
    for i in range(2000):
        value=1000 if i in peaks else 0
        s1.append({"index":i,"values":[0,value,0]})
    s2=[{"index":i,"values":[1,1]} for i in range(2000)]
    r=compute_window("s",4,s1,s2,"offline")
    assert r["heart_rate"]==89.9
    assert math.isclose(r["magnitude"],math.sqrt(2),abs_tol=0.1)
