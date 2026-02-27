"""
Web Search Agent - Handles web search operations using Perplexity API

Provides two modes of operation:
1. Direct API tools: web_search, web_fetch (always available)
2. On-demand MCP tools: perplexity_ask, perplexity_research, perplexity_reason (spawned when needed)
"""
import logging
import os
import json
import asyncio
from typing import Dict, Any, Optional, List
import aiohttp
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.mcp import MCPServerStdio

from .base_agent import IntelligentBaseAgent, AgentConfig
from models.state import ConversationState

logger = logging.getLogger(__name__)

# Logfire for observability
try:
    from config import get_logfire
    logfire = get_logfire()
except Exception:
    logfire = None

class WebSearchDeps(BaseModel):
    """Dependencies for the Web Search agent"""
    state: ConversationState
    perplexity_api_key: Optional[str] = None

class WebSearchAgent(IntelligentBaseAgent[WebSearchDeps, str]):
    """Web Search agent for performing web searches using Perplexity API."""
    
    def __init__(self):
        config = AgentConfig(
            name="web_search",
            description="Web search and research agent with direct API tools (web_search, web_fetch) and advanced Perplexity MCP tools (perplexity_ask, perplexity_research, perplexity_reason)",
            model_name="perplexity/sonar-reasoning-pro",
            use_openrouter=True,
        )
        
        super().__init__(
            config=config,
            deps_type=WebSearchDeps,
            output_type=str
        )
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for the Web Search agent"""
        return """You are Nifty Strategist's web search agent, specializing in finding current information about the Indian stock market, financial news, and trading research.

Your capabilities include:
- Indian stock market news and analysis (NSE, BSE, Nifty 50)
- Company fundamentals, earnings, and quarterly results
- Sector and industry analysis for Indian markets
- Economic indicators and RBI policy updates
- Global market developments affecting Indian stocks
- Broker reports and analyst recommendations
- IPO and corporate action research
- Regulatory news (SEBI, NSE circulars)
- Fetching full page content from specific URLs
- Deep research with comprehensive analysis
- Advanced reasoning for complex financial questions

## TOOLS - TWO CATEGORIES

### Direct API Tools (Fast, Always Available)
1. **web_search**: Search the web using Perplexity Search API
   - Use for discovering information and finding relevant URLs
   - Returns search results with titles, snippets, and URLs
   - Supports batch queries, country filtering, and domain filtering

2. **web_fetch**: Fetch full content from a specific URL
   - Use AFTER web_search when you need more detailed information
   - Extracts clean text content from HTML pages
   - Useful for reading full articles, analyst reports, filings

### Perplexity MCP Tools (Advanced AI-Powered)
3. **perplexity_ask**: General conversational AI with real-time web search
   - Uses sonar-pro model for comprehensive answers
   - Best for: Questions needing synthesis of multiple sources
   - Returns well-structured answers with citations

4. **perplexity_research**: Deep, comprehensive research
   - Uses sonar-deep-research model for thorough analysis
   - Best for: Complex topics requiring extensive research
   - Returns detailed reports with citations and analysis

5. **perplexity_reason**: Advanced reasoning and problem-solving
   - Uses sonar-reasoning-pro model for logical analysis
   - Best for: Complex problems, comparisons, decision-making
   - Returns structured reasoning with conclusions

## WHEN TO USE EACH TOOL

**Use web_search + web_fetch for:**
- Quick stock news lookups
- Latest quarterly results or earnings
- Checking specific analyst ratings or price targets
- Market status and index movements
- Regulatory announcements

**Use perplexity_ask for:**
- General market sentiment questions
- Quick summaries of company performance
- "What happened to X stock today?" type queries

**Use perplexity_research for:**
- Comprehensive stock/sector analysis
- Comparing two companies (e.g., "HDFC Bank vs ICICI Bank")
- Industry deep dives (IT sector outlook, pharma trends)
- Macro research (India GDP, inflation, FII flows)

