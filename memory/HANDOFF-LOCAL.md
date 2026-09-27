# 切换到本地会话

## 为什么要切换
云环境登录小红书有三道障碍：
1. 网络策略拦截了 `www.xiaohongshu.com`，这一条可以在环境设置里放行；
2. 用的是机房 IP，而且每次都是新设备（容器用完就回收），容易触发风控；
3. 无头浏览器没有你的登录状态，每次都得重新扫码登录。

本地会话会用你自己的 Chrome、登录状态和家庭网络 IP，这三点就都不是问题了。

## 步骤
1. 本地克隆仓库，切到开发分支：
   ```
   git clone https://github.com/christczp-a11y/JevDev.git
   cd JevDev
   git checkout claude/loving-cerf-f4z5v5
   ```
2. 安装 TypeSafe 插件（在本地终端运行一次即可）：
   ```
   claude plugin marketplace add typesafe-ai/skills
   claude plugin install typesafe@typesafe-ai
   ```
3. 选一种方式打开本地会话：
   - Claude Desktop：打开 JevDev 文件夹，启用 Claude in Chrome（用你自己的 Chrome 和登录状态）
   - 或者在终端的 JevDev 目录下运行 `claude`，想在手机上继续时改用 `claude remote-control`
4. 会话的第一句话：「先读 memory/PROGRESS.md 和 memory/README.md，继续工作」
5. 小红书账号：由 Chris 在 Chrome 里手动登录，Claude 不处理密码和验证码
