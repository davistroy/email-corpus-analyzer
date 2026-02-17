# Email Corpus Extraction and Analysis - Technical Specification

## Document Version
Version: 1.0  
Date: October 5, 2025  
Purpose: Detailed implementation specification for AI coder

---

## Project Overview

### Objective
Build a system to extract all emails from a Hotmail inbox via M365 MCP server, analyze the corpus to discover natural patterns, and generate suggested email categories based on actual email data.

### Scope
This specification covers **Phase 0** only: corpus extraction and initial analysis. It does NOT cover the subsequent email-by-email categorization process.

### Success Criteria
1. Successfully extract 100% of emails from Hotmail inbox
2. Generate structured data file containing all email metadata and content
3. Analyze corpus and produce pattern discovery report
4. Suggest initial category structure with confidence metrics
5. All data stored locally for privacy

---

## Step 1: Extract Entire Inbox

### Requirements

#### 1.1 M365 MCP Server Integration

**Tools Available:**
The M365 MCP server provides the following tools for email access:
- `list_mail_messages` - List emails in inbox with filtering/pagination
- `get_mail_message` - Get full details of a specific email by ID
- `list_mail_folders` - List all mail folders
- `read_gmail_profile` - Get user email address (note: works for M365 too)

**Connection Assumptions:**
- M365 MCP server is already configured and authenticated
- User has granted appropriate permissions to access mail
- Server is accessible via standard MCP protocol

#### 1.2 Extraction Process

**Pseudo-code Workflow:**
```python
def extract_all_emails():
    """
    Extract all emails from Hotmail inbox via M365 MCP server
    """
    all_emails = []
    page_token = None
    
    while True:
        # Fetch batch of messages (M365 default: 10, max: 500)
        # Use maximum page size for efficiency
        response = list_mail_messages(
            top=500,  # Maximum results per page
            page_token=page_token,
            select=['id', 'subject', 'from', 'toRecipients', 
                   'receivedDateTime', 'bodyPreview', 'hasAttachments'],
            order_by=['receivedDateTime desc']
        )
        
        message_list = response['value']
        
        # For each message, fetch full details
        for message_summary in message_list:
            message_id = message_summary['id']
            
            # Get full message details including body
            full_message = get_mail_message(
                message_id=message_id,
                select=['id', 'subject', 'from', 'toRecipients',
                       'receivedDateTime', 'body', 'sender',
                       'ccRecipients', 'bccRecipients']
            )
            
            # Extract and structure data
            email_data = {
                'id': full_message['id'],
                'sender': extract_sender(full_message),
                'recipient': extract_recipient(full_message),
                'subject': full_message.get('subject', ''),
                'body_text': extract_body_text(full_message),
                'received_date': full_message.get('receivedDateTime'),
                'has_attachments': message_summary.get('hasAttachments', False)
            }
            
            all_emails.append(email_data)
            
            # Progress indicator
            if len(all_emails) % 50 == 0:
                print(f"Processed {len(all_emails)} emails...")
        
        # Check for more pages
        page_token = response.get('@odata.nextLink') or response.get('nextPageToken')
        if not page_token:
            break
    
    return all_emails
```

#### 1.3 Data Extraction Functions

**Extract Sender:**
```python
def extract_sender(message):
    """
    Extract sender email and name from message object
    
    Expected format from M365:
    {
        'from': {
            'emailAddress': {
                'address': 'john@example.com',
                'name': 'John Doe'
            }
        }
    }
    """
    from_field = message.get('from', {})
    email_address = from_field.get('emailAddress', {})
    
    return {
        'email': email_address.get('address', ''),
        'name': email_address.get('name', ''),
        'domain': extract_domain(email_address.get('address', ''))
    }

def extract_domain(email):
    """Extract domain from email address"""
    if '@' in email:
        return email.split('@')[1].lower()
    return ''
```

**Extract Recipient:**
```python
def extract_recipient(message):
    """
    Extract primary recipient (first 'to' address)
    
    Expected format from M365:
    {
        'toRecipients': [
            {
                'emailAddress': {
                    'address': 'recipient@example.com',
                    'name': 'Recipient Name'
                }
            }
        ]
    }
    """
    to_recipients = message.get('toRecipients', [])
    
    if to_recipients:
        first_recipient = to_recipients[0].get('emailAddress', {})
        return {
            'email': first_recipient.get('address', ''),
            'name': first_recipient.get('name', '')
        }
    
    return {'email': '', 'name': ''}
```

**Extract Body Text:**
```python
def extract_body_text(message):
    """
    Extract plain text from email body
    
    M365 body format:
    {
        'body': {
            'contentType': 'html' or 'text',
            'content': '<html>...' or 'plain text...'
        }
    }
    """
    body = message.get('body', {})
    content = body.get('content', '')
    content_type = body.get('contentType', 'text')
    
    if content_type == 'html':
        # Strip HTML tags to get plain text
        return strip_html(content)
    
    return content

def strip_html(html_content):
    """
    Remove HTML tags and decode entities
    Use BeautifulSoup or simple regex for basic stripping
    """
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Remove script and style elements
    for script in soup(['script', 'style']):
        script.decompose()
    
    # Get text and clean up whitespace
    text = soup.get_text()
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    text = ' '.join(chunk for chunk in chunks if chunk)
    
    return text
```

#### 1.4 Output File Format

**File Location:**
Save to: `/mnt/user-data/outputs/email_corpus.json`

