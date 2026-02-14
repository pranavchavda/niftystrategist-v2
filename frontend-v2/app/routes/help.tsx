import { useNavigate } from 'react-router';
import {
  ChatBubbleLeftRightIcon,
  ChartBarIcon,
  CpuChipIcon,
  SparklesIcon,
  ArrowLeftIcon,
  BookOpenIcon,
  RocketLaunchIcon,
  LightBulbIcon,
  ClipboardDocumentListIcon,
  ArrowPathIcon,
  MicrophoneIcon,
  ArrowTrendingUpIcon,
  WalletIcon,
  MagnifyingGlassIcon,
  BriefcaseIcon,
  Cog6ToothIcon,
  DocumentTextIcon,
  BoltIcon,
  PencilSquareIcon,
  LinkIcon,
  ShieldCheckIcon,
} from '@heroicons/react/24/outline';
import { useState } from 'react';

export default function Help() {
  const navigate = useNavigate();
  const [expandedSection, setExpandedSection] = useState<string | null>('getting-started');

  const toggleSection = (section: string) => {
    setExpandedSection(expandedSection === section ? null : section);
  };

  return (
    <div className="relative min-h-screen overflow-hidden bg-gradient-to-br from-white via-zinc-50 to-white dark:from-zinc-950 dark:via-zinc-950/90 dark:to-zinc-900">
      {/* Background gradients */}
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -top-32 -right-20 h-72 w-72 rounded-full bg-blue-200/40 blur-3xl dark:bg-blue-500/20" />
        <div className="absolute top-1/3 -left-32 h-96 w-96 rounded-full bg-purple-200/30 blur-3xl dark:bg-purple-500/20" />
        <div className="absolute bottom-0 right-1/4 h-80 w-80 rounded-full bg-emerald-200/30 blur-3xl dark:bg-emerald-500/15" />
      </div>

      <div className="relative z-10 flex min-h-screen flex-col">
        {/* Header */}
        <header className="flex flex-col gap-6 px-6 pt-10 sm:gap-8 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-4">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-600">
              <ArrowTrendingUpIcon className="h-9 w-9 text-white" />
            </div>
            <div>
              <h1 className="text-3xl font-bold text-zinc-900 dark:text-white">
                Help & Documentation
              </h1>
              <p className="text-sm text-zinc-600 dark:text-zinc-400">
                Everything you need to know about Nifty Strategist
              </p>
            </div>
          </div>
          <button
            onClick={() => navigate('/')}
            className="inline-flex items-center gap-2 rounded-full border border-zinc-200/70 bg-white/80 px-4 py-2 text-sm text-zinc-700 shadow-sm backdrop-blur transition-all hover:bg-zinc-50 hover:border-zinc-300 dark:border-white/10 dark:bg-white/5 dark:text-zinc-300 dark:hover:bg-white/10"
          >
            <ArrowLeftIcon className="h-5 w-5" />
            <span>Back to Home</span>
          </button>
        </header>

        <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col px-6 pb-20 pt-8">
          {/* Quick Start Card */}
          <div className="mb-12 overflow-hidden rounded-2xl border border-blue-100/70 bg-gradient-to-br from-blue-50/80 via-white/80 to-purple-50/80 p-8 shadow-lg backdrop-blur-md dark:border-blue-500/25 dark:from-blue-500/10 dark:via-zinc-900/80 dark:to-purple-500/10">
            <div className="flex items-start gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-blue-600/10 text-blue-600 dark:bg-blue-500/20 dark:text-blue-300">
                <RocketLaunchIcon className="h-6 w-6" />
              </div>
              <div className="flex-1">
                <h2 className="text-2xl font-bold text-zinc-900 dark:text-white">
                  Welcome to Nifty Strategist!
                </h2>
                <p className="mt-2 text-zinc-600 dark:text-zinc-400">
                  Nifty Strategist is your AI-powered trading assistant for the Indian stock market (NSE/BSE).
                  Analyze stocks, track your portfolio, get trade recommendations with technical analysis,
                  and execute orders -- all through natural conversation. It starts in paper trading mode so you
                  can explore safely before connecting your broker.
                </p>
                <button
                  onClick={() => navigate('/chat/' + `thread_${Date.now()}`)}
                  className="mt-4 inline-flex items-center gap-2 rounded-full bg-blue-600 px-6 py-2 text-sm font-semibold text-white shadow-lg transition-all hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600"
                >
                  <ChatBubbleLeftRightIcon className="h-5 w-5" />
                  Start Your First Conversation
                </button>
              </div>
            </div>
          </div>

          {/* Sections */}
          <div className="space-y-4">
            {/* Getting Started */}
            <Section
              id="getting-started"
              title="Getting Started"
              icon={BookOpenIcon}
              expanded={expandedSection === 'getting-started'}
              onToggle={() => toggleSection('getting-started')}
            >
              <div className="space-y-4 text-zinc-700 dark:text-zinc-300">
                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">
                    1. Start a conversation
                  </h4>
                  <p className="text-sm">
                    Click the <strong>"New Task"</strong> button in the sidebar to begin a new conversation.
                    Each conversation has its own thread that remembers everything you've discussed.
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">
                    2. Ask in natural language
                  </h4>
                  <p className="text-sm mb-2">
                    Just type what you want. No special commands needed. For example:
                  </p>
                  <ul className="text-sm space-y-1 ml-4 list-disc">
                    <li>"What's happening with RELIANCE today?"</li>
                    <li>"Analyze TCS for swing trading"</li>
                    <li>"Compare INFY and WIPRO on technicals"</li>
                    <li>"Show my portfolio"</li>
                    <li>"How's the market looking?"</li>
                  </ul>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">
                    3. Watch it work in real-time
                  </h4>
                  <p className="text-sm">
                    As the AI works, you'll see a live progress panel showing what it's doing -- fetching
                    quotes, running analysis, checking your portfolio. Responses stream in so you can
                    start reading immediately.
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">
                    4. Approve trades before they execute
                  </h4>
                  <p className="text-sm">
                    Before placing any order, the AI pauses and asks for your explicit approval. You'll see
                    the full order details -- stock, quantity, price, order type -- and can approve or reject.
                    You always have the final say.
                  </p>
                </div>
              </div>
            </Section>

            {/* Features & Capabilities */}
            <Section
              id="features"
              title="Features & Capabilities"
              icon={SparklesIcon}
              expanded={expandedSection === 'features'}
              onToggle={() => toggleSection('features')}
            >
              <div className="space-y-6">
                <Feature
                  icon={MagnifyingGlassIcon}
                  title="Stock Analysis"
                  color="blue"
                  description="Technical analysis with RSI, MACD, SMA, EMA, and ATR indicators. Analyze individual stocks or compare multiple stocks side by side. Get buy/sell/hold signals with clear reasoning."
                />
                <Feature
                  icon={ChartBarIcon}
                  title="Market Data"
                  color="purple"
                  description="Live quotes and historical OHLCV data for NSE-listed stocks. Check if the market is open or closed, view pre-open data, and get time until the next market event."
                />
                <Feature
                  icon={BriefcaseIcon}
                  title="Portfolio Management"
                  color="green"
                  description="View your holdings, open positions, and P&L. Calculate position sizes based on your risk tolerance, account size, and stop-loss levels."
                />
                <Feature
                  icon={WalletIcon}
                  title="Order Execution"
                  color="amber"
                  description="Place buy/sell orders with human-in-the-loop approval. Supports market and limit orders. Use dry-run mode to simulate orders without placing them. After-market orders (AMO) are automatically detected."
                />
                <Feature
                  icon={ArrowTrendingUpIcon}
                  title="Watchlist"
                  color="cyan"
                  description="Maintain a personal watchlist of stocks you're tracking. Set price alerts and targets so you know when stocks reach your entry or exit levels."
                />
                <Feature
                  icon={CpuChipIcon}
                  title="Memory System"
                  color="indigo"
                  description="The AI remembers your risk tolerance, trading style, sector preferences, and past learnings. Over time, recommendations become more personalized to your approach."
                />
                <Feature
                  icon={LightBulbIcon}
                  title="Educational Explanations"
                  color="orange"
                  description="Every recommendation comes with clear reasoning explained in plain language. You'll learn technical analysis concepts naturally as you use the platform."
                />
                <Feature
                  icon={LinkIcon}
                  title="Web Search"
                  color="purple"
                  description="The AI can search the web for recent news, earnings reports, and market developments to complement its technical analysis with fundamental context."
                />
              </div>
            </Section>

            {/* Chat Interface */}
            <Section
              id="chat-interface"
              title="Chat Interface Guide"
              icon={ChatBubbleLeftRightIcon}
              expanded={expandedSection === 'chat-interface'}
              onToggle={() => toggleSection('chat-interface')}
            >
              <div className="space-y-4 text-zinc-700 dark:text-zinc-300">
                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">
                    Sidebar & Conversations
                  </h4>
                  <p className="text-sm">
                    The left sidebar shows all your conversations, grouped by date (Today, Yesterday,
                    Previous 7 Days, Older). You can <strong>search</strong> conversations by title,
                    <strong> pin</strong> important ones to the top, and <strong>delete</strong> ones you
                    no longer need. The sidebar can be collapsed to save screen space.
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">
                    Scratchpad
                  </h4>
                  <p className="text-sm">
                    The right panel is your scratchpad -- a quick notepad for jotting down trade ideas,
                    support/resistance levels, or anything you want to keep handy. It auto-saves as you type
                    and persists across sessions. On desktop, toggle it with the arrow icon on the right edge.
                    On mobile, tap the pencil icon in the top-right corner.
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">
                    File Uploads
                  </h4>
                  <p className="text-sm">
                    Click the paperclip icon to upload files. The AI can analyze chart screenshots,
                    read spreadsheets, and process documents. Great for "what do you see in this chart?" questions.
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2 flex items-center gap-2">
                    <MicrophoneIcon className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                    Voice Input
                  </h4>
                  <p className="text-sm">
                    Click the microphone button to speak your message instead of typing. The transcribed
                    text gets appended to your current input, so you can mix voice and typed input freely.
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">
                    Stopping & Interrupting
                  </h4>
                  <p className="text-sm">
                    If the AI is mid-response and you want it to stop, click the <strong>Stop</strong> button.
                    You'll see an amber banner indicating the response was interrupted. You can continue
                    the conversation normally afterwards.
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">
                    Keyboard Shortcuts
                  </h4>
                  <p className="text-sm">
                    <strong>Enter</strong> to send a message, <strong>Shift+Enter</strong> for a new line,
                    <strong> Esc</strong> to clear the input field. Hover over any message to reveal a
                    copy button for easy copying of analysis data.
                  </p>
                </div>
              </div>
            </Section>

            {/* Cockpit Dashboard */}
            <Section
              id="dashboard"
              title="Cockpit Dashboard"
              icon={ChartBarIcon}
              expanded={expandedSection === 'dashboard'}
              onToggle={() => toggleSection('dashboard')}
            >
              <div className="space-y-4 text-zinc-700 dark:text-zinc-300">
                <p className="text-sm">
                  Access the Cockpit from the dashboard icon in the sidebar's quick navigation bar.
                  It provides a real-time trading command center with these panels:
                </p>
                <ul className="text-sm space-y-2 ml-4 list-disc">
                  <li><strong>Market Pulse:</strong> NIFTY 50, SENSEX, and BANKNIFTY indices with live prices and change percentages</li>
                  <li><strong>Watchlist Panel:</strong> Your tracked stocks with live prices. Click any stock to see its chart</li>
                  <li><strong>Price Chart:</strong> Interactive candlestick charts with multiple timeframes (1D, 1W, 1M, etc.)</li>
                  <li><strong>Positions Table:</strong> Your open positions showing P&L, quantity, average price, and holding days</li>
                  <li><strong>Daily Scorecard:</strong> Summary of today's trading performance</li>
                  <li><strong>Cockpit Chat:</strong> A compact AI chat panel for quick market queries without leaving the dashboard</li>
                </ul>
                <div className="mt-4 p-4 rounded-lg bg-blue-50/50 dark:bg-blue-500/5 border border-blue-200/50 dark:border-blue-500/20">
                  <p className="text-sm text-blue-800 dark:text-blue-200">
                    <strong>Note:</strong> The dashboard requires your Upstox account to be connected for
                    live data. In paper trading mode, you'll see simulated data.
                  </p>
                </div>
              </div>
            </Section>

            {/* Notes */}
            <Section
              id="notes"
              title="Notes"
              icon={DocumentTextIcon}
              expanded={expandedSection === 'notes'}
              onToggle={() => toggleSection('notes')}
            >
              <div className="space-y-4 text-zinc-700 dark:text-zinc-300">
                <p className="text-sm">
                  Notes is a full-featured note-taking system accessible from the user menu in the sidebar footer.
                  Use it for trade journals, research notes, strategy documentation, or anything you want to keep organized.
                </p>
                <ul className="text-sm space-y-2 ml-4 list-disc">
                  <li><strong>Categories:</strong> Organize notes into Personal, Work, Ideas, or Reference categories</li>
                  <li><strong>Tags:</strong> Add custom tags to notes and filter by them</li>
                  <li><strong>Starring:</strong> Star important notes for quick access</li>
                  <li><strong>Search:</strong> Full-text search across all your notes</li>
                  <li><strong>Markdown:</strong> Write notes in Markdown with live preview for formatted content</li>
                  <li><strong>Wiki Links:</strong> Link between notes using <code className="bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded text-xs">[[Note Title]]</code> syntax to build a connected knowledge base</li>
                  <li><strong>Public Sharing:</strong> Publish any note as a shareable public link, optionally protected with a password and expiration date</li>
                </ul>
                <p className="text-sm mt-2">
                  Notes are different from the Scratchpad -- the scratchpad is a quick temporary notepad
                  always visible in the chat view, while Notes is a structured system for longer-term content.
                </p>
              </div>
            </Section>

            {/* Automations */}
            <Section
              id="automations"
              title="Automations"
              icon={BoltIcon}
              expanded={expandedSection === 'automations'}
              onToggle={() => toggleSection('automations')}
            >
              <div className="space-y-4 text-zinc-700 dark:text-zinc-300">
                <p className="text-sm">
                  Automations let you schedule AI-powered workflows that run automatically on a schedule.
                  Access them from the user menu in the sidebar footer.
                </p>
                <ul className="text-sm space-y-2 ml-4 list-disc">
                  <li><strong>Custom Workflows:</strong> Create your own automations with a custom prompt. For example,
                    "Scan my watchlist for stocks with RSI below 30 and send me a summary"</li>
                  <li><strong>Scheduling:</strong> Run workflows on a schedule (daily, weekly) or as a one-time scheduled task</li>
                  <li><strong>Run History:</strong> View past runs with their results, status, and duration</li>
                  <li><strong>Manual Trigger:</strong> Run any workflow on-demand with the play button</li>
                  <li><strong>Notifications:</strong> Get notified when workflows complete or fail</li>
                </ul>
              </div>
            </Section>

            {/* Settings */}
            <Section
              id="settings"
              title="Settings"
              icon={Cog6ToothIcon}
              expanded={expandedSection === 'settings'}
              onToggle={() => toggleSection('settings')}
            >
              <div className="space-y-4 text-zinc-700 dark:text-zinc-300">
                <p className="text-sm">
                  Access Settings from the user menu in the sidebar footer. Here's what you can configure:
                </p>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">Appearance</h4>
                  <p className="text-sm">
                    Choose between Light, Dark, or System theme. System mode automatically matches
                    your device's settings.
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">AI Model</h4>
                  <p className="text-sm">
                    Choose which AI model powers your conversations. Different models offer different
                    tradeoffs between speed and intelligence. Your preference is saved and applies to
                    all new conversations.
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">Trade Approval Mode</h4>
                  <p className="text-sm">
                    Toggle between <strong>Approval Mode</strong> (the AI asks before placing any order)
                    and <strong>Auto Mode</strong> (orders execute without confirmation). Approval Mode
                    is strongly recommended and enabled by default.
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">Upstox Connection</h4>
                  <p className="text-sm">
                    Connect your Upstox demat account to enable live market data and real trading.
                    Click "Connect Upstox" to authorize via Upstox's secure OAuth flow. You can
                    disconnect at any time. See the "Paper vs Live Trading" section below for details.
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">MCP Servers</h4>
                  <p className="text-sm">
                    Advanced feature: Connect external MCP (Model Context Protocol) servers to give the AI
                    access to additional tools and data sources. Access this from the MCP tab in Settings.
                  </p>
                </div>
              </div>
            </Section>

            {/* Memory Management */}
            <Section
              id="memory"
              title="Memory System"
              icon={CpuChipIcon}
              expanded={expandedSection === 'memory'}
              onToggle={() => toggleSection('memory')}
            >
              <div className="space-y-4 text-zinc-700 dark:text-zinc-300">
                <p className="text-sm">
                  The AI automatically builds a profile of your trading preferences over time. You can
                  view and manage your memories from the user menu in the sidebar footer. Memory categories include:
                </p>
                <ul className="text-sm space-y-2 ml-4 list-disc">
                  <li><strong>Risk Tolerance:</strong> Your preferred risk level per trade (e.g., max 2% of capital)</li>
                  <li><strong>Position Sizing:</strong> How you size your positions relative to your portfolio</li>
                  <li><strong>Trading Style:</strong> Swing trader, day trader, positional -- your approach</li>
                  <li><strong>Sector Preferences:</strong> Sectors you follow closely (IT, banking, pharma, etc.)</li>
                  <li><strong>Avoid List:</strong> Stocks or sectors you prefer not to trade</li>
                  <li><strong>Past Learnings:</strong> Lessons from previous trades</li>
                  <li><strong>Schedule:</strong> When you typically trade or check markets</li>
                  <li><strong>Experience Level:</strong> Beginner, intermediate, or advanced -- affects explanation depth</li>
                </ul>
                <div className="mt-4 p-4 rounded-lg bg-blue-50/50 dark:bg-blue-500/5 border border-blue-200/50 dark:border-blue-500/20">
                  <p className="text-sm text-blue-800 dark:text-blue-200">
                    <strong>Tip:</strong> Tell the AI about your preferences naturally in conversation --
                    "I'm a swing trader who focuses on IT stocks with max 2% risk per trade." It will
                    remember this for future conversations.
                  </p>
                </div>
              </div>
            </Section>

            {/* Trading Modes */}
            <Section
              id="trading-modes"
              title="Paper vs Live Trading"
              icon={WalletIcon}
              expanded={expandedSection === 'trading-modes'}
              onToggle={() => toggleSection('trading-modes')}
            >
              <div className="space-y-4 text-zinc-700 dark:text-zinc-300">
                <p className="text-sm">
                  Nifty Strategist supports two trading modes, toggled from the switch at the bottom of the sidebar:
                </p>
                <ul className="text-sm space-y-2 ml-4 list-disc">
                  <li><strong>Paper Trading (default):</strong> Practice with simulated orders. No real money involved.
                    Perfect for learning, testing strategies, or just exploring the platform.</li>
                  <li><strong>Live Trading:</strong> Real orders via your connected Upstox account.
                    Requires Upstox OAuth authorization in Settings.</li>
                </ul>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2 mt-4">
                    Connecting Upstox
                  </h4>
                  <p className="text-sm">
                    Go to <strong>Settings</strong> and click <strong>"Connect Upstox"</strong>. You'll be
                    redirected to Upstox's login page to authorize Nifty Strategist. After approval, you'll
                    be redirected back and can switch to live trading mode. Your Upstox tokens are encrypted
                    and stored securely.
                  </p>
                </div>

                <div className="mt-4 p-4 rounded-lg bg-amber-50/50 dark:bg-amber-500/5 border border-amber-200/50 dark:border-amber-500/20">
                  <p className="text-sm text-amber-800 dark:text-amber-200">
                    <strong>Important:</strong> The trading mode toggle is visible at the bottom of the sidebar
                    at all times. Always verify your mode before asking the AI to place orders. Switching to
                    live mode requires a confirmation step.
                  </p>
                </div>
              </div>
            </Section>

            {/* Example Prompts */}
            <Section
              id="example-prompts"
              title="Example Prompts"
              icon={PencilSquareIcon}
              expanded={expandedSection === 'example-prompts'}
              onToggle={() => toggleSection('example-prompts')}
            >
              <div className="space-y-4 text-zinc-700 dark:text-zinc-300">
                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">Market Overview</h4>
                  <ul className="text-sm space-y-1 ml-4 list-disc">
                    <li>"Is the market open right now?"</li>
                    <li>"Give me a quick market summary"</li>
                    <li>"What time does the market close today?"</li>
                  </ul>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">Stock Analysis</h4>
                  <ul className="text-sm space-y-1 ml-4 list-disc">
                    <li>"Analyze RELIANCE for a swing trade"</li>
                    <li>"What's the RSI and MACD for HDFC Bank?"</li>
                    <li>"Compare TCS, INFY, and WIPRO on technicals"</li>
                    <li>"Show me the daily chart for TATAMOTORS"</li>
                    <li>"Find Nifty 50 stocks with RSI below 30"</li>
                  </ul>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">Portfolio & Orders</h4>
                  <ul className="text-sm space-y-1 ml-4 list-disc">
                    <li>"Show my current portfolio"</li>
                    <li>"How are my positions doing today?"</li>
                    <li>"Buy 10 shares of RELIANCE at market price"</li>
                    <li>"Place a limit order for INFY at 1450"</li>
                    <li>"What's the right position size for HDFC if I want to risk 2%?"</li>
                  </ul>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">Watchlist</h4>
                  <ul className="text-sm space-y-1 ml-4 list-disc">
                    <li>"Add SBIN to my watchlist"</li>
                    <li>"Show my watchlist with current prices"</li>
                    <li>"Set a price alert for TATASTEEL at 130"</li>
                  </ul>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">Learning</h4>
                  <ul className="text-sm space-y-1 ml-4 list-disc">
                    <li>"What does RSI divergence mean?"</li>
                    <li>"Explain MACD crossover in simple terms"</li>
                    <li>"How should I set stop losses for swing trades?"</li>
                  </ul>
                </div>
              </div>
            </Section>

            {/* Best Practices */}
            <Section
              id="best-practices"
              title="Best Practices"
              icon={LightBulbIcon}
              expanded={expandedSection === 'best-practices'}
              onToggle={() => toggleSection('best-practices')}
            >
              <div className="space-y-4 text-zinc-700 dark:text-zinc-300">
                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">
                    Be specific with your requests
                  </h4>
                  <p className="text-sm">
                    Instead of "analyze stocks," try "analyze RELIANCE and HDFC for swing trades with a
                    5-day holding period." The more context you provide, the better the analysis.
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">
                    Start with paper trading
                  </h4>
                  <p className="text-sm">
                    New to the platform or new to trading? Paper trading mode lets you practice
                    everything without risking real money. Build confidence before switching to live.
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">
                    Share your preferences early
                  </h4>
                  <p className="text-sm">
                    Tell the AI about your trading style, risk tolerance, and favorite sectors in your
                    first few conversations. It will remember these and tailor future recommendations.
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">
                    Review orders carefully
                  </h4>
                  <p className="text-sm">
                    Always review the full order details (stock, quantity, price, order type) before
                    approving. Keep Approval Mode enabled in Settings for an extra safety net.
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">
                    Use the scratchpad and notes together
                  </h4>
                  <p className="text-sm">
                    Use the scratchpad for quick temporary notes during a trading session. Move important
                    findings to Notes for long-term reference -- trade journals, strategy documentation,
                    research notes.
                  </p>
                </div>
              </div>
            </Section>

            {/* Troubleshooting */}
            <Section
              id="troubleshooting"
              title="Troubleshooting"
              icon={ArrowPathIcon}
              expanded={expandedSection === 'troubleshooting'}
              onToggle={() => toggleSection('troubleshooting')}
            >
              <div className="space-y-4 text-zinc-700 dark:text-zinc-300">
                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">
                    Not getting a response
                  </h4>
                  <p className="text-sm">
                    Check your internet connection and refresh the page. If the problem persists, start a
                    new conversation. Your conversation history is always preserved.
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">
                    Response was interrupted
                  </h4>
                  <p className="text-sm">
                    If you or the system stopped a response mid-stream, you'll see an amber warning banner.
                    Just continue the conversation normally -- ask to retry or rephrase your request.
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">
                    "Market data unavailable" errors
                  </h4>
                  <p className="text-sm">
                    Live market data requires a connected Upstox account. Go to <strong>Settings</strong> and
                    connect Upstox. Note that Upstox tokens expire daily and may need re-authorization.
                    Historical data is available even outside market hours (9:15 AM - 3:30 PM IST).
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">
                    Orders rejected or failing
                  </h4>
                  <p className="text-sm">
                    Common reasons: insufficient funds, market is closed (try AMO orders after hours),
                    invalid quantity or price. The AI will explain the rejection reason. Make sure your
                    Upstox account has sufficient margin for the trade.
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">
                    Can't access a feature
                  </h4>
                  <p className="text-sm">
                    Features like Dashboard, Memory, and Settings require specific permissions assigned
                    to your account. Contact Pranav if you need access to additional features.
                  </p>
                </div>
              </div>
            </Section>

            {/* Safety & Security */}
            <Section
              id="safety"
              title="Safety & Security"
              icon={ShieldCheckIcon}
              expanded={expandedSection === 'safety'}
              onToggle={() => toggleSection('safety')}
            >
              <div className="space-y-4 text-zinc-700 dark:text-zinc-300">
                <ul className="text-sm space-y-2 ml-4 list-disc">
                  <li><strong>Human-in-the-loop:</strong> No trade is ever placed without your explicit approval (when Approval Mode is on)</li>
                  <li><strong>Paper trading default:</strong> New accounts start in paper trading mode -- no risk of accidental real trades</li>
                  <li><strong>Encrypted credentials:</strong> Your Upstox tokens are encrypted at rest using industry-standard encryption</li>
                  <li><strong>Session-based auth:</strong> JWT tokens expire after 7 days, requiring re-login</li>
                  <li><strong>Dry-run orders:</strong> You can ask the AI to simulate any order with <code className="bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded text-xs">--dry-run</code> before placing it for real</li>
                  <li><strong>No financial advice:</strong> Nifty Strategist provides technical analysis and trade execution tools. It is not a registered financial advisor. Always do your own research</li>
                </ul>
              </div>
            </Section>

            {/* Support */}
            <Section
              id="support"
              title="Need More Help?"
              icon={ClipboardDocumentListIcon}
              expanded={expandedSection === 'support'}
              onToggle={() => toggleSection('support')}
            >
              <div className="space-y-4 text-zinc-700 dark:text-zinc-300">
                <p className="text-sm">
                  If you're stuck or have questions not covered here:
                </p>
                <ul className="text-sm space-y-2 ml-4 list-disc">
                  <li>Ask the AI directly -- it knows its own capabilities and can help you navigate features</li>
                  <li>Contact Pranav for technical support or account issues</li>
                </ul>
                <div className="mt-6 p-4 rounded-lg bg-gradient-to-br from-blue-50/80 to-purple-50/80 dark:from-blue-500/5 dark:to-purple-500/5 border border-blue-200/50 dark:border-blue-500/20">
                  <p className="text-sm font-semibold text-blue-900 dark:text-blue-100 mb-2">
                    Remember: You're always in control
                  </p>
                  <p className="text-sm text-blue-800 dark:text-blue-200">
                    Nifty Strategist provides analysis and recommendations, but you always have the final say.
                    Review all trade details carefully before approving. Start with paper trading until you're
                    comfortable with the platform.
                  </p>
                </div>
              </div>
            </Section>
          </div>

          {/* Back to Home CTA */}
          <div className="mt-12 text-center">
            <button
              onClick={() => navigate('/')}
              className="inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-blue-600 via-purple-600 to-blue-600 px-8 py-4 text-base font-semibold text-white shadow-xl shadow-blue-600/25 transition-all duration-300 hover:scale-[1.02] hover:shadow-2xl"
            >
              <ArrowLeftIcon className="h-5 w-5" />
              <span>Return to Home</span>
            </button>
          </div>
        </main>

        <footer className="mt-20 text-center text-sm text-zinc-500 dark:text-zinc-500 pb-8">
          <p>Nifty Strategist v2.0 - AI Trading Assistant by Pranav</p>
        </footer>
      </div>
    </div>
  );
}

