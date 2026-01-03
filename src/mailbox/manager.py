"""
Mailbox manager for orchestrating operations across mailboxes.

Handles extraction, analysis, and cross-mailbox operations.
"""
import asyncio
from datetime import datetime
from pathlib import Path
from uuid import UUID

from src.models.corpus import Corpus
from src.models.mailbox import Mailbox, MailboxStatus
from src.models.provider import ProviderType
from src.providers import create_provider, get_provider_for_mailbox
from src.providers.base import AuthenticationError
from src.utils.file_manager import load_json, save_json
from src.utils.logger import get_logger

from .registry import MailboxRegistry

logger = get_logger(__name__)


class MailboxManager:
    """
    Orchestrate operations across multiple mailboxes.

    Provides high-level operations for extraction, analysis,
    and cross-mailbox aggregation.
    """

    def __init__(
        self,
        registry: MailboxRegistry | None = None,
        data_dir: Path | None = None,
    ):
        """
        Initialize the mailbox manager.

        Args:
            registry: Mailbox registry. Creates default if None.
            data_dir: Data directory. Defaults to ~/.email-analyzer
        """
        self.data_dir = data_dir or Path.home() / ".email-analyzer"
        self.registry = registry or MailboxRegistry(self.data_dir)
        self._ensure_data_dir()

    def _ensure_data_dir(self) -> None:
        """Ensure data directory structure exists."""
        (self.data_dir / "data").mkdir(parents=True, exist_ok=True)
        (self.data_dir / "credentials").mkdir(parents=True, exist_ok=True)
        # Secure permissions
        self.data_dir.chmod(0o700)

    def add_mailbox(
        self,
        name: str,
        provider: ProviderType,
        email_address: str,
        **provider_config,
    ) -> Mailbox:
        """
        Add a new mailbox configuration.

        Args:
            name: User-friendly display name.
            provider: Email provider type.
            email_address: Email address.
            **provider_config: Provider-specific configuration.

        Returns:
            Created Mailbox instance.
        """
        mailbox = Mailbox(
            name=name,
            provider=provider,
            email_address=email_address,
            provider_config=provider_config,
            status=MailboxStatus.PENDING_AUTH,
        )

        # Create mailbox data directory
        mailbox_dir = mailbox.get_data_dir(self.data_dir)
        mailbox_dir.mkdir(parents=True, exist_ok=True)
        (mailbox_dir / "checkpoints").mkdir(exist_ok=True)

        self.registry.add_mailbox(mailbox)
        logger.info(f"Created mailbox: {name} ({provider.value})")

        return mailbox

    async def authenticate_mailbox(self, mailbox_id: UUID | str) -> bool:
        """
        Authenticate a mailbox.

        Args:
            mailbox_id: Mailbox ID.

        Returns:
            True if authentication successful.

        Raises:
            KeyError: If mailbox not found.
        """
        mailbox = self.registry.get_mailbox(mailbox_id)
        if not mailbox:
            raise KeyError(f"Mailbox not found: {mailbox_id}")

        try:
            provider = get_provider_for_mailbox(mailbox)
            success = await provider.authenticate()

            if success:
                mailbox.set_active()
                self.registry.update_mailbox(mailbox)
                logger.info(f"Authenticated mailbox: {mailbox.name}")
            else:
                mailbox.set_error("Authentication failed")
                self.registry.update_mailbox(mailbox)

            await provider.close()
            return success

        except AuthenticationError as e:
            mailbox.set_error(str(e))
            self.registry.update_mailbox(mailbox)
            raise

    async def extract_mailbox(
        self,
        mailbox_id: UUID | str,
        batch_size: int = 100,
        since: datetime | None = None,
        folder: str = "INBOX",
        progress_callback=None,
    ) -> Corpus:
        """
        Extract emails from a mailbox.

        Args:
            mailbox_id: Mailbox ID.
            batch_size: Emails per batch.
            since: Only extract emails after this date.
            folder: Folder to extract from.
            progress_callback: Optional callback(current, total).

        Returns:
            Extracted Corpus.

        Raises:
            KeyError: If mailbox not found.
        """
        from src.extractors.async_extractor import AsyncEmailExtractor

        mailbox = self.registry.get_mailbox(mailbox_id)
        if not mailbox:
            raise KeyError(f"Mailbox not found: {mailbox_id}")

        provider = get_provider_for_mailbox(mailbox)

        try:
            extractor = AsyncEmailExtractor(
                provider=provider,
                mailbox=mailbox,
                data_dir=self.data_dir,
            )

            corpus = await extractor.extract_all(
                batch_size=batch_size,
                since=since,
                folder=folder,
                progress_callback=progress_callback,
            )

            # Update mailbox state
            mailbox.mark_extraction_complete(len(corpus.emails))
            mailbox.corpus_path = str(mailbox.get_corpus_path(self.data_dir))
            self.registry.update_mailbox(mailbox)

            # Save corpus
            corpus_path = mailbox.get_corpus_path(self.data_dir)
            save_json(corpus.model_dump(mode="json"), corpus_path)

            logger.info(f"Extracted {len(corpus.emails)} emails from {mailbox.name}")
            return corpus

        finally:
            await provider.close()

    async def extract_all_mailboxes(
        self,
        mailbox_ids: list[UUID | str] | None = None,
        concurrency: int = 3,
        **extract_kwargs,
    ) -> dict[UUID, Corpus]:
        """
        Extract from multiple mailboxes concurrently.

        Args:
            mailbox_ids: Specific mailboxes to extract. None = all active.
            concurrency: Maximum concurrent extractions.
            **extract_kwargs: Arguments passed to extract_mailbox.

        Returns:
            Dict mapping mailbox ID to extracted Corpus.
        """
        if mailbox_ids:
            mailboxes = [
                self.registry.get_mailbox(mid)
                for mid in mailbox_ids
            ]
            mailboxes = [m for m in mailboxes if m]
        else:
            mailboxes = self.registry.list_mailboxes(status=MailboxStatus.ACTIVE)

        if not mailboxes:
            logger.warning("No mailboxes to extract")
            return {}

        semaphore = asyncio.Semaphore(concurrency)
        results: dict[UUID, Corpus] = {}

        async def extract_one(mailbox: Mailbox) -> tuple[UUID, Corpus | Exception]:
            async with semaphore:
                try:
                    corpus = await self.extract_mailbox(
                        mailbox.id,
                        **extract_kwargs,
                    )
                    return mailbox.id, corpus
                except Exception as e:
                    logger.error(f"Failed to extract {mailbox.name}: {e}")
                    return mailbox.id, e

        tasks = [extract_one(m) for m in mailboxes]
        completed = await asyncio.gather(*tasks)

        for mailbox_id, result in completed:
            if isinstance(result, Corpus):
                results[mailbox_id] = result

        return results

    def get_corpus(self, mailbox_id: UUID | str) -> Corpus | None:
        """
        Load corpus for a mailbox.

        Args:
            mailbox_id: Mailbox ID.

        Returns:
            Corpus if exists, None otherwise.
        """
        mailbox = self.registry.get_mailbox(mailbox_id)
        if not mailbox:
            return None

        corpus_path = mailbox.get_corpus_path(self.data_dir)
        if not corpus_path.exists():
            return None

        try:
            data = load_json(corpus_path)
            return Corpus(**data)
        except Exception as e:
            logger.error(f"Failed to load corpus for {mailbox.name}: {e}")
            return None

    def get_all_corpora(self) -> dict[UUID, Corpus]:
        """
        Load all available corpora.

        Returns:
            Dict mapping mailbox ID to Corpus.
        """
        result = {}
        for mailbox in self.registry.list_mailboxes():
            corpus = self.get_corpus(mailbox.id)
            if corpus:
                result[mailbox.id] = corpus
        return result

    def get_combined_corpus(self) -> Corpus | None:
        """
        Combine all corpora into a single corpus.

        Returns:
            Combined Corpus, or None if no corpora available.
        """
        from src.models.corpus import Corpus, CorpusMetadata

        corpora = self.get_all_corpora()
        if not corpora:
            return None

        all_emails = []
        for corpus in corpora.values():
            all_emails.extend(corpus.emails)

        if not all_emails:
            return None

        # Create combined metadata
        metadata = CorpusMetadata(
            user_email=all_emails[0].sender_email,  # Placeholder
            extraction_date=datetime.now(),
            total_emails=len(all_emails),
            source="combined",
        )

        return Corpus(
            extraction_metadata=metadata,
            emails=all_emails,
            schema_version="2.0",
        )

    def remove_mailbox(self, mailbox_id: UUID | str, delete_data: bool = False) -> bool:
        """
        Remove a mailbox configuration.

        Args:
            mailbox_id: Mailbox ID.
            delete_data: Also delete extracted data.

        Returns:
            True if removed.
        """
        mailbox = self.registry.get_mailbox(mailbox_id)
        if not mailbox:
            return False

        if delete_data:
            import shutil
            data_dir = mailbox.get_data_dir(self.data_dir)
            if data_dir.exists():
                shutil.rmtree(data_dir)
                logger.info(f"Deleted data for mailbox: {mailbox.name}")

        return self.registry.remove_mailbox(mailbox_id)
