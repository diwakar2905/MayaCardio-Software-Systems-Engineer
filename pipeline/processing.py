import math
N=400

def compute_window(sid,w,s1,s2,mode):
    a,b=w*N,(w+1)*N
    x={r["index"]:r["values"] for r in s1}
    y={r["index"]:r["values"] for r in s2}
    xs=[x[i] for i in range(a,b) if i in x]; ys=[y[i] for i in range(a,b) if i in y]
    def stats(rows,n):
        out=[]
        for c in range(n):
            v=[r[c] for r in rows if len(r)>c]
            out.append({"mean":round(sum(v)/len(v),1) if v else None,"min":min(v) if v else None,"max":max(v) if v else None})
        return out
    mags=[math.sqrt(r[0]**2+r[1]**2) for r in ys if len(r)>=2]
    hr=None
    if w>=4:
        lo,hi=(w-4)*N,(w+1)*N
        # all samples in the five-second interval must exist
        if all(i in x for i in range(lo,hi)):
            peaks=[]; last=None
            for i in range(max(800,lo),hi-1):
                prior=[x[j][1] for j in range(i-800,i)]
                if len(prior)!=800: continue
                if x[i][1]>x[i-1][1] and x[i][1]>x[i+1][1] and x[i][1]>max(prior)/2 and (last is None or i-last>=100):
                    peaks.append(i); last=i
            if len(peaks)>=2:
                gaps=[(bb-aa)/N for aa,bb in zip(peaks,peaks[1:])]
                if sum(gaps)>0: hr=round(60/(sum(gaps)/len(gaps)),1)
    return {"session_id":sid,"window":w,"start_index":a,"end_index_exclusive":b,
      "missing_1":N-len(xs),"missing_2":N-len(ys),"complete":len(xs)==N and len(ys)==N,
      "sensor_1":stats(xs,3),"sensor_2":stats(ys,2),
      "magnitude":round(sum(mags)/len(mags),1) if mags else None,"heart_rate":hr,"mode":mode}

def compute_windows(sid,s1,s2,mode):
    # A window is ready only when both channels have advanced past its end.
    h1=max([r["index"] for r in s1]+[-1]); h2=max([r["index"] for r in s2]+[-1])
    highest=min(h1,h2)
    return [compute_window(sid,w,s1,s2,mode) for w in range((highest+1)//N)]
