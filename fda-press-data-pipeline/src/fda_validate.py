import os, json, re
from typing import List, Dict, Tuple

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_PATH = os.path.join(BASE_DIR, "data", "raw", "raw_articles.jsonl")
PROCESSED_PATH = os.path.join(BASE_DIR, "data", "curated", "processed_articles.jsonl")
VERIFIED_PATH = os.path.join(BASE_DIR, "data", "curated", "verified_articles.jsonl")
MIN_SUMMARY_LEN = 10

def read_jsonl(path:str) -> list[dict]:
    items: list[dict] = []
    
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            items.append(data)
    return items

def append_jsonl(path:str, obj:dict) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def normalize_body(text:str) -> str:
    s = (text or "")
    s = s.replace("\u00a0", " ")
    s = s.replace("\n", " ").replace("\r", " ")

    s = s.replace("“", '"').replace("”", '"').replace("’", "'")
    s = s.replace("–", "-").replace("—", "-")

    s = re.sub(r"\s+", " ", s).strip()
    return s


def build_body_index(raw_items: List[Dict]) -> Dict[str, str]:
    idx = {}
    for a in raw_items:
        h = a.get("url_hash")
        if not h:
            continue
        idx[h] = normalize_body(a.get("body_en") or "")
    return idx


def validate_record(rec:Dict, body_en:str) -> Tuple[bool, List[str]]:
    err = []
    
    summary_ko = (rec.get("summary_ko") or "").strip()
    if len(summary_ko) < MIN_SUMMARY_LEN:
        err.append(f"summary_ko_too_short:{len(summary_ko)}")
        
    keywords = rec.get("keywords")
    if not isinstance(keywords,list) or len(keywords) == 0:
        err.append(f"keyword_invalid")
        
    evidence = (rec.get("evidence"))
    if not isinstance(evidence, list) or len(evidence) == 0:
        err.append("evidence_invalid")
    else:
        if not body_en:
            err.append("body_missing")
        else:
            body_norm = normalize_body(body_en).lower()
            for i, j in enumerate(evidence):
                j = (j or "").strip()
                if not j:
                    err.append(f"evidence_empty:idx{i}")
                    continue
                
                ev_norm = normalize_body(j).lower()

                if ev_norm not in body_norm:
                    err.append(f"evidence_not_in_body:idx{i}")

    return len(err) == 0, err


def main():
    os.makedirs(os.path.dirname(VERIFIED_PATH), exist_ok=True)
    processed_hash = set()
    
    if os.path.exists(OUT_PATH):
        with open(OUT_PATH, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    if "url_hash" in data and "error" not in data:
                        processed_hash.add(data["url_hash"])
                except:
                    continue

    all_articles = read_jsonl(RAW_PATH)
    target_articles = [a for a in all_articles if a.get("url_hash") not in processed_hash]
    print(f"전체 {len(all_articles)}건 중 신규 가공 대상: {len(target_articles)}건")
    if not target_articles:
        print("새 기사가 없음")
        return
    ok=0
    fail=0
    for rec in processed_items:
        url_hash = rec.get("url_hash")
        body_en = body_idx.get(url_hash, "")
        
        is_verified, errs = validate_record(rec, body_en)
        out = dict(rec)
        out["is_verified"] = is_verified
        if not is_verified:
            out["verification_errs"] = errs
            
        append_jsonl(VERIFIED_PATH, out)
        
        if is_verified:
            ok+=1
        else:
            fail+=1
    print(f"[DONE] {VERIFIED_PATH}")
    print(f" OK={ok}, FAIL={fail}, TOTAL={ok+fail}")


if __name__ == "__main__":
    main()