**JSON Schema:**
```json
{
  "extraction_metadata": {
    "extraction_date": "2025-10-05T14:30:00Z",
    "total_emails": 1523,
    "source": "Hotmail/M365",
    "user_email": "user@hotmail.com"
  },
  "emails": [
    {
      "id": "AAMkAGI2T...",
      "sender": {
        "email": "john@example.com",
        "name": "John Doe",
        "domain": "example.com"
      },
      "recipient": {
        "email": "user@hotmail.com",
        "name": "User Name"
      },
      "subject": "Q3 Project Update",
      "body_text": "Hi team, here's the update on our Q3 progress...",
      "received_date": "2025-09-15T10:30:00Z",
      "has_attachments": false
    }
  ]
}
```

**File Size Considerations:**
- Typical email: ~2-5KB in JSON
- 1000 emails: ~2-5MB
- 10,000 emails: ~20-50MB
- Use UTF-8 encoding
- Pretty-print for readability (can compress later if needed)

#### 1.5 Error Handling

**Required Error Handling:**

```python
def safe_extract_all_emails():
    """Wrapper with comprehensive error handling"""
    try:
        all_emails = []
        failed_emails = []
        
        # Get message list with retry logic
        messages = fetch_all_message_ids_with_retry()
        
        for msg_summary in messages:
            try:
                # Fetch individual email with timeout
                email_data = fetch_single_email_with_retry(msg_summary['id'])
                all_emails.append(email_data)
                
            except MessageFetchError as e:
                # Log failed email but continue
                failed_emails.append({
                    'id': msg_summary['id'],
                    'error': str(e)
                })
                continue
            
            except Exception as e:
                # Unexpected error - log and continue
                log_error(f"Unexpected error processing {msg_summary['id']}: {e}")
                failed_emails.append({
                    'id': msg_summary['id'],
                    'error': f"Unexpected: {str(e)}"
                })
                continue
        
        # Save both successful and failed extractions
        save_results(all_emails, failed_emails)
        
        return {
            'success': True,
            'total_processed': len(all_emails),
            'failed_count': len(failed_emails),
            'failed_emails': failed_emails
        }
        
    except Exception as e:
        # Critical failure
        log_critical_error(e)
        return {
            'success': False,
            'error': str(e)
        }

def fetch_single_email_with_retry(message_id, max_retries=3):
    """Fetch single email with exponential backoff"""
    for attempt in range(max_retries):
        try:
            return get_mail_message(message_id=message_id)
        except RateLimitError:
            wait_time = 2 ** attempt  # 1s, 2s, 4s
            time.sleep(wait_time)
        except TimeoutError:
            if attempt == max_retries - 1:
                raise
            time.sleep(1)
    
    raise MessageFetchError(f"Failed to fetch after {max_retries} attempts")
```

**Error Log Format:**
Save to: `/mnt/user-data/outputs/extraction_errors.log`
```
[2025-10-05 14:30:15] ERROR: Failed to fetch email ID: AAMkAGI2T... - Timeout
[2025-10-05 14:30:20] ERROR: Failed to parse body for email ID: BBMkAGI3U... - Invalid HTML
```

#### 1.6 Progress Tracking

**Console Output:**
```
Starting email extraction...
Fetching message list...
Found 1,523 total emails to process

Processing batch 1/4...
[##########------------------------] 50/1523 emails (3.3%)

Processing batch 2/4...
[####################--------------] 500/1523 emails (32.8%)

...

Extraction complete!
Successfully processed: 1,521 emails
Failed: 2 emails (see extraction_errors.log)
Output saved to: /mnt/user-data/outputs/email_corpus.json
```

**Checkpoint System:**
```python
# Save progress every 100 emails in case of interruption
if len(all_emails) % 100 == 0:
    save_checkpoint({
        'emails_processed': len(all_emails),
        'last_processed_id': email_data['id'],
        'timestamp': datetime.now().isoformat()
    })
```

---

## Step 2: Run Analysis

### Requirements

#### 2.1 Analysis Components

The analysis should discover patterns across multiple dimensions:

1. **Sender Analysis**
2. **Subject Pattern Analysis**
3. **Content Semantic Analysis**
4. **Temporal Pattern Analysis**
5. **Volume Statistics**

#### 2.2 Sender Analysis

**Objective:** Group emails by sender characteristics to identify natural categories

**Implementation:**

```python
def analyze_senders(corpus):
    """
    Analyze sender patterns in email corpus
    
    Returns:
        - Sender frequency distribution
        - Domain clustering
        - Sender type classification
    """
    sender_stats = {}
    domain_stats = {}
    
    for email in corpus['emails']:
        sender_email = email['sender']['email']
        sender_domain = email['sender']['domain']
        
        # Count by sender
        if sender_email not in sender_stats:
            sender_stats[sender_email] = {
                'email': sender_email,
                'name': email['sender']['name'],
                'domain': sender_domain,
                'count': 0,
                'sample_subjects': [],
                'email_ids': []
            }
        
        sender_stats[sender_email]['count'] += 1
        sender_stats[sender_email]['email_ids'].append(email['id'])
        
        # Collect sample subjects (max 5 per sender)
        if len(sender_stats[sender_email]['sample_subjects']) < 5:
            sender_stats[sender_email]['sample_subjects'].append(email['subject'])
        
        # Count by domain
        domain_stats[sender_domain] = domain_stats.get(sender_domain, 0) + 1
    
    # Sort by frequency
    top_senders = sorted(
        sender_stats.values(),
        key=lambda x: x['count'],
        reverse=True
    )[:50]  # Top 50 senders
    
    top_domains = sorted(
        domain_stats.items(),
        key=lambda x: x[1],
        reverse=True
    )[:30]  # Top 30 domains
    
    return {
        'top_senders': top_senders,
        'top_domains': [{'domain': d, 'count': c} for d, c in top_domains],
        'unique_senders': len(sender_stats),
        'unique_domains': len(domain_stats)
    }
```

