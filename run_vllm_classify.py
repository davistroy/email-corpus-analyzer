#!/usr/bin/env python
"""Async parallel email classifier for RunPod vLLM endpoints.

Uses the OpenAI-compatible API via RunPod serverless worker-vllm.
Fires concurrent requests to maximize throughput on RunPod serverless
endpoints. Relies on prompt-based JSON enforcement (Qwen2.5-7B-Instruct
reliably follows JSON output instructions).

Usage:
    # Full corpus classification:
    python run_vllm_classify.py --endpoint-id YOUR_ENDPOINT_ID

    # Classify only remaining uncategorized emails:
    python run_vllm_classify.py --endpoint-id YOUR_ENDPOINT_ID --remaining

    # Custom concurrency and model:
    python run_vllm_classify.py --endpoint-id abc123 --concurrency 32 --model Qwen/Qwen2.5-7B-Instruct

Environment:
    RUNPOD_API_KEY: Required. RunPod API key.
"""

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Force unbuffered output and UTF-8 encoding (Windows cp1252 can't handle emoji)
os.environ["PYTHONUNBUFFERED"] = "1"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def log(msg: str) -> None:
    """Print with timestamp and immediate flush."""
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


# ---------------------------------------------------------------------------
# Async classifier
# ---------------------------------------------------------------------------


def parse_json_content(content: str) -> dict:
    """Parse JSON from model response, handling common edge cases."""
    text = content.strip()
    # Strip markdown code fences
    if text.startswith("```"):
        text = text.split("\n", 1)[-1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3].strip()
        elif "```" in text:
            text = text[: text.rfind("```")].strip()
    return json.loads(text)


async def classify_email(
    client,
    model: str,
    system_prompt: str,
    user_prompt: str,
    email_id: str,
    semaphore: asyncio.Semaphore,
    categories: list[str],
    max_retries: int = 2,
) -> dict:
    """Classify a single email with retries and concurrency control."""
    async with semaphore:
        for attempt in range(max_retries + 1):
            try:
                response = await client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.0,
                    max_tokens=200,
                )
                content = response.choices[0].message.content
                parsed = parse_json_content(content)

                category = parsed.get("category", "")
                confidence = float(parsed.get("confidence", 0.0))
                reasoning = parsed.get("reasoning", "")

                # Validate category
                if category not in categories:
                    confidence = min(confidence, 0.3)
                    reasoning = f"[non-standard category '{category}'] {reasoning}"

                return {
                    "email_id": email_id,
                    "category": category,
                    "confidence": confidence,
                    "reasoning": reasoning,
                }

            except json.JSONDecodeError as e:
                if attempt < max_retries:
                    await asyncio.sleep(1)
                    continue
                return {
                    "email_id": email_id,
                    "category": "",
                    "confidence": 0.0,
                    "reasoning": "",
                    "error": f"JSON parse error: {e}",
                }
            except Exception as e:
                if attempt < max_retries:
                    await asyncio.sleep(2**attempt)
                    continue
                return {
                    "email_id": email_id,
                    "category": "",
                    "confidence": 0.0,
                    "reasoning": "",
                    "error": str(e),
                }
        return {
            "email_id": email_id,
            "category": "",
            "confidence": 0.0,
            "reasoning": "",
            "error": "max retries exceeded",
        }


