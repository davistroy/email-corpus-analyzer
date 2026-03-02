#!/usr/bin/env python
"""Classify remaining emails via RunPod /runsync endpoint with aiohttp.

Uses direct HTTP calls instead of the OpenAI SDK to avoid proxy timeout issues
with RunPod's /openai/v1/ route on long emails.
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

os.environ["PYTHONUNBUFFERED"] = "1"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def log(msg: str) -> None:
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


async def classify_one(
    session, endpoint_url, api_key, model, system_prompt, user_prompt, email_id, semaphore
):
    """Classify one email via /runsync with explicit timeout."""
    async with semaphore:
        payload = {
            "input": {
                "openai_route": "/v1/chat/completions",
                "openai_input": {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_tokens": 200,
                    "temperature": 0.0,
                },
            }
        }
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        for attempt in range(3):
            try:
                async with session.post(
                    f"{endpoint_url}/runsync", headers=headers, json=payload, timeout=60
                ) as resp:
                    data = await resp.json()

                status = data.get("status")
                if status == "COMPLETED":
                    output = data.get("output", [{}])
                    if isinstance(output, list) and output:
                        content = (
                            output[0].get("choices", [{}])[0].get("message", {}).get("content", "")
                        )
                    else:
                        content = ""
                    # Parse JSON
                    text = content.strip()
                    if text.startswith("```"):
                        text = text.split("\n", 1)[-1]
                        if "```" in text:
                            text = text[: text.rfind("```")].strip()
                    parsed = json.loads(text)
                    return {
                        "email_id": email_id,
                        "category": parsed.get("category", ""),
                        "confidence": float(parsed.get("confidence", 0.0)),
                        "reasoning": parsed.get("reasoning", ""),
                    }
                if status == "IN_QUEUE":
                    # Workers not ready, retry after delay
                    if attempt < 2:
                        await asyncio.sleep(5)
                        continue
                    return {
                        "email_id": email_id,
                        "category": "",
                        "confidence": 0.0,
                        "reasoning": "",
                        "error": "IN_QUEUE",
                    }
                return {
                    "email_id": email_id,
                    "category": "",
                    "confidence": 0.0,
                    "reasoning": "",
                    "error": f"status={status}",
                }

            except (json.JSONDecodeError, KeyError, IndexError) as e:
                if attempt < 2:
                    await asyncio.sleep(1)
                    continue
                return {
                    "email_id": email_id,
                    "category": "",
                    "confidence": 0.0,
                    "reasoning": "",
                    "error": f"parse: {e}",
                }
            except Exception as e:
                if attempt < 2:
                    await asyncio.sleep(2**attempt)
                    continue
                return {
                    "email_id": email_id,
                    "category": "",
                    "confidence": 0.0,
                    "reasoning": "",
                    "error": str(e)[:100],
                }
        return {
            "email_id": email_id,
            "category": "",
            "confidence": 0.0,
            "reasoning": "",
            "error": "max retries exceeded",
        }


async def main_async():
    import aiohttp
    import yaml

    from src.classifiers.sanitizer import EmailSanitizer

    endpoint_id = sys.argv[1] if len(sys.argv) > 1 else "ugv18uy75v2262"
    model = "Qwen/Qwen2.5-7B-Instruct"
    max_body = 6000  # Aggressive truncation for remaining long emails
    concurrency = 12
    confidence_threshold = 0.6

    api_key = os.environ.get("RUNPOD_API_KEY", "")
    if not api_key:
        log("ERROR: RUNPOD_API_KEY not set")
        sys.exit(1)

    endpoint_url = f"https://api.runpod.ai/v2/{endpoint_id}"

    # Load categories
    cats_data = yaml.safe_load(
        (Path.home() / "data/outputs/categories.yaml").read_text(encoding="utf-8")
    )
    categories = [c["name"] for c in cats_data["categories"]]
    cat_descriptions = {c["name"]: c.get("description", "") for c in cats_data["categories"]}

    # Load corpus
    raw_corpus = json.loads(
        (Path.home() / "data/outputs/email_corpus.json").read_text(encoding="utf-8")
    )
    all_emails = raw_corpus["emails"]
    del raw_corpus

    # Load existing report
    report_path = Path.home() / "data/outputs/classify_report_batch.json"
    existing_report = json.loads(report_path.read_text(encoding="utf-8"))
    already_categorized = existing_report.get("categorized_emails", {})
    log(f"Already categorized: {len(already_categorized)}")

    emails_to_classify = [e for e in all_emails if e["id"] not in already_categorized]
    log(f"Remaining to classify: {len(emails_to_classify)}")

    if not emails_to_classify:
        log("All done!")
        return

    # Build system prompt
    cat_lines = []
    for name in categories:
        desc = cat_descriptions.get(name, "")
        cat_lines.append(f"- {name}: {desc}" if desc else f"- {name}")
    system_prompt = (
        "You are an email classification assistant. "
        "Classify each email into exactly one of these categories:\n"
        + "\n".join(cat_lines)
        + '\n\nRespond with ONLY a JSON object: {"category": "...", "confidence": 0.0-1.0, "reasoning": "..."}. '
        "No other text."
    )

    sanitizer = EmailSanitizer()
    semaphore = asyncio.Semaphore(concurrency)

    # Build tasks
    async with aiohttp.ClientSession() as session:
        tasks = []
        truncated = 0
        for email_data in emails_to_classify:
            body = email_data.get("body_text", "")
            if len(body) > max_body:
                body = body[:max_body] + "\n[...truncated]"
                truncated += 1
            content = sanitizer.wrap_for_prompt(email_data.get("subject", ""), body)
            user_prompt = (
                f"Classify the following email:\n\n"
                f"From: {email_data.get('sender_email', '')} ({email_data.get('sender_domain', '')})\n"
                f"{content}"
            )
            tasks.append(
                classify_one(
                    session,
                    endpoint_url,
                    api_key,
                    model,
                    system_prompt,
                    user_prompt,
                    email_data["id"],
                    semaphore,
                )
            )

        log(f"Truncated {truncated} emails to {max_body} chars")
        log(f"Firing {len(tasks)} requests (concurrency={concurrency})...")

        total = len(tasks)
        results = []
        t_start = time.time()

        for completed, coro in enumerate(asyncio.as_completed(tasks), 1):
            result = await coro
            results.append(result)
            if completed % 50 == 0 or completed == total:
                elapsed = time.time() - t_start
                rate = completed / elapsed if elapsed > 0 else 0
                errors = sum(1 for r in results if "error" in r)
                log(f"Progress: {completed}/{total} | {rate:.1f}/sec | errors: {errors}")

    # Merge results
    categorized = dict(already_categorized)
    category_counts = {}
    for entry in categorized.values():
        cat = entry["category"]
        category_counts[cat] = category_counts.get(cat, 0) + 1

    new_cat = 0
    new_err = 0
    for r in results:
        if "error" not in r and r["confidence"] >= confidence_threshold and r["category"]:
            cat = r["category"]
            category_counts[cat] = category_counts.get(cat, 0) + 1
            categorized[r["email_id"]] = {
                "category": cat,
                "confidence": r["confidence"],
                "source": f"llm:vllm:{model}",
            }
            new_cat += 1
        elif "error" in r:
            new_err += 1

    all_email_ids = [e["id"] for e in all_emails]
    categorized_ids = set(categorized.keys())
    uncategorized_ids = [eid for eid in all_email_ids if eid not in categorized_ids]

    total_emails = len(all_emails)
    cat_count = len(categorized)
    coverage = cat_count / total_emails * 100

    report = {
        "total_emails": total_emails,
        "categorized_count": cat_count,
        "uncategorized_count": len(uncategorized_ids),
        "coverage_percentage": round(coverage, 1),
        "model": model,
        "endpoint_id": endpoint_id,
        "categories_used": dict(sorted(category_counts.items(), key=lambda x: -x[1])),
        "categorized_emails": categorized,
        "uncategorized_email_ids": uncategorized_ids,
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    log(f"\n{'=' * 60}")
    log(f"New categorized: {new_cat}, errors: {new_err}")
    log(f"Total: {cat_count}/{total_emails} ({coverage:.1f}%)")
    log(f"Still uncategorized: {len(uncategorized_ids)}")
    log(f"Report saved: {report_path}")


if __name__ == "__main__":
    asyncio.run(main_async())
