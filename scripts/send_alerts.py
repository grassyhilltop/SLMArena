#!/usr/bin/env python3
"""Announce events found by update_data.py (data/events_pending.json).

Each event becomes a GitHub release (watchers who chose Watch -> Custom -> Releases get an email, and
the releases.atom feed updates). If the BUTTONDOWN_API_KEY secret is set and newsletter.send_alerts
is true in config/site.json, the same text is also sent to the Buttondown mailing list.

    python3 scripts/send_alerts.py           # announce pending events, if any
    python3 scripts/send_alerts.py --test    # announce a clearly labelled test event
    python3 scripts/send_alerts.py --test-email   # email only: a test sent to the newsletter's own inbox
    python3 scripts/send_alerts.py --test-live    # a labelled test sent to the list, only while it has <= 3 confirmed

--test-email creates a Buttondown draft and sends it as a test (Buttondown's send-draft endpoint), which goes to
the account owner unless the optional BUTTONDOWN_TEST_TO secret names other addresses (comma-separated). No address
is ever printed: the workflow logs of a public repository are public.
"""
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PENDING = os.path.join(ROOT, "data", "events_pending.json")


def body_text(events, site, test):
    lines = []
    if test:
        lines += ["This is a test of the alert pipeline. Nothing has changed on the leaderboard.", ""]
    for e in events:
        # GitHub turns "#<digits>" into issue links, so never write it.
        lines += ["## " + re.sub(r"#(?=\d)", "No. ", e["title"]), re.sub(r"#(?=\d)", "No. ", e.get("detail", "")), ""]
    lines += [f"Live leaderboard and forecast: {site['site_url']}",
              "Scores: Epoch Capabilities Index (Epoch AI, CC BY 4.0)."]
    return "\n".join(lines)


def github_release(title, body, test):
    tag = "alert-" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S") + ("-test" if test else "")
    cmd = ["gh", "release", "create", tag, "--title", title, "--notes", body]
    if test:
        cmd.append("--prerelease")
    r = subprocess.run(cmd, capture_output=True, text=True)
    print("release:", r.stdout.strip() or r.stderr.strip())
    if r.returncode != 0:
        # Fail the job before the data commit, so the next run computes the same events and retries.
        sys.exit(f"GitHub release failed (exit {r.returncode}); events kept in {PENDING}")


