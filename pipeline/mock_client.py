import json,socket,zlib

class MockError(Exception): pass

def data_array_bytes(raw):
    key=raw.find(b'"data"')
    if key<0: raise MockError("missing data")
    start=raw.find(b'[',key)
    if start<0: raise MockError("missing data array")
    depth=0; string=False; escape=False
    for i in range(start,len(raw)):
        c=raw[i]
        if string:
            if escape: escape=False
            elif c==92: escape=True
            elif c==34: string=False
        elif c==34: string=True
        elif c==91: depth+=1
        elif c==93:
            depth-=1
            if depth==0: return raw[start:i+1]
    raise MockError("unterminated data array")

def validate(raw):
    try: o=json.loads(raw.decode())
    except (UnicodeDecodeError, json.JSONDecodeError) as e: raise MockError(f"bad JSON: {e}") from e
    for k in ("session_id","sensor","first_index","count","lost","data","crc32"):
        if k not in o: raise MockError("missing "+k)
    if o["sensor"] not in (1,2) or o["count"]!=len(o["data"]): raise MockError("invalid sensor/count")
    expected=f'{zlib.crc32(data_array_bytes(raw)) & 0xffffffff:08x}'
    actual=str(o["crc32"]).lower().removeprefix("0x").zfill(8)
    if actual!=expected: raise MockError(f"CRC mismatch: expected {expected}, got {actual}")
    if any(len(row)!=(3 if o["sensor"]==1 else 2) or any(not isinstance(v,int) for v in row) for row in o["data"]):
        raise MockError("invalid channel shape/value")
    return o

def read(host,port,sensor,timeout=1.0,from_index=None):
    req={"cmd":"read","sensor":sensor}
    if from_index is not None: req["from_index"]=from_index
    with socket.create_connection((host,port),timeout=timeout) as s:
        s.settimeout(timeout); s.sendall((json.dumps(req,separators=(",",":"))+"\n").encode())
        buf=bytearray()
        while not buf.endswith(b"\n"):
            chunk=s.recv(65536)
            if not chunk: break
            buf.extend(chunk)
            if len(buf)>16*1024*1024: raise MockError("reply too large")
        if not buf: raise MockError("empty reply")
        return validate(bytes(buf).strip())