async def run_classification(
    emails_to_classify: list[dict],
    categories: list[str],
    category_descriptions: dict[str, str],
    endpoint_id: str,
    api_key: str,
    model: str,
    concurrency: int,
    max_body_chars: int = 10000,
) -> list[dict]:
    """Run parallel classification of all emails."""
    from openai import AsyncOpenAI

    base_url = f"https://api.runpod.ai/v2/{endpoint_id}/openai/v1"
    client = AsyncOpenAI(base_url=base_url, api_key=api_key, timeout=120.0)
    semaphore = asyncio.Semaphore(concurrency)

    # Build system prompt — MUST be byte-identical for prefix caching
    cat_lines = []
    for name in categories:
        desc = category_descriptions.get(name, "")
        if desc:
            cat_lines.append(f"- {name}: {desc}")
        else:
            cat_lines.append(f"- {name}")

    system_prompt = (
        "You are an email classification assistant. "
        "Classify each email into exactly one of these categories:\n"
        + "\n".join(cat_lines)
        + '\n\nRespond with ONLY a JSON object: {"category": "...", "confidence": 0.0-1.0, "reasoning": "..."}. '
        "No other text."
    )

    log(f"System prompt: {len(system_prompt)} chars")
    log(f"Starting {len(emails_to_classify)} classifications with concurrency={concurrency}")

    # Build sanitizer
    from src.classifiers.sanitizer import EmailSanitizer

    sanitizer = EmailSanitizer()

    # Build user prompts
    truncated = 0
    tasks = []
    for email_data in emails_to_classify:
        body = email_data.get("body_text", "")
        if len(body) > max_body_chars:
            body = body[:max_body_chars] + "\n[...truncated]"
            truncated += 1
        content = sanitizer.wrap_for_prompt(
            email_data.get("subject", ""),
            body,
        )
        user_prompt = (
            f"Classify the following email:\n\n"
            f"From: {email_data.get('sender_email', '')} ({email_data.get('sender_domain', '')})\n"
            f"{content}"
        )
        tasks.append(
            classify_email(
                client=client,
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                email_id=email_data["id"],
                semaphore=semaphore,
                categories=categories,
            )
        )

    if truncated:
        log(f"Truncated {truncated} emails to {max_body_chars} chars")

    # Progress tracking
    total = len(tasks)
    results = []
    t_start = time.time()

    # Process with progress updates
    for completed, coro in enumerate(asyncio.as_completed(tasks), 1):
        result = await coro
        results.append(result)
        if completed % 100 == 0 or completed == total:
            elapsed = time.time() - t_start
            rate = completed / elapsed if elapsed > 0 else 0
            eta = (total - completed) / rate if rate > 0 else 0
            errors = sum(1 for r in results if "error" in r)
            log(
                f"Progress: {completed}/{total} ({completed / total * 100:.1f}%) "
                f"| {rate:.1f}/sec | ETA {eta:.0f}s | errors: {errors}"
            )

    await client.close()
    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Async vLLM email classifier")
    parser.add_argument("--endpoint-id", required=True, help="RunPod endpoint ID")
    parser.add_argument(
        "--remaining", action="store_true", help="Classify only uncategorized emails"
    )
    parser.add_argument("--concurrency", type=int, default=24, help="Max concurrent requests")
    parser.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct", help="Model name")
    parser.add_argument(
        "--confidence-threshold", type=float, default=0.6, help="Min confidence to accept"
    )
    args = parser.parse_args()

    t_start = time.time()
    log("=== VLLM CLASSIFY START ===")
    log(f"Endpoint: {args.endpoint_id}")
    log(f"Model: {args.model}")
    log(f"Concurrency: {args.concurrency}")
    log(f"Mode: {'remaining only' if args.remaining else 'full corpus'}")

    # Verify API key
    api_key = os.environ.get("RUNPOD_API_KEY", "")
    if not api_key:
        log("ERROR: RUNPOD_API_KEY not set")
        sys.exit(1)
    log(f"API key: {api_key[:8]}...")

    # Load categories
    import yaml

    cats_path = Path.home() / "data/outputs/categories.yaml"
    cats_data = yaml.safe_load(cats_path.read_text(encoding="utf-8"))
    categories = [c["name"] for c in cats_data["categories"]]
    cat_descriptions = {c["name"]: c.get("description", "") for c in cats_data["categories"]}
    log(f"Categories: {len(categories)}")

    # Load corpus as raw JSON (avoid Pydantic overhead for 79MB file)
    log("Loading corpus...")
    t0 = time.time()
    raw_corpus = json.loads(
        (Path.home() / "data/outputs/email_corpus.json").read_text(encoding="utf-8")
    )
    all_emails = raw_corpus["emails"]
    del raw_corpus  # free memory
    log(f"Corpus loaded: {len(all_emails)} emails in {time.time() - t0:.1f}s")

    # Load existing report if in remaining mode
    already_categorized = {}
    if args.remaining:
        report_path = Path.home() / "data/outputs/classify_report_batch.json"
        if report_path.exists():
            existing_report = json.loads(report_path.read_text(encoding="utf-8"))
            already_categorized = existing_report.get("categorized_emails", {})
            log(f"Existing report: {len(already_categorized)} already categorized")
        else:
            log("No existing report found, classifying all emails")
            args.remaining = False

    # Filter emails
    if args.remaining:
        emails_to_classify = [e for e in all_emails if e["id"] not in already_categorized]
        log(f"Emails to classify: {len(emails_to_classify)} (skipping {len(already_categorized)})")
    else:
        emails_to_classify = all_emails

    if not emails_to_classify:
        log("All emails already classified!")
        return

    # Run async classification
    results = asyncio.run(
        run_classification(
            emails_to_classify=emails_to_classify,
            categories=categories,
            category_descriptions=cat_descriptions,
            endpoint_id=args.endpoint_id,
            api_key=api_key,
            model=args.model,
            concurrency=args.concurrency,
        )
    )

    # Build merged report
    log("\n=== Building report ===")
    categorized = dict(already_categorized)
    category_counts = {}

    # Count existing
    for entry in categorized.values():
        cat = entry["category"]
        category_counts[cat] = category_counts.get(cat, 0) + 1

    # Add new results
    new_categorized = 0
    new_errors = 0
    for r in results:
        if "error" not in r and r["confidence"] >= args.confidence_threshold and r["category"]:
            cat = r["category"]
            category_counts[cat] = category_counts.get(cat, 0) + 1
            categorized[r["email_id"]] = {
                "category": cat,
                "confidence": r["confidence"],
                "source": f"llm:vllm:{args.model}",
            }
            new_categorized += 1
        else:
            if "error" in r:
                new_errors += 1

    # Build uncategorized list
    all_email_ids = [e["id"] for e in all_emails]
    categorized_ids = set(categorized.keys())
    uncategorized_ids = [eid for eid in all_email_ids if eid not in categorized_ids]

    total = len(all_emails)
    cat_count = len(categorized)
    uncat_count = len(uncategorized_ids)
    coverage = cat_count / total * 100 if total > 0 else 0

    report = {
        "total_emails": total,
        "categorized_count": cat_count,
        "uncategorized_count": uncat_count,
        "coverage_percentage": round(coverage, 1),
        "model": args.model,
        "endpoint_id": args.endpoint_id,
        "categories_used": dict(sorted(category_counts.items(), key=lambda x: -x[1])),
        "categorized_emails": categorized,
        "uncategorized_email_ids": uncategorized_ids,
    }

    # Save
    out_path = Path.home() / "data/outputs/classify_report_batch.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    t_total = time.time() - t_start
    log(f"\n{'=' * 60}")
    log("CLASSIFICATION COMPLETE")
    log(f"{'=' * 60}")
    log(f"Total time: {t_total:.0f}s ({t_total / 60:.1f} min)")
    log(f"Submitted: {len(emails_to_classify)}")
    log(f"New categorized: {new_categorized}")
    log(f"Errors: {new_errors}")
    log(f"Total categorized: {cat_count}/{total} ({coverage:.1f}%)")
    log(f"Uncategorized: {uncat_count}")
    log(f"Categories used: {len(category_counts)}")
    log("\nTop categories:")
    for name, count in sorted(category_counts.items(), key=lambda x: -x[1])[:15]:
        log(f"  {name}: {count} ({count / total * 100:.1f}%)")
    log(f"\nReport saved: {out_path}")


if __name__ == "__main__":
    main()
