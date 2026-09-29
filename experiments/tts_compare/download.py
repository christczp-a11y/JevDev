"""下载模型到默认的 HuggingFace 缓存（不进仓库）。网络不稳时自动续传重试。"""
import sys
import time
from huggingface_hub import snapshot_download

for repo in sys.argv[1:]:
    for attempt in range(1, 21):
        try:
            p = snapshot_download(repo)
            print("ok", repo, p, flush=True)
            break
        except Exception as e:  # noqa: BLE001
            print(f"retry {attempt} {repo}: {type(e).__name__}", flush=True)
            time.sleep(3)
    else:
        print("FAILED", repo, flush=True)
