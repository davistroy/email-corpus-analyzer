#!/usr/bin/env python3
"""
Email Corpus Analyzer - Modern CLI with Typer.

Multi-provider, multi-mailbox email analysis system.

Commands:
  mailbox   - Manage email mailbox configurations
  extract   - Extract emails from mailboxes
  analyze   - Analyze email corpus for patterns
  suggest   - Generate category suggestions
  review    - Interactively review categories
  report    - Generate analysis reports
  pipeline  - Run complete workflow
"""
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table

from src.mailbox import MailboxManager, MailboxRegistry
from src.models.mailbox import MailboxStatus
from src.models.provider import ProviderType
from src.utils.file_manager import load_json, save_json
from src.utils.logger import get_logger, setup_logging

# Initialize
app = typer.Typer(
    name="email-analyzer",
    help="Multi-provider email corpus analysis with LLM-powered categorization",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()
logger = get_logger(__name__)

# Subcommand groups
mailbox_app = typer.Typer(help="Manage email mailboxes")
app.add_typer(mailbox_app, name="mailbox")

# Output formats
class OutputFormat:
    """Available output formats."""
    TABLE = "table"
    JSON = "json"
    MARKDOWN = "markdown"
    TEXT = "text"


# ============================================================================
# MAILBOX COMMANDS
# ============================================================================

@mailbox_app.command("add")
def mailbox_add(
    name: str = typer.Option(..., "--name", "-n", help="Friendly name for mailbox"),
    provider: str = typer.Option(..., "--provider", "-p", help="Provider: m365, gmail, imap"),
    email: str = typer.Option(..., "--email", "-e", help="Email address"),
    # M365 options
    tenant_id: Optional[str] = typer.Option(None, "--tenant", help="M365 tenant ID (for corporate)"),
    client_id: Optional[str] = typer.Option(None, "--client-id", help="M365 client ID"),
    # Gmail options
    credentials: Optional[Path] = typer.Option(None, "--credentials", help="Gmail credentials.json path"),
    # IMAP options
    host: Optional[str] = typer.Option(None, "--host", help="IMAP server hostname"),
    port: int = typer.Option(993, "--port", help="IMAP server port"),
    password: Optional[str] = typer.Option(None, "--password", help="IMAP password (will prompt if not provided)"),
):
    """
    Add a new mailbox for analysis.

    Configure a mailbox to extract and analyze emails from. Each provider
    has different authentication requirements:

    M365 (Microsoft 365/Outlook):
      • Personal accounts: No additional config needed
      • Corporate: Provide --tenant and --client-id

    Gmail:
      • Requires OAuth credentials.json from Google Cloud Console

    IMAP:
      • Requires --host and optionally --password

    Examples:
      email-analyzer mailbox add --name "Work" --provider m365 --email user@company.com
      email-analyzer mailbox add --name "Personal" --provider gmail --email user@gmail.com --credentials ~/creds.json
      email-analyzer mailbox add --name "Legacy" --provider imap --email user@oldmail.com --host imap.oldmail.com
    """
    try:
        provider_type = ProviderType(provider.lower())
    except ValueError:
        console.print(f"[red]Invalid provider: {provider}. Use: m365, gmail, imap[/red]")
        raise typer.Exit(1)

    # Build provider config
    provider_config = {}

    if provider_type == ProviderType.M365:
        if tenant_id:
            provider_config["tenant_id"] = tenant_id
        if client_id:
            provider_config["client_id"] = client_id

    elif provider_type == ProviderType.GMAIL:
        if not credentials:
            console.print("[red]Gmail requires --credentials path to credentials.json[/red]")
            raise typer.Exit(1)
        provider_config["credentials_file"] = str(credentials)

    elif provider_type == ProviderType.IMAP:
        if not host:
            console.print("[red]IMAP requires --host[/red]")
            raise typer.Exit(1)
        provider_config["host"] = host
        provider_config["port"] = port
        if password:
            provider_config["password"] = password
        else:
            # Prompt for password
            password = typer.prompt("IMAP password", hide_input=True)
            provider_config["password"] = password

    # Create mailbox
    manager = MailboxManager()
    mailbox = manager.add_mailbox(
        name=name,
        provider=provider_type,
        email_address=email,
        **provider_config,
    )

    console.print(Panel(
        f"[green]Mailbox added successfully![/green]\n\n"
        f"ID: {mailbox.id}\n"
        f"Name: {mailbox.name}\n"
        f"Provider: {mailbox.provider.value}\n"
        f"Email: {mailbox.email_address}\n"
        f"Status: {mailbox.status.value}\n\n"
        f"[yellow]Run 'email-analyzer mailbox auth {mailbox.id}' to authenticate[/yellow]",
        title="Mailbox Created",
    ))


@mailbox_app.command("list")
def mailbox_list(
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="Filter by provider"),
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status"),
):
    """List all configured mailboxes."""
    registry = MailboxRegistry()

    # Apply filters
    provider_filter = ProviderType(provider) if provider else None
    status_filter = MailboxStatus(status) if status else None

    mailboxes = registry.list_mailboxes(
        provider=provider_filter,
        status=status_filter,
    )

    if not mailboxes:
        console.print("[yellow]No mailboxes configured. Use 'email-analyzer mailbox add' to add one.[/yellow]")
        return

    table = Table(title="Configured Mailboxes")
    table.add_column("Name", style="cyan")
    table.add_column("Provider", style="magenta")
    table.add_column("Email", style="green")
    table.add_column("Status", style="yellow")
    table.add_column("Emails", justify="right")
    table.add_column("Last Sync")
    table.add_column("ID", style="dim")

    for mb in mailboxes:
        status_color = {
            MailboxStatus.ACTIVE: "green",
            MailboxStatus.PAUSED: "yellow",
            MailboxStatus.ERROR: "red",
            MailboxStatus.PENDING_AUTH: "yellow",
        }.get(mb.status, "white")

        last_sync = mb.extraction.last_extraction.strftime("%Y-%m-%d %H:%M") if mb.extraction.last_extraction else "-"

        table.add_row(
            mb.name,
            mb.provider.value,
            mb.email_address,
            f"[{status_color}]{mb.status.value}[/{status_color}]",
            str(mb.extraction.total_emails) if mb.extraction.total_emails else "-",
            last_sync,
            str(mb.id)[:8],
        )

    console.print(table)


