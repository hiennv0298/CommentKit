"""Tìm bài Threads nổi bật bằng API chính thức (keyword_search) và lấy bình luận."""
import os, time, random
import requests

POST_FIELDS = "id,text,media_type,permalink,timestamp,username,has_replies,is_quote_post,is_reply"
REPLY_FIELDS = "id,text,username,timestamp,has_replies,replied_to,root_post"


class ThreadsError(RuntimeError):
    pass


class Threads:
    def __init__(self, token, base):
        if not token:
            raise ThreadsError("Chưa có THREADS_ACCESS_TOKEN trong .env")
        self.token, self.base = token, base.rstrip("/")

    def _get(self, path, **params):
        params["access_token"] = self.token
        r = requests.get(f"{self.base}/{path.lstrip('/')}", params=params, timeout=30)
        try:
            data = r.json()
        except ValueError:
            raise ThreadsError(f"HTTP {r.status_code}: {r.text[:200]}")
        if r.status_code != 200 or "error" in data:
            err = data.get("error", {})
            raise ThreadsError(f"{path}: {err.get('code')} {err.get('message', r.text[:200])}")
        return data

    def me(self):
        return self._get("me", fields="id,username")

    def search(self, q, search_type="TOP", days_back=7, limit=25):
        since = int(time.time()) - days_back * 86400
        data = self._get("keyword_search", q=q, search_type=search_type, media_type="TEXT",
                         since=since, limit=limit, fields=POST_FIELDS)
        return data.get("data", [])

    def conversation(self, media_id, limit=50):
        try:
            data = self._get(f"{media_id}/conversation", fields=REPLY_FIELDS, reverse="false", limit=limit)
        except ThreadsError:
            # thử lại bằng /replies (chỉ bình luận cấp 1)
            data = self._get(f"{media_id}/replies", fields=REPLY_FIELDS, reverse="false", limit=limit)
        return data.get("data", [])


def collect_candidates(api, cfg, seen_ids, log=print):
    """Gom ứng viên từ vài từ khoá (xoay vòng ngẫu nhiên), lọc bài đã dùng / quá ngắn / quá dài."""
    tc = cfg["threads"]
    kws = random.sample(tc["keywords"], min(tc["keywords_per_run"], len(tc["keywords"])))
    pool = {}
    for kw in kws:
        try:
            posts = api.search(kw, tc["search_type"], tc["days_back"], tc["per_keyword"])
        except ThreadsError as e:
            log(f"  ! search '{kw}': {e}")
            continue
        log(f"  search '{kw}': {len(posts)} bài")
        for rank, p in enumerate(posts):
            t = (p.get("text") or "").strip()
            if p["id"] in seen_ids or p.get("is_reply") or p.get("is_quote_post"):
                continue
            if not (tc["min_len"] <= len(t) <= tc["max_len"]):
                continue
            # TOP đã xếp theo độ phổ biến; ưu tiên bài có bình luận và đứng đầu
            score = (2 if p.get("has_replies") else 0) + max(0, 1 - rank / 25)
            if p["id"] not in pool or pool[p["id"]]["_score"] < score:
                pool[p["id"]] = dict(p, _kw=kw, _score=score)
    cands = sorted(pool.values(), key=lambda p: -p["_score"])[: tc["candidates_to_claude"]]
    for p in cands[: tc["replies_for_top"]]:
        if not p.get("has_replies"):
            continue
        try:
            reps = api.conversation(p["id"])
            p["_replies"] = [r["text"].strip() for r in reps if (r.get("text") or "").strip()][:30]
        except ThreadsError as e:
            log(f"  ! replies {p['id']}: {e}")
    return cands
