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
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
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
)
console = Console()
logger = get_logger(__name__)

# Subcommand groups
mailbox_app = typer.Typer(help="Manage email mailboxes")
app.add_typer(mailbox_app, name="mailbox")


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
    """Add a new mailbox for analysis."""
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


# ============================================================================
# EXTRACTION COMMANDS
# ============================================================================

@app.command("extract")
def extract(
    mailbox: Optional[str] = typer.Option(None, "--mailbox", "-m", help="Mailbox name or ID (default: all)"),
    since: Optional[str] = typer.Option(None, "--since", help="Extract emails since date (YYYY-MM-DD)"),
    folder: str = typer.Option("INBOX", "--folder", "-f", help="Folder to extract from"),
    batch_size: int = typer.Option(100, "--batch-size", "-b", help="Emails per batch"),
):
    """Extract emails from configured mailboxes."""
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
    mailbox: Optional[str] = typer.Option(None, "--mailbox", "-m", help="Mailbox to analyze (default: all)"),
    use_llm: bool = typer.Option(False, "--llm", help="Use LLM for cluster naming"),
    method: str = typer.Option("hdbscan", "--method", help="Clustering method: hdbscan, kmeans"),
    num_clusters: int = typer.Option(10, "--clusters", "-k", help="Number of clusters (for kmeans)"),
    min_cluster_size: int = typer.Option(10, "--min-size", help="Min cluster size (for hdbscan)"),
):
    """Analyze email corpus for patterns."""
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
    mailbox: Optional[str] = typer.Option(None, "--mailbox", "-m", help="Mailbox for suggestions"),
    use_llm: bool = typer.Option(False, "--llm", help="Use LLM for intelligent suggestions"),
    min_cluster_pct: float = typer.Option(5.0, "--min-cluster", help="Min cluster percentage"),
    min_sender_count: int = typer.Option(20, "--min-sender", help="Min emails from sender"),
):
    """Generate category suggestions."""
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
# REPORT COMMANDS
# ============================================================================

@app.command("report")
def report(
    mailbox: Optional[str] = typer.Option(None, "--mailbox", "-m", help="Mailbox for report"),
    format: str = typer.Option("markdown", "--format", "-f", help="Output format: markdown, json"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
    cross_mailbox: bool = typer.Option(False, "--cross-mailbox", help="Generate cross-mailbox analysis"),
):
    """Generate analysis report."""
    manager = MailboxManager()

    if cross_mailbox:
        console.print("Generating cross-mailbox report...")
        # TODO: Implement cross-mailbox analysis
        console.print("[yellow]Cross-mailbox analysis not yet implemented[/yellow]")
        return

    # Load analysis for single mailbox
    if mailbox:
        mb = manager.registry.get_mailbox(mailbox) or manager.registry.get_by_name(mailbox)
        if not mb:
            console.print(f"[red]Mailbox not found: {mailbox}[/red]")
            raise typer.Exit(1)
        analysis_path = mb.get_analysis_path(manager.data_dir)
        report_name = f"{mb.name}_report"
    else:
        analysis_path = manager.data_dir / "data" / "combined_analysis.json"
        report_name = "combined_report"

    if not analysis_path.exists():
        console.print(f"[red]No analysis results. Run analyze first.[/red]")
        raise typer.Exit(1)

    from src.models.analysis_results import AnalysisResults
    analysis_data = load_json(analysis_path)
    results = AnalysisResults(**analysis_data)

    # Generate report content
    if format == "json":
        content = analysis_data
        suffix = ".json"
    else:
        from src.generators.category_generator import CategoryGenerator
        generator = CategoryGenerator()

        # Load suggestions if available
        suggestions_path = analysis_path.parent / "suggestions.json"
        if suggestions_path.exists():
            from src.models.category import Category
            suggestions_data = load_json(suggestions_path)
            categories = [Category(**c) for c in suggestions_data]
            content = generator.generate_report(categories)
        else:
            content = f"# Analysis Report\n\nTotal emails: {results.volume_stats.total_emails}\n"
            content += f"Unique senders: {results.sender_analysis.unique_senders}\n"
            content += f"Content clusters: {len(results.content_clusters)}\n"
        suffix = ".md"

    # Write output
    if output:
        output_path = output
    else:
        output_path = manager.data_dir / "data" / f"{report_name}{suffix}"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if format == "json":
        save_json(content, output_path)
    else:
        output_path.write_text(content, encoding="utf-8")

    console.print(f"[green]Report saved to: {output_path}[/green]")


# ============================================================================
# PIPELINE COMMAND
# ============================================================================

@app.command("pipeline")
def pipeline(
    mailbox: Optional[str] = typer.Option(None, "--mailbox", "-m", help="Mailbox to process"),
    use_llm: bool = typer.Option(False, "--llm", help="Use LLM for intelligent analysis"),
    skip_extract: bool = typer.Option(False, "--skip-extract", help="Skip extraction step"),
):
    """Run complete analysis pipeline."""
    console.print(Panel(
        "[bold]Email Analysis Pipeline[/bold]\n\n"
        "Steps: Extract → Analyze → Suggest → Report",
        title="Pipeline",
    ))

    # Step 1: Extract
    if not skip_extract:
        console.print("\n[bold]Step 1/4: Extraction[/bold]")
        extract(mailbox=mailbox)
    else:
        console.print("\n[bold]Step 1/4: Extraction[/bold] (skipped)")

    # Step 2: Analyze
    console.print("\n[bold]Step 2/4: Analysis[/bold]")
    analyze(mailbox=mailbox, use_llm=use_llm)

    # Step 3: Suggest
    console.print("\n[bold]Step 3/4: Suggestions[/bold]")
    suggest(mailbox=mailbox, use_llm=use_llm)

    # Step 4: Report
    console.print("\n[bold]Step 4/4: Report[/bold]")
    report(mailbox=mailbox)

    console.print(Panel(
        "[green]Pipeline complete![/green]\n\n"
        "Review the generated report and suggestions.",
        title="Done",
    ))


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main entry point."""
    setup_logging()
    app()


if __name__ == "__main__":
    main()