// Section component for collapsible sections
interface SectionProps {
  id: string;
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  expanded: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}

function Section({ id, title, icon: Icon, expanded, onToggle, children }: SectionProps) {
  return (
    <div className="overflow-hidden rounded-2xl border border-zinc-200/70 bg-white/80 backdrop-blur-md shadow-lg transition-all dark:border-white/10 dark:bg-white/5">
      <button
        onClick={onToggle}
        className="flex w-full items-center justify-between px-6 py-4 text-left transition-colors hover:bg-zinc-50/50 dark:hover:bg-white/5"
      >
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-500/10 text-blue-600 dark:bg-blue-500/15 dark:text-blue-300">
            <Icon className="h-5 w-5" />
          </div>
          <h3 className="text-lg font-semibold text-zinc-900 dark:text-white">
            {title}
          </h3>
        </div>
        <svg
          className={`h-5 w-5 text-zinc-500 transition-transform dark:text-zinc-400 ${expanded ? 'rotate-180' : ''
            }`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {expanded && (
        <div className="border-t border-zinc-200/70 px-6 py-6 dark:border-white/10">
          {children}
        </div>
      )}
    </div>
  );
}

// Feature component for feature cards
interface FeatureProps {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  description: string;
  color: 'blue' | 'purple' | 'red' | 'green' | 'amber' | 'indigo' | 'orange' | 'cyan';
}

function Feature({ icon: Icon, title, description, color }: FeatureProps) {
  const colorClasses = {
    blue: 'bg-blue-500/10 text-blue-600 dark:bg-blue-500/15 dark:text-blue-300',
    purple: 'bg-purple-500/10 text-purple-600 dark:bg-purple-500/15 dark:text-purple-300',
    red: 'bg-red-500/10 text-red-600 dark:bg-red-500/15 dark:text-red-300',
    green: 'bg-emerald-500/10 text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-300',
    amber: 'bg-amber-500/10 text-amber-600 dark:bg-amber-500/15 dark:text-amber-300',
    indigo: 'bg-indigo-500/10 text-indigo-600 dark:bg-indigo-500/15 dark:text-indigo-300',
    orange: 'bg-orange-500/10 text-orange-600 dark:bg-orange-500/15 dark:text-orange-300',
    cyan: 'bg-cyan-500/10 text-cyan-600 dark:bg-cyan-500/15 dark:text-cyan-300',
  };

  return (
    <div className="flex items-start gap-4">
      <div className={`flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl ${colorClasses[color]}`}>
        <Icon className="h-5 w-5" />
      </div>
      <div>
        <h4 className="font-semibold text-zinc-900 dark:text-white">{title}</h4>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">{description}</p>
      </div>
    </div>
  );
}