**Use perplexity_reason for:**
- Investment thesis evaluation
- Risk analysis for specific positions
- "Should I buy X at current levels?" type questions
- Sector rotation analysis

## MULTI-STEP RESEARCH WORKFLOW

For comprehensive research tasks, combine tools:

1. **Quick research**: perplexity_ask for synthesized answer
2. **Deep research**: perplexity_research for comprehensive analysis
3. **Specific data**: web_search + web_fetch for raw content from specific sites
4. **Decision support**: perplexity_reason for logical analysis

**Example workflow for "Should I invest in Reliance Industries?":**
Option A (AI-powered): perplexity_research("Reliance Industries investment analysis 2026 fundamentals technicals")
Option B (Manual): web_search → web_fetch multiple URLs → synthesize

## SEARCH BEST PRACTICES

1. Use specific, targeted queries for better results
2. Include "NSE" or "India" for Indian market context
3. Use country: "IN" for India-focused searches
4. Choose the right tool for the task complexity
5. For complex questions, prefer perplexity_research over multiple web_search calls

**Search tips:**
- Include stock exchange: "RELIANCE NSE quarterly results"
- Add timeframes for recent info: "Nifty 50 outlook 2026"
- Use financial terms: "HDFC Bank NPA ratio Q3 2026"
- For global context: "US Fed rate impact on Indian markets"

## TRUSTED SOURCES FOR INDIAN MARKETS

Prioritize these domains when relevant:
- moneycontrol.com, economictimes.com, livemint.com (news)
- screener.in, trendlyne.com, tickertape.in (fundamentals)
- nseindia.com, bseindia.com (official exchange data)
- rbi.org.in, sebi.gov.in (regulatory)

## RESPONSE FORMAT

Your final response MUST:
1. Synthesize information from ALL sources used
2. Include inline citations with source names/URLs
3. Provide structured, comprehensive answers
4. Note any conflicting information between sources
5. Instruct the orchestrator to provide all citations to the user
6. Use INR (₹) for all monetary values unless comparing globally

