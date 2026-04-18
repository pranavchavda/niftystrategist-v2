#!/usr/bin/env python3
"""
Financial News Tracker - A tool to fetch and analyze financial news using Perplexity's APIs.

Supports two API backends:
  • Agent API  (POST /v1/agent) — frontier third-party models with web_search tool
  • Sonar API  (POST /chat/completions) — Perplexity-native sonar models

See https://docs.perplexity.ai/docs/getting-started/overview for full docs.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

import re
import requests
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load .env so API keys are available when run directly from terminal
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_backend_dir, ".env"))


# Common NSE symbols that need disambiguation (global name conflicts)
NSE_SYMBOL_MAP = {
    "MAZDOCK": "Mazagon Dock Shipbuilders",
    "TATAMOTORS": "Tata Motors",
    "RELIANCE": "Reliance Industries",
    "TCS": "Tata Consultancy Services",
    "INFY": "Infosys",
    "HDFCBANK": "HDFC Bank",
    "ICICIBANK": "ICICI Bank",
    "SBIN": "State Bank of India",
    "BHARTIARTL": "Bharti Airtel",
    "ADANIPORTS": "Adani Ports",
    "NTPC": "NTPC Limited",
    "COALINDIA": "Coal India",
    "HINDALCO": "Hindalco Industries",
    "SUNPHARMA": "Sun Pharmaceutical",
    "DRREDDY": "Dr. Reddy's Laboratories",
    "BAJFINANCE": "Bajaj Finance",
    "KOTAKBANK": "Kotak Mahindra Bank",
    "AXISBANK": "Axis Bank",
    "INDUSINDBK": "IndusInd Bank",
    "M&M": "Mahindra & Mahindra",
    "MARUTI": "Maruti Suzuki",
    "TITAN": "Titan Company",
    "ULTRACEMCO": "UltraTech Cement",
    "NESTLEIND": "Nestle India",
    "GRASIM": "Grasim Industries",
    "ADANIENT": "Adani Enterprises",
    "ADANIGREEN": "Adani Green Energy",
    "ADANITRANS": "Adani Transmission",
    "POWERGRID": "Power Grid Corporation",
    "ONGC": "Oil and Natural Gas Corporation",
    "BPCL": "Bharat Petroleum",
    "IOC": "Indian Oil Corporation",
    "LT": "Larsen & Toubro",
    "WIPRO": "Wipro Limited",
    "TECHM": "Tech Mahindra",
    "HEROMOTOCO": "Hero MotoCorp",
    "BAJAJ-AUTO": "Bajaj Auto",
    "EICHERMOT": "Eicher Motors",
    "DIVISLAB": "Divi's Laboratories",
    "CIPLA": "Cipla Limited",
    "APOLLOHOSP": "Apollo Hospitals",
    "MEDMAN": "Medplus Health Services",
    "SHRIRAMFIN": "Shriram Finance",
    "CHOLAFIN": "Cholamandalam Investment",
    "MUTHOOTFIN": "Muthoot Finance",
    "DLF": "DLF Limited",
    "GODREJPROP": "Godrej Properties",
    "BERGER": "Berger Paints",
    "PIDILIT": "Pidilite Industries",
    "AMBER": "Amber Enterprises",
}


def _is_likely_nse_symbol(query: str) -> bool:
    """Check if query looks like an NSE stock symbol."""
    query = query.strip().upper()
    # NSE symbols are typically 2-10 uppercase letters, may include hyphen
    pattern = r'^[A-Z]{2,10}(-[A-Z]{1,3})?$'
    return bool(re.match(pattern, query))


def _transform_nse_query(query: str) -> str:
    """
    Transform NSE symbols into better Perplexity queries.
    
    Handles:
    - Auto-prefix with NSE: for disambiguation
    - Expand common symbols to full company names
    """
    query = query.strip()
    upper_query = query.upper()
    
    # Check if it's a known NSE symbol that needs expansion
    if upper_query in NSE_SYMBOL_MAP:
        company_name = NSE_SYMBOL_MAP[upper_query]
        return f"NSE: {company_name} ({upper_query}) stock news"
    
    # For other uppercase symbols, try to prefix with NSE:
    if _is_likely_nse_symbol(query):
        return f"NSE: {query} stock news"
    
    return query


class NewsItem(BaseModel):
    """Model for representing a single financial news item."""
    headline: str = Field(description="The news headline")
    summary: str = Field(description="Brief summary of the news")
    impact: str = Field(description="Potential market impact: HIGH, MEDIUM, LOW, or NEUTRAL")
    sectors_affected: List[str] = Field(description="List of sectors/companies affected")
    source: str = Field(description="News source")


class MarketAnalysis(BaseModel):
    """Model for financial market analysis."""
    market_sentiment: str = Field(description="Overall market sentiment: BULLISH, BEARISH, or NEUTRAL")
    key_drivers: List[str] = Field(description="Key factors driving the market")
    risks: List[str] = Field(description="Current market risks")
    opportunities: List[str] = Field(description="Potential market opportunities")


class FinancialNewsResult(BaseModel):
    """Model for the complete financial news result."""
    query_topic: str = Field(description="The topic/query that was searched")
    time_period: str = Field(description="Time period covered by the news")
    summary: str = Field(description="Executive summary of the financial news")
    news_items: List[NewsItem] = Field(description="List of relevant news items")
    market_analysis: MarketAnalysis = Field(description="Overall market analysis")
    recommendations: List[str] = Field(description="Investment recommendations or insights")


# ---------------------------------------------------------------------------
# API backend helpers
# ---------------------------------------------------------------------------

# Sonar-native model identifiers (use Sonar API at /chat/completions)
SONAR_MODELS = {"sonar", "sonar-pro", "sonar-reasoning", "sonar-reasoning-pro", "sonar-deep-research"}

# Agent API presets (shorthand names that resolve to a model + system prompt)
AGENT_PRESETS = {"fast-search", "pro-search", "deep-research"}

# Default frontier model for the Agent API (highest accuracy third-party model)
DEFAULT_AGENT_MODEL = "nvidia/nemotron-3-super-120b-a12b"

# Default Sonar model (highest accuracy Perplexity-native model)
DEFAULT_SONAR_MODEL = "sonar-pro"


def _is_sonar_model(model: str) -> bool:
    """Return True if *model* should be routed through the Sonar chat/completions API."""
    return model in SONAR_MODELS


def _is_agent_preset(model: str) -> bool:
    """Return True if *model* is actually an Agent API preset name."""
    return model in AGENT_PRESETS


class FinancialNewsTracker:
    """A class to interact with Perplexity APIs for financial news tracking.

    Automatically selects the right backend:
      • Agent API  (/v1/agent)         — for third-party models & presets
      • Sonar API  (/chat/completions) — for Perplexity-native sonar models
    """

    AGENT_API_URL = "https://api.perplexity.ai/v1/agent"
    SONAR_API_URL = "https://api.perplexity.ai/v1/sonar"
    DEFAULT_MODEL = DEFAULT_AGENT_MODEL

    # Models that support structured outputs (Sonar API only)
    STRUCTURED_OUTPUT_MODELS = ["sonar", "sonar-pro", "sonar-reasoning", "sonar-reasoning-pro"]

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the FinancialNewsTracker with API key.

        Args:
            api_key: Perplexity API key. If None, will try to read from environment.
        """
        self.api_key = api_key or self._get_api_key()
        if not self.api_key:
            raise ValueError(
                "API key not found. Please provide via argument or environment variable PPLX_API_KEY."
            )

    def _get_api_key(self) -> str:
        """
        Try to get API key from environment or from a file.

        Returns:
            The API key if found, empty string otherwise.
        """
        api_key = os.environ.get("PPLX_API_KEY", "") or os.environ.get("PERPLEXITY_API_KEY", "")
        if api_key:
            return api_key

        for key_file in ["pplx_api_key", ".pplx_api_key"]:
            key_path = Path(key_file)
            if key_path.exists():
                try:
                    return key_path.read_text().strip()
                except Exception:
                    pass

        return ""

    # --------------------------------------------------------------------- #
    # Public entry point                                                      #
    # --------------------------------------------------------------------- #

    def get_financial_news(
        self,
        query: str,
        time_range: str = "24h",
        model: str = DEFAULT_MODEL,
        use_structured_output: bool = False
    ) -> Dict[str, Any]:
        """
        Fetch financial news based on the query.

        Routes to the Agent API or Sonar API depending on the model chosen.

        Args:
            query: The financial topic or query (e.g., "tech stocks", "S&P 500", "cryptocurrency")
            time_range: Time range for news (e.g., "24h", "1w", "1m")
            model: The model to use.  Accepts:
                   - Agent API third-party models (e.g. "anthropic/claude-opus-4-6")
                   - Agent API presets            (e.g. "pro-search")
                   - Sonar models                 (e.g. "sonar-reasoning-pro")
            use_structured_output: Whether to use structured output (Sonar API only)

        Returns:
            The parsed response containing financial news and analysis.
        """
        if not query or not query.strip():
            return {"error": "Query is empty. Please provide a financial topic to search."}

        if _is_sonar_model(model):
            return self._fetch_via_sonar(query, time_range, model, use_structured_output)
        else:
            return self._fetch_via_agent(query, time_range, model)

    # --------------------------------------------------------------------- #
    # Agent API backend  (POST /v1/agent)                                     #
    # --------------------------------------------------------------------- #

    def _fetch_via_agent(
        self,
        query: str,
        time_range: str,
        model: str,
    ) -> Dict[str, Any]:
        """Use the Agent API with web_search tool for highest accuracy."""

        transformed_query = _transform_nse_query(query)
        today_str = datetime.now().strftime("%Y-%m-%d")
        time_context = self._get_time_context(time_range)
        cutoff_date = self._date_cutoff(time_range)

        date_constraint = ""
        if cutoff_date:
            date_constraint = f"\n- HARD DATE CUTOFF: Only use sources published on or after {cutoff_date}. Discard anything older."

        instructions = f"""You are a professional financial analyst with expertise in market research and news analysis.
Your task is to provide comprehensive, factual financial news updates and market context.
Focus on accuracy, relevance, and factual grounding. Do NOT provide investment recommendations, trade advice, or allocation suggestions — report what is happening, not what the reader should do.

CRITICAL FRESHNESS RULES:
- Today is {today_str}. Only cite sources from within the requested time window ({time_context}).{date_constraint}
- State the publication date of every news item you cite (YYYY-MM-DD).
- If you cannot confirm a source's date, mark it "date not confirmed" and de-prioritize it.
- Never present year-old or generic analysis as "recent". Reject stale material.

You have access to a web_search tool. Use it proactively to find the freshest financial data.
Use 2-4 focused search queries to cover different angles (price action, fundamentals, news, analyst views).
Append "today" or "this week" or "{today_str}" to your search queries to bias toward recent results.
Keep queries brief: 2-5 words each. NEVER ask permission to search — just search."""

        user_input = f"""Provide a comprehensive financial news update and market context for: {transformed_query}

Time period: {time_context} (as of {today_str})

Please include:
1. Recent relevant news items with their potential market impact (include each item's publication date)
2. Overall market sentiment and analysis
3. Key market drivers and risks
4. Sectors or companies most affected

Focus on the most significant and recent developments. Exclude anything outside the time window. Do NOT include investment recommendations, trade advice, buy/sell calls, or allocation suggestions — this briefing is factual context only."""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        data: Dict[str, Any] = {
            "input": user_input,
            "instructions": instructions,
            "tools": [{"type": "web_search"}],
        }

        # If it's a preset name, use that; otherwise specify the model
        if _is_agent_preset(model):
            data["preset"] = model
        else:
            data["model"] = model

        try:
            response = requests.post(self.AGENT_API_URL, headers=headers, json=data)
            response.raise_for_status()
            result = response.json()

            return self._parse_agent_response(result)

        except requests.exceptions.RequestException as e:
            return {"error": f"Agent API request failed: {str(e)}"}
        except Exception as e:
            return {"error": f"Unexpected error: {str(e)}"}

    def _parse_agent_response(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Parse the Agent API response structure.

        Agent API responses have an ``output`` array containing items of different
        types: ``search_results``, ``fetch_url_results``, and ``message``.
        """
        parsed: Dict[str, Any] = {}

        if result.get("status") == "failed":
            error = result.get("error", {})
            return {"error": f"Agent API error: {error.get('message', 'Unknown error')}"}

        output_items = result.get("output", [])
        search_sources: List[Dict[str, Any]] = []
        content_text = ""

        for item in output_items:
            item_type = item.get("type", "")

            if item_type == "search_results":
                # Collect search result metadata (titles, urls, dates)
                for sr in item.get("results", []):
                    search_sources.append({
                        "title": sr.get("title", ""),
                        "url": sr.get("url", ""),
                        "date": sr.get("date", ""),
                        "snippet": sr.get("snippet", ""),
                    })

            elif item_type == "message":
                # Extract the assistant's text content
                for content_block in item.get("content", []):
                    if content_block.get("type") == "output_text":
                        content_text += content_block.get("text", "")

        parsed["raw_response"] = content_text

        # Attach search sources as citations
        if search_sources:
            parsed["citations"] = [s["url"] for s in search_sources if s.get("url")]
            parsed["search_results"] = search_sources

        # Include usage/cost info if available
        usage = result.get("usage")
        if usage:
            parsed["usage"] = usage

        # Include model that was actually used
        if result.get("model"):
            parsed["model_used"] = result["model"]

        return parsed

    # --------------------------------------------------------------------- #
    # Sonar API backend  (POST /chat/completions)                             #
    # --------------------------------------------------------------------- #

    def _fetch_via_sonar(
        self,
        query: str,
        time_range: str,
        model: str,
        use_structured_output: bool,
    ) -> Dict[str, Any]:
        """Use the Sonar chat/completions API (Perplexity-native models)."""

        transformed_query = _transform_nse_query(query)
        today_str = datetime.now().strftime("%Y-%m-%d")
        time_context = self._get_time_context(time_range)

        system_prompt = f"""You are a professional financial analyst with expertise in market research and news analysis.
        Your task is to provide comprehensive, factual financial news updates and market context.
        Focus on accuracy, relevance, and factual grounding. Do NOT provide investment recommendations, trade advice, or allocation suggestions — report what is happening, not what the reader should do.

        CRITICAL FRESHNESS RULES:
        - Today is {today_str}. Only cite sources from within the requested time window.
        - State the publication date of every news item you cite (YYYY-MM-DD).
        - If you cannot confirm a source's date, mark it "date not confirmed" and de-prioritize it.
        - Never present year-old or generic analysis as "recent". Reject stale material."""

        user_prompt = f"""Provide a comprehensive financial news update and market context for: {transformed_query}

Time period: {time_context} (as of {today_str})

Please include:
1. Recent relevant news items with their potential market impact (include each item's publication date)
2. Overall market sentiment and analysis
3. Key market drivers and risks
4. Sectors or companies most affected

Focus on the most significant and recent developments. Exclude anything outside the time window. Do NOT include investment recommendations, trade advice, buy/sell calls, or allocation suggestions — this briefing is factual context only."""

        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        data: Dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        }

        recency = self._recency_filter_for(time_range)
        if recency:
            data["search_recency_filter"] = recency

        # Hard date cutoff — limits search index to recent publications
        cutoff = self._date_cutoff(time_range)
        if cutoff:
            data["search_after_date_filter"] = cutoff

        can_use_structured_output = model in self.STRUCTURED_OUTPUT_MODELS and use_structured_output
        if can_use_structured_output:
            data["response_format"] = {
                "type": "json_schema",
                "json_schema": {"schema": FinancialNewsResult.model_json_schema()},
            }

        try:
            response = requests.post(self.SONAR_API_URL, headers=headers, json=data)
            response.raise_for_status()
            result = response.json()

            citations = result.get("citations", [])

            if "choices" in result and result["choices"] and "message" in result["choices"][0]:
                content = result["choices"][0]["message"]["content"]
                
                # Extract reasoning if available (e.g. from sonar-reasoning-pro models)
                reasoning = None
                if "<think>" in content and "</think>" in content:
                    parts = content.split("</think>", 1)
                    reasoning = parts[0].replace("<think>", "").strip()
                    content = parts[1].strip()

                if can_use_structured_output:
                    try:
                        clean_content = content
                        if clean_content.startswith("```json"):
                            clean_content = clean_content.split("```json")[-1].rsplit("```", 1)[0].strip()
                        elif clean_content.startswith("```"):
                            clean_content = clean_content.split("```")[-1].rsplit("```", 1)[0].strip()

                        parsed = json.loads(clean_content)
                        if citations and "citations" not in parsed:
                            parsed["citations"] = citations
                        if reasoning:
                            parsed["reasoning"] = reasoning
                        return parsed
                    except json.JSONDecodeError as e:
                        return {"error": f"Failed to parse structured output: {str(e)}", "raw_response": content, "citations": citations, "reasoning": reasoning}
                else:
                    parsed = self._parse_response(content)
                    if citations and "citations" not in parsed:
                        parsed["citations"] = citations
                    if reasoning:
                        parsed["reasoning"] = reasoning
                    return parsed

            return {"error": "Unexpected API response format", "raw_response": result}

        except requests.exceptions.RequestException as e:
            return {"error": f"API request failed: {str(e)}"}
        except Exception as e:
            return {"error": f"Unexpected error: {str(e)}"}

    # --------------------------------------------------------------------- #
    # Shared helpers                                                          #
    # --------------------------------------------------------------------- #

    def _recency_filter_for(self, time_range: str) -> Optional[str]:
        """Map CLI time_range to Perplexity search_recency_filter enum."""
        return {
            "1h": "hour",
            "24h": "day",
            "1w": "week",
            "1m": "month",
            "3m": "month",
            "1y": "year",
        }.get(time_range)

    def _date_cutoff(self, time_range: str) -> Optional[str]:
        """Return a hard date cutoff string in MM/DD/YYYY format for the given time_range.

        This is used with Perplexity's ``search_after_date_filter`` parameter to
        restrict the search index to only recent publications.
        """
        now = datetime.now()
        delta_map = {
            "1h": timedelta(hours=1),
            "24h": timedelta(days=1),
            "1w": timedelta(weeks=1),
            "1m": timedelta(days=30),
            "3m": timedelta(days=90),
            "1y": timedelta(days=365),
        }
        delta = delta_map.get(time_range)
        if delta is None:
            return None
        cutoff = now - delta
        return cutoff.strftime("%-m/%-d/%Y")

    def _get_time_context(self, time_range: str) -> str:
        """
        Convert time range shorthand to descriptive context.

        Args:
            time_range: Time range string (e.g., "24h", "1w")

        Returns:
            Descriptive time context string.
        """
        now = datetime.now()

        if time_range == "1h":
            return "Last hour"
        elif time_range == "24h":
            return "Last 24 hours"
        elif time_range == "1w":
            return "Last 7 days"
        elif time_range == "1m":
            return "Last 30 days"
        elif time_range == "3m":
            return "Last 3 months"
        elif time_range == "1y":
            return "Last year"
        else:
            return f"Recent period ({time_range})"

    def _parse_response(self, content: str) -> Dict[str, Any]:
        """
        Parse the response content to extract structured information.

        Args:
            content: The response content from the API

        Returns:
            A dictionary with parsed information.
        """
        try:
            # Try to extract JSON if present
            if "```json" in content:
                json_content = content.split("```json")[1].split("```")[0].strip()
                return json.loads(json_content)
            elif "```" in content:
                json_content = content.split("```")[1].split("```")[0].strip()
                return json.loads(json_content)
            else:
                # Fallback to returning raw content
                return {"raw_response": content}
        except (json.JSONDecodeError, IndexError):
            return {"raw_response": content}


def display_results(results: Dict[str, Any], format_json: bool = False):
    """
    Display the financial news results in a human-readable format.

    Args:
        results: The financial news results dictionary
        format_json: Whether to display the results as formatted JSON
    """
    if "error" in results:
        print(f"Error: {results['error']}")
        if "raw_response" in results:
            print("\nRaw response:")
            print(results["raw_response"])
        return

    if format_json:
        print(json.dumps(results, indent=2))
        return

    if "model_used" in results:
        print(f"\n🤖 Model: {results['model_used']}")

    if "query_topic" in results:
        print(f"\n📊 FINANCIAL NEWS REPORT: {results['query_topic']}")
        print(f"📅 Period: {results.get('time_period', 'Recent')}")

        if "reasoning" in results:
            print(f"\n🧠 REASONING:")
            print(f"{results['reasoning']}\n")

        if "summary" in results:
            print(f"\n📝 EXECUTIVE SUMMARY:")
            print(f"{results['summary']}\n")

        if "market_analysis" in results:
            analysis = results["market_analysis"]
            sentiment = analysis.get("market_sentiment", "UNKNOWN")
            sentiment_emoji = "🐂" if sentiment == "BULLISH" else "🐻" if sentiment == "BEARISH" else "⚖️"

            print(f"📈 MARKET ANALYSIS:")
            print(f"  Sentiment: {sentiment_emoji} {sentiment}")

            if "key_drivers" in analysis and analysis["key_drivers"]:
                print(f"\n  Key Drivers:")
                for driver in analysis["key_drivers"]:
                    print(f"    • {driver}")

            if "risks" in analysis and analysis["risks"]:
                print(f"\n  ⚠️  Risks:")
                for risk in analysis["risks"]:
                    print(f"    • {risk}")

            if "opportunities" in analysis and analysis["opportunities"]:
                print(f"\n  💡 Opportunities:")
                for opportunity in analysis["opportunities"]:
                    print(f"    • {opportunity}")

        if "news_items" in results and results["news_items"]:
            print(f"\n📰 KEY NEWS ITEMS:")
            for i, item in enumerate(results["news_items"], 1):
                impact = item.get("impact", "UNKNOWN")
                impact_emoji = "🔴" if impact == "HIGH" else "🟡" if impact == "MEDIUM" else "🟢" if impact == "LOW" else "⚪"

                print(f"\n{i}. {item.get('headline', 'No headline')}")
                print(f"   Impact: {impact_emoji} {impact}")
                print(f"   Summary: {item.get('summary', 'No summary')}")

                if "sectors_affected" in item and item["sectors_affected"]:
                    print(f"   Sectors: {', '.join(item['sectors_affected'])}")

                if "source" in item:
                    print(f"   Source: {item['source']}")

        if "recommendations" in results and results["recommendations"]:
            print(f"\n💼 INSIGHTS & RECOMMENDATIONS:")
            for rec in results["recommendations"]:
                print(f"  • {rec}")

    elif "raw_response" in results:
        print("\n📊 FINANCIAL NEWS ANALYSIS:")
        print(results["raw_response"])

    # Show citations (URLs from either API)
    if "citations" in results and results["citations"]:
        print("\n📚 Sources:")
        for citation in results["citations"]:
            print(f"  • {citation}")

    # Show search result metadata if available (Agent API)
    if "search_results" in results and results["search_results"]:
        # Sort by date descending (newest first) and limit to 10
        sr_list = list(results["search_results"])
        sr_list.sort(key=lambda s: s.get("date", "0000-00-00"), reverse=True)
        sr_list = sr_list[:10]

        print(f"\n🔍 Search Results Referenced ({len(sr_list)} most recent):")
        for i, sr in enumerate(sr_list, 1):
            title = sr.get("title", "Untitled")
            url = sr.get("url", "")
            date = sr.get("date", "unknown date")
            print(f"  {i}. [{date}] {title}")
            if url:
                print(f"     {url}")

    # Show usage/cost if available
    if "usage" in results:
        usage = results["usage"]
        cost = usage.get("cost", {})
        total_cost = cost.get("total_cost")
        if total_cost is not None:
            print(f"\n💰 API Cost: ${total_cost:.5f}")


def main():
    """Main entry point for the financial news tracker CLI."""
    model_help = (
        f"Model to use. Accepts:\n"
        f"  Agent API models: anthropic/claude-opus-4-6, openai/gpt-5.4, google/gemini-3.1-pro-preview, etc.\n"
        f"  Agent API presets: pro-search, fast-search, deep-research\n"
        f"  Sonar models:     sonar, sonar-pro, sonar-reasoning-pro\n"
        f"  (default: {FinancialNewsTracker.DEFAULT_MODEL})"
    )

    parser = argparse.ArgumentParser(
        description="Financial News Tracker - Fetch and analyze financial news using Perplexity APIs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "query",
        type=str,
        help="Financial topic to search (e.g., 'tech stocks', 'S&P 500', 'cryptocurrency', 'AAPL')"
    )

    parser.add_argument(
        "-t",
        "--time-range",
        type=str,
        default="24h",
        choices=["1h", "24h", "1w", "1m", "3m", "1y"],
        help="Time range for news (default: 24h)"
    )

    parser.add_argument(
        "-m",
        "--model",
        type=str,
        default=FinancialNewsTracker.DEFAULT_MODEL,
        help=model_help,
    )

    parser.add_argument(
        "-k",
        "--api-key",
        type=str,
        help="Perplexity API key (if not provided, will look for environment variable PPLX_API_KEY)"
    )

    parser.add_argument(
        "-j",
        "--json",
        action="store_true",
        help="Output results as JSON"
    )

    parser.add_argument(
        "--structured-output",
        action="store_true",
        help="Enable structured output format (Sonar models only, requires Tier 3+ API access)"
    )

    args = parser.parse_args()

    try:
        tracker = FinancialNewsTracker(api_key=args.api_key)

        backend = "Agent API" if not _is_sonar_model(args.model) else "Sonar API"
        print(f"Fetching financial news for '{args.query}' via {backend} [{args.model}]...", file=sys.stderr)

        results = tracker.get_financial_news(
            query=args.query,
            time_range=args.time_range,
            model=args.model,
            use_structured_output=args.structured_output
        )

        display_results(results, format_json=args.json)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
