# GitHub Actions + 飞书定时复盘

本目录已经加入：

- `.github/workflows/us-market-daily-recap.yml`：每天北京时间 07:00 触发，也支持手动触发。
- `scripts/run_daily_recap.ps1`：严格按北京时间日期寻找新生成的 Word 报告，拒绝发送旧报告，并把报告复制到当前任务目录的 `outputs`。
- `scripts/send_feishu_webhook.py`：读取 `FEISHU_WEBHOOK_URL`，向飞书自定义机器人发送短文本通知，不把 webhook 写入仓库。
- `scripts/generate_daily_recap.py`：按北京时间日期解析最近完成的美股交易日，执行采集、轮动、期权、指数纳入、图表和 Word 生成。
- `scripts/run_daily_recap_task.ps1`：Windows 计划任务入口，保留日志并调用同一条日报链路。

## 为什么使用 Windows 自托管 runner

GitHub-hosted runner 运行在云端，不能访问本机的 `D:\codex`、Codex skill 或当前任务目录。要让报告继续使用本地 skill、Word 环境和本地数据，应在这台 Windows 机器上安装一个 GitHub self-hosted runner。工作流故意不使用 `actions/checkout`，而是直接运行：

`C:\Users\Administrator\Documents\Codex\2026-08-10\us-market-daily-recap`

## 一次性配置

1. 在 GitHub 建立一个**私有仓库**，把当前任务目录中的工作流和 `scripts` 提交并推送到默认分支。当前本地目录尚未配置 Git remote，因此这一步需要在 GitHub 端完成。
2. 打开仓库 `Settings -> Actions -> Runners -> New self-hosted runner`，选择 Windows x64，按 GitHub 页面给出的命令在本机安装 runner。建议安装为 Windows service，并保留默认标签 `self-hosted`、`windows`、`x64`。
   如果安装成 Windows service，请确认该 service 使用的账号能读写 `C:\Users\Administrator\Documents\Codex\2026-08-10\us-market-daily-recap` 和 `D:\codex`；不要只在交互式 PowerShell 里设置变量后就认为 service 能看到它们。
3. 在仓库 `Settings -> Secrets and variables -> Actions` 新建 Secret：
   - Name: `FEISHU_WEBHOOK_URL`
   - Value: 你提供的飞书机器人 webhook
4. 在 self-hosted runner 上设置 `US_MARKET_RECAP_COMMAND`，指向你现有的“生成当天复盘 Word”入口。例如：

   `D:\codex\outputs\us_market_daily_recaps\run_daily_recap.ps1`

   该命令需要接受 `-ReportDateBjt yyyy-MM-dd -TaskDir <当前任务目录>` 参数，并生成：

   `us_market_recap_<北京时间日期>_BJT_us_<美东交易日期>_final.docx`

   文件应放在当前任务目录的 `outputs`，或者 skill 的标准目录 `D:\codex\outputs\us_market_daily_recaps`。如果没有配置生成器，工作流会明确失败，不会把历史报告推送到飞书。
5. 先在 GitHub Actions 页面使用 `workflow_dispatch` 手动跑一次；确认 Word 报告和飞书消息都成功后，再依赖定时运行。

## 时间与交付口径

- 触发时间是 `Asia/Shanghai` 每天 07:00；GitHub 的计划任务可能因平台负载稍有延迟。
- 报告正文仍以 `D:\codex\skills\us-market-daily-recap\SKILL.md` 为准，最终交付必须是 `.docx`。
- 飞书自定义机器人 webhook 只能发送消息，不能把本机 `.docx` 直接上传到群里。消息会包含本地报告路径；在 Actions 运行时还会包含该次运行地址，并将 Word 作为 Actions artifact 保留 14 天。
- 不要把 webhook 写进源码、Markdown、日志或公开仓库。飞书官方也建议妥善保管 webhook，并可在机器人设置中开启关键词、IP 白名单或签名校验。

## 本地自检

在确认 `FEISHU_WEBHOOK_URL` 已作为进程环境变量设置后，可以手动执行：

```powershell
$env:CODEX_TASK_DIR = 'C:\Users\Administrator\Documents\Codex\2026-08-10\us-market-daily-recap'
& "$env:CODEX_TASK_DIR\scripts\run_daily_recap.ps1" -ReportDateBjt (Get-Date -Format yyyy-MM-dd)
```

这会先执行生成器，再检查本次启动后是否出现对应日期的新 `.docx`，最后才发送飞书。不要用 `-SkipGenerate` 作为正常定时路径；它只适合你已经在同一时间生成完报告后的故障排查。

## 本机 07:00 计划任务

如果 GitHub self-hosted runner 尚未安装，Windows 计划任务 `Codex US Market Daily Recap` 仍可直接执行同一条本地链路。它以 SYSTEM 身份运行，使用 `D:\python\python.exe`，把报告复制到当前任务目录的 `outputs`，并写入 `outputs\scheduler_logs`。GitHub Actions workflow 仍保留为远端仓库的可审计执行入口和 artifact 保存入口。
