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
  CommandLineIcon,
  ClipboardDocumentListIcon,
  ArrowPathIcon,
  MicrophoneIcon,
  ArrowTrendingUpIcon,
  WalletIcon,
  MagnifyingGlassIcon,
  BriefcaseIcon,
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
                  Nifty Strategist is an AI-powered trading assistant for the Indian stock market (NSE/BSE).
                  It can analyze stocks, track your portfolio, suggest trades based on technical analysis,
                  and execute orders with your approval -- all through natural language conversations.
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
                    Click the "New Task" button in the sidebar or the input bar on the home page
                    to start a new conversation. Each conversation gets a unique thread that maintains context.
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">
                    2. Ask in natural language
                  </h4>
                  <p className="text-sm mb-2">
                    Nifty Strategist understands natural language. No need for specific commands or syntax. Examples:
                  </p>
                  <ul className="text-sm space-y-1 ml-4 list-disc">
                    <li>"Analyze RELIANCE for swing trading"</li>
                    <li>"Compare INFY and TCS technicals"</li>
                    <li>"Show my portfolio and current positions"</li>
                    <li>"Find Nifty 50 stocks with bullish RSI divergence"</li>
                  </ul>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">
                    3. Watch real-time progress
                  </h4>
                  <p className="text-sm">
                    Nifty Strategist shows you what it's doing in real-time using the TODO panel above the chat input.
                    You can see tasks as they move from pending to in progress to completed.
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">
                    4. Approve trades before execution
                  </h4>
                  <p className="text-sm">
                    Before placing any order, Nifty Strategist will ask for your explicit approval.
                    You always have the final say on trade execution.
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
                  description="Technical analysis with RSI, MACD, SMA, EMA, and ATR indicators. Analyze individual stocks or compare multiple stocks side by side."
                />
                <Feature
                  icon={ChartBarIcon}
                  title="Market Data"
                  color="purple"
                  description="Live quotes and historical OHLCV data for Nifty 50 stocks via Upstox API. Check market status and pre-open data."
                />
                <Feature
                  icon={BriefcaseIcon}
                  title="Portfolio Management"
                  color="green"
                  description="View your holdings, open positions, and P&L. Calculate position sizes based on your risk tolerance and account size."
                />
                <Feature
                  icon={WalletIcon}
                  title="Order Execution"
                  color="amber"
                  description="Place buy/sell orders with human-in-the-loop approval. Supports market and limit orders with dry-run mode for testing."
                />
                <Feature
                  icon={ArrowTrendingUpIcon}
                  title="Watchlist"
                  color="cyan"
                  description="Maintain a personal watchlist with price target alerts. Get notified when stocks hit your entry or exit levels."
                />
                <Feature
                  icon={CpuChipIcon}
                  title="Memory System"
                  color="indigo"
                  description="Nifty Strategist remembers your risk tolerance, trading style, sector preferences, and past learnings to provide personalized recommendations."
                />
                <Feature
                  icon={LightBulbIcon}
                  title="Educational Focus"
                  color="orange"
                  description="Every recommendation comes with reasoning explained in beginner-friendly language. Learn trading concepts as you go."
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
                    Scratchpad
                  </h4>
                  <p className="text-sm">
                    Click the notepad icon in the sidebar to open the scratchpad. Use it for tracking trade ideas,
                    noting support/resistance levels, or storing important information. It auto-saves as you type.
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">
                    File Uploads
                  </h4>
                  <p className="text-sm">
                    Click the paperclip icon to upload files (images, spreadsheets, documents). Nifty Strategist can
                    analyze chart screenshots, extract data from spreadsheets, and process document content.
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">
                    Message Formatting
                  </h4>
                  <p className="text-sm">
                    Nifty Strategist renders Markdown formatting, code syntax highlighting, and structured data tables.
                    Responses stream in real-time so you see progress immediately.
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">
                    Conversation History
                  </h4>
                  <p className="text-sm">
                    All conversations are saved in the sidebar. Click on any conversation to resume it.
                    The full context is preserved so Nifty Strategist remembers your previous interactions.
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2 flex items-center gap-2">
                    <MicrophoneIcon className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                    Voice Input
                  </h4>
                  <p className="text-sm">
                    Click the microphone button in the chat input to use voice transcription. Speak your message
                    and it will be automatically transcribed. The transcribed text is appended
                    to your current message, allowing you to mix voice and typed input.
                  </p>
                </div>
              </div>
            </Section>

            {/* Dashboard */}
            <Section
              id="dashboard"
              title="Cockpit Dashboard"
              icon={ChartBarIcon}
              expanded={expandedSection === 'dashboard'}
              onToggle={() => toggleSection('dashboard')}
            >
              <div className="space-y-4 text-zinc-700 dark:text-zinc-300">
                <p className="text-sm">
                  The Cockpit Dashboard provides a real-time trading command center:
                </p>
                <ul className="text-sm space-y-2 ml-4 list-disc">
                  <li><strong>Market Pulse:</strong> NIFTY 50, SENSEX, BANKNIFTY indices with real-time prices</li>
                  <li><strong>Watchlist Panel:</strong> Track your favorite stocks with live prices and alerts</li>
                  <li><strong>Price Chart:</strong> Interactive candlestick charts with multiple timeframes</li>
                  <li><strong>Positions Table:</strong> Open positions with P&L, quantity, and hold days</li>
                  <li><strong>Daily Scorecard:</strong> Day's trading performance summary</li>
                  <li><strong>Cockpit Chat:</strong> Integrated AI chat for quick market queries</li>
                </ul>
              </div>
            </Section>

            {/* Memory Management */}
            <Section
              id="memory"
              title="Memory Management"
              icon={CpuChipIcon}
              expanded={expandedSection === 'memory'}
              onToggle={() => toggleSection('memory')}
            >
              <div className="space-y-4 text-zinc-700 dark:text-zinc-300">
                <p className="text-sm">
                  Nifty Strategist's memory system stores and recalls important information automatically:
                </p>
                <ul className="text-sm space-y-2 ml-4 list-disc">
                  <li><strong>Risk Tolerance:</strong> Your preferred risk level per trade (e.g., max 2% risk)</li>
                  <li><strong>Trading Style:</strong> Swing trader, day trader, positional -- your approach</li>
                  <li><strong>Sector Preferences:</strong> Favorite sectors like IT, banking, pharma</li>
                  <li><strong>Avoid List:</strong> Stocks you prefer not to trade</li>
                  <li><strong>Past Learnings:</strong> Lessons from previous trades for smarter future decisions</li>
                </ul>
                <div className="mt-4 p-4 rounded-lg bg-blue-50/50 dark:bg-blue-500/5 border border-blue-200/50 dark:border-blue-500/20">
                  <p className="text-sm text-blue-800 dark:text-blue-200">
                    <strong>Pro Tip:</strong> Extract memories after important conversations about your trading preferences
                    or lessons learned. This helps Nifty Strategist provide more personalized recommendations.
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
                  Nifty Strategist supports both paper trading and live trading modes:
                </p>
                <ul className="text-sm space-y-2 ml-4 list-disc">
                  <li><strong>Paper Trading:</strong> Practice with virtual funds. No real money at risk. Great for learning and testing strategies.</li>
                  <li><strong>Live Trading:</strong> Real orders via Upstox. Requires connecting your Upstox account in Settings.</li>
                </ul>
                <div className="mt-4 p-4 rounded-lg bg-amber-50/50 dark:bg-amber-500/5 border border-amber-200/50 dark:border-amber-500/20">
                  <p className="text-sm text-amber-800 dark:text-amber-200">
                    <strong>Important:</strong> You can toggle between paper and live trading using the switch in the sidebar footer.
                    Always verify your trading mode before placing orders.
                  </p>
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
                    Be specific with requests
                  </h4>
                  <p className="text-sm">
                    Instead of "analyze stocks," try "analyze RELIANCE and HDFC for swing trades with a 5-day holding period."
                    More context helps Nifty Strategist provide better analysis.
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">
                    Start with paper trading
                  </h4>
                  <p className="text-sm">
                    If you're new to trading, start with paper trading mode to practice without risking real money.
                    Build confidence with the system before switching to live trading.
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">
                    Extract memories regularly
                  </h4>
                  <p className="text-sm">
                    After conversations about your trading preferences, risk tolerance, or lessons learned,
                    use "Extract Memories" to save that knowledge for future conversations.
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">
                    Review before executing trades
                  </h4>
                  <p className="text-sm">
                    Always review the trade details (stock, quantity, price, order type) before approving.
                    You can stop execution with the Stop button if needed.
                  </p>
                </div>
              </div>
            </Section>

            {/* Tips & Tricks */}
            <Section
              id="tips-tricks"
              title="Tips & Tricks"
              icon={CommandLineIcon}
              expanded={expandedSection === 'tips-tricks'}
              onToggle={() => toggleSection('tips-tricks')}
            >
              <div className="space-y-4 text-zinc-700 dark:text-zinc-300">
                <ul className="text-sm space-y-3 ml-4 list-disc">
                  <li>
                    <strong>Quick navigation:</strong> Use the sidebar to switch between conversations, dashboard,
                    and other sections without losing context.
                  </li>
                  <li>
                    <strong>Voice input:</strong> Click the microphone button to dictate messages instead of typing.
                    Great for longer market analysis requests.
                  </li>
                  <li>
                    <strong>Real-time streaming:</strong> Responses stream in real-time. You don't need to wait for
                    the full response before reading the analysis.
                  </li>
                  <li>
                    <strong>Conversation context:</strong> Nifty Strategist remembers the entire conversation thread.
                    You can reference previous analyses naturally.
                  </li>
                  <li>
                    <strong>Copy responses:</strong> Hover over messages to see a copy button for
                    easy copying of analysis data or trade details.
                  </li>
                  <li>
                    <strong>Keyboard shortcuts:</strong> Enter to send, Shift+Enter for new line, Esc to clear input.
                  </li>
                </ul>
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
                    Check your internet connection and refresh the page. If the problem persists, start a new
                    conversation. Your conversation history is preserved.
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">
                    Response was interrupted
                  </h4>
                  <p className="text-sm">
                    If you stopped a response mid-stream, you'll see an amber warning banner. You can continue
                    the conversation normally -- just ask to retry or rephrase your request.
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">
                    Market data unavailable
                  </h4>
                  <p className="text-sm">
                    Market data requires a valid Upstox connection. Check that your Upstox account is connected
                    in Settings. Data is available during market hours (9:15 AM - 3:30 PM IST) and after hours for historical data.
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">
                    Can't access a feature
                  </h4>
                  <p className="text-sm">
                    Some features require specific permissions. Contact Pranav if you need access to
                    additional features.
                  </p>
                </div>
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
                  If you're still stuck or have questions not covered here:
                </p>
                <ul className="text-sm space-y-2 ml-4 list-disc">
                  <li>Ask Nifty Strategist directly -- it can answer questions about its own capabilities</li>
                  <li>Contact Pranav for technical support</li>
                </ul>
                <div className="mt-6 p-4 rounded-lg bg-gradient-to-br from-blue-50/80 to-purple-50/80 dark:from-blue-500/5 dark:to-purple-500/5 border border-blue-200/50 dark:border-blue-500/20">
                  <p className="text-sm font-semibold text-blue-900 dark:text-blue-100 mb-2">
                    Remember: Always review trades before execution
                  </p>
                  <p className="text-sm text-blue-800 dark:text-blue-200">
                    Nifty Strategist provides analysis and recommendations, but you always have the final say.
                    Review all trade details carefully before approving execution.
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
