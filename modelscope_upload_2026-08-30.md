# 魔搭社区全量上传（紧急避险）2026-08-30

## 目标
每日 800 积分取消，需将工作区全部文件（灵魂/记忆/设计稿/引擎源码/小说/归档等，不脱敏）紧急避险上传到魔搭社区新建数据集。

## 决策
- 百炼 Key 处理：选 **B** — 上传副本中把活密钥 `sk-REDACTED-REPLACE-WITH-YOUR-OWN` 全量替换为 `sk-REDACTED-IN-PUBLIC-DUMP`（非破坏，只改临时镜像，不动源活文件）。
- 魔搭令牌：`ms-REDACTED`（用户 Lxs945911 提供），用完即删；仅通过 `ms` 的 `--token` 参数传入，不落盘。
- 许可证：Apache-2.0（魔搭数据集选项无 CC BY-SA）。

## 执行
1. 镜像工作区到 `C:\Users\qq366410837\.qclaw\_ms_upload_stage`（robocopy /E，12173 文件 / 135.8MB）。
2. 镜像内 49 个文件含活密钥 → 全量替换为占位符（阶段目录验证：活密钥残留 0，打码出现 108 处）。
3. 写 README-upload.md 说明打码声明。
4. `ms create Lxs945911/tu8-full-workspace-2026-08-30 --repo_type dataset --visibility public --license "Apache License 2.0" --token <tok>` → 创建成功。
5. `ms upload --repo-type dataset --token <tok> --max-workers 8 <repo> <stage> .` → 24 批提交，约 7 分钟，`UPLOAD_EXITCODE=0`。

## 收尾
- 删临时镜像目录 + 含 token 的脚本/日志（工作区 token 残留扫描 = 0）。
- 用户已在 ModelScope 服务端 revoke 令牌（"用完即删"闭环达成）。
- 本地 `.modelscope/credentials/` 为 CLI 自动落盘的登录态缓存，令牌 revoke 后已失效；删除该目录曾被安全策略拦截需二次确认，因令牌已废留着无害，待用户决定。

## 结论
紧急避险完成：全量工作区已作为公开数据集持久化于魔搭服务端，积分取消不影响此备份。百炼活密钥已隔离，无明文密钥进入公开仓库。
