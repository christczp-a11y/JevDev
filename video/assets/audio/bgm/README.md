# 背景音乐（按集）

- 从 tj03 起每集用本地开源模型 ACE-Step 1.5（MIT 许可，可商用）自己生成，只用真乐器音色，不要合成器 / 电子鼓（PITFALLS A8，Chris 10-02）。
- 生成和筛选：`video/music_gen.py`、`video/music_screen.py`；候选的提示词、种子、筛选数据在 `video/out/bgm_cands/README.md`（不进 git）。
- 进这个目录前统一处理：`ffmpeg -af "highpass=f=70,loudnorm=I=-20:TP=-2:LRA=11"`（手机放不出 70 Hz 以下；合成器混音时会再压低）。
- 分镜表顶层 `"bgm": "video/assets/audio/bgm/<文件>.mp3"` 选用；不写就用旧的 `video/assets/audio/bgm_main.mp3`（tj01、tj02）。

| 文件 | 来源 | 描述 | 用在 |
|---|---|---|---|
| `tj03_cand12.mp3` | ACE-Step 1.5，候选 12 | 琵琶 + 古筝对话式拨弦、留白多，96 BPM | **tj03**（Chris 10-02 选定） |
| `tj03_cand2.mp3` | 候选 2 | 琵琶 + 拨弦，最活泼，96 BPM | 候选 |
| `tj03_cand5.mp3` | 候选 5 | 最疏的拨弦，108 BPM | 候选 |
| `tj03_cand8.mp3` | 候选 8 | 古筝 + 箫，最慢最温柔，90 BPM | 候选 |
