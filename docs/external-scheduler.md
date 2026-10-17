# 外部调度触发方案

原生 GitHub schedule 当前是 `3 21 * * *`，对应北京时间 05:03；watchdog 是 `23 21 * * *`，对应北京时间 05:23。Scheduled #7 的历史样本在整点触发后延迟了 141.7 分钟，但 Runner 排队只有 3 秒；这只能证明 GitHub 调度存在延迟，不能证明改成非整点就一定准时。非整点和提前运行只用于降低整点拥堵概率，不是准时保证。北京时间 07:03 仍由 Codex/external dispatcher 作为第二次补偿触发。

## 推荐配置：cron-job.org

cron-job.org 支持固定时区、POST、自定义请求头、失败通知和执行历史。仓库已提供幂等配置脚本 `scripts/setup_cron_job_org.py`：同一标题的任务存在时只更新，不会重复创建。

1. 在 cron-job.org 注册并在 `Settings` 生成 API key。
2. 在 GitHub 创建一个仅限本仓库的 fine-grained PAT，权限只给 `Actions: Read and write`。该 PAT 只用于触发 `workflow_dispatch`，不要使用仓库内容写权限。
3. 在本地 PowerShell 当前进程设置两个环境变量，然后运行配置脚本：

```powershell
$env:CRON_JOB_ORG_API_KEY = '<cron-job.org API key>'
$env:GITHUB_DISPATCH_PAT = '<GitHub fine-grained PAT>'
python scripts/setup_cron_job_org.py
```

也可以让脚本隐藏读取两个凭据，不把它们写入环境变量或 PowerShell 历史：

```powershell
python scripts/setup_cron_job_org.py --interactive
```

脚本配置的任务是 `Asia/Shanghai` 每天 `07:03`，请求超时 60 秒，并启用 cron-job.org 的失败/恢复通知。检查任务而不修改：

```powershell
python scripts/setup_cron_job_org.py --check
```

停用而不删除：

```powershell
python scripts/setup_cron_job_org.py --disable
```

预览请求且不访问外部 API：

```powershell
python scripts/setup_cron_job_org.py --dry-run
```

脚本不会把两个凭据写入仓库；配置后 GitHub PAT 会作为 cron-job.org 对 GitHub API 发请求的 `Authorization` 请求头保存。不要把 PAT 或 cron-job.org API key 提交到 GitHub。当前仓库只能自动完成 GitHub 侧的配置，cron-job.org 账户和两个凭据不在本地环境中，因此外部任务必须由用户完成一次 `--interactive` 配置；在此之前 GitHub schedule 和 watchdog 仍负责兜底。

脚本实际设置的 POST 请求如下：

```http
POST https://api.github.com/repos/simondongxiao/us-market-daily-recap/actions/workflows/us-market-daily-recap.yml/dispatches
Authorization: Bearer <外部调度器保存的 GitHub fine-grained PAT>
Accept: application/vnd.github+json
Content-Type: application/json

{"ref":"main"}
```

PAT 只需要对该仓库授予 Actions workflow dispatch 所需的最小写权限。不要把 PAT 写入仓库，也不要把飞书 Webhook 写进 URL；两者都应只保存在外部调度器的 Secret 中。当前仓库的 `FEISHU_WEBHOOK_URL` Secret 已存在，不需要重复配置。

GitHub 的 `workflow_dispatch` API 返回成功只代表工作流已被接收；最终报告仍由现有 Windows-hosted runner 生成，成功交付以后才写入状态并由去重逻辑抑制重复发送。

自动去重由 `state/daily_delivery_state.json` 和固定的 Actions concurrency group 共同完成，键包含：

- `report_date_bjt`
- `us_trade_date`
- Word + HTML SHA-256 内容版本
- 飞书发送状态

同一版本已成功发送时，手动、Scheduled、外部 dispatch 和 watchdog 都会跳过重复飞书；内容版本变化时允许以 `revision` 补发。飞书结果不明确时记录 `UNKNOWN_DELIVERY`，下一次补偿仍可重试，不会伪装成成功。

仓库内另有 07:20 北京时间运行的 `us-market-daily-recap-watchdog.yml`：若状态中没有当天成功交付，它只请求一次补偿 `workflow_dispatch`。补偿仍走同一套去重和完整 Pages 校验。
