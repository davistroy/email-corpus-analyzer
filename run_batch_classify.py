#!/usr/bin/env python
"""Standalone batch classification script with explicit progress output.

Bypasses CLI logging/buffering issues for better visibility when running
as a background task.
"""

import json
import os
import sys
import time
from pathlib import Path

# Force unbuffered output
os.environ["PYTHONUNBUFFERED"] = "1"


def log(msg: str) -> None:
    """Print with immediate flush."""
    print(msg, flush=True)


def main() -> None:
    t_start = time.time()
    log(f"=== BATCH CLASSIFY START: {time.strftime('%H:%M:%S')} ===")

    # Verify API key
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        log("ERROR: ANTHROPIC_API_KEY not set")
        sys.exit(1)
    log(f"API key: {api_key[:12]}...")

    import anthropic

    client = anthropic.Anthropic()

    # Load categories
    cats_path = Path.home() / "data/outputs/categories.yaml"
    import yaml

    cats_data = yaml.safe_load(cats_path.read_text(encoding="utf-8"))
    categories = [c["name"] for c in cats_data["categories"]]
    cat_descriptions = {c["name"]: c.get("description", "") for c in cats_data["categories"]}
    log(f"Categories: {len(categories)}")

    # Load corpus
    log("Loading corpus...")
    t0 = time.time()
    from src.models.corpus import Corpus

    corpus = Corpus.model_validate_json(
        (Path.home() / "data/outputs/email_corpus.json").read_text(encoding="utf-8")
    )
    log(f"Corpus loaded: {len(corpus.emails)} emails in {time.time() - t0:.1f}s")

    # Build batch classifier components
    from src.classifiers.batch_classifier import CLASSIFICATION_TOOL
    from src.classifiers.sanitizer import EmailSanitizer

    sanitizer = EmailSanitizer()

    # Build system prompt
    cat_lines = []
    for name in categories:
        desc = cat_descriptions.get(name, "")
        if desc:
            cat_lines.append(f"- {name}: {desc}")
        else:
            cat_lines.append(f"- {name}")
    system_prompt = (
        "You are an email classification assistant. "
        "Classify emails into exactly one of these categories:\n"
        + "\n".join(cat_lines)
        + "\n\nUse the classify_email tool to respond."
    )

    # Build all requests
    log("Building requests...")
    t0 = time.time()
    all_requests = []
    email_ids = []  # parallel list for mapping results back
    for idx, email in enumerate(corpus.emails):
        content = sanitizer.wrap_for_prompt(email.subject, email.body_text)
        user_prompt = (
            f"Classify the following email:\n\n"
            f"From: {email.sender_email} ({email.sender_domain})\n"
            f"{content}"
        )
        all_requests.append(
            {
                "custom_id": f"e{idx}",
                "params": {
                    "model": "claude-sonnet-4-6",
                    "max_tokens": 1024,
                    "temperature": 0.0,
                    "system": system_prompt,
                    "tools": [CLASSIFICATION_TOOL],
                    "tool_choice": {"type": "tool", "name": "classify_email"},
                    "messages": [{"role": "user", "content": user_prompt}],
                },
            }
        )
        email_ids.append(email.id)
        if (idx + 1) % 5000 == 0:
            log(f"  Built {idx + 1}/{len(corpus.emails)}")
    log(f"All {len(all_requests)} requests built in {time.time() - t0:.1f}s")

    # Submit in chunks of 1000
    chunk_size = 1000
    total_chunks = (len(all_requests) + chunk_size - 1) // chunk_size
    batch_ids = []
    submitted_count = 0

    for chunk_idx in range(total_chunks):
        start = chunk_idx * chunk_size
        end = min(start + chunk_size, len(all_requests))
        chunk = all_requests[start:end]

        log(
            f"\n--- Batch {chunk_idx + 1}/{total_chunks} "
            f"(emails {start}-{end - 1}, {len(chunk)} requests) ---"
        )

        # Submit
        t0 = time.time()
        try:
            batch = client.messages.batches.create(requests=chunk)
        except anthropic.BadRequestError as e:
            if "credit balance" in str(e).lower():
                log(f"CREDIT EXHAUSTED after {submitted_count} emails. Collecting partial results.")
                break
            raise
        t_submit = time.time() - t0
        log(f"Submitted in {t_submit:.1f}s: id={batch.id}")
        batch_ids.append((batch.id, start, end))
        submitted_count = end

        # Poll for completion
        poll_count = 0
        while True:
            batch = client.messages.batches.retrieve(batch.id)
            c = batch.request_counts
            if poll_count % 6 == 0:  # Log every 30s
                log(
                    f"  Polling: ok={c.succeeded} proc={c.processing} "
                    f"err={c.errored} ({time.time() - t0:.0f}s elapsed)"
                )
            if batch.processing_status == "ended":
                log(f"  DONE: ok={c.succeeded} err={c.errored} in {time.time() - t0:.0f}s")
                break
            poll_count += 1
            time.sleep(5)

    # Collect results
    log(f"\n=== Collecting results from {len(batch_ids)} batches ===")
    results = {}  # idx -> {category, confidence, reasoning, error}

    for batch_id, _start, _end in batch_ids:
        for result in client.messages.batches.results(batch_id):
            # Parse custom_id back to index
            idx = int(result.custom_id[1:])  # "e123" -> 123
            real_email_id = email_ids[idx]

            if result.result.type == "succeeded":
                msg = result.result.message
                # Find tool_use block
                for block in msg.content:
                    if block.type == "tool_use" and block.name == "classify_email":
                        inp = block.input
                        results[idx] = {
                            "email_id": real_email_id,
                            "category": inp.get("category", "Unknown"),
                            "confidence": inp.get("confidence", 0.0),
                            "reasoning": inp.get("reasoning", ""),
                        }
                        break
                else:
                    results[idx] = {
                        "email_id": real_email_id,
                        "category": "Unknown",
                        "confidence": 0.0,
                        "reasoning": "No tool_use block in response",
                        "error": True,
                    }
            else:
                results[idx] = {
                    "email_id": real_email_id,
                    "category": "Unknown",
                    "confidence": 0.0,
                    "reasoning": "",
                    "error": str(result.result),
                }

    # Build report
    log(f"\n=== Building report ({len(results)} results) ===")

    confidence_threshold = 0.6
    categorized = {}
    uncategorized_ids = []
    category_counts = {}

    for idx in range(len(corpus.emails)):
        email = corpus.emails[idx]
        r = results.get(idx)
        if r and r.get("confidence", 0) >= confidence_threshold and not r.get("error"):
            cat = r["category"]
            if cat not in category_counts:
                category_counts[cat] = 0
            category_counts[cat] += 1
            categorized[email.id] = {
                "category": cat,
                "confidence": r["confidence"],
                "source": "llm:claude",
            }
        else:
            uncategorized_ids.append(email.id)

    total = len(corpus.emails)
    cat_count = len(categorized)
    uncat_count = len(uncategorized_ids)
    coverage = cat_count / total * 100 if total > 0 else 0

    report = {
        "total_emails": total,
        "categorized_count": cat_count,
        "uncategorized_count": uncat_count,
        "coverage_percentage": round(coverage, 1),
        "submitted_count": submitted_count,
        "categories_used": dict(sorted(category_counts.items(), key=lambda x: -x[1])),
        "categorized_emails": categorized,
        "uncategorized_email_ids": uncategorized_ids,
    }

    # Save
    out_path = Path.home() / "data/outputs/classify_report_batch.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    t_total = time.time() - t_start
    log(f"\n{'=' * 60}")
    log("BATCH CLASSIFICATION COMPLETE")
    log(f"{'=' * 60}")
    log(f"Total time: {t_total:.0f}s ({t_total / 60:.1f} min)")
    log(f"Emails submitted: {submitted_count}/{total}")
    log(f"Results received: {len(results)}")
    log(f"Categorized: {cat_count} ({coverage:.1f}%)")
    log(f"Uncategorized: {uncat_count}")
    log(f"Categories used: {len(category_counts)}")
    log("\nTop categories:")
    for name, count in sorted(category_counts.items(), key=lambda x: -x[1])[:15]:
        log(f"  {name}: {count} ({count / total * 100:.1f}%)")
    log(f"\nReport saved: {out_path}")


if __name__ == "__main__":
    main()
