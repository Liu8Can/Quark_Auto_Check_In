# ⭐️ 夸克网盘自动签到

![GitHub stars](https://img.shields.io/github/stars/Liu8Can/Quark_Auot_Check_In) ![GitHub forks](https://img.shields.io/github/forks/Liu8Can/Quark_Auot_Check_In) ![License](https://img.shields.io/github/license/Liu8Can/Quark_Auot_Check_In) ![Last Commit](https://img.shields.io/github/last-commit/Liu8Can/Quark_Auot_Check_In) ![GitHub Actions](https://github.com/Liu8Can/Quark_Auot_Check_In/actions/workflows/quark_signin.yml/badge.svg) ![CI](https://github.com/Liu8Can/Quark_Auot_Check_In/actions/workflows/ci.yml/badge.svg)

通过 GitHub Actions 自动完成夸克网盘每日签到并领取空间奖励，支持单账号和多账号。

## 🚀 功能

- 北京时间每天约 **09:00** 执行签到，**13:00** 进行失败兜底。
- 当天所有账号成功后写入日期缓存，第二次任务自动跳过。
- 多账号逐个执行；某个账号失败不会阻断其他账号。
- 任何账号失败时工作流返回失败，并保留当天第二次重试机会。
- 每月在独立的 `heartbeat` 分支生成保活提交，不污染 `main` 历史。

## 📋 使用方法

### 1. Fork 并启用 Actions

Fork 本仓库后进入 **Actions** 页面。如果 GitHub 显示工作流尚未启用，请点击 **I understand my workflows, go ahead and enable them**。

工作流已经声明所需的最小权限：签到工作流仅使用 `contents: read`，保活工作流使用 `contents: write`。通常不需要手动把整个仓库的 Workflow permissions 改成读写权限；如果组织策略禁止保活分支写入，请联系组织管理员调整。

### 2. 获取签到参数

> **新版夸克 App 抓包说明**
>
> 近期版本的夸克 App 在部分 Android 环境下对 HTTPS 证书校验较严格。仅安装普通“用户 CA 证书”时，可能无法正常解密夸克的 HTTPS 请求。实体手机通常需要 Root 后将抓包 CA 安装为**系统证书**，配置相对麻烦。
>
> 因此目前更推荐使用 **MuMu 模拟器 + Root + ProxyPin 系统证书**完成抓包，不需要 Root 自己的实体手机。

#### 推荐方案：MuMu 模拟器 + ProxyPin

- [MuMu 模拟器官网](https://mumu.163.com/)
- [ProxyPin 官方 GitHub](https://github.com/wanghongenpin/proxypin)

操作步骤：

1. 安装并启动 **MuMu 模拟器**。
2. 在 MuMu 设置中开启 **Root 权限**。
3. 在模拟器中安装 **夸克 App** 和 **ProxyPin**。
4. 打开 ProxyPin，按照提示安装 HTTPS 抓包证书。
5. 将 ProxyPin 的 CA 证书安装为 Android **系统证书**，而不仅是普通用户证书。
6. 启动 ProxyPin 的 HTTPS 抓包，然后打开夸克 App。
7. 进入夸克网盘的**签到 / 领空间**页面。
8. 回到 ProxyPin，搜索请求域名：

```text
drive-m.quark.cn
```

重点找到类似下面的请求：

```text
https://drive-m.quark.cn/1/clouddrive/act/growth/reward?...
```

9. 复制该请求的**完整 Request URL**。

新版 URL 通常会包含较多参数，例如 `device_model`、`mt`、`ut`、`ds`、`xs`、`kps`、`sign`、`vcode` 等。本项目会从完整 URL 中自动解析签到所需的核心参数，因此**不需要手动拆解新版 URL**。

> **请原样复制完整 URL。** 不要手动修改其中的 `+`、`=`、`%xx` 等字符。新版参数中可能包含字面量 `+`，当前版本已经兼容这种格式。

推荐配置：

```text
user=张三; url=https://drive-m.quark.cn/1/clouddrive/act/growth/reward?...;
```

#### 旧格式仍然兼容

升级后**不会影响原有用户配置**。以下方式均继续支持：

**方式一：新版或旧版完整 URL**

只要 URL 中包含签到需要的 `kps`、`sign`、`vcode` 参数，都可以继续直接填写：

```text
user=张三; url=https://drive-m.quark.cn/...&kps=abcdefg&sign=hijklmn&vcode=111111111;
```

以前已经保存的旧链接无需为了格式变化重新改写；如果凭证本身仍然有效，可以继续使用。

**方式二：手动填写旧版参数**

原来的手填格式同样完全兼容：

```text
user=张三; kps=abcdefg; sign=hijklmn; vcode=111111111;
```

也就是说，已有用户可以保持原来的 Secret 不变；新用户则更推荐直接保存完整抓包 URL，减少复制和拆分参数时出错的可能。

#### 如果抓不到夸克请求

如果出现以下情况：

- ProxyPin 能抓到其他 App，但看不到夸克请求；
- 打开夸克后出现网络异常；
- ProxyPin 显示 SSL / TLS / Certificate 相关错误；
- 安装普通用户证书后仍然无法解密夸克 HTTPS 请求；

优先检查 ProxyPin CA 是否已经安装为**系统证书**。如果实体手机没有 Root，建议直接使用上面的 **MuMu + Root + ProxyPin** 方案。

> `kps`、`sign`、`vcode` 以及完整抓包 URL 都属于敏感账号凭证。不要提交到代码、Issue 或公开截图中，只应保存到自己仓库的 GitHub Actions Secret `COOKIE_QUARK`。如果怀疑凭证已经泄露，请重新获取参数并及时更新 Secret。

### 3. 配置 GitHub Secret

进入 Fork 仓库的 **Settings → Secrets and variables → Actions → New repository secret**：

- Name：`COOKIE_QUARK`
- Secret：粘贴上一步整理的账号配置

多账号可以用换行分隔：

```text
user=账号一; url=https://...;
user=账号二; url=https://...;
```

也可以使用 `&&` 分隔：

```text
user=账号一; url=https://...; && user=账号二; url=https://...;
```

### 4. 手动测试

进入 **Actions → 夸克网盘每日签到 → Run workflow**。第一次运行会真实请求签到接口；当天全部账号已经成功后，再次运行将显示“今日已全部签到成功，跳过重复执行”。

## 🔁 执行与重试逻辑

1. 工作流按北京时间生成当天的缓存键。
2. 如果缓存命中，签到相关步骤全部跳过。
3. 如果没有命中，逐个处理 `COOKIE_QUARK` 中的账号。
4. 所有账号成功或已签到时，保存当天成功标记。
5. 任一账号配置错误、凭证失效或接口异常时，工作流失败且不保存标记，13:00 会再次尝试。

## ❓ 常见问题

### 提示“缺少必要参数”

检查每个账号是否都包含 `kps`、`sign`、`vcode`，或者完整 URL 是否确实带有这三个查询参数。空行会自动忽略。

### 单账号正常，多账号失败

请确认账号之间使用换行或 `&&` 分隔，并且每个账号都是一套完整参数。新版脚本会继续处理后续账号，并在日志中明确指出失败的是第几个账号。

### 提示“获取成长信息失败”或“凭证失效”

通常表示抓取的参数已经过期或不完整，请重新抓取并更新 `COOKIE_QUARK`。接口临时异常也会让工作流失败，但不会写入当日成功缓存，因此仍会保留第二次重试机会。

### 定时任务没有准点运行

GitHub Actions 的计划任务可能延迟数分钟到数十分钟，这是平台调度机制导致的正常现象。工作流还会加入最多 60 秒的随机延迟。

### 保活分支为什么每月被强制更新

`heartbeat` 是专门的孤儿分支，每月仅保留最新一条空提交，用于避免长期无活动的 Fork 被 GitHub 自动停用定时任务；它不会改动 `main`。

## ⚠️ 注意事项

- 本项目仅供学习交流，请勿用于非法用途。
- 夸克接口和参数可能随官方更新而变化；出现集中失效时请先查看 Issues。
- 频繁手动触发可能被服务限制，请谨慎操作。
- 本项目采用 MIT License。复制和分发时请保留原作者版权及许可声明。

本项目基于 [BNDou/Auto_Check_In](https://github.com/BNDou/Auto_Check_In) 的夸克签到功能修改而来。

## 🙏 贡献者

感谢以下贡献者对项目的改进：

- [@Spectrollay](https://github.com/Spectrollay) — 优化签到工作流与自动化逻辑（[#1](https://github.com/Liu8Can/Quark_Auot_Check_In/pull/1)）
- [@haozihong](https://github.com/haozihong) — 将保活提交迁移至独立分支，保持主分支历史整洁（[#4](https://github.com/Liu8Can/Quark_Auot_Check_In/pull/4)）
- [@HSSkyBoy](https://github.com/HSSkyBoy) — 优化签到流程结构与按日期缓存机制（[#16](https://github.com/Liu8Can/Quark_Auot_Check_In/pull/16)）

📧 联系邮箱：[liucan01234@gmail.com](mailto:liucan01234@gmail.com)

欢迎提交 Issue、PR 和 Star 支持项目发展。
