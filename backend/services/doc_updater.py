"""
Shopify Documentation Updater

Checks for documentation updates on application startup.
Automatically downloads and indexes new documentation when changes are detected.

Usage:
    from services.doc_updater import check_and_update_docs
    await check_and_update_docs()
"""

import asyncio
import hashlib
import logging
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

from sqlalchemy import text
from database.session import get_db_session

logger = logging.getLogger(__name__)


class DocUpdater:
    """Manages documentation updates"""

    def __init__(self, docs_dir: Optional[Path] = None, check_interval_days: int = 7):
        """
        Initialize documentation updater.

        Args:
            docs_dir: Path to shopify-api documentation directory
            check_interval_days: Minimum days between update checks
        """
        if docs_dir is None:
            backend_dir = Path(__file__).parent.parent
            docs_dir = backend_dir / "docs" / "shopify-api"

        self.docs_dir = docs_dir
        self.check_interval = timedelta(days=check_interval_days)

    async def should_check_for_updates(self) -> bool:
        """
        Check if enough time has passed since last update check.

        Returns:
            True if we should check for updates, False otherwise
        """
        async with get_db_session() as session:
            result = await session.execute(
                text("""
                    SELECT MAX(last_checked) as last_check
                    FROM docs_metadata
                """)
            )
            row = result.fetchone()

            if not row or not row[0]:
                logger.info("No previous update checks found - will check now")
                return True

            last_check = row[0]
            time_since_check = datetime.now(timezone.utc) - last_check

            if time_since_check > self.check_interval:
                logger.info(f"Last check was {time_since_check.days} days ago - will check for updates")
                return True
            else:
                logger.info(f"Last check was {time_since_check.days} days ago - skipping update check")
                return False

    async def get_current_content_hash(self) -> str:
        """Calculate hash of current documentation content"""
        if not self.docs_dir.exists():
            return ""

        hasher = hashlib.sha256()
        for file_path in sorted(self.docs_dir.rglob("*.md")):
            if file_path.name.lower() not in ["index.md", "readme.md"]:
                hasher.update(file_path.read_bytes())

        return hasher.hexdigest()

    async def get_stored_content_hash(self, api_name: str) -> Optional[str]:
        """Get the stored content hash for an API from database"""
        async with get_db_session() as session:
            result = await session.execute(
                text("SELECT content_hash FROM docs_metadata WHERE api_name = :api"),
                {"api": api_name}
            )
            row = result.fetchone()
            return row[0] if row else None

    async def update_last_checked(self):
        """Update last_checked timestamp for all APIs"""
        async with get_db_session() as session:
            await session.execute(
                text("UPDATE docs_metadata SET last_checked = NOW()")
            )
            await session.commit()

    async def docs_exist(self) -> bool:
        """Check if documentation has been downloaded"""
        if not self.docs_dir.exists():
            return False

        # Check if we have any markdown files
        md_files = list(self.docs_dir.rglob("*.md"))
        return len(md_files) > 0

    async def check_and_update(self, force: bool = False) -> Dict[str, Any]:
        """
        Check for documentation updates and download/index if needed.

        Args:
            force: Force update regardless of time interval

        Returns:
            Dictionary with update status and details
        """
        result = {
            "checked": False,
            "updated": False,
            "downloaded": False,
            "indexed": False,
            "message": "",
            "error": None
        }

        try:
            # Check if docs exist at all
            docs_exist = await self.docs_exist()

            if not docs_exist:
                logger.warning("⚠️  Shopify documentation not found locally")
                logger.info("Run: python backend/scripts/download_shopify_docs.py")
                result["message"] = "Documentation not downloaded. Run download script."
                return result

            # Check if we should check for updates (time-based)
            if not force and not await self.should_check_for_updates():
                result["message"] = f"Skipped check (last checked within {self.check_interval.days} days)"
                return result

            # Calculate current hash
            logger.info("🔍 Checking for documentation updates...")
            current_hash = await self.get_current_content_hash()

            # Check if docs have been indexed
            async with get_db_session() as session:
                count_result = await session.execute(text("SELECT COUNT(*) FROM docs"))
                doc_count = count_result.fetchone()[0]

            if doc_count == 0:
                logger.info("📊 Documentation not indexed - running initial index...")
                from services.doc_indexer import DocIndexer
                indexer = DocIndexer(self.docs_dir)
                await indexer.index_all()
                result["indexed"] = True
                result["message"] = f"Indexed {doc_count} documents"

            # Compare with stored hash
            stored_hash = await self.get_stored_content_hash("admin")  # Use admin as reference

            result["checked"] = True
            await self.update_last_checked()

            if current_hash != stored_hash:
                logger.info("🔄 Documentation changes detected - re-indexing...")
                from services.doc_indexer import DocIndexer
                indexer = DocIndexer(self.docs_dir)
                await indexer.index_all()
                result["updated"] = True
                result["indexed"] = True
                result["message"] = "Documentation updated and re-indexed"
                logger.info("✅ Documentation update complete")
            else:
                logger.info("✅ Documentation is up to date")
                result["message"] = "Documentation is up to date"

        except Exception as e:
            logger.error(f"❌ Error checking/updating documentation: {e}")
            result["error"] = str(e)
            result["message"] = f"Error: {str(e)}"

        return result


async def check_and_update_docs(force: bool = False) -> Dict[str, Any]:
    """
    Convenience function for checking and updating documentation.
    Called from main.py on application startup.

    Args:
        force: Force update regardless of time interval

    Returns:
        Dictionary with update status
    """
    updater = DocUpdater()
    return await updater.check_and_update(force=force)


async def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Check and update Shopify documentation")
    parser.add_argument("--force", action="store_true", help="Force update check")
    parser.add_argument("--docs-dir", type=Path, help="Documentation directory")
    parser.add_argument("--interval-days", type=int, default=7, help="Days between checks")

    args = parser.parse_args()

    updater = DocUpdater(
        docs_dir=args.docs_dir,
        check_interval_days=args.interval_days
    )

    result = await updater.check_and_update(force=args.force)
    print(f"\n{'='*60}")
    print(f"Result: {result['message']}")
    print(f"  Checked: {result['checked']}")
    print(f"  Downloaded: {result['downloaded']}")
    print(f"  Indexed: {result['indexed']}")
    print(f"  Updated: {result['updated']}")
    if result['error']:
        print(f"  Error: {result['error']}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(main())