**Sender Type Classification:**

```python
def classify_sender_type(sender_data):
    """
    Classify sender as: personal, service, marketing, or work
    
    Uses heuristics:
    - Personal: Low volume, conversational subjects
    - Service: Specific service domains (bank, utility, etc.)
    - Marketing: High volume, promotional keywords, unsubscribe links
    - Work: Company domain, work-related keywords
    """
    domain = sender_data['domain']
    count = sender_data['count']
    subjects = sender_data['sample_subjects']
    
    # Service indicators
    service_domains = ['paypal.com', 'amazon.com', 'noreply', 'no-reply',
                       'notification', 'alerts', 'service']
    if any(sd in domain for sd in service_domains):
        return 'service'
    
    # Marketing indicators
    marketing_keywords = ['unsubscribe', 'promotional', 'offer', 'sale',
                          'discount', 'deal', 'newsletter']
    subject_text = ' '.join(subjects).lower()
    if count > 10 and any(kw in subject_text for kw in marketing_keywords):
        return 'marketing'
    
    # Work indicators (customize with user's company domain)
    # For now, use generic work keywords
    work_keywords = ['meeting', 'project', 'team', 'deadline', 're:', 'fwd:']
    if any(kw in subject_text for kw in work_keywords):
        return 'work'
    
    # Default to personal
    return 'personal'
```

#### 2.3 Subject Pattern Analysis

**Objective:** Identify recurring patterns in subject lines

```python
import re
from collections import Counter

def analyze_subject_patterns(corpus):
    """
    Extract common patterns from email subjects
    """
    all_subjects = [email['subject'] for email in corpus['emails']]
    
    # 1. Extract common prefixes
    prefixes = []
    for subject in all_subjects:
        # Match common prefixes: RE:, FWD:, etc.
        match = re.match(r'^(RE:|FWD:|Fwd:|Re:)\s*', subject, re.IGNORECASE)
        if match:
            prefixes.append(match.group(1).upper())
    
    prefix_counts = Counter(prefixes)
    
    # 2. Extract numbered patterns (e.g., "Invoice #12345")
    numbered_patterns = []
    for subject in all_subjects:
        # Find patterns like: "Invoice #123", "Order #456", etc.
        patterns = re.findall(r'(\w+)\s*[#№]\s*\d+', subject)
        numbered_patterns.extend(patterns)
    
    numbered_pattern_counts = Counter(numbered_patterns)
    
    # 3. Extract common keywords (excluding stop words)
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 
                  'to', 'for', 'of', 'with', 'by', 'from', 'up', 'about', 
                  'into', 'through', 'during', 'your', 'you', 'is', 'are'}
    
    all_words = []
    for subject in all_subjects:
        words = re.findall(r'\b\w+\b', subject.lower())
        filtered_words = [w for w in words if w not in stop_words and len(w) > 3]
        all_words.extend(filtered_words)
    
    keyword_counts = Counter(all_words).most_common(50)
    
    # 4. Identify bracket patterns [Tag], (Category), etc.
    bracket_patterns = []
    for subject in all_subjects:
        brackets = re.findall(r'[\[\(]([^\]\)]+)[\]\)]', subject)
        bracket_patterns.extend(brackets)
    
    bracket_counts = Counter(bracket_patterns).most_common(20)
    
    return {
        'common_prefixes': dict(prefix_counts),
        'numbered_patterns': dict(numbered_pattern_counts.most_common(20)),
        'top_keywords': keyword_counts,
        'bracket_tags': bracket_counts,
        'total_subjects_analyzed': len(all_subjects)
    }
```

#### 2.4 Content Semantic Analysis

**Objective:** Use embeddings and clustering to find thematic groups

**Implementation Option 1: Using Sentence Transformers (Recommended)**

```python
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans
import numpy as np

def analyze_content_semantics(corpus, num_clusters=10):
    """
    Cluster emails by semantic content similarity
    
    Args:
        corpus: Email corpus data
        num_clusters: Number of thematic clusters to create
    
    Returns:
        Cluster assignments and representative samples
    """
    # Initialize embedding model
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    emails = corpus['emails']
    
    # Create text representation for each email
    email_texts = []
    for email in emails:
        # Combine subject and first 500 chars of body
        combined_text = f"{email['subject']} {email['body_text'][:500]}"
        email_texts.append(combined_text)
    
    # Generate embeddings
    print("Generating embeddings...")
    embeddings = model.encode(email_texts, show_progress_bar=True)
    
    # Cluster emails
    print(f"Clustering into {num_clusters} groups...")
    kmeans = KMeans(n_clusters=num_clusters, random_state=42)
    cluster_labels = kmeans.fit_predict(embeddings)
    
    # Analyze each cluster
    clusters = []
    for i in range(num_clusters):
        cluster_indices = np.where(cluster_labels == i)[0]
        cluster_emails = [emails[idx] for idx in cluster_indices]
        
        # Get representative samples (closest to centroid)
        cluster_embeddings = embeddings[cluster_indices]
        centroid = kmeans.cluster_centers_[i]
        distances = np.linalg.norm(cluster_embeddings - centroid, axis=1)
        closest_indices = np.argsort(distances)[:5]
        
        representative_samples = [cluster_emails[idx] for idx in closest_indices]
        
        # Extract common themes
        all_subjects = [e['subject'] for e in cluster_emails]
        all_senders = [e['sender']['domain'] for e in cluster_emails]
        
        clusters.append({
            'cluster_id': i,
            'size': len(cluster_emails),
            'percentage': (len(cluster_emails) / len(emails)) * 100,
            'representative_samples': [
                {
                    'subject': sample['subject'],
                    'sender': sample['sender']['email'],
                    'body_preview': sample['body_text'][:200]
                }
                for sample in representative_samples
            ],
            'common_domains': Counter(all_senders).most_common(5),
            'email_ids': [e['id'] for e in cluster_emails]
        })
    
    # Sort clusters by size
    clusters.sort(key=lambda x: x['size'], reverse=True)
    
    return {
        'clusters': clusters,
        'num_clusters': num_clusters,
        'total_emails_clustered': len(emails)
    }
```