NEVER respond without citing sources. The orchestrator will format your citations for the user.
"""
    
    def _register_tools(self) -> None:
        """Register tools with the agent"""
        
        @self.agent.tool
        async def web_search(
            ctx: RunContext[WebSearchDeps],
            query: str,
            max_results: int = 10,
            country: Optional[str] = "IN",  # default to India
            search_domain_filter: Optional[List[str]] = None,
            queries: Optional[List[str]] = None,
        ) -> str:
            """
            Perform a web search using Perplexity Search API

            Args:
                query: Search query string
                max_results: Maximum number of results (default: 10)
                country: Two-letter country code (default: "CA" for Canada)
                search_domain_filter: List of domains to prioritize/filter (e.g., ["example.com", "test.com"])
                queries: List of additional related queries for batch searching

            Returns:
                Formatted search results with sources
            """
            import time

            # Create Logfire span for web search
            if logfire:
                span = logfire.span(
                    "web_search.perplexity",
                    query=query[:100],
                    max_results=max_results
                )
            else:
                from contextlib import nullcontext
                span = nullcontext()

            try:
                async with span:
                    start_time = time.time()

                    if logfire:
                        logfire.info("web_search.started", query=query[:200])

                    # Get API key from deps
                    api_key = ctx.deps.perplexity_api_key
                    if not api_key:
                        return "Error: Perplexity API key not configured. Please set PERPLEXITY_SEARCH_KEY environment variable."

                    # Prepare request payload for Search API
                    # Using the new Search API endpoint - no model parameter needed
                    payload = {
                        "query": query,
                        "max_results": max_results,
                    }

                    # Only include optional parameters if they're provided
                    if country:
                        payload["country"] = country
                    if search_domain_filter:
                        payload["search_domain_filter"] = search_domain_filter
                    if queries:
                        payload["queries"] = queries

                    # Make API request
                    headers = {
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    }

                    # Make the API request with timeout
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            "https://api.perplexity.ai/search",
                            json=payload,
                            headers=headers,
                            timeout=30.0
                        ) as response:
                            if response.status != 200:
                                error_text = await response.text()
                                logger.error(f"Perplexity Search API error: {response.status} - {error_text}")
                                if logfire:
                                    logfire.error("web_search.api_error", status=response.status, error=error_text[:200])
                                return f"Error: Search API returned status {response.status}"

                            data = await response.json()

                    # Extract and format response from Search API
                    # API returns: {"results": [{"title": "...", "url": "...", "snippet": "...", "crawl_date": "...", "last_updated": "..."}]}
                    response_text = f"🔍 Search Results for: '{query}'\n\n"

                    results = data.get("results", [])

                    if not results:
                        if logfire:
                            logfire.info("web_search.no_results", query=query)
                        return f"No results found for query: '{query}'"

                    sources_count = len(results)

                    # Format results
                    for i, result in enumerate(results[:max_results], 1):
                        title = result.get("title", "No title")
                        url = result.get("url", "")
                        snippet = result.get("snippet", "")

                        response_text += f"**{i}. {title}**\n"
                        if snippet:
                            response_text += f"{snippet}\n"
                        if url:
                            response_text += f"🔗 {url}\n"
                        response_text += "\n"

                    # Log success metrics
                    total_time = time.time() - start_time
                    if logfire:
                        logfire.info(
                            "web_search.completed",
                            time_ms=int(total_time * 1000),
                            sources_count=sources_count,
                            response_length=len(response_text)
                        )

                    return response_text

            except asyncio.TimeoutError:
                if logfire:
                    logfire.error("web_search.timeout", query=query)
                return "Error: Search request timed out. Please try again with a simpler query."
            except Exception as e:
                logger.error(f"Error performing web search: {e}")
                if logfire:
                    logfire.error("web_search.error", query=query, error=str(e), error_type=type(e).__name__)
                return f"Error performing search: {str(e)}"
        
        @self.agent.tool
        async def web_fetch(
            ctx: RunContext[WebSearchDeps],
            url: str,
            extract_text: bool = True,
            max_content_length: int = 50000,
        ) -> str:
            """
            Fetch the full content of a specific URL.
            
            Use this tool after web_search when you need more detailed information
            from a specific page that appeared in search results.

            Args:
                url: The URL to fetch content from
                extract_text: If True, extract clean text content; if False, return raw HTML (default: True)
                max_content_length: Maximum characters to return (default: 50000)

            Returns:
                The fetched page content (text or HTML based on extract_text parameter)
            """
            import time
            from bs4 import BeautifulSoup
            
            # Create Logfire span for web fetch
            if logfire:
                span = logfire.span(
                    "web_fetch.url",
                    url=url[:200],
                    extract_text=extract_text
                )
            else:
                from contextlib import nullcontext
                span = nullcontext()

            try:
                async with span:
                    start_time = time.time()

                    if logfire:
                        logfire.info("web_fetch.started", url=url[:200])

                    # Validate URL
                    if not url.startswith(('http://', 'https://')):
                        return "Error: Invalid URL. URL must start with http:// or https://"

                    # Set up headers to mimic a browser request
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                        "Accept-Language": "en-US,en;q=0.5",
                        "Accept-Encoding": "gzip, deflate, br",
                        "Connection": "keep-alive",
                    }

                    # Make the request with timeout
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            url,
                            headers=headers,
                            timeout=aiohttp.ClientTimeout(total=30),
                            allow_redirects=True
                        ) as response:
                            if response.status != 200:
                                error_msg = f"Error: Failed to fetch URL. Status code: {response.status}"
                                logger.error(f"Web fetch error: {response.status} for URL: {url}")
                                if logfire:
                                    logfire.error("web_fetch.http_error", status=response.status, url=url[:200])
                                return error_msg

                            # Check content type
                            content_type = response.headers.get('Content-Type', '')
                            if 'text/html' not in content_type and 'text/plain' not in content_type and 'application/json' not in content_type:
                                return f"Error: Unsupported content type: {content_type}. This tool only supports HTML, plain text, and JSON content."

                            # Read content
                            raw_content = await response.text()

                    # Process content based on extract_text flag
                    if extract_text and 'text/html' in content_type:
                        # Parse HTML and extract text
                        soup = BeautifulSoup(raw_content, 'html.parser')
                        
                        # Remove script and style elements
                        for script in soup(["script", "style", "nav", "footer", "header", "aside"]):
                            script.decompose()
                        
                        # Get text content
                        text = soup.get_text(separator='\n', strip=True)
                        
                        # Clean up excessive whitespace
                        lines = [line.strip() for line in text.splitlines() if line.strip()]
                        content = '\n'.join(lines)
                    else:
                        content = raw_content

                    # Truncate if necessary
                    if len(content) > max_content_length:
                        content = content[:max_content_length] + f"\n\n... [Content truncated at {max_content_length} characters]"

                    # Format response
                    response_text = f"📄 Content from: {url}\n\n"
                    response_text += f"Content-Type: {content_type}\n"
                    response_text += f"Content Length: {len(content)} characters\n\n"
                    response_text += "---\n\n"
                    response_text += content

                    # Log success metrics
                    total_time = time.time() - start_time
                    if logfire:
                        logfire.info(
                            "web_fetch.completed",
                            time_ms=int(total_time * 1000),
                            content_length=len(content),
                            url=url[:200]
                        )

                    return response_text

            except asyncio.TimeoutError:
                if logfire:
                    logfire.error("web_fetch.timeout", url=url[:200])
                return "Error: Request timed out while fetching the URL. The server may be slow or unresponsive."
            except aiohttp.ClientError as e:
                logger.error(f"Error fetching URL {url}: {e}")
                if logfire:
                    logfire.error("web_fetch.client_error", url=url[:200], error=str(e))
                return f"Error: Failed to fetch URL - {str(e)}"
            except Exception as e:
                logger.error(f"Error fetching URL {url}: {e}")
                if logfire:
                    logfire.error("web_fetch.error", url=url[:200], error=str(e), error_type=type(e).__name__)
                return f"Error fetching URL: {str(e)}"

    async def run(self, prompt: str, deps: WebSearchDeps, **kwargs):
        """
        Run web search agent with ON-DEMAND Perplexity MCP server spawning.

        This spawns the Perplexity MCP server to provide advanced tools:
        - perplexity_ask: Conversational AI with web search (sonar-pro)
        - perplexity_research: Deep research (sonar-deep-research)
        - perplexity_reason: Advanced reasoning (sonar-reasoning-pro)

        The existing web_search and web_fetch tools are registered directly
        on the temp agent for fast, direct API access.
        """
        mcp_servers = []

        try:
            # Prepare MCP environment with Perplexity API key
            mcp_env = os.environ.copy()

            # Get API key - check multiple sources (deps, PERPLEXITY_API_KEY, PERPLEXITY_SEARCH_KEY)
            api_key = (
                deps.perplexity_api_key
                or os.getenv("PERPLEXITY_API_KEY")
                or os.getenv("PERPLEXITY_SEARCH_KEY")  # Fallback to search key
            )
            if not api_key:
                logger.warning("[Web Search Agent] No Perplexity API key found - MCP tools will not be available")
            else:
                # MCP server expects PERPLEXITY_API_KEY
                mcp_env['PERPLEXITY_API_KEY'] = api_key

            # Spawn Perplexity MCP server on-demand
            logger.info("[Web Search Agent] Spawning Perplexity MCP server...")
            perplexity_server = MCPServerStdio(
                command='npx',
                args=['-y', '@perplexity-ai/mcp-server'],
                env=mcp_env
            )
            mcp_servers.append(perplexity_server)

            # Create temporary agent with on-demand MCP toolsets
            temp_agent = Agent(
                model=self.model,
                name=self.name,
                deps_type=WebSearchDeps,
                output_type=str,
                instructions=self._get_system_prompt(),
                retries=self.config.max_retries,
                toolsets=mcp_servers  # Use on-demand MCP servers
            )

            # Re-register the direct API tools on temp agent
            @temp_agent.tool
            async def web_search(
                ctx: RunContext[WebSearchDeps],
                query: str,
                max_results: int = 10,
                country: Optional[str] = "CA",
                search_domain_filter: Optional[List[str]] = None,
                queries: Optional[List[str]] = None,
            ) -> str:
                """
                Perform a web search using Perplexity Search API (direct, fast).

                Args:
                    query: Search query string
                    max_results: Maximum number of results (default: 10)
                    country: Two-letter country code (default: "CA" for Canada)
                    search_domain_filter: List of domains to prioritize/filter
                    queries: List of additional related queries for batch searching

                Returns:
                    Formatted search results with sources
                """
                import time

                if logfire:
                    span = logfire.span("web_search.perplexity", query=query[:100], max_results=max_results)
                else:
                    from contextlib import nullcontext
                    span = nullcontext()

                try:
                    async with span:
                        start_time = time.time()
                        if logfire:
                            logfire.info("web_search.started", query=query[:200])

                        search_api_key = (
                            ctx.deps.perplexity_api_key
                            or os.getenv("PERPLEXITY_SEARCH_KEY")
                            or os.getenv("PERPLEXITY_API_KEY")
                        )
                        if not search_api_key:
                            return "Error: Perplexity API key not configured."

                        payload = {"query": query, "max_results": max_results}
                        if country:
                            payload["country"] = country
                        if search_domain_filter:
                            payload["search_domain_filter"] = search_domain_filter
                        if queries:
                            payload["queries"] = queries

                        headers = {
                            "Authorization": f"Bearer {search_api_key}",
                            "Content-Type": "application/json"
                        }

                        async with aiohttp.ClientSession() as session:
                            async with session.post(
                                "https://api.perplexity.ai/search",
                                json=payload,
                                headers=headers,
                                timeout=30.0
                            ) as response:
                                if response.status != 200:
                                    error_text = await response.text()
                                    logger.error(f"Perplexity Search API error: {response.status} - {error_text}")
                                    return f"Error: Search API returned status {response.status}"

                                data = await response.json()

                        response_text = f"🔍 Search Results for: '{query}'\n\n"
                        results = data.get("results", [])

                        if not results:
                            return f"No results found for query: '{query}'"

                        for i, result in enumerate(results[:max_results], 1):
                            title = result.get("title", "No title")
                            url = result.get("url", "")
                            snippet = result.get("snippet", "")

                            response_text += f"**{i}. {title}**\n"
                            if snippet:
                                response_text += f"{snippet}\n"
                            if url:
                                response_text += f"🔗 {url}\n"
                            response_text += "\n"

                        total_time = time.time() - start_time
                        if logfire:
                            logfire.info("web_search.completed", time_ms=int(total_time * 1000), sources_count=len(results))

                        return response_text

                except asyncio.TimeoutError:
                    return "Error: Search request timed out."
                except Exception as e:
                    logger.error(f"Error performing web search: {e}")
                    return f"Error performing search: {str(e)}"

            @temp_agent.tool
            async def web_fetch(
                ctx: RunContext[WebSearchDeps],
                url: str,
                extract_text: bool = True,
                max_content_length: int = 50000,
            ) -> str:
                """
                Fetch the full content of a specific URL.

                Args:
                    url: The URL to fetch content from
                    extract_text: If True, extract clean text content (default: True)
                    max_content_length: Maximum characters to return (default: 50000)

                Returns:
                    The fetched page content
                """
                import time
                from bs4 import BeautifulSoup

                if logfire:
                    span = logfire.span("web_fetch.url", url=url[:200], extract_text=extract_text)
                else:
                    from contextlib import nullcontext
                    span = nullcontext()

                try:
                    async with span:
                        start_time = time.time()
                        if logfire:
                            logfire.info("web_fetch.started", url=url[:200])

                        if not url.startswith(('http://', 'https://')):
                            return "Error: Invalid URL. Must start with http:// or https://"

                        headers = {
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                            "Accept-Language": "en-US,en;q=0.5",
                        }

                        async with aiohttp.ClientSession() as session:
                            async with session.get(
                                url,
                                headers=headers,
                                timeout=aiohttp.ClientTimeout(total=30),
                                allow_redirects=True
                            ) as response:
                                if response.status != 200:
                                    return f"Error: Failed to fetch URL. Status code: {response.status}"

                                content_type = response.headers.get('Content-Type', '')
                                if 'text/html' not in content_type and 'text/plain' not in content_type and 'application/json' not in content_type:
                                    return f"Error: Unsupported content type: {content_type}"

                                raw_content = await response.text()

                        if extract_text and 'text/html' in content_type:
                            soup = BeautifulSoup(raw_content, 'html.parser')
                            for script in soup(["script", "style", "nav", "footer", "header", "aside"]):
                                script.decompose()
                            text = soup.get_text(separator='\n', strip=True)
                            lines = [line.strip() for line in text.splitlines() if line.strip()]
                            content = '\n'.join(lines)
                        else:
                            content = raw_content

                        if len(content) > max_content_length:
                            content = content[:max_content_length] + f"\n\n... [Truncated at {max_content_length} chars]"

                        response_text = f"📄 Content from: {url}\n\n"
                        response_text += f"Content-Type: {content_type}\n"
                        response_text += f"Content Length: {len(content)} characters\n\n---\n\n"
                        response_text += content

                        total_time = time.time() - start_time
                        if logfire:
                            logfire.info("web_fetch.completed", time_ms=int(total_time * 1000), content_length=len(content))

                        return response_text

                except asyncio.TimeoutError:
                    return "Error: Request timed out while fetching the URL."
                except aiohttp.ClientError as e:
                    return f"Error: Failed to fetch URL - {str(e)}"
                except Exception as e:
                    logger.error(f"Error fetching URL {url}: {e}")
                    return f"Error fetching URL: {str(e)}"

            # Run the temporary agent with both direct API tools and MCP tools
            logger.info(f"[Web Search Agent] Running with Perplexity MCP server")
            result = await temp_agent.run(prompt, deps=deps, **kwargs)
            logger.info(f"✅ Web Search agent completed")

            return result

        except BaseException as e:
            # Log full traceback including ExceptionGroup sub-exceptions
            import traceback
            logger.error(f"❌ Web Search agent error: {e}")
            logger.error(f"❌ Full traceback:\n{traceback.format_exc()}")
            # If it's an ExceptionGroup (from TaskGroup), log each sub-exception
            if hasattr(e, 'exceptions'):
                for i, sub_exc in enumerate(e.exceptions):
                    logger.error(f"❌ Sub-exception {i}: {type(sub_exc).__name__}: {sub_exc}")
                    logger.error(f"❌ Sub-exception {i} traceback:\n{''.join(traceback.format_exception(sub_exc))}")
            raise RuntimeError(f"Web Search agent encountered an error: {str(e)}")

        finally:
            # Clean up MCP servers
            for server in mcp_servers:
                try:
                    if hasattr(server, 'cleanup'):
                        await server.cleanup()
                    logger.info("[Web Search Agent] MCP server cleaned up")
                except Exception as e:
                    logger.warning(f"[Web Search Agent] Error cleaning up MCP server: {e}")
