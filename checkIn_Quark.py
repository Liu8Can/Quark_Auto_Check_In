"""Quark cloud-drive daily sign-in.

The script accepts one or more account entries from ``COOKIE_QUARK``. Accounts
may be separated by a newline or ``&&``. Both the legacy kps/sign/vcode format
and the newer captured-URL format are supported.
"""

from __future__ import annotations

import os
import random
import re
import sys
import time
from typing import Callable
from urllib.parse import unquote, urlparse

import requests


INFO_URL = "https://drive-m.quark.cn/1/clouddrive/capacity/growth/info"
SIGN_URL = "https://drive-m.quark.cn/1/clouddrive/capacity/growth/sign"
REQUIRED_PARAMS = ("kps", "sign", "vcode")


class ConfigError(ValueError):
    """Raised when COOKIE_QUARK is missing or malformed."""


class QuarkAPIError(RuntimeError):
    """Raised when the Quark API cannot complete a sign-in operation."""


def send(title: str, message: str) -> None:
    """Print a notification-compatible summary."""

    print(f"{title}:\n{message}")


def split_account_entries(raw_value: str | None) -> list[str]:
    """Split COOKIE_QUARK into non-empty account entries."""

    if not raw_value or not raw_value.strip():
        raise ConfigError("未配置 COOKIE_QUARK，或变量内容为空")

    entries = [entry.strip() for entry in re.split(r"\r?\n|&&", raw_value)]
    entries = [entry for entry in entries if entry]
    if not entries:
        raise ConfigError("COOKIE_QUARK 中没有可用的账号配置")
    return entries


def extract_params(url: str) -> dict[str, str]:
    """Extract the credentials used by the mobile growth API from a URL."""

    # Quark credentials may contain literal "+" characters.  parse_qs() treats
    # "+" as a space (application/x-www-form-urlencoded semantics), which
    # corrupts newer captured URLs.  Split the raw query ourselves and apply
    # percent-decoding only, preserving literal plus signs exactly as captured.
    query: dict[str, str] = {}
    for part in urlparse(url).query.split("&"):
        if not part:
            continue
        key, separator, value = part.partition("=")
        if not separator:
            value = ""
        key = unquote(key)
        if key not in query:
            query[key] = unquote(value)

    return {name: query.get(name, "") for name in REQUIRED_PARAMS}


def parse_account(entry: str, index: int) -> dict[str, str]:
    """Parse and validate one account entry."""

    account: dict[str, str] = {}
    for field in entry.split(";"):
        field = field.strip()
        if not field:
            continue
        if "=" not in field:
            raise ConfigError(f"第 {index} 个账号存在无效字段：{field}")
        key, value = field.split("=", 1)
        key = key.strip()
        if not key:
            raise ConfigError(f"第 {index} 个账号存在空字段名")
        account[key] = value.strip()

    if "url" in account:
        for key, value in extract_params(account["url"]).items():
            account.setdefault(key, value)

    missing = [key for key in REQUIRED_PARAMS if not account.get(key)]
    if missing:
        raise ConfigError(
            f"第 {index} 个账号缺少必要参数：{', '.join(missing)}"
        )

    account.setdefault("user", f"账号{index}")
    return account


def _api_error_message(payload: dict, fallback: str) -> str:
    message = payload.get("message") or payload.get("msg")
    code = payload.get("code")
    if message:
        return str(message)
    if code is not None:
        return f"{fallback}（code={code}）"
    return fallback