**Implementation Option 2: Using OpenAI/Claude API for sampling**

```python
def analyze_content_with_llm(corpus, sample_size=100):
    """
    Use LLM to analyze random sample and identify themes
    
    More cost-effective for large corpuses
    """
    import random
    
    emails = corpus['emails']
    
    # Take random sample
    sample = random.sample(emails, min(sample_size, len(emails)))
    
    # Create summary for LLM analysis
    sample_summaries = []
    for email in sample:
        sample_summaries.append({
            'sender_domain': email['sender']['domain'],
            'subject': email['subject'],
            'body_preview': email['body_text'][:300]
        })
    
    # This would be sent to Claude/GPT for analysis
    # (Implementation depends on API availability)
    
    return sample_summaries
```

**Dependencies Required:**
```
sentence-transformers==2.2.2
scikit-learn==1.3.0
numpy==1.24.3
```

#### 2.5 Temporal Pattern Analysis

```python
from datetime import datetime
from collections import defaultdict

def analyze_temporal_patterns(corpus):
    """
    Analyze when emails are received and identify patterns
    """
    emails = corpus['emails']
    
    # Group by sender and analyze frequency
    sender_timelines = defaultdict(list)
    
    for email in emails:
        sender = email['sender']['email']
        date = datetime.fromisoformat(email['received_date'].replace('Z', '+00:00'))
        sender_timelines[sender].append(date)
    
    # Classify senders by frequency
    frequency_classification = {}
    
    for sender, dates in sender_timelines.items():
        sorted_dates = sorted(dates)
        
        if len(dates) == 1:
            freq_type = 'one-time'
        elif len(dates) >= 10:
            # Check if regular
            date_diffs = [(sorted_dates[i+1] - sorted_dates[i]).days 
                          for i in range(len(sorted_dates)-1)]
            avg_diff = sum(date_diffs) / len(date_diffs)
            
            if avg_diff < 2:
                freq_type = 'daily'
            elif avg_diff < 8:
                freq_type = 'weekly'
            elif avg_diff < 35:
                freq_type = 'monthly'
            else:
                freq_type = 'occasional'
        else:
            freq_type = 'occasional'
        
        frequency_classification[sender] = {
            'type': freq_type,
            'count': len(dates),
            'first_email': sorted_dates[0].isoformat(),
            'last_email': sorted_dates[-1].isoformat()
        }
    
    # Summarize
    freq_summary = Counter([v['type'] for v in frequency_classification.values()])
    
    return {
        'frequency_distribution': dict(freq_summary),
        'sender_frequencies': frequency_classification
    }
```

#### 2.6 Volume Statistics

```python
def calculate_volume_statistics(corpus):
    """Calculate basic statistics about the email corpus"""
    emails = corpus['emails']
    
    total_emails = len(emails)
    
    # Body length stats
    body_lengths = [len(email['body_text']) for email in emails]
    avg_body_length = sum(body_lengths) / len(body_lengths)
    
    # Attachment stats
    with_attachments = sum(1 for email in emails if email['has_attachments'])
    
    # Date range
    dates = [datetime.fromisoformat(email['received_date'].replace('Z', '+00:00'))
             for email in emails]
    oldest = min(dates)
    newest = max(dates)
    date_span_days = (newest - oldest).days
    
    return {
        'total_emails': total_emails,
        'unique_senders': len(set(e['sender']['email'] for e in emails)),
        'date_range': {
            'oldest': oldest.isoformat(),
            'newest': newest.isoformat(),
            'span_days': date_span_days
        },
        'with_attachments': with_attachments,
        'attachment_percentage': (with_attachments / total_emails) * 100,
        'avg_body_length_chars': int(avg_body_length),
        'emails_per_day': total_emails / max(date_span_days, 1)
    }
```

#### 2.7 Master Analysis Function

