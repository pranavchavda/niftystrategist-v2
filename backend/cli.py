#!/usr/bin/env python3
"""
CLI Interface for EspressoBot using Pydantic AI

This provides an interactive command-line chat interface with the same
capabilities as the web UI, using the documentation-driven architecture.

Features:
- Full orchestrator with doc-driven approach
- Memory injection support
- Conversation persistence
- Web research capabilities
- Real-time streaming

Usage:
    python cli.py                    # Full orchestrator with all features
    python cli.py --simple           # Simple agent without tools
    python cli.py --user user@email  # Specify user for memory loading
"""

import asyncio
import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime, timezone

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

# Load environment variables
load_dotenv()

from agents.orchestrator import OrchestratorAgent, OrchestratorDeps
from agents.google_workspace_agent import GoogleWorkspaceAgent
from agents.web_search_agent import WebSearchAgent
from models.state import ConversationState
from pydantic_ai import Agent
import logging

# Configure logging - reduced for cleaner CLI output
logging.basicConfig(
    level=logging.WARNING,  # Changed from FATAL to WARNING for better debugging
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def get_user_memories(user_email: str, limit: int = 10) -> list[str]:
    """
    Load user memories from database for context injection.

    Args:
        user_email: User email to load memories for
        limit: Maximum number of memories to load

    Returns:
        List of memory strings
    """
    try:
        from database.operations import MemoryOps
        from database.session import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            # Get memories by user_id (which is email in our system)
            memories = await MemoryOps.get_user_memories(
                session=session,
                user_id=user_email,
                limit=limit
            )

            if memories:
                logger.info(f"Loaded {len(memories)} memories for {user_email}")
                # Format memories for injection (Memory model uses 'fact' field)
                return [m.fact for m in memories]

            return []

    except Exception as e:
        logger.warning(f"Could not load memories: {e}")
        return []


async def run_cli_with_persistence(
    agent,
    deps,
    thread_id: str,
    user_email: str,
    prog_name: str = "Agent"
):
    """
    Custom CLI loop that saves messages to database for CLI-Web continuity.

    This replaces Pydantic AI's to_cli() to enable:
    - Message persistence to PostgreSQL
    - Conversation visibility in web sidebar
    - Seamless CLI → Web handoff
    """
    from database.operations import MessageOps
    from database.session import AsyncSessionLocal
    import uuid

    print(f"\n{prog_name} is ready. Type your message or '/exit' to quit.\n")

    # Message history for Pydantic AI (in-memory, for context)
    message_history = []

    while True:
        try:
            # Get user input
            user_input = input("You: ").strip()

            if not user_input:
                continue

            # Check for exit commands
            if user_input.lower() in ['/exit', '/quit', 'exit', 'quit']:
                print("\n👋 Exiting...")
                break

            # Save user message to database
            user_msg_id = f"msg_{uuid.uuid4().hex[:12]}"
            async with AsyncSessionLocal() as session:
                try:
                    await MessageOps.add_message(
                        session=session,
                        conversation_id=thread_id,
                        message_id=user_msg_id,
                        role="user",
                        content=user_input
                    )
                except Exception as e:
                    logger.warning(f"Could not save user message to DB: {e}")

            # Add to message history for context
            message_history.append({
                "role": "user",
                "content": user_input
            })

            # Call agent with streaming
            print(f"\n{prog_name}: ", end="", flush=True)

            try:
                assistant_response = ""

                # Run agent with streaming
                async with agent.run_stream(user_input, deps=deps, message_history=message_history) as stream:
                    async for chunk in stream.stream_text():
                        # Calculate delta (new text since last chunk)
                        delta = chunk[len(assistant_response):]
                        if delta:
                            print(delta, end="", flush=True)
                        assistant_response = chunk

                print("\n")  # Newline after response

                # Save assistant message to database
                assistant_msg_id = f"msg_{uuid.uuid4().hex[:12]}"
                async with AsyncSessionLocal() as session:
                    try:
                        await MessageOps.add_message(
                            session=session,
                            conversation_id=thread_id,
                            message_id=assistant_msg_id,
                            role="assistant",
                            content=assistant_response
                        )
                    except Exception as e:
                        logger.warning(f"Could not save assistant message to DB: {e}")

                # Add to message history for context
                message_history.append({
                    "role": "assistant",
                    "content": assistant_response
                })

            except Exception as e:
                logger.error(f"Error calling agent: {e}", exc_info=True)
                print(f"\n❌ Error: {e}\n")

        except EOFError:
            # Ctrl+D pressed
            print("\n\n👋 Exiting...")
            break
        except KeyboardInterrupt:
            # Ctrl+C pressed
            print("\n\n👋 Interrupted by user")
            break


async def run_cli_with_persistence_and_history(
    agent,
    deps,
    thread_id: str,
    user_email: str,
    message_history: list,
    prog_name: str = "Agent"
):
    """
    Custom CLI loop for resuming conversations with existing message history.

    This is the same as run_cli_with_persistence but starts with an existing
    message history loaded from the database.
    """
    # Delegate to the main function with pre-populated history
    from database.operations import MessageOps
    from database.session import AsyncSessionLocal
    import uuid

    print(f"\n{prog_name} is ready. Continue the conversation or type '/exit' to quit.\n")

    while True:
        try:
            # Get user input
            user_input = input("You: ").strip()

            if not user_input:
                continue

            # Check for exit commands
            if user_input.lower() in ['/exit', '/quit', 'exit', 'quit']:
                print("\n👋 Exiting...")
                break

            # Save user message to database
            user_msg_id = f"msg_{uuid.uuid4().hex[:12]}"
            async with AsyncSessionLocal() as session:
                try:
                    await MessageOps.add_message(
                        session=session,
                        conversation_id=thread_id,
                        message_id=user_msg_id,
                        role="user",
                        content=user_input
                    )
                except Exception as e:
                    logger.warning(f"Could not save user message to DB: {e}")

            # Add to message history for context
            message_history.append({
                "role": "user",
                "content": user_input
            })

            # Call agent with streaming
            print(f"\n{prog_name}: ", end="", flush=True)

            try:
                assistant_response = ""

                # Run agent with streaming and full history
                async with agent.run_stream(user_input, deps=deps, message_history=message_history) as stream:
                    async for chunk in stream.stream_text():
                        # Calculate delta (new text since last chunk)
                        delta = chunk[len(assistant_response):]
                        if delta:
                            print(delta, end="", flush=True)
                        assistant_response = chunk

                print("\n")  # Newline after response

                # Save assistant message to database
                assistant_msg_id = f"msg_{uuid.uuid4().hex[:12]}"
                async with AsyncSessionLocal() as session:
                    try:
                        await MessageOps.add_message(
                            session=session,
                            conversation_id=thread_id,
                            message_id=assistant_msg_id,
                            role="assistant",
                            content=assistant_response
                        )
                    except Exception as e:
                        logger.warning(f"Could not save assistant message to DB: {e}")

                # Add to message history for context
                message_history.append({
                    "role": "assistant",
                    "content": assistant_response
                })

            except Exception as e:
                logger.error(f"Error calling agent: {e}", exc_info=True)
                print(f"\n❌ Error: {e}\n")

        except EOFError:
            # Ctrl+D pressed
            print("\n\n👋 Exiting...")
            break
        except KeyboardInterrupt:
            # Ctrl+C pressed
            print("\n\n👋 Interrupted by user")
            break


async def extract_session_memories(thread_id: str, user_email: str) -> None:
    """
    Extract memories from CLI session after conversation ends.

    Args:
        thread_id: The conversation thread_id
        user_email: User email to associate memories with
    """
    try:
        from database.operations import ConversationOps, MemoryOps
        from database.session import AsyncSessionLocal
        from agents.memory_extractor import get_memory_extractor
        import openai

        print("\n🧠 Extracting memories from this session...")

        async with AsyncSessionLocal() as session:
            # Get conversation messages
            conversation = await ConversationOps.get_conversation(
                session=session,
                thread_id=thread_id,
                user_id=user_email,
                include_messages=True
            )

            if not conversation or not conversation.messages:
                print("   ℹ️  No messages to extract from")
                return

            # Format conversation history for extraction
            conversation_history = []
            for msg in conversation.messages:
                conversation_history.append({
                    "role": msg.role,
                    "content": msg.content
                })

            # Extract memories using the memory extractor
            memory_extractor = get_memory_extractor()
            extraction_result = await memory_extractor.extract_memories(
                conversation_history=conversation_history,
                conversation_id=thread_id
            )

            if extraction_result.memories and len(extraction_result.memories) > 0:
                # Save memories with embeddings
                openai_client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

                for extracted_memory in extraction_result.memories:
                    # Generate embedding
                    embedding_response = await openai_client.embeddings.create(
                        model="text-embedding-3-large",
                        input=extracted_memory.fact
                    )
                    embedding = embedding_response.data[0].embedding

                    # Save to database using add_memory (not create_memory)
                    await MemoryOps.add_memory(
                        session=session,
                        conversation_id=thread_id,
                        user_id=user_email,
                        fact=extracted_memory.fact,
                        category=extracted_memory.category,
                        confidence=extracted_memory.confidence,
                        embedding=embedding
                    )

                await session.commit()

                print(f"   ✅ Extracted and saved {len(extraction_result.memories)} new memories:")
                for memory in extraction_result.memories[:5]:  # Show first 5
                    # Display fact (truncated if too long)
                    fact = memory.fact if len(memory.fact) <= 60 else memory.fact[:57] + "..."
                    print(f"      • {fact}")
                if len(extraction_result.memories) > 5:
                    print(f"      ... and {len(extraction_result.memories) - 5} more")
            else:
                print("   ℹ️  No significant memories to extract from this session")

    except Exception as e:
        logger.error(f"Error extracting memories: {e}", exc_info=True)
        print(f"   ⚠️  Could not extract memories: {str(e)}")


async def run_full_orchestrator(user_email: str = "pranav@idrinkcoffee.com"):
    """
    Run the full orchestrator with documentation-driven architecture.

    This matches the web UI's capabilities:
    - Documentation reading and synthesis
    - Specialist spawning for complex tasks
    - Bash execution for Shopify operations
    - Web research via web_search agent
    - Memory injection for personalization
    - Database persistence for CLI-Web continuity
    """
    print("🚀 Starting EspressoBot CLI with Documentation-Driven Architecture")
    print("-" * 70)
    print("Initializing agents...")

    try:
        # Initialize orchestrator
        orchestrator = OrchestratorAgent()

        # Initialize domain-specific agents
        from agents.marketing_agent import MarketingAgent
        from agents.vision_agent import vision_agent
        from agents.price_monitor_agent import PriceMonitorAgent
        from agents.graphics_designer_agent import GraphicsDesignerAgent
        from agents.shopify_mcp_user_agent import ShopifyMCPUserAgent

        google_workspace_agent = GoogleWorkspaceAgent()
        web_search_agent = WebSearchAgent()
        marketing_agent = MarketingAgent()
        price_monitor_agent = PriceMonitorAgent()
        graphics_designer_agent = GraphicsDesignerAgent()
        shopify_mcp_user_agent = ShopifyMCPUserAgent()

        # Register domain-specific agents
        orchestrator.register_agent("google_workspace", google_workspace_agent)
        orchestrator.register_agent("web_search", web_search_agent)
        orchestrator.register_agent("marketing", marketing_agent)
        orchestrator.register_agent("vision", vision_agent)
        orchestrator.register_agent("price_monitor", price_monitor_agent)
        orchestrator.register_agent("graphics_designer", graphics_designer_agent)
        orchestrator.register_agent("shopify_mcp_user", shopify_mcp_user_agent)

        print("✅ Agents initialized successfully!")
        print("\n📚 Architecture: Documentation-Driven")
        print("   Core Tools: read_docs, spawn_specialist, execute_bash")
        print("   Domain Agents: google_workspace, web_search, marketing, vision, price_monitor, graphics_designer, shopify_mcp_user")

        # Load user memories
        print(f"\n🧠 Loading memories for {user_email}...")
        user_memories = await get_user_memories(user_email, limit=10)

        if user_memories:
            print(f"   ✅ Loaded {len(user_memories)} memories")
        else:
            print("   ℹ️  No memories found (first session or new user)")

        print("\n" + "="*70)
        print("You can now interact with EspressoBot.")
        print("Type 'exit' or 'quit' to end the session and extract memories.")
        print("="*70 + "\n")

        # Create conversation state with unique thread ID
        thread_id = f"cli_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        state = ConversationState(
            thread_id=thread_id,
            user_id=user_email
        )

        # Create conversation in database for CLI-Web continuity
        from database.operations import ConversationOps
        from database.session import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            try:
                await ConversationOps.create_conversation(
                    session=session,
                    thread_id=thread_id,
                    user_id=user_email,
                    title="CLI Session - " + datetime.now().strftime("%Y-%m-%d %H:%M")
                )
                print(f"💾 Conversation created in database: {thread_id}")
                print(f"   This conversation will be visible in the web interface sidebar\n")
            except Exception as e:
                logger.warning(f"Could not create conversation in database: {e}")
                print(f"⚠️  Database persistence unavailable: {e}\n")

        # Create dependencies with memories
        deps = OrchestratorDeps(
            state=state,
            available_agents=orchestrator.specialized_agents,
            user_memories=user_memories
        )

        # Run custom CLI loop with database persistence
        # This replaces to_cli() to enable message saving for CLI-Web continuity
        try:
            await run_cli_with_persistence(
                agent=orchestrator.agent,
                deps=deps,
                thread_id=thread_id,
                user_email=user_email,
                prog_name="EspressoBot"
            )
        except (KeyboardInterrupt, EOFError):
            # User exited normally (Ctrl+C or 'exit')
            pass

        # Extract memories after conversation ends
        await extract_session_memories(state.thread_id, user_email)

    except KeyboardInterrupt:
        print("\n\n👋 Session interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        logger.error(f"CLI error: {e}", exc_info=True)
        raise


async def run_simple_agent():
    """
    Run a simple test agent without tools for quick testing.
    Useful for testing basic LLM responses without Shopify/database access.
    """
    print("🎯 Starting Simple Test Agent (No Tools)")
    print("-" * 70)

    # Create a simple agent for testing
    simple_agent = Agent(
        'openai:gpt-4.1-mini',  # Fast and cheap for testing
        instructions="""You are EspressoBot, an AI assistant for e-commerce management.

You help with:
- Product management (search, pricing, inventory)
- Sales analytics and reports
- Order tracking and fulfillment
- Google Workspace integration (Gmail, Calendar, Drive)
- Web research for product information
- General e-commerce questions

Note: This is SIMPLE MODE without real tool access. You can discuss approaches
and strategies, but acknowledge that actual operations require the full CLI mode.""",
        name="EspressoBot-Simple"
    )

    print("✅ Simple agent ready!")
    print("\n" + "="*70)
    print("You can test basic interactions without Shopify/database access.")
    print("For full functionality, run without --simple flag.")
    print("Type 'exit' or 'quit' to end the session.")
    print("="*70 + "\n")

    # Run the simple agent in CLI mode
    await simple_agent.to_cli(prog_name="EspressoBot (Simple Mode)")


def check_environment():
    """Check if environment is properly configured."""
    has_openrouter = bool(os.getenv("OPENROUTER_API_KEY"))
    has_openai = bool(os.getenv("OPENAI_API_KEY"))
    has_shopify = bool(os.getenv("SHOPIFY_ACCESS_TOKEN"))
    has_db = bool(os.getenv("DATABASE_URL"))

    if not (has_openrouter or has_openai):
        print("\n⚠️  WARNING: No LLM API keys found!")
        print("Please set OPENROUTER_API_KEY or OPENAI_API_KEY in your .env file")
        return False

    print("✅ Environment configured:")

    if has_openrouter:
        print("  ✓ OpenRouter API available (GLM 4.6, GPT-5)")
    if has_openai:
        print("  ✓ OpenAI API available (GPT-4.1)")
    if has_shopify:
        print("  ✓ Shopify API configured")
    else:
        print("  ⚠ Shopify API not configured (limited functionality)")
    if has_db:
        print("  ✓ Database configured (memory system available)")
    else:
        print("  ⚠ Database not configured (no memory persistence)")

    return True


async def index_docs_command(args):
    """Index all documentation files for semantic search."""
    print("\n" + "="*70)
    print("  📚 Documentation Indexer")
    print("="*70 + "\n")

    try:
        from utils.docs_indexer import DocsIndexer
        from database.session import AsyncSessionLocal

        # Get docs directory
        backend_dir = Path(__file__).parent
        docs_dir = backend_dir / "docs"

        if not docs_dir.exists():
            print(f"❌ Documentation directory not found: {docs_dir}")
            return False

        print(f"📁 Scanning documentation directory: {docs_dir}")

        # Create indexer
        indexer = DocsIndexer(
            docs_dir=str(docs_dir),
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap
        )

        # Reindex all documentation
        async with AsyncSessionLocal() as session:
            result = await indexer.reindex_all(session)

        print(f"\n✅ Indexing complete!")
        print(f"   Files indexed: {result['files']}")
        print(f"   Chunks created: {result['chunks']}")
        print(f"   Total tokens: {result['tokens']:,}")
        print(f"   Avg chunk size: {result['tokens'] // result['chunks']:.0f} tokens\n")

        return True

    except Exception as e:
        print(f"\n❌ Error indexing documentation: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return False


async def reindex_file_command(args):
    """Reindex a specific documentation file."""
    print("\n" + "="*70)
    print("  📄 Reindex Single File")
    print("="*70 + "\n")

    try:
        from utils.docs_indexer import DocsIndexer
        from database.session import AsyncSessionLocal

        backend_dir = Path(__file__).parent
        docs_dir = backend_dir / "docs"

        print(f"📄 Reindexing: {args.file_path}")

        # Create indexer
        indexer = DocsIndexer(
            docs_dir=str(docs_dir),
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap
        )

        # Reindex specific file
        async with AsyncSessionLocal() as session:
            result = await indexer.reindex_file(args.file_path, session)

        print(f"\n✅ File reindexed!")
        print(f"   Chunks created: {result['chunks']}")
        print(f"   Total tokens: {result['tokens']:,}\n")

        return True

    except FileNotFoundError:
        print(f"\n❌ File not found: {args.file_path}")
        print(f"   Hint: Path should be relative to backend directory")
        print(f"   Example: docs/product-guidelines/breville.md\n")
        return False
    except Exception as e:
        print(f"\n❌ Error reindexing file: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return False


async def search_docs_command(args):
    """Search documentation semantically."""
    print("\n" + "="*70)
    print("  🔍 Semantic Documentation Search")
    print("="*70 + "\n")

    try:
        import openai
        from database.operations import DocsOps
        from database.session import AsyncSessionLocal

        print(f"Query: {args.query}")
        print(f"Limit: {args.limit}")
        print(f"Threshold: {args.threshold}\n")

        # Generate embedding for query
        client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        embedding_response = await client.embeddings.create(
            model="text-embedding-3-large",
            input=args.query
        )
        query_embedding = embedding_response.data[0].embedding

        # Search documentation
        async with AsyncSessionLocal() as session:
            results = await DocsOps.search_docs_semantic(
                session=session,
                embedding=query_embedding,
                limit=args.limit,
                similarity_threshold=args.threshold
            )

        if not results:
            print("❌ No relevant documentation found.")
            print(f"\nTry:")
            print(f"  - Lowering threshold (current: {args.threshold})")
            print(f"  - Using different search terms")
            print(f"  - Checking if documentation is indexed\n")
            return False

        print(f"✅ Found {len(results)} relevant chunks:\n")
        print("="*70)

        for i, (chunk, similarity) in enumerate(results, 1):
            print(f"\n📄 Result {i} - Relevance: {similarity:.1%}")
            print(f"   File: {chunk.file_path}")
            if chunk.heading_context:
                print(f"   Section: {chunk.heading_context}")
            print(f"   Tokens: {chunk.chunk_tokens}")
            print(f"\n{chunk.chunk_text}\n")
            print("-"*70)

        return True

    except Exception as e:
        print(f"\n❌ Error searching documentation: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return False


async def list_conversations_command(args):
    """List user's conversations with formatted output"""
    from database.operations import ConversationOps
    from database.session import AsyncSessionLocal
    from rich.console import Console
    from rich.table import Table
    from datetime import datetime, timezone

    console = Console()

    try:
        async with AsyncSessionLocal() as session:
            convos = await ConversationOps.list_conversations(
                session=session,
                user_id=args.user,
                limit=args.limit,
                include_archived=args.archived
            )

            # Filter starred if requested
            if args.starred:
                convos = [c for c in convos if c.is_starred]

            if not convos:
                console.print("[yellow]No conversations found[/yellow]")
                if not args.archived:
                    console.print("[dim]Tip: Use --archived to include archived conversations[/dim]")
                return

            # Create rich table
            table = Table(title=f"📚 Your Conversations ({len(convos)})", show_header=True, header_style="bold cyan")
            table.add_column("Thread ID", style="cyan", no_wrap=True, width=12)
            table.add_column("Title", style="white")
            table.add_column("Msgs", justify="right", style="blue", width=6)
            table.add_column("Updated", style="green", width=10)
            table.add_column("", style="magenta", width=3)  # Status icons

            for convo in convos:
                # Short thread ID (last 8 chars)
                short_id = convo.id[-8:] if len(convo.id) > 8 else convo.id

                # Count messages (loadwithoptions would be better but this works)
                msg_count = "?"  # Default if messages not loaded

                # Format updated time
                now = datetime.now(timezone.utc)
                delta = now - convo.updated_at
                if delta.days > 0:
                    time_str = f"{delta.days}d ago"
                elif delta.seconds > 3600:
                    time_str = f"{delta.seconds // 3600}h ago"
                elif delta.seconds > 60:
                    time_str = f"{delta.seconds // 60}m ago"
                else:
                    time_str = "just now"

                # Status icons
                status_icons = []
                if convo.is_starred:
                    status_icons.append("⭐")
                if convo.is_archived:
                    status_icons.append("📁")
                if not status_icons:
                    status_icons.append("💬")

                status = " ".join(status_icons)

                # Truncate long titles
                title = convo.title[:50] + "..." if len(convo.title) > 50 else convo.title

                table.add_row(short_id, title, msg_count, time_str, status)

            console.print(table)
            console.print(f"\n[dim]💡 To resume: espressobot resume <thread_id>[/dim]")
            console.print(f"[dim]   Example: espressobot resume {convos[0].id[-8:]}[/dim]")

            return True

    except Exception as e:
        console.print(f"[red]❌ Error listing conversations: {e}[/red]")
        if hasattr(args, 'debug') and args.debug:
            import traceback
            traceback.print_exc()
        return False


async def resume_conversation_command(args):
    """Resume an existing conversation with full context"""
    from database.operations import ConversationOps
    from database.session import AsyncSessionLocal
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel

    console = Console()

    try:
        async with AsyncSessionLocal() as session:
            # Resolve short thread_id if needed
            thread_id = args.thread_id
            if len(args.thread_id) <= 8:
                # Query for conversations ending with these chars
                convos = await ConversationOps.list_conversations(
                    session=session,
                    user_id=args.user,
                    limit=100,
                    include_archived=True
                )
                matching = [c for c in convos if c.id.endswith(args.thread_id)]

                if not matching:
                    console.print(f"[red]❌ No conversation found ending with '{args.thread_id}'[/red]")
                    return False
                elif len(matching) > 1:
                    console.print(f"[yellow]⚠️  Multiple conversations match '{args.thread_id}':[/yellow]\n")
                    for c in matching:
                        console.print(f"  • [cyan]{c.id}[/cyan] - {c.title}")
                    console.print("\n[dim]Please provide more characters from thread_id[/dim]")
                    return False

                thread_id = matching[0].id
                console.print(f"[dim]Resolved to: {thread_id}[/dim]\n")

            # Load conversation with messages
            convo = await ConversationOps.get_conversation(
                session=session,
                thread_id=thread_id,
                user_id=args.user,
                include_messages=True
            )

            if not convo:
                console.print(f"[red]❌ Conversation not found: {thread_id}[/red]")
                console.print(f"[dim]Run 'espressobot list --user {args.user}' to see available conversations[/dim]")
                return False

            # Display conversation summary
            console.print()
            console.print(Panel(
                f"[bold]{convo.title}[/bold]\n\n"
                f"[dim]Thread ID:[/dim] {convo.id}\n"
                f"[dim]Messages:[/dim] {len(convo.messages) if convo.messages else 0}\n"
                f"[dim]Updated:[/dim] {convo.updated_at.strftime('%Y-%m-%d %H:%M:%S')}",
                title="[cyan]📝 Resuming Conversation[/cyan]",
                border_style="cyan"
            ))

            # Show recent messages (last 5)
            if convo.messages:
                console.print("\n[bold]Recent conversation:[/bold]")
                recent_messages = sorted(convo.messages, key=lambda m: m.timestamp)[-5:]

                for msg in recent_messages:
                    role_emoji = "👤" if msg.role == "user" else "🤖"
                    role_color = "yellow" if msg.role == "user" else "blue"

                    # Preview content (first 150 chars)
                    content_preview = msg.content[:150] + "..." if len(msg.content) > 150 else msg.content

                    console.print(f"\n{role_emoji} [bold {role_color}]{msg.role}[/bold {role_color}]:")
                    console.print(Markdown(content_preview))

                console.print("\n" + "─" * 70 + "\n")

            # Load user memories
            console.print("[dim]Loading memories...[/dim]")
            user_memories = await get_user_memories(args.user, limit=10)

            if user_memories:
                console.print(f"[green]✓ Loaded {len(user_memories)} memories[/green]\n")
            else:
                console.print("[dim]No memories found[/dim]\n")

        # Check environment unless skipped
        if not args.no_check:
            console.print("[dim]Checking environment...[/dim]")
            if not check_environment():
                console.print("\n[yellow]⚠️  Environment issues detected[/yellow]")
                console.print("[dim]Run with --no-check to proceed anyway[/dim]\n")
                return False
            console.print("[green]✓ Environment OK[/green]\n")

        # Initialize orchestrator
        from agents.orchestrator import OrchestratorAgent, OrchestratorDeps
        from models.state import ConversationState
        from agents.marketing_agent import MarketingAgent
        from agents.vision_agent import vision_agent
        from agents.price_monitor_agent import PriceMonitorAgent
        from agents.graphics_designer_agent import GraphicsDesignerAgent
        from agents.shopify_mcp_user_agent import ShopifyMCPUserAgent
        from agents.google_workspace_agent import GoogleWorkspaceAgent
        from agents.web_search_agent import WebSearchAgent

        orchestrator = OrchestratorAgent()

        # Register domain agents
        google_workspace_agent = GoogleWorkspaceAgent()
        web_search_agent = WebSearchAgent()
        marketing_agent = MarketingAgent()
        price_monitor_agent = PriceMonitorAgent()
        graphics_designer_agent = GraphicsDesignerAgent()
        shopify_mcp_user_agent = ShopifyMCPUserAgent()

        orchestrator.register_agent("google_workspace", google_workspace_agent)
        orchestrator.register_agent("web_search", web_search_agent)
        orchestrator.register_agent("marketing", marketing_agent)
        orchestrator.register_agent("vision", vision_agent)
        orchestrator.register_agent("price_monitor", price_monitor_agent)
        orchestrator.register_agent("graphics_designer", graphics_designer_agent)
        orchestrator.register_agent("shopify_mcp_user", shopify_mcp_user_agent)

        # Create state with EXISTING thread_id
        state = ConversationState(
            thread_id=thread_id,
            user_id=args.user
        )

        # Build message history for Pydantic AI
        message_history = []
        if convo.messages:
            for msg in sorted(convo.messages, key=lambda m: m.timestamp):
                message_history.append({
                    "role": msg.role,
                    "content": msg.content
                })

        # Create deps
        deps = OrchestratorDeps(
            state=state,
            available_agents=orchestrator.specialized_agents,
            user_memories=user_memories
        )

        # Ready to resume
        console.print("[bold green]✅ Ready to continue conversation![/bold green]")
        console.print("[dim]Type your message or /exit to quit[/dim]\n")

        # Run orchestrator with message history and persistence
        try:
            await run_cli_with_persistence_and_history(
                agent=orchestrator.agent,
                deps=deps,
                thread_id=thread_id,
                user_email=args.user,
                message_history=message_history,  # Pass conversation history!
                prog_name=f"EspressoBot - {convo.title[:30]}"
            )
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Session interrupted[/yellow]")

        # Extract memories after session ends
        console.print("\n")
        await extract_session_memories(thread_id, args.user)

        return True

    except Exception as e:
        console.print(f"\n[red]❌ Error resuming conversation: {e}[/red]")
        if hasattr(args, 'debug') and args.debug:
            import traceback
            traceback.print_exc()
        return False


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="EspressoBot CLI - Interactive chat and documentation management",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # Add subparsers for commands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Chat command (default)
    chat_parser = subparsers.add_parser('chat', help='Interactive chat interface (default)')
    chat_parser.add_argument(
        "--simple",
        action="store_true",
        help="Run simple agent without tools (for quick testing)"
    )
    chat_parser.add_argument(
        "--user",
        type=str,
        default="pranav@idrinkcoffee.com",
        help="User email for memory loading (default: pranav@idrinkcoffee.com)"
    )
    chat_parser.add_argument(
        "--no-check",
        action="store_true",
        help="Skip environment checks"
    )
    chat_parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )

    # List conversations command
    list_parser = subparsers.add_parser('list', help='List your conversations')
    list_parser.add_argument(
        "--user",
        type=str,
        default="pranav@idrinkcoffee.com",
        help="User email (default: pranav@idrinkcoffee.com)"
    )
    list_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Number of conversations to show (default: 20)"
    )
    list_parser.add_argument(
        "--starred",
        action="store_true",
        help="Show only starred conversations"
    )
    list_parser.add_argument(
        "--archived",
        action="store_true",
        help="Include archived conversations"
    )

    # Resume conversation command
    resume_parser = subparsers.add_parser('resume', help='Resume an existing conversation')
    resume_parser.add_argument(
        'thread_id',
        type=str,
        help='Thread ID to resume (full ID or last 8 characters)'
    )
    resume_parser.add_argument(
        "--user",
        type=str,
        default="pranav@idrinkcoffee.com",
        help="User email (default: pranav@idrinkcoffee.com)"
    )
    resume_parser.add_argument(
        "--no-check",
        action="store_true",
        help="Skip environment checks"
    )
    resume_parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )

    # Index docs command
    index_parser = subparsers.add_parser('index-docs', help='Index all documentation for semantic search')
    index_parser.add_argument(
        "--chunk-size",
        type=int,
        default=800,
        help="Target chunk size in tokens (default: 800)"
    )
    index_parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=100,
        help="Overlap between chunks in tokens (default: 100)"
    )
    index_parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )

    # Reindex file command
    reindex_parser = subparsers.add_parser('reindex-file', help='Reindex a specific documentation file')
    reindex_parser.add_argument(
        "file_path",
        type=str,
        help="Path to file relative to backend directory (e.g., docs/product-guidelines/breville.md)"
    )
    reindex_parser.add_argument(
        "--chunk-size",
        type=int,
        default=800,
        help="Target chunk size in tokens (default: 800)"
    )
    reindex_parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=100,
        help="Overlap between chunks in tokens (default: 100)"
    )
    reindex_parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )

    # Search docs command
    search_parser = subparsers.add_parser('search-docs', help='Search documentation semantically')
    search_parser.add_argument(
        "query",
        type=str,
        help="Search query (e.g., 'How to create products with variants?')"
    )
    search_parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Maximum number of results (default: 5)"
    )
    search_parser.add_argument(
        "--threshold",
        type=float,
        default=0.55,
        help="Minimum similarity threshold 0.0-1.0 (default: 0.55)"
    )
    search_parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )

    args = parser.parse_args()

    # Enable debug logging if requested
    if hasattr(args, 'debug') and args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")

    # Default to chat if no command specified
    if args.command is None:
        args.command = 'chat'
        args.simple = False
        args.user = "pranav@idrinkcoffee.com"
        args.no_check = False
        args.debug = False

    # Handle commands
    try:
        if args.command == 'index-docs':
            success = asyncio.run(index_docs_command(args))
            sys.exit(0 if success else 1)

        elif args.command == 'reindex-file':
            success = asyncio.run(reindex_file_command(args))
            sys.exit(0 if success else 1)

        elif args.command == 'search-docs':
            success = asyncio.run(search_docs_command(args))
            sys.exit(0 if success else 1)

        elif args.command == 'list':
            success = asyncio.run(list_conversations_command(args))
            sys.exit(0 if success else 1)

        elif args.command == 'resume':
            success = asyncio.run(resume_conversation_command(args))
            sys.exit(0 if success else 1)

        elif args.command == 'chat':
            print("\n" + "="*70)
            print("  🤖 EspressoBot CLI Interface")
            print("  📚 Documentation-Driven Architecture")
            print("="*70 + "\n")

            # Check environment unless skipped
            if not args.no_check:
                if not check_environment():
                    print("\n⚠️  Environment issues detected.")
                    print("Run with --no-check to proceed anyway, or fix configuration.\n")
                    sys.exit(1)
                print()  # Blank line for spacing

            # Run chat mode
            if args.simple:
                asyncio.run(run_simple_agent())
            else:
                asyncio.run(run_full_orchestrator(user_email=args.user))

    except KeyboardInterrupt:
        print("\n\n👋 Session ended by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        if hasattr(args, 'debug') and args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)

    print("\n👋 Goodbye!\n")


if __name__ == "__main__":
    main()