@mailbox_app.command("auth")
def mailbox_auth(
    mailbox_id: str = typer.Argument(..., help="Mailbox ID or name"),
):
    """Authenticate a mailbox."""
    manager = MailboxManager()
    registry = manager.registry

    # Find mailbox by ID or name
    mailbox = registry.get_mailbox(mailbox_id) or registry.get_by_name(mailbox_id)
    if not mailbox:
        console.print(f"[red]Mailbox not found: {mailbox_id}[/red]")
        raise typer.Exit(1)

    console.print(f"Authenticating mailbox: {mailbox.name} ({mailbox.provider.value})")

    try:
        success = asyncio.run(manager.authenticate_mailbox(mailbox.id))
        if success:
            console.print(f"[green]Authentication successful![/green]")
        else:
            console.print(f"[red]Authentication failed[/red]")
            raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Authentication error: {e}[/red]")
        raise typer.Exit(1)


@mailbox_app.command("remove")
def mailbox_remove(
    mailbox_id: str = typer.Argument(..., help="Mailbox ID or name"),
    delete_data: bool = typer.Option(False, "--delete-data", help="Also delete extracted data"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Remove a mailbox configuration."""
    manager = MailboxManager()
    registry = manager.registry

    mailbox = registry.get_mailbox(mailbox_id) or registry.get_by_name(mailbox_id)
    if not mailbox:
        console.print(f"[red]Mailbox not found: {mailbox_id}[/red]")
        raise typer.Exit(1)

    if not force:
        confirm = typer.confirm(
            f"Remove mailbox '{mailbox.name}'?" +
            (" (including all data)" if delete_data else "")
        )
        if not confirm:
            raise typer.Abort()

    manager.remove_mailbox(mailbox.id, delete_data=delete_data)
    console.print(f"[green]Mailbox removed: {mailbox.name}[/green]")


@mailbox_app.command("info")
def mailbox_info(
    mailbox_id: str = typer.Argument(..., help="Mailbox ID or name"),
    format: str = typer.Option("text", "--format", "-f", help="Output format: text, json"),
):
    """Show detailed information about a mailbox."""
    manager = MailboxManager()
    registry = manager.registry

    mailbox = registry.get_mailbox(mailbox_id) or registry.get_by_name(mailbox_id)
    if not mailbox:
        console.print(f"[red]Mailbox not found: {mailbox_id}[/red]")
        raise typer.Exit(1)

    if format == "json":
        # Output as JSON
        output = {
            "id": str(mailbox.id),
            "name": mailbox.name,
            "provider": mailbox.provider.value,
            "email_address": mailbox.email_address,
            "status": mailbox.status.value,
            "extraction": {
                "total_emails": mailbox.extraction.total_emails,
                "last_extraction": mailbox.extraction.last_extraction.isoformat() if mailbox.extraction.last_extraction else None,
                "corpus_path": mailbox.corpus_path,
            },
            "analysis": {
                "last_analysis": mailbox.analysis.last_analysis.isoformat() if mailbox.analysis.last_analysis else None,
                "analysis_path": mailbox.analysis.analysis_path,
            },
            "provider_config": mailbox.provider_config,
        }
        console.print_json(data=output)
    else:
        # Output as formatted text
        status_color = {
            MailboxStatus.ACTIVE: "green",
            MailboxStatus.PAUSED: "yellow",
            MailboxStatus.ERROR: "red",
            MailboxStatus.PENDING_AUTH: "yellow",
        }.get(mailbox.status, "white")

        info_text = f"""[bold]Mailbox Information[/bold]

[cyan]Basic Info:[/cyan]
  ID: {mailbox.id}
  Name: {mailbox.name}
  Provider: {mailbox.provider.value}
  Email: {mailbox.email_address}
  Status: [{status_color}]{mailbox.status.value}[/{status_color}]

[cyan]Extraction:[/cyan]
  Total Emails: {mailbox.extraction.total_emails or 0}
  Last Extraction: {mailbox.extraction.last_extraction.strftime("%Y-%m-%d %H:%M:%S") if mailbox.extraction.last_extraction else "Never"}
  Corpus Path: {mailbox.corpus_path or "Not set"}

[cyan]Analysis:[/cyan]
  Last Analysis: {mailbox.analysis.last_analysis.strftime("%Y-%m-%d %H:%M:%S") if mailbox.analysis.last_analysis else "Never"}
  Analysis Path: {mailbox.analysis.analysis_path or "Not set"}

[cyan]Provider Configuration:[/cyan]"""

        for key, value in mailbox.provider_config.items():
            # Mask sensitive values
            if "password" in key.lower() or "secret" in key.lower():
                value = "********"
            info_text += f"\n  {key}: {value}"

        console.print(Panel(info_text, title=f"Mailbox: {mailbox.name}", border_style="blue"))


# ============================================================================
# EXTRACTION COMMANDS
# ============================================================================

@app.command("extract")
def extract(
    mailbox: Optional[str] = typer.Option(None, "--mailbox", "-m", help="Mailbox name or ID (default: all active)"),
    since: Optional[str] = typer.Option(None, "--since", help="Extract emails since date (YYYY-MM-DD)"),
    folder: str = typer.Option("INBOX", "--folder", "-f", help="Folder to extract from"),
    batch_size: int = typer.Option(100, "--batch-size", "-b", help="Emails per batch"),
):
    """
    Extract emails from configured mailboxes.

    Downloads emails from one or more mailboxes and stores them locally
    for analysis. Supports resumption if interrupted.

    Examples:
      email-analyzer extract
      email-analyzer extract --mailbox "Work"
      email-analyzer extract --since 2024-01-01 --batch-size 50
    """
    manager = MailboxManager()

    # Parse since date
    since_date = None
    if since:
        try:
            since_date = datetime.strptime(since, "%Y-%m-%d")
        except ValueError:
            console.print(f"[red]Invalid date format: {since}. Use YYYY-MM-DD[/red]")
            raise typer.Exit(1)

    # Find mailboxes to extract
    if mailbox:
        mb = manager.registry.get_mailbox(mailbox) or manager.registry.get_by_name(mailbox)
        if not mb:
            console.print(f"[red]Mailbox not found: {mailbox}[/red]")
            raise typer.Exit(1)
        mailbox_ids = [mb.id]
    else:
        mailboxes = manager.registry.list_mailboxes(status=MailboxStatus.ACTIVE)
        if not mailboxes:
            console.print("[yellow]No active mailboxes. Add and authenticate a mailbox first.[/yellow]")
            raise typer.Exit(1)
        mailbox_ids = [m.id for m in mailboxes]

    console.print(f"Extracting from {len(mailbox_ids)} mailbox(es)...")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Extracting emails...", total=None)

        def progress_callback(p):
            desc = f"Extracted {p.emails_fetched} emails"
            if p.total_emails:
                desc += f" / {p.total_emails}"
            progress.update(task, description=desc)

        try:
            results = asyncio.run(manager.extract_all_mailboxes(
                mailbox_ids=mailbox_ids,
                batch_size=batch_size,
                since=since_date,
                folder=folder,
            ))

            # Summary
            total_emails = sum(c.extraction_metadata.total_emails for c in results.values())
            console.print(f"\n[green]Extraction complete![/green]")
            console.print(f"Total emails extracted: {total_emails}")

            for mb_id, corpus in results.items():
                mb = manager.registry.get_mailbox(mb_id)
                console.print(f"  - {mb.name}: {len(corpus.emails)} emails")

        except Exception as e:
            console.print(f"[red]Extraction failed: {e}[/red]")
            raise typer.Exit(1)


# ============================================================================
# ANALYSIS COMMANDS
# ============================================================================

@app.command("analyze")
def analyze(
    mailbox: Optional[str] = typer.Option(None, "--mailbox", "-m", help="Mailbox to analyze (default: combined)"),
    use_llm: bool = typer.Option(False, "--llm", help="Use LLM for cluster naming"),
    method: str = typer.Option("hdbscan", "--method", help="Clustering method: hdbscan, kmeans"),
    num_clusters: int = typer.Option(10, "--clusters", "-k", help="Number of clusters (for kmeans)"),
    min_cluster_size: int = typer.Option(10, "--min-size", help="Min cluster size (for hdbscan)"),
):
    """
    Analyze email corpus for patterns.

    Runs multiple analyzers to identify:
      • High-volume senders and patterns
      • Subject line patterns and templates
      • Content clusters (semantic grouping)
      • Temporal patterns (time-of-day, day-of-week)
      • Volume statistics

    Examples:
      email-analyzer analyze
      email-analyzer analyze --mailbox "Work" --llm
      email-analyzer analyze --method kmeans --clusters 15
    """
    from src.analyzers import run_full_analysis
    from src.analyzers.semantic_analyzer import ClusteringMethod, SemanticAnalyzer
    from src.models.corpus import Corpus

    manager = MailboxManager()

    # Get corpus to analyze
    if mailbox:
        mb = manager.registry.get_mailbox(mailbox) or manager.registry.get_by_name(mailbox)
        if not mb:
            console.print(f"[red]Mailbox not found: {mailbox}[/red]")
            raise typer.Exit(1)
        corpus = manager.get_corpus(mb.id)
        if not corpus:
            console.print(f"[red]No corpus for mailbox. Run extract first.[/red]")
            raise typer.Exit(1)
    else:
        corpus = manager.get_combined_corpus()
        if not corpus:
            console.print("[red]No corpus available. Run extract first.[/red]")
            raise typer.Exit(1)

    console.print(f"Analyzing {len(corpus.emails)} emails...")

    # Configure clustering method
    cluster_method = ClusteringMethod.HDBSCAN if method.lower() == "hdbscan" else ClusteringMethod.KMEANS

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Running analysis...", total=5)

        try:
            results = run_full_analysis(
                corpus=corpus,
                num_clusters=num_clusters,
                progress_callback=lambda name, c, t: progress.update(task, description=f"Running {name} analysis..."),
            )

            progress.update(task, completed=5)

            # Save results
            if mailbox:
                mb = manager.registry.get_by_name(mailbox) or manager.registry.get_mailbox(mailbox)
                analysis_path = mb.get_analysis_path(manager.data_dir)
            else:
                analysis_path = manager.data_dir / "data" / "combined_analysis.json"

            analysis_path.parent.mkdir(parents=True, exist_ok=True)
            save_json(results.model_dump(mode="json"), analysis_path)

            # Summary
            console.print(f"\n[green]Analysis complete![/green]")
            console.print(f"Unique senders: {results.sender_analysis.unique_senders}")
            console.print(f"Content clusters: {len(results.content_clusters)}")
            console.print(f"Results saved to: {analysis_path}")

        except Exception as e:
            console.print(f"[red]Analysis failed: {e}[/red]")
            raise typer.Exit(1)


# ============================================================================
# SUGGESTION COMMANDS
# ============================================================================

@app.command("suggest")
def suggest(
    mailbox: Optional[str] = typer.Option(None, "--mailbox", "-m", help="Mailbox for suggestions (default: combined)"),
    use_llm: bool = typer.Option(False, "--llm", help="Use LLM for intelligent suggestions"),
    min_cluster_pct: float = typer.Option(5.0, "--min-cluster", help="Min cluster percentage"),
    min_sender_count: int = typer.Option(20, "--min-sender", help="Min emails from sender"),
):
    """
    Generate category suggestions.

    Uses analysis results to suggest organizational categories based on:
      • Content clusters
      • High-volume senders
      • Subject patterns
      • Domain patterns

    Examples:
      email-analyzer suggest
      email-analyzer suggest --mailbox "Work" --llm
      email-analyzer suggest --min-cluster 10.0 --min-sender 50
    """
    from src.generators.category_generator import CategoryGenerator
    from src.models.analysis_results import AnalysisResults

    manager = MailboxManager()

    # Load analysis results
    if mailbox:
        mb = manager.registry.get_mailbox(mailbox) or manager.registry.get_by_name(mailbox)
        if not mb:
            console.print(f"[red]Mailbox not found: {mailbox}[/red]")
            raise typer.Exit(1)
        analysis_path = mb.get_analysis_path(manager.data_dir)
    else:
        analysis_path = manager.data_dir / "data" / "combined_analysis.json"

    if not analysis_path.exists():
        console.print(f"[red]No analysis results. Run analyze first.[/red]")
        raise typer.Exit(1)

    try:
        analysis_data = load_json(analysis_path)
        results = AnalysisResults(**analysis_data)
    except Exception as e:
        console.print(f"[red]Failed to load analysis: {e}[/red]")
        raise typer.Exit(1)

    console.print("Generating category suggestions...")

    generator = CategoryGenerator(use_llm=use_llm)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Generating suggestions...", total=None)

        categories = generator.generate_suggestions(
            analysis_results=results,
            min_cluster_percentage=min_cluster_pct,
            min_sender_count=min_sender_count,
        )

        # Save suggestions
        if mailbox:
            suggestions_path = mb.get_suggestions_path(manager.data_dir)
        else:
            suggestions_path = manager.data_dir / "data" / "suggestions.json"

        suggestions_path.parent.mkdir(parents=True, exist_ok=True)
        save_json([c.model_dump(mode="json") for c in categories], suggestions_path)

        # Generate report
        report = generator.generate_report(categories)
        report_path = suggestions_path.with_suffix(".md")
        report_path.write_text(report, encoding="utf-8")

    console.print(f"\n[green]Generated {len(categories)} category suggestions![/green]")
    console.print(f"Suggestions saved to: {suggestions_path}")
    console.print(f"Report saved to: {report_path}")

    # Preview top 5
    table = Table(title="Top 5 Category Suggestions")
    table.add_column("Category", style="cyan")
    table.add_column("Confidence", justify="right")
    table.add_column("Count", justify="right")
    table.add_column("Source")

    for cat in categories[:5]:
        table.add_row(
            cat.category_name,
            f"{cat.confidence * 100:.0f}%",
            str(cat.email_count or "-"),
            cat.source.value,
        )

    console.print(table)


# ============================================================================
# REVIEW COMMANDS
# ============================================================================

@app.command("review")
def review(
    mailbox: Optional[str] = typer.Option(None, "--mailbox", "-m", help="Mailbox for review (default: combined)"),
    skip_cleanup: bool = typer.Option(False, "--skip-cleanup", help="Skip cleanup prompt after review"),
):
    """
    Interactively review category suggestions.

    Allows you to:
    - Accept, rename, merge, or delete suggested categories
    - Add custom categories
    - Optionally clean up intermediate files

    Examples:
      email-analyzer review
      email-analyzer review --mailbox "Work"
      email-analyzer review --skip-cleanup
    """
    from src.models.category import Category
    from src.ui.category_review import review_categories, cleanup_intermediate_files

    manager = MailboxManager()

    # Load suggestions
    if mailbox:
        mb = manager.registry.get_mailbox(mailbox) or manager.registry.get_by_name(mailbox)
        if not mb:
            console.print(f"[red]Mailbox not found: {mailbox}[/red]")
            raise typer.Exit(1)
        suggestions_path = mb.get_suggestions_path(manager.data_dir)
        approved_path = mb.get_approved_path(manager.data_dir)
        data_dir = mb.get_data_dir(manager.data_dir)
    else:
        suggestions_path = manager.data_dir / "data" / "suggestions.json"
        approved_path = manager.data_dir / "data" / "approved_categories.json"
        data_dir = manager.data_dir / "data"

    if not suggestions_path.exists():
        console.print(f"[red]No category suggestions found. Run 'suggest' first.[/red]")
        raise typer.Exit(1)

    try:
        suggestions_data = load_json(suggestions_path)
        # Handle both list format and dict format with 'categories' key
        if isinstance(suggestions_data, dict) and "categories" in suggestions_data:
            categories = [Category(**c) for c in suggestions_data["categories"]]
        else:
            categories = [Category(**c) for c in suggestions_data]

        console.print(f"[cyan]Starting interactive review of {len(categories)} categories...[/cyan]\n")

        # Run interactive review
        approved = review_categories(categories, output_path=approved_path)

        console.print(f"\n[green]Review complete! {len(approved)} categories approved.[/green]")
        console.print(f"[cyan]Approved categories saved to: {approved_path}[/cyan]")

        # Optional cleanup
        if not skip_cleanup:
            cleanup_intermediate_files(str(data_dir))

    except Exception as e:
        logger.error(f"Review failed: {e}", exc_info=True)
        console.print(f"[red]Review failed: {e}[/red]")
        raise typer.Exit(1)


# ============================================================================
# REPORT COMMANDS
# ============================================================================

@app.command("report")
def report(
    mailbox: Optional[str] = typer.Option(None, "--mailbox", "-m", help="Mailbox for report (default: combined)"),
    format: str = typer.Option("html", "--format", "-f", help="Output format: html, json, csv, markdown, table, all"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
    pretty: bool = typer.Option(True, "--pretty/--compact", help="Pretty print JSON (for json format)"),
    zip_csv: bool = typer.Option(True, "--zip/--no-zip", help="Export CSV as zip archive (for csv format)"),
    cross_mailbox: bool = typer.Option(False, "--cross-mailbox", help="Generate cross-mailbox analysis"),
):
    """
    Generate analysis report.

    Creates comprehensive reports from analysis results in multiple formats:
      • HTML: Interactive report with styling and visualizations
      • JSON: Structured data export with metadata
      • CSV: Tabular data files (multiple CSVs or zip)
      • Markdown: Simple text report
      • Table: Display in terminal
      • All: Generate all file formats (html, json, csv, markdown)

    Examples:
      email-analyzer report --format html
      email-analyzer report --mailbox "Work" --format json --output work_report.json
      email-analyzer report --format csv --no-zip
      email-analyzer report --format all
      email-analyzer report --cross-mailbox --format table
    """
    from src.models.analysis_results import AnalysisResults
    from src.models.category import Category
    from src.reports import (
        CSVReportGenerator,
        DirectoryCSVReportGenerator,
        HTMLReportGenerator,
        JSONReportGenerator,
        ReportMetadata,
    )

    manager = MailboxManager()

    if cross_mailbox:
        console.print("[cyan]Generating cross-mailbox report...[/cyan]")
        _generate_cross_mailbox_report(manager, format, output)
        return

    # Load analysis for mailbox or combined
    if mailbox:
        mb = manager.registry.get_mailbox(mailbox) or manager.registry.get_by_name(mailbox)
        if not mb:
            console.print(f"[red]Mailbox not found: {mailbox}[/red]")
            raise typer.Exit(1)
        analysis_path = mb.get_analysis_path(manager.data_dir)
        suggestions_path = mb.get_suggestions_path(manager.data_dir)
        report_name = f"{mb.name.replace(' ', '_')}_report"
        mailbox_name = mb.name
        mailbox_email = mb.email_address
    else:
        analysis_path = manager.data_dir / "data" / "combined_analysis.json"
        suggestions_path = manager.data_dir / "data" / "suggestions.json"
        report_name = "combined_report"
        mailbox_name = None
        mailbox_email = None

    if not analysis_path.exists():
        console.print(f"[red]No analysis results. Run analyze first.[/red]")
        raise typer.Exit(1)

    try:
        # Load analysis results
        analysis_data = load_json(analysis_path)
        results = AnalysisResults(**analysis_data)

        # Load categories if available
        categories = None
        if suggestions_path.exists():
            try:
                suggestions_data = load_json(suggestions_path)
                if isinstance(suggestions_data, dict) and "categories" in suggestions_data:
                    categories = [Category(**c) for c in suggestions_data["categories"]]
                else:
                    categories = [Category(**c) for c in suggestions_data]
            except Exception as e:
                logger.warning(f"Could not load categories: {e}")

        # Handle table format (terminal display)
        if format == "table":
            _display_analysis_table(results, mailbox_name or "Combined")
            return

        # Create metadata
        metadata = ReportMetadata(
            generated_at=datetime.now(),
            generator_version="2.0.0",
            mailbox_name=mailbox_name,
            mailbox_email=mailbox_email,
            total_emails=results.volume_stats.total_emails,
        )

        # Determine output directory
        if output:
            base_output = output
        else:
            base_output = manager.data_dir / "reports" / report_name

        # Generate reports based on format
        formats_to_generate = ["html", "json", "csv", "markdown"] if format == "all" else [format]

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Generating reports...", total=len(formats_to_generate))

            generated_files = []

            for fmt in formats_to_generate:
                progress.update(task, description=f"Generating {fmt.upper()} report...")

                try:
                    if fmt == "html":
                        generator = HTMLReportGenerator()
                        output_path = base_output.with_suffix(".html") if format != "all" else base_output.parent / f"{base_output.name}.html"
                        generator.save(output_path, results, categories, metadata=metadata)
                        generated_files.append(("HTML", output_path))

                    elif fmt == "json":
                        generator = JSONReportGenerator(pretty=pretty)
                        output_path = base_output.with_suffix(".json") if format != "all" else base_output.parent / f"{base_output.name}.json"
                        generator.save(output_path, results, categories, metadata=metadata)
                        generated_files.append(("JSON", output_path))

                    elif fmt == "csv":
                        if zip_csv:
                            generator = CSVReportGenerator(export_as_zip=True)
                            output_path = base_output.with_suffix(".zip") if format != "all" else base_output.parent / f"{base_output.name}_csv.zip"
                        else:
                            generator = DirectoryCSVReportGenerator()
                            output_path = base_output if format != "all" else base_output.parent / f"{base_output.name}_csv"
                        generator.save(output_path, results, categories, metadata=metadata)
                        generated_files.append(("CSV", output_path))

                    elif fmt == "markdown":
                        # Use the existing markdown generator from category generator
                        from src.generators.category_generator import CategoryGenerator
                        cat_generator = CategoryGenerator()

                        if categories:
                            content = cat_generator.generate_report(categories)
                        else:
                            content = _generate_basic_report(results)

                        output_path = base_output.with_suffix(".md") if format != "all" else base_output.parent / f"{base_output.name}.md"
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        output_path.write_text(content, encoding="utf-8")
                        generated_files.append(("Markdown", output_path))

                    progress.advance(task)

                except Exception as e:
                    console.print(f"[red]Error generating {fmt} report: {e}[/red]")
                    logger.exception(f"Report generation error for {fmt}")
                    continue

        # Display results
        console.print(f"\n[green]Report generation complete![/green]\n")

        if generated_files:
            table = Table(title="Generated Reports")
            table.add_column("Format", style="cyan")
            table.add_column("Path", style="green")

            for fmt, path in generated_files:
                table.add_row(fmt, str(path))

            console.print(table)
        else:
            console.print("[yellow]No reports were generated[/yellow]")

    except Exception as e:
        console.print(f"[red]Report generation failed: {e}[/red]")
        logger.exception("Report generation error")
        raise typer.Exit(1)


def _generate_cross_mailbox_report(manager: MailboxManager, format: str, output: Optional[Path]):
    """Generate cross-mailbox analysis report."""
    mailboxes = manager.registry.list_mailboxes()
    if not mailboxes:
        console.print("[yellow]No mailboxes configured.[/yellow]")
        return

    # Collect analysis results from all mailboxes
    all_results = {}
    for mailbox in mailboxes:
        analysis_path = mailbox.get_analysis_path(manager.data_dir)
        if analysis_path.exists():
            try:
                from src.models.analysis_results import AnalysisResults
                analysis_data = load_json(analysis_path)
                all_results[mailbox.name] = AnalysisResults(**analysis_data)
            except Exception as e:
                logger.warning(f"Failed to load analysis for {mailbox.name}: {e}")

    if not all_results:
        console.print("[yellow]No analysis results available. Run analyze first.[/yellow]")
        return

    if format == "table":
        # Display cross-mailbox comparison table
        table = Table(title="Cross-Mailbox Analysis")
        table.add_column("Mailbox", style="cyan")
        table.add_column("Total Emails", justify="right")
        table.add_column("Unique Senders", justify="right")
        table.add_column("Content Clusters", justify="right")
        table.add_column("Avg Daily Volume", justify="right")

        for name, results in all_results.items():
            table.add_row(
                name,
                str(results.volume_stats.total_emails),
                str(results.sender_analysis.unique_senders),
                str(len(results.content_clusters)),
                f"{results.volume_stats.emails_per_day:.1f}",
            )

        console.print(table)

    elif format == "json":
        # Generate JSON report
        output_data = {
            "report_date": datetime.now().isoformat(),
            "mailboxes": {},
            "totals": {
                "total_emails": sum(r.volume_stats.total_emails for r in all_results.values()),
                "total_senders": sum(r.sender_analysis.unique_senders for r in all_results.values()),
                "total_clusters": sum(len(r.content_clusters) for r in all_results.values()),
            }
        }

        for name, results in all_results.items():
            output_data["mailboxes"][name] = {
                "total_emails": results.volume_stats.total_emails,
                "unique_senders": results.sender_analysis.unique_senders,
                "content_clusters": len(results.content_clusters),
                "avg_daily_volume": results.volume_stats.emails_per_day,
            }

        output_path = output or manager.data_dir / "data" / "cross_mailbox_report.json"
        save_json(output_data, output_path)
        console.print(f"[green]Cross-mailbox report saved to: {output_path}[/green]")

    else:  # markdown
        # Generate markdown report
        content = "# Cross-Mailbox Analysis Report\n\n"
        content += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        content += f"## Summary\n\n"
        content += f"- Total Mailboxes: {len(all_results)}\n"
        content += f"- Total Emails: {sum(r.volume_stats.total_emails for r in all_results.values())}\n"
        content += f"- Total Unique Senders: {sum(r.sender_analysis.unique_senders for r in all_results.values())}\n\n"
        content += "## Mailbox Details\n\n"

        for name, results in all_results.items():
            content += f"### {name}\n\n"
            content += f"- Total Emails: {results.volume_stats.total_emails}\n"
            content += f"- Unique Senders: {results.sender_analysis.unique_senders}\n"
            content += f"- Content Clusters: {len(results.content_clusters)}\n"
            content += f"- Average Daily Volume: {results.volume_stats.emails_per_day:.1f}\n"
            content += f"- Date Range: {results.volume_stats.date_range_start.strftime('%Y-%m-%d')} to {results.volume_stats.date_range_end.strftime('%Y-%m-%d')}\n\n"

        output_path = output or manager.data_dir / "data" / "cross_mailbox_report.md"
        output_path.write_text(content, encoding="utf-8")
        console.print(f"[green]Cross-mailbox report saved to: {output_path}[/green]")


def _display_analysis_table(results, mailbox_name: str):
    """Display analysis results as a table."""
    from src.models.analysis_results import AnalysisResults

    console.print(Panel(
        f"[bold]Analysis Results: {mailbox_name}[/bold]",
        border_style="blue"
    ))

    # Volume statistics
    vol_table = Table(title="Volume Statistics")
    vol_table.add_column("Metric", style="cyan")
    vol_table.add_column("Value", justify="right")
    vol_table.add_row("Total Emails", str(results.volume_stats.total_emails))
    vol_table.add_row("Emails per Day", f"{results.volume_stats.emails_per_day:.1f}")
    vol_table.add_row("Date Range", f"{results.volume_stats.date_range_start.strftime('%Y-%m-%d')} to {results.volume_stats.date_range_end.strftime('%Y-%m-%d')}")
    console.print(vol_table)
    console.print()

    # Sender analysis
    sender_table = Table(title="Top Senders")
    sender_table.add_column("Sender", style="cyan")
    sender_table.add_column("Email Count", justify="right")
    sender_table.add_column("Percentage", justify="right")
    for sender in results.sender_analysis.top_senders[:10]:
        sender_table.add_row(
            sender.email,
            str(sender.email_count),
            f"{sender.percentage:.1f}%",
        )
    console.print(sender_table)
    console.print()

    # Content clusters
    if results.content_clusters:
        cluster_table = Table(title="Content Clusters")
        cluster_table.add_column("Cluster", justify="right")
        cluster_table.add_column("Size", justify="right")
        cluster_table.add_column("Percentage", justify="right")
        cluster_table.add_column("Suggested Name", style="cyan")
        for i, cluster in enumerate(results.content_clusters[:10], 1):
            cluster_table.add_row(
                str(i),
                str(cluster.size),
                f"{cluster.percentage:.1f}%",
                cluster.suggested_name or "—",
            )
        console.print(cluster_table)


def _generate_basic_report(results) -> str:
    """Generate a basic markdown report without suggestions."""
    from src.models.analysis_results import AnalysisResults

    content = f"# Email Analysis Report\n\n"
    content += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    content += f"## Summary\n\n"
    content += f"- Total Emails: {results.volume_stats.total_emails}\n"
    content += f"- Unique Senders: {results.sender_analysis.unique_senders}\n"
    content += f"- Content Clusters: {len(results.content_clusters)}\n"
    content += f"- Average Daily Volume: {results.volume_stats.emails_per_day:.1f}\n"
    content += f"- Date Range: {results.volume_stats.date_range_start.strftime('%Y-%m-%d')} to {results.volume_stats.date_range_end.strftime('%Y-%m-%d')}\n\n"

    content += f"## Top Senders\n\n"
    for sender in results.sender_analysis.top_senders[:10]:
        content += f"- **{sender.email}**: {sender.email_count} emails ({sender.percentage:.1f}%)\n"

    if results.content_clusters:
        content += f"\n## Content Clusters\n\n"
        for i, cluster in enumerate(results.content_clusters[:10], 1):
            content += f"### Cluster {i}\n"
            content += f"- Size: {cluster.size} emails ({cluster.percentage:.1f}%)\n"
            if cluster.suggested_name:
                content += f"- Name: {cluster.suggested_name}\n"
            content += "\n"

    return content


# ============================================================================
# PIPELINE COMMAND
# ============================================================================

@app.command("pipeline")
def pipeline(
    mailbox: Optional[str] = typer.Option(None, "--mailbox", "-m", help="Mailbox to process (default: all active)"),
    use_llm: bool = typer.Option(False, "--llm", help="Use LLM for intelligent analysis"),
    skip_extract: bool = typer.Option(False, "--skip-extract", help="Skip extraction step"),
    skip_review: bool = typer.Option(False, "--skip-review", help="Skip interactive review step"),
    skip_cleanup: bool = typer.Option(False, "--skip-cleanup", help="Skip cleanup after review"),
):
    """
    Run complete analysis pipeline.

    Executes all steps in sequence:
      1. Extract emails from mailbox(es)
      2. Analyze corpus for patterns
      3. Generate category suggestions
      4. Interactive review (optional)
      5. Generate final report

    Examples:
      email-analyzer pipeline
      email-analyzer pipeline --mailbox "Work" --llm
      email-analyzer pipeline --skip-extract --skip-review
    """
    console.print(Panel(
        "[bold]Email Analysis Pipeline[/bold]\n\n"
        "Steps: Extract → Analyze → Suggest → Review → Report",
        title="Pipeline Starting",
        border_style="blue",
    ))

    errors = []
    completed_steps = []

    try:
        # Step 1: Extract
        if not skip_extract:
            console.print("\n[bold cyan]Step 1/5: Extraction[/bold cyan]")
            try:
                extract(mailbox=mailbox)
                completed_steps.append("Extract")
            except typer.Exit as e:
                if e.exit_code != 0:
                    errors.append("Extraction failed")
                    _show_pipeline_error("Extraction", errors)
                    raise typer.Exit(1)
            except Exception as e:
                errors.append(f"Extraction error: {e}")
                _show_pipeline_error("Extraction", errors)
                raise typer.Exit(1)
        else:
            console.print("\n[bold yellow]Step 1/5: Extraction[/bold yellow] (skipped)")
            completed_steps.append("Extract (skipped)")

        # Step 2: Analyze
        console.print("\n[bold cyan]Step 2/5: Analysis[/bold cyan]")
        try:
            analyze(mailbox=mailbox, use_llm=use_llm)
            completed_steps.append("Analyze")
        except typer.Exit as e:
            if e.exit_code != 0:
                errors.append("Analysis failed")
                _show_pipeline_error("Analysis", errors)
                raise typer.Exit(1)
        except Exception as e:
            errors.append(f"Analysis error: {e}")
            _show_pipeline_error("Analysis", errors)
            raise typer.Exit(1)

        # Step 3: Suggest
        console.print("\n[bold cyan]Step 3/5: Suggestions[/bold cyan]")
        try:
            suggest(mailbox=mailbox, use_llm=use_llm)
            completed_steps.append("Suggest")
        except typer.Exit as e:
            if e.exit_code != 0:
                errors.append("Suggestion generation failed")
                _show_pipeline_error("Suggestions", errors)
                raise typer.Exit(1)
        except Exception as e:
            errors.append(f"Suggestion error: {e}")
            _show_pipeline_error("Suggestions", errors)
            raise typer.Exit(1)

        # Step 4: Review (optional)
        if not skip_review:
            console.print("\n[bold cyan]Step 4/5: Interactive Review[/bold cyan]")
            try:
                review(mailbox=mailbox, skip_cleanup=skip_cleanup)
                completed_steps.append("Review")
            except typer.Exit as e:
                if e.exit_code != 0:
                    errors.append("Review failed")
                    _show_pipeline_error("Review", errors)
                    raise typer.Exit(1)
            except Exception as e:
                errors.append(f"Review error: {e}")
                _show_pipeline_error("Review", errors)
                raise typer.Exit(1)
        else:
            console.print("\n[bold yellow]Step 4/5: Interactive Review[/bold yellow] (skipped)")
            completed_steps.append("Review (skipped)")

        # Step 5: Report
        console.print("\n[bold cyan]Step 5/5: Final Report[/bold cyan]")
        try:
            report(mailbox=mailbox, format="markdown")
            completed_steps.append("Report")
        except typer.Exit as e:
            if e.exit_code != 0:
                errors.append("Report generation failed")
                _show_pipeline_error("Report", errors)
                raise typer.Exit(1)
        except Exception as e:
            errors.append(f"Report error: {e}")
            _show_pipeline_error("Report", errors)
            raise typer.Exit(1)

        # Success!
        console.print(Panel(
            "[green bold]Pipeline Complete![/green bold]\n\n"
            f"Completed steps: {', '.join(completed_steps)}\n\n"
            "Next steps:\n"
            "  • Review the generated reports and approved categories\n"
            "  • Use 'email-analyzer report --cross-mailbox' for multi-mailbox analysis\n"
            "  • Run 'email-analyzer mailbox list' to see all configured mailboxes",
            title="Success",
            border_style="green",
        ))

    except KeyboardInterrupt:
        console.print("\n[yellow]Pipeline interrupted by user[/yellow]")
        if completed_steps:
            console.print(f"[cyan]Completed steps:[/cyan] {', '.join(completed_steps)}")
        raise typer.Exit(130)


def _show_pipeline_error(step: str, errors: list[str]):
    """Display pipeline error information."""
    console.print(Panel(
        f"[red bold]Pipeline Failed at: {step}[/red bold]\n\n"
        f"Errors:\n" + "\n".join(f"  • {e}" for e in errors) + "\n\n"
        "You can:\n"
        "  • Fix the error and run the pipeline again\n"
        "  • Use --skip-extract to resume from analysis\n"
        "  • Run individual commands separately for more control",
        title="Pipeline Error",
        border_style="red",
    ))


# ============================================================================
# UTILITY COMMANDS
# ============================================================================

@app.command("version")
def version():
    """Show version information."""
    console.print(Panel(
        "[bold cyan]Email Corpus Analyzer[/bold cyan]\n\n"
        "Version: 2.0.0\n"
        "Multi-provider email analysis with LLM-powered categorization\n\n"
        "[dim]Supported providers: M365, Gmail, IMAP[/dim]",
        border_style="blue"
    ))


@app.command("status")
def status():
    """
    Show overall system status.

    Displays configured mailboxes, extraction status, and available analyses.

    Example:
      email-analyzer status
    """
    manager = MailboxManager()
    registry = manager.registry

    mailboxes = registry.list_mailboxes()

    if not mailboxes:
        console.print("[yellow]No mailboxes configured. Use 'email-analyzer mailbox add' to get started.[/yellow]")
        return

    # Overall statistics
    total_emails = sum(m.extraction.total_emails or 0 for m in mailboxes)
    active_count = sum(1 for m in mailboxes if m.status == MailboxStatus.ACTIVE)
    pending_count = sum(1 for m in mailboxes if m.status == MailboxStatus.PENDING_AUTH)

    console.print(Panel(
        f"[bold]System Status[/bold]\n\n"
        f"[cyan]Mailboxes:[/cyan]\n"
        f"  Total: {len(mailboxes)}\n"
        f"  Active: {active_count}\n"
        f"  Pending Authentication: {pending_count}\n\n"
        f"[cyan]Emails:[/cyan]\n"
        f"  Total Extracted: {total_emails:,}\n\n"
        f"[cyan]Data Directory:[/cyan]\n"
        f"  {manager.data_dir}",
        title="Email Analyzer Status",
        border_style="blue"
    ))

    # Mailbox details
    table = Table(title="Mailbox Details")
    table.add_column("Name", style="cyan")
    table.add_column("Provider", style="magenta")
    table.add_column("Status", style="yellow")
    table.add_column("Emails", justify="right")
    table.add_column("Last Extraction")
    table.add_column("Last Analysis")

    for mb in mailboxes:
        status_emoji = {
            MailboxStatus.ACTIVE: "✓",
            MailboxStatus.PAUSED: "⏸",
            MailboxStatus.ERROR: "✗",
            MailboxStatus.PENDING_AUTH: "⚠",
        }.get(mb.status, "?")

        table.add_row(
            mb.name,
            mb.provider.value,
            f"{status_emoji} {mb.status.value}",
            str(mb.extraction.total_emails or 0),
            mb.extraction.last_extraction.strftime("%Y-%m-%d") if mb.extraction.last_extraction else "Never",
            mb.analysis.last_analysis.strftime("%Y-%m-%d") if mb.analysis.last_analysis else "Never",
        )

    console.print(table)

    # Next steps
    if pending_count > 0:
        console.print("\n[yellow]⚠ Some mailboxes need authentication. Run:[/yellow]")
        for mb in mailboxes:
            if mb.status == MailboxStatus.PENDING_AUTH:
                console.print(f"  email-analyzer mailbox auth {mb.name}")
    elif total_emails == 0:
        console.print("\n[cyan]→ Next step: Extract emails[/cyan]")
        console.print("  email-analyzer extract")
    else:
        console.print("\n[cyan]→ System ready! You can:[/cyan]")
        console.print("  • Run analysis: email-analyzer analyze")
        console.print("  • Run complete pipeline: email-analyzer pipeline")
        console.print("  • Generate report: email-analyzer report")


# ============================================================================
# MAIN
# ============================================================================

def main():
    """
    Email Corpus Analyzer - Multi-provider email analysis.

    A comprehensive tool for analyzing email patterns across multiple providers
    (M365, Gmail, IMAP) with LLM-powered categorization.

    Quick Start:
      1. Add a mailbox:     email-analyzer mailbox add --name "Work" --provider m365 --email you@company.com
      2. Authenticate:      email-analyzer mailbox auth Work
      3. Run pipeline:      email-analyzer pipeline

    Common Commands:
      mailbox add     - Configure a new mailbox
      extract         - Download emails
      analyze         - Find patterns
      suggest         - Generate categories
      review          - Approve suggestions
      report          - Generate reports
      pipeline        - Run all steps

    For detailed help on any command:
      email-analyzer COMMAND --help
    """
    setup_logging()
    try:
        app()
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        console.print(f"\n[red]Error: {e}[/red]")
        console.print("[dim]Run with --verbose for details[/dim]")
        sys.exit(1)


if __name__ == "__main__":
    main()