```python
def run_full_analysis(corpus_file_path):
    """
    Run complete analysis on extracted corpus
    
    Args:
        corpus_file_path: Path to email_corpus.json
    
    Returns:
        Complete analysis results
    """
    # Load corpus
    with open(corpus_file_path, 'r', encoding='utf-8') as f:
        corpus = json.load(f)
    
    print("Starting corpus analysis...")
    print(f"Analyzing {len(corpus['emails'])} emails...")
    
    # Run all analyses
    results = {}
    
    print("\n1. Analyzing senders...")
    results['sender_analysis'] = analyze_senders(corpus)
    
    print("2. Analyzing subject patterns...")
    results['subject_patterns'] = analyze_subject_patterns(corpus)
    
    print("3. Analyzing content semantics...")
    results['content_clusters'] = analyze_content_semantics(corpus, num_clusters=10)
    
    print("4. Analyzing temporal patterns...")
    results['temporal_patterns'] = analyze_temporal_patterns(corpus)
    
    print("5. Calculating volume statistics...")
    results['volume_stats'] = calculate_volume_statistics(corpus)
    
    print("\nAnalysis complete!")
    
    # Save analysis results
    analysis_output_path = '/mnt/user-data/outputs/corpus_analysis_results.json'
    with open(analysis_output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"Results saved to: {analysis_output_path}")
    
    return results
```

#### 2.8 Analysis Output Format

**File Location:**
`/mnt/user-data/outputs/corpus_analysis_results.json`

**Schema:**
```json
{
  "sender_analysis": {
    "top_senders": [...],
    "top_domains": [...],
    "unique_senders": 342,
    "unique_domains": 156
  },
  "subject_patterns": {
    "common_prefixes": {"RE:": 45, "FWD:": 23},
    "numbered_patterns": {"Invoice": 12, "Order": 34},
    "top_keywords": [["meeting", 45], ["update", 38]],
    "bracket_tags": [["URGENT", 12], ["Team", 8]]
  },
  "content_clusters": {
    "clusters": [
      {
        "cluster_id": 0,
        "size": 234,
        "percentage": 15.4,
        "representative_samples": [...],
        "common_domains": [["amazon.com", 45]]
      }
    ]
  },
  "temporal_patterns": {...},
  "volume_stats": {...}
}
```

---

## Step 3: Generate Suggested Categories

### Requirements

#### 3.1 Category Generation Logic

```python
def generate_category_suggestions(analysis_results):
    """
    Use analysis results to suggest initial email categories
    
    Combines multiple signals:
    - Sender clustering
    - Content themes
    - Subject patterns
    - Temporal patterns
    """
    suggested_categories = []
    
    # 1. Categories from content clusters
    clusters = analysis_results['content_clusters']['clusters']
    
    for cluster in clusters:
        # Only suggest categories for significant clusters (>5% of emails)
        if cluster['percentage'] < 5:
            continue
        
        # Generate category name based on cluster characteristics
        category = generate_category_from_cluster(cluster)
        suggested_categories.append(category)
    
    # 2. Categories from high-volume senders
    top_senders = analysis_results['sender_analysis']['top_senders'][:10]
    
    for sender in top_senders:
        # If sender has >20 emails, might deserve own category
        if sender['count'] > 20:
            category = generate_category_from_sender(sender)
            suggested_categories.append(category)
    
    # 3. Domain-based categories
    top_domains = analysis_results['sender_analysis']['top_domains'][:15]
    
    domain_categories = generate_domain_categories(top_domains)
    suggested_categories.extend(domain_categories)
    
    # 4. Merge similar categories
    merged_categories = merge_similar_categories(suggested_categories)
    
    # 5. Add confidence scores
    scored_categories = score_category_confidence(merged_categories, analysis_results)
    
    # Sort by confidence
    scored_categories.sort(key=lambda x: x['confidence'], reverse=True)
    
    return scored_categories
```

#### 3.2 Category Generation from Clusters

```python
def generate_category_from_cluster(cluster):
    """
    Analyze cluster characteristics and suggest category name
    
    Uses LLM (Claude) to interpret cluster and suggest category
    """
    # Prepare cluster summary for LLM
    summary = {
        'size': cluster['size'],
        'percentage': cluster['percentage'],
        'sample_subjects': [s['subject'] for s in cluster['representative_samples']],
        'sample_senders': [s['sender'] for s in cluster['representative_samples']],
        'sample_bodies': [s['body_preview'] for s in cluster['representative_samples']],
        'common_domains': cluster['common_domains']
    }
    
    # Call LLM to interpret (pseudo-code - actual implementation uses Claude API)
    prompt = f"""
    Analyze this cluster of emails and suggest an appropriate category name.
    
    Cluster size: {summary['size']} emails ({summary['percentage']:.1f}% of inbox)
    
    Sample subjects:
    {chr(10).join(f"- {s}" for s in summary['sample_subjects'][:5])}
    
    Common sender domains:
    {chr(10).join(f"- {d[0]} ({d[1]} emails)" for d in summary['common_domains'][:3])}
    
    Sample content previews:
    {chr(10).join(f"- {s}" for s in summary['sample_bodies'][:3])}
    
    Suggest:
    1. A concise category name (2-4 words)
    2. A brief description
    3. What makes this cluster distinct
    
    Format as JSON:
    {{
      "category_name": "...",
      "description": "...",
      "distinguishing_features": ["...", "..."]
    }}
    """
    
    # This would call Claude API
    # For now, return structure
    return {
        'category_name': 'Generated Category',
        'description': 'Description based on cluster analysis',
        'source': 'content_cluster',
        'source_id': cluster['cluster_id'],
        'email_count': cluster['size'],
        'percentage': cluster['percentage'],
        'example_email_ids': cluster['email_ids'][:10],
        'distinguishing_features': []
    }
```

#### 3.3 Predefined Category Templates