def buttondown(subject, body, test, site):
    key = os.environ.get("BUTTONDOWN_API_KEY")
    nl = site.get("newsletter", {})
    if not key or not nl.get("send_alerts"):
        print("Buttondown: not configured, skipped")
        return
    payload = {"subject": subject, "body": body, "status": "draft" if test else nl.get("email_status", "about_to_send")}
    req = urllib.request.Request("https://api.buttondown.com/v1/emails", data=json.dumps(payload).encode(),
                                 headers={"Authorization": f"Token {key}", "Content-Type": "application/json",
                                          "X-Buttondown-Live-Dangerously": "true"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            print("Buttondown:", r.status, "(draft)" if test else "")
    except Exception as e:  # never fail the daily job over email
        print(f"::warning::Buttondown failed: {e}")


EMAIL_RE = re.compile(r"[^\s\"'<>@]+@[^\s\"'<>@]+")


def _bd(method, path, key, payload=None):
    req = urllib.request.Request("https://api.buttondown.com/v1" + path, method=method,
                                 data=None if payload is None else json.dumps(payload).encode(),
                                 headers={"Authorization": f"Token {key}", "Content-Type": "application/json",
                                          "X-Buttondown-Live-Dangerously": "true"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read().decode("utf-8", "replace")
            return r.status, (json.loads(raw) if raw.strip().startswith(("{", "[")) else {})
    except urllib.error.HTTPError as e:
        return e.code, {"error": EMAIL_RE.sub("<address>", e.read().decode("utf-8", "replace"))[:600]}


def test_email(site):
    """Create a draft and send it as a test to the newsletter owner (never to the subscriber list)."""
    key = os.environ.get("BUTTONDOWN_API_KEY")
    if not key:
        sys.exit("BUTTONDOWN_API_KEY is not set")
    subject = f"[Test] {site['site_name']} email alerts work"
    body = body_text([{"title": f"Test email from {site['site_name']}", "detail": "If you can read this in your inbox, email alerts work."}], site, True)
    st, draft = _bd("POST", "/emails", key, {"subject": subject, "body": body, "status": "draft"})
    print("Buttondown draft:", st)
    if st >= 300 or "id" not in draft:
        sys.exit(f"could not create the draft: {draft.get('error', '')}")
    to = [x.strip() for x in os.environ.get("BUTTONDOWN_TEST_TO", "").split(",") if x.strip()]
    st, res = _bd("POST", f"/emails/{draft['id']}/send-draft", key, {"recipients": to} if to else {})
    print("Buttondown send-draft:", st, "(no recipients given: Buttondown's default)" if not to else f"(to {len(to)} address(es) from BUTTONDOWN_TEST_TO)")
    # what Buttondown says it did, with any address masked (public logs)
    print("Buttondown response:", EMAIL_RE.sub("<address>", json.dumps(res))[:800])
    if st >= 300:
        sys.exit(f"send-draft failed: {res.get('error', '')}")


def test_live(site, max_list=3):
    """Send a clearly labelled test through the real alert path (a normal send to the whole list), but only while the
    list is tiny, so a test never reaches a real audience. Prints counts, never addresses."""
    key = os.environ.get("BUTTONDOWN_API_KEY")
    if not key:
        sys.exit("BUTTONDOWN_API_KEY is not set")
    st, subs = _bd("GET", "/subscribers", key)
    if st >= 300:
        sys.exit(f"could not read the subscriber list: {subs.get('error', '')}")
    items = subs.get("results", [])
    kinds = {}
    for x in items:
        k = x.get("type") or x.get("subscriber_type") or "unknown"
        kinds[k] = kinds.get(k, 0) + 1
    confirmed = kinds.get("regular", 0) if any(k != "unknown" for k in kinds) else len(items)
    print("Buttondown subscribers:", subs.get("count", len(items)), "by type:", kinds)
    if confirmed == 0:
        sys.exit("No confirmed subscribers yet; nothing to send.")
    if confirmed > max_list:
        sys.exit(f"{confirmed} confirmed subscribers: not sending a test to a real audience. Use --test-email instead.")
    subject = f"[Test] {site['site_name']} alert"
    body = body_text([{"title": f"Test alert from {site['site_name']}", "detail": "Sent through the same path as real alerts. If you can read this in your inbox, alerts reach you."}], site, True)
    st, res = _bd("POST", "/emails", key, {"subject": subject, "body": body, "status": "about_to_send"})
    print("Buttondown send to list:", st, "status:", res.get("status", ""), res.get("error", ""))
    if st >= 300:
        sys.exit("send failed")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--test-email", action="store_true")
    ap.add_argument("--test-live", action="store_true")
    a = ap.parse_args()
    if a.test_live:
        test_live(json.load(open(os.path.join(ROOT, "config", "site.json"), encoding="utf-8")))
        return
    if a.test_email:
        test_email(json.load(open(os.path.join(ROOT, "config", "site.json"), encoding="utf-8")))
        return
    site = json.load(open(os.path.join(ROOT, "config", "site.json"), encoding="utf-8"))
    if a.test:
        events = [{"title": f"Test alert from {site['site_name']}", "detail": "If you can read this, alerts work."}]
    elif os.path.exists(PENDING):
        events = json.load(open(PENDING, encoding="utf-8"))
    else:
        print("No events.")
        return
    if not events:
        return
    subject = ("[Test] " if a.test else "") + (events[0]["title"] if len(events) == 1 else f"{events[0]['title']} (+{len(events) - 1} more)")
    body = body_text(events, site, a.test)
    github_release(subject, body, a.test)
    buttondown(subject, body, a.test, site)
    if not a.test and os.path.exists(PENDING):
        os.remove(PENDING)


if __name__ == "__main__":
    main()