class Quark:
    """Small client for Quark's mobile growth endpoints."""

    def __init__(
        self,
        account: dict[str, str],
        session: requests.Session | None = None,
        timeout: int = 20,
    ) -> None:
        self.account = account
        self.session = session or requests.Session()
        self.timeout = timeout

    @staticmethod
    def convert_bytes(value: int | float) -> str:
        units = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
        size = float(value)
        unit_index = 0
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        return f"{size:.2f} {units[unit_index]}"

    def _params(self) -> dict[str, str]:
        return {
            "pr": "ucpro",
            "fr": "android",
            **{key: self.account[key] for key in REQUIRED_PARAMS},
        }

    def _request(self, method: str, url: str, **kwargs) -> dict:
        stage = "查询签到状态" if method == "GET" else "提交签到"
        attempts = 3 if method == "GET" else 1
        for attempt in range(1, attempts + 1):
            started = time.monotonic()
            try:
                response = self.session.request(method, url, timeout=self.timeout, **kwargs)
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise QuarkAPIError(f"{stage}返回格式异常")
                return payload
            except (requests.Timeout, requests.ConnectionError) as exc:
                print(f"⚠️ {stage}第 {attempt}/{attempts} 次失败：{type(exc).__name__}，耗时 {time.monotonic()-started:.1f}s")
                if attempt == attempts:
                    raise QuarkAPIError(f"{stage}网络失败（{type(exc).__name__}）") from exc
                time.sleep(2 ** (attempt - 1) + random.uniform(0, 1))
            except requests.RequestException as exc:
                status = getattr(getattr(exc, "response", None), "status_code", None)
                if method == "GET" and status in (429, 500, 502, 503, 504) and attempt < attempts:
                    time.sleep(2 ** (attempt - 1) + random.uniform(0, 1))
                    continue
                raise QuarkAPIError(f"{stage}请求失败（HTTP {status or 'unknown'}）") from exc
            except ValueError as exc:
                raise QuarkAPIError(f"{stage}返回了无法解析的数据") from exc
        raise QuarkAPIError(f"{stage}重试耗尽")

    def get_growth_info(self) -> dict:
        payload = self._request("GET", INFO_URL, params=self._params())
        data = payload.get("data")
        if not isinstance(data, dict):
            raise QuarkAPIError(_api_error_message(payload, "获取成长信息失败"))
        return data

    def get_growth_sign(self) -> int | float:
        payload = self._request(
            "POST",
            SIGN_URL,
            params=self._params(),
            json={"sign_cyclic": True},
        )
        data = payload.get("data")
        if not isinstance(data, dict) or "sign_daily_reward" not in data:
            raise QuarkAPIError(_api_error_message(payload, "签到失败"))
        return data["sign_daily_reward"]

    def do_sign(self) -> str:
        growth_info = self.get_growth_info()
        cap_sign = growth_info.get("cap_sign")
        if not isinstance(cap_sign, dict):
            raise QuarkAPIError("成长信息中缺少 cap_sign 字段")

        user = self.account["user"]
        vip_label = "88VIP" if growth_info.get("88VIP") else "普通用户"
        total_capacity = growth_info.get("total_capacity", 0)
        composition = growth_info.get("cap_composition") or {}
        accumulated = composition.get("sign_reward", 0)
        progress = cap_sign.get("sign_progress", "?")
        target = cap_sign.get("sign_target", "?")

        lines = [
            f"{vip_label} {user}",
            f"💾 网盘总容量：{self.convert_bytes(total_capacity)}，"
            f"签到累计容量：{self.convert_bytes(accumulated)}",
        ]

        if cap_sign.get("sign_daily"):
            reward = cap_sign.get("sign_daily_reward", 0)
            lines.append(
                f"✅ 今日已签到 +{self.convert_bytes(reward)}，"
                f"连签进度（{progress}/{target}）"
            )
        else:
            try:
                reward = self.get_growth_sign()
            except QuarkAPIError as exc:
                if "网络失败" not in str(exc):
                    raise
                print("⚠️ POST 结果不确定，重新查询签到状态")
                verified = self.get_growth_info().get("cap_sign")
                if not isinstance(verified, dict) or not verified.get("sign_daily"):
                    raise QuarkAPIError("未确认签到成功，等待定时补签") from exc
                reward = verified.get("sign_daily_reward", 0)
                lines.append("✅ 复查确认今日已签到")
                return "\n".join(lines)
            next_progress = progress + 1 if isinstance(progress, int) else "?"
            lines.append(
                f"✅ 签到成功 +{self.convert_bytes(reward)}，"
                f"连签进度（{next_progress}/{target}）"
            )

        return "\n".join(lines)


def main(
    cookie_value: str | None = None,
    quark_factory: Callable[[dict[str, str]], Quark] | None = None,
) -> int:
    """Run every configured account and return a process-compatible exit code."""

    print("----------夸克网盘开始签到----------")
    if cookie_value is None:
        cookie_value = os.getenv("COOKIE_QUARK")
    quark_factory = quark_factory or Quark

    try:
        entries = split_account_entries(cookie_value)
    except ConfigError as exc:
        print(f"❌ {exc}")
        return 2

    print(f"✅ 检测到共 {len(entries)} 个夸克账号\n")
    results: list[str] = []
    failures = 0

    for index, entry in enumerate(entries, start=1):
        heading = f"🙍🏻‍♂️ 第 {index} 个账号"
        try:
            account = parse_account(entry, index)
            result = quark_factory(account).do_sign()
            results.append(f"{heading}\n{result}")
        except (ConfigError, QuarkAPIError, KeyError, TypeError, ValueError) as exc:
            failures += 1
            results.append(f"{heading}\n❌ {exc}")
        except Exception as exc:  # Keep later accounts running on unexpected errors.
            failures += 1
            results.append(f"{heading}\n❌ 未知错误：{type(exc).__name__}")

    summary = "\n\n".join(results)
    send("夸克自动签到", summary)
    print(
        f"\n----------执行完毕：成功 {len(entries) - failures}，失败 {failures}----------"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