```python
def apply_category_templates(analysis_results):
    """
    Apply common category templates based on known patterns
    """
    templates = [
        {
            'name': 'Financial & Banking',
            'keywords': ['invoice', 'payment', 'bank', 'statement', 'bill', 'credit'],
            'domains': ['paypal.com', 'chase.com', 'bankofamerica.com', 
                        'wellsfargo.com', 'stripe.com'],
            'description': 'Financial transactions, banking, and billing'
        },
        {
            'name': 'Shopping & E-commerce',
            'keywords': ['order', 'shipped', 'delivery', 'purchase', 'receipt'],
            'domains': ['amazon.com', 'ebay.com', 'etsy.com', 'shopify.com'],
            'description': 'Online shopping confirmations and shipping updates'
        },
        {
            'name': 'Social Media',
            'keywords': ['notification', 'mentioned', 'comment', 'friend request'],
            'domains': ['facebookmail.com', 'linkedin.com', 'twitter.com',
                        'instagram.com', 'tiktok.com'],
            'description': 'Social media notifications and updates'
        },
        {
            'name': 'Newsletters & Marketing',
            'keywords': ['unsubscribe', 'newsletter', 'promotional', 'offer',
                         'subscribe', 'digest'],
            'domains': [],
            'description': 'Marketing emails and newsletters'
        },
        {
            'name': 'Travel & Transportation',
            'keywords': ['flight', 'booking', 'reservation', 'itinerary',
                         'hotel', 'trip'],
            'domains': ['airlines.com', 'airbnb.com', 'booking.com',
                        'expedia.com', 'uber.com'],
            'description': 'Travel bookings and transportation'
        },
        {
            'name': 'Account & Security',
            'keywords': ['password', 'security', 'verify', 'confirm', '2fa',
                         'authentication', 'reset'],
            'domains': [],
            'description': 'Account security and verification emails'
        }
    ]
    
    matched_categories = []
    
    # Check which templates match the corpus
    for template in templates:
        match_score = calculate_template_match(template, analysis_results)
        
        if match_score > 0.1:  # At least 10% of emails match
            matched_categories.append({
                'category_name': template['name'],
                'description': template['description'],
                'source': 'template',
                'match_percentage': match_score * 100,
                'template_data': template
            })
    
    return matched_categories

def calculate_template_match(template, analysis_results):
    """Calculate what percentage of emails match a template"""
    # Count matches based on keywords and domains
    # Return percentage of total emails that match
    # (Simplified - actual implementation would scan corpus)
    return 0.15  # Placeholder
```

#### 3.4 Category Confidence Scoring

```python
def score_category_confidence(categories, analysis_results):
    """
    Assign confidence scores to each suggested category
    
    Confidence based on:
    - Number of emails in category
    - Consistency of signals (subject, sender, content alignment)
    - Distinctiveness from other categories
    """
    total_emails = analysis_results['volume_stats']['total_emails']
    
    for category in categories:
        signals = []
        
        # Signal 1: Volume (more emails = higher confidence)
        if 'email_count' in category:
            volume_score = min(category['email_count'] / total_emails * 2, 1.0)
            signals.append(volume_score)
        
        # Signal 2: Source type
        if category['source'] == 'template':
            signals.append(0.9)  # Templates are high confidence
        elif category['source'] == 'content_cluster':
            signals.append(0.75)  # Clusters are medium-high
        else:
            signals.append(0.6)  # Other sources medium
        
        # Signal 3: Percentage of corpus
        if 'percentage' in category:
            if category['percentage'] > 15:
                signals.append(0.9)
            elif category['percentage'] > 8:
                signals.append(0.7)
            else:
                signals.append(0.5)
        
        # Calculate overall confidence (average of signals)
        category['confidence'] = sum(signals) / len(signals)
        category['confidence_breakdown'] = {
            'signals_used': len(signals),
            'signal_scores': signals
        }
    
    return categories
```

#### 3.5 Category Suggestion Output

**Generate Human-Readable Report:**

```python
def generate_category_report(suggested_categories, analysis_results):
    """
    Create human-readable report of suggested categories
    """
    report_lines = []
    
    report_lines.append("# Email Category Suggestions")
    report_lines.append(f"\nBased on analysis of {analysis_results['volume_stats']['total_emails']} emails")
    report_lines.append(f"From {analysis_results['volume_stats']['unique_senders']} unique senders")
    report_lines.append("\n---\n")
    
    report_lines.append("## Suggested Categories\n")
    
    for i, category in enumerate(suggested_categories, 1):
        report_lines.append(f"### {i}. {category['category_name']}")
        report_lines.append(f"**Confidence:** {category['confidence']*100:.1f}%")
        report_lines.append(f"**Description:** {category['description']}")
        
        if 'email_count' in category:
            report_lines.append(f"**Estimated emails:** {category['email_count']} "
                               f"({category.get('percentage', 0):.1f}% of inbox)")
        
        if 'distinguishing_features' in category and category['distinguishing_features']:
            report_lines.append(f"**Key features:**")
            for feature in category['distinguishing_features']:
                report_lines.append(f"  - {feature}")
        
        if 'example_email_ids' in category:
            report_lines.append(f"**Sample size:** {len(category['example_email_ids'])} emails")
        
        report_lines.append("")  # Blank line
    
    report_lines.append("\n---\n")
    report_lines.append("## Next Steps\n")
    report_lines.append("1. Review suggested categories")
    report_lines.append("2. Modify, merge, or add new categories as needed")
    report_lines.append("3. Approve final category structure")
    report_lines.append("4. Begin email-by-email categorization with approved categories")
    
    return "\n".join(report_lines)
```

**Output Files:**

Save to `/mnt/user-data/outputs/category_suggestions.json`:
```json
{
  "generation_date": "2025-10-05T15:30:00Z",
  "total_emails_analyzed": 1523,
  "categories": [
    {
      "category_name": "Shopping & Orders",
      "description": "E-commerce purchases and shipping notifications",
      "confidence": 0.92,
      "email_count": 234,
      "percentage": 15.4,
      "source": "content_cluster",
      "example_email_ids": ["AAMk...", "BBMk..."],
      "distinguishing_features": [
        "Order confirmations",
        "Shipping tracking",
        "Delivery notifications"
      ]
    }
  ]
}
```

Save to `/mnt/user-data/outputs/category_suggestions_report.md`:
Markdown formatted report (from generate_category_report function)

---

## Step 4: Review and Approval Interface

### Requirements

#### 4.1 Interactive Review Process

```python
def interactive_category_review(suggested_categories, corpus):
    """
    Present categories to user for review and modification
    
    User can:
    - Accept category as-is
    - Rename category
    - Merge categories
    - Delete category
    - Add new custom category
    """
    print("\n" + "="*60)
    print("CATEGORY REVIEW - Interactive Mode")
    print("="*60)
    
    approved_categories = []
    
    for i, category in enumerate(suggested_categories, 1):
        print(f"\n--- Category {i} of {len(suggested_categories)} ---")
        print(f"Name: {category['category_name']}")
        print(f"Description: {category['description']}")
        print(f"Confidence: {category['confidence']*100:.1f}%")
        print(f"Emails: {category.get('email_count', 'Unknown')} "
              f"({category.get('percentage', 0):.1f}% of inbox)")
        
        # Show sample emails
        if 'example_email_ids' in category:
            print("\nSample emails in this category:")
            sample_ids = category['example_email_ids'][:3]
            for email_id in sample_ids:
                email = find_email_by_id(corpus, email_id)
                print(f"  - From: {email['sender']['email']}")
                print(f"    Subject: {email['subject']}")
        
        print("\nOptions:")
        print("  [A] Accept this category")
        print("  [R] Rename category")
        print("  [M] Merge with another category")
        print("  [D] Delete this category")
        print("  [S] Skip for now")
        
        choice = input("\nYour choice: ").strip().upper()
        
        if choice == 'A':
            approved_categories.append(category)
            print(f"✓ Category '{category['category_name']}' approved")
        
        elif choice == 'R':
            new_name = input("Enter new category name: ").strip()
            if new_name:
                category['category_name'] = new_name
                category['user_modified'] = True
                approved_categories.append(category)
                print(f"✓ Category renamed to '{new_name}' and approved")
        
        elif choice == 'M':
            print("\nAvailable categories to merge with:")
            for j, cat in enumerate(approved_categories, 1):
                print(f"  {j}. {cat['category_name']}")
            
            merge_choice = input("Enter category number to merge with (or 0 to cancel): ")
            try:
                merge_idx = int(merge_choice) - 1
                if 0 <= merge_idx < len(approved_categories):
                    target = approved_categories[merge_idx]
                    # Merge logic
                    merged = merge_categories(target, category)
                    approved_categories[merge_idx] = merged
                    print(f"✓ Merged into '{target['category_name']}'")
            except ValueError:
                print("Invalid choice, skipping")
        
        elif choice == 'D':
            print(f"✗ Category '{category['category_name']}' deleted")
            # Don't add to approved
        
        else:  # 'S' or invalid
            print("Skipped for review later")
    
    # Option to add custom categories
    print("\n" + "="*60)
    print("Would you like to add any custom categories?")
    while True:
        add_custom = input("Add custom category? (y/n): ").strip().lower()
        if add_custom != 'y':
            break
        
        custom_name = input("Category name: ").strip()
        custom_desc = input("Description: ").strip()
        
        if custom_name:
            approved_categories.append({
                'category_name': custom_name,
                'description': custom_desc,
                'source': 'custom',
                'confidence': 1.0,
                'user_created': True
            })
            print(f"✓ Custom category '{custom_name}' added")
    
    return approved_categories

def merge_categories(category1, category2):
    """Merge two categories"""
    merged = category1.copy()
    merged['category_name'] = f"{category1['category_name']} & {category2['category_name']}"
    merged['description'] = f"{category1['description']} | {category2['description']}"
    merged['email_count'] = category1.get('email_count', 0) + category2.get('email_count', 0)
    
    # Merge example email IDs
    ids1 = set(category1.get('example_email_ids', []))
    ids2 = set(category2.get('example_email_ids', []))
    merged['example_email_ids'] = list(ids1.union(ids2))
    
    merged['merged_from'] = [category1['category_name'], category2['category_name']]
    
    return merged
```

#### 4.2 Final Category Structure Output

After user approves categories, save final structure:

**File:** `/mnt/user-data/outputs/approved_categories.json`

```json
{
  "approval_date": "2025-10-05T16:00:00Z",
  "total_categories": 12,
  "categories": [
    {
      "category_id": "cat_001",
      "category_name": "Work - Projects",
      "description": "Work-related project communications and updates",
      "confidence": 0.95,
      "email_count": 156,
      "percentage": 10.2,
      "source": "content_cluster",
      "user_modified": false,
      "rules": {
        "sender_domains": ["company.com"],
        "keywords": ["project", "meeting", "deadline"],
        "example_email_ids": ["AAMk...", "BBMk..."]
      }
    },
    {
      "category_id": "cat_002",
      "category_name": "Personal",
      "description": "Personal correspondence with friends and family",
      "source": "custom",
      "user_created": true,
      "confidence": 1.0
    }
  ],
  "processing_stats": {
    "suggested_categories": 15,
    "approved_categories": 12,
    "modified_categories": 3,
    "merged_categories": 1,
    "deleted_categories": 2,
    "custom_categories": 1
  }
}
```

---

## Implementation Checklist

### Dependencies
```
# requirements.txt
beautifulsoup4==4.12.2
sentence-transformers==2.2.2
scikit-learn==1.3.0
numpy==1.24.3
```

### File Structure
```
/project/
├── extract_corpus.py          # Step 1: Extraction
├── analyze_corpus.py           # Step 2: Analysis
├── generate_categories.py      # Step 3: Category generation
├── review_interface.py         # Step 4: Interactive review
├── main.py                     # Orchestrator script
├── requirements.txt
└── /mnt/user-data/outputs/
    ├── email_corpus.json
    ├── extraction_errors.log
    ├── corpus_analysis_results.json
    ├── category_suggestions.json
    ├── category_suggestions_report.md
    └── approved_categories.json
```

### Main Orchestrator

```python
# main.py
def main():
    """
    Main orchestrator for email corpus extraction and analysis
    """
    print("Email Categorization System - Phase 0")
    print("Corpus Extraction and Analysis")
    print("="*60)
    
    # Step 1: Extract corpus
    print("\nStep 1: Extracting email corpus...")
    corpus_path = '/mnt/user-data/outputs/email_corpus.json'
    
    extraction_result = safe_extract_all_emails()
    
    if not extraction_result['success']:
        print(f"ERROR: Extraction failed - {extraction_result['error']}")
        return
    
    print(f"✓ Extracted {extraction_result['total_processed']} emails")
    if extraction_result['failed_count'] > 0:
        print(f"⚠ {extraction_result['failed_count']} emails failed (see extraction_errors.log)")
    
    # Step 2: Run analysis
    print("\nStep 2: Running corpus analysis...")
    analysis_results = run_full_analysis(corpus_path)
    print("✓ Analysis complete")
    
    # Step 3: Generate category suggestions
    print("\nStep 3: Generating category suggestions...")
    suggested_categories = generate_category_suggestions(analysis_results)
    
    # Apply templates
    template_categories = apply_category_templates(analysis_results)
    all_suggestions = suggested_categories + template_categories
    
    # Remove duplicates and score
    final_suggestions = merge_similar_categories(all_suggestions)
    final_suggestions = score_category_confidence(final_suggestions, analysis_results)
    
    # Save suggestions
    save_category_suggestions(final_suggestions)
    
    # Generate report
    report = generate_category_report(final_suggestions, analysis_results)
    save_category_report(report)
    
    print(f"✓ Generated {len(final_suggestions)} category suggestions")
    
    # Step 4: Interactive review
    print("\nStep 4: Review and approve categories...")
    corpus = load_corpus(corpus_path)
    approved_categories = interactive_category_review(final_suggestions, corpus)
    
    # Save approved categories
    save_approved_categories(approved_categories)
    
    print("\n" + "="*60)
    print("Phase 0 Complete!")
    print("="*60)
    print(f"\nApproved {len(approved_categories)} categories")
    print("\nOutput files:")
    print("  - email_corpus.json")
    print("  - corpus_analysis_results.json")
    print("  - category_suggestions.json")
    print("  - category_suggestions_report.md")
    print("  - approved_categories.json")
    print("\nReady to proceed to Phase 1: Email-by-email categorization")

if __name__ == "__main__":
    main()
```

---

## Error Handling & Edge Cases

### Common Issues

1. **Rate Limiting**
   - Implement exponential backoff
   - Add delays between batches (e.g., 100ms)
   - Respect API rate limits

2. **Large Inbox (10,000+ emails)**
   - Process in batches of 500
   - Save checkpoints every 1000 emails
   - Provide ETA and progress updates

3. **Malformed Emails**
   - Skip emails with missing required fields
   - Log errors but continue processing
   - Provide summary of skipped emails

4. **HTML Parsing Failures**
   - Fallback to raw text if HTML parsing fails
   - Use BeautifulSoup with error recovery
   - Log parsing failures

5. **Memory Constraints**
   - Stream processing for very large corpuses
   - Don't load all emails into memory at once
   - Use generators where possible

6. **Unicode/Encoding Issues**
   - Always use UTF-8 encoding
   - Handle encoding errors gracefully
   - Preserve special characters in JSON

### Testing Recommendations

1. **Test with small sample first** (10-20 emails)
2. **Verify M365 MCP connection** before full extraction
3. **Check output file formats** match specification
4. **Validate JSON structure** before analysis
5. **Test with different inbox sizes** (100, 1000, 10000 emails)

---

## Performance Targets

- **Extraction:** 50-100 emails per minute (depends on network/API)
- **Analysis:** Complete analysis in < 5 minutes for 1000 emails
- **Category generation:** < 2 minutes
- **Total time (1000 emails):** 20-30 minutes including review

---

## Deliverables

1. Working Python scripts for all steps
2. Generated output files in specified formats
3. Error logs and processing reports
4. Approved category structure ready for Phase 1

---

## Next Phase Preview

After completion of Phase 0, the next phase will be:
- Email-by-email categorization using approved categories
- Interactive learning system
- Pattern refinement based on user corrections
- Automation setup for daily processing

This specification provides complete implementation details for Phase 0 only.
