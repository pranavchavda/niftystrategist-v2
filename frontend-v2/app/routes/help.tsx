import { useNavigate } from 'react-router';
import {
  ChatBubbleLeftRightIcon,
  ChartBarIcon,
  CpuChipIcon,
  TagIcon,
  Cog6ToothIcon,
  DocumentTextIcon,
  SparklesIcon,
  ShoppingCartIcon,
  ArrowLeftIcon,
  BookOpenIcon,
  RocketLaunchIcon,
  LightBulbIcon,
  CommandLineIcon,
  ClipboardDocumentListIcon,
  ChatBubbleBottomCenterTextIcon,
  ArrowPathIcon,
  MicrophoneIcon,
  PencilSquareIcon,
} from '@heroicons/react/24/outline';
import { useState } from 'react';

const logo = new URL('../assets/eblogo.webp', import.meta.url).href;

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
            <img
              src={logo}
              alt="EspressoBot"
              className="h-24 w-24 object-contain"
              draggable="false"
            />
            <div>
              <h1 className="text-3xl font-bold text-zinc-900 dark:text-white">
                Help & Documentation
              </h1>
              <p className="text-sm text-zinc-600 dark:text-zinc-400">
                Everything you need to know about EspressoBot
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
                  Welcome to EspressoBot!
                </h2>
                <p className="mt-2 text-zinc-600 dark:text-zinc-400">
                  EspressoBot is an AI-powered assistant designed specifically for iDrinkCoffee.com operations.
                  It can manage Shopify products, analyze marketing data, handle Google Workspace tasks, research
                  competitors, and monitor MAP compliance—all through natural language conversations.
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
                    Click "Work with EspressoBot" on the home page or the "New Task" button in the sidebar
                    to start a new conversation. Each conversation gets a unique thread ID that maintains context.
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">
                    2. Ask in natural language
                  </h4>
                  <p className="text-sm mb-2">
                    EspressoBot understands natural language. No need for specific commands or syntax. Examples:
                  </p>
                  <ul className="text-sm space-y-1 ml-4 list-disc">
                    <li>"Search for Breville espresso machines under $500"</li>
                    <li>"What were our Google Ads conversions last week?"</li>
                    <li>"Draft an email to suppliers about new product arrivals"</li>
                    <li>"Show me MAP violations for De'Longhi products"</li>
                  </ul>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">
                    3. Watch real-time progress
                  </h4>
                  <p className="text-sm">
                    EspressoBot shows you what it's doing in real-time using the TODO panel above the chat input.
                    You can see tasks as they move from pending → in progress → completed.
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">
                    4. Stop anytime
                  </h4>
                  <p className="text-sm">
                    Click the Stop button if you need to interrupt EspressoBot. It will gracefully pause
                    and save its progress. You can continue the conversation afterward.
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
                  icon={ShoppingCartIcon}
                  title="Shopify Management"
                  color="blue"
                  description="GraphQL-first approach with 48 validated operations. Create, update, and search products. Manage inventory, pricing, images, metafields, and variants through natural language."
                />
                <Feature
                  icon={ChartBarIcon}
                  title="Marketing Analytics"
                  color="purple"
                  description="Query Google Analytics 4 for website traffic, conversions, and user behavior. Analyze Google Ads campaigns, ROAS, and keyword performance."
                />
                <Feature
                  icon={ChatBubbleBottomCenterTextIcon}
                  title="Google Workspace"
                  color="red"
                  description="Read and send emails via Gmail. Manage calendar events and meetings. Access Google Drive files. Create and manage Google Tasks."
                />
                <Feature
                  icon={TagIcon}
                  title="Price Monitor"
                  color="green"
                  description="Automatic MAP (Minimum Advertised Price) compliance monitoring. AI-powered competitor product matching. Severity-based alert system."
                />
                <Feature
                  icon={DocumentTextIcon}
                  title="Content CMS"
                  color="amber"
                  description="Edit category landing pages, hero banners, and metaobjects. Manage FAQ sections, comparison tables, and rich content blocks."
                />
                <Feature
                  icon={CpuChipIcon}
                  title="Memory System"
                  color="indigo"
                  description="EspressoBot remembers product specifications, user preferences, and operational knowledge. Semantic search with 3072-dimension embeddings."
                />
                <Feature
                  icon={CommandLineIcon}
                  title="GraphQL Operations"
                  color="cyan"
                  description="48 validated GraphQL operations for all Shopify Admin API tasks. EspressoBot reads documentation, composes queries, and executes them directly—no specialized tools needed."
                />
                <Feature
                  icon={LightBulbIcon}
                  title="Web Research"
                  color="orange"
                  description="Powered by Perplexity AI for real-time competitor research, market trends, and product information from across the web."
                />
                <Feature
                  icon={PencilSquareIcon}
                  title="Notes System (Second Brain)"
                  color="green"
                  description="Personal knowledge management with Obsidian vault sync, semantic search, tags and categories, and AI-powered autocomplete. Fast loading with intelligent content previews."
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
                    Click the notepad icon in the sidebar to open the scratchpad. Use it for temporary notes,
                    tracking context across conversations, or storing important information. It auto-saves as you type.
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">
                    File Uploads
                  </h4>
                  <p className="text-sm">
                    Click the paperclip icon to upload files (images, spreadsheets, documents). EspressoBot can
                    analyze images, extract data from spreadsheets, and process document content.
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">
                    Message Formatting
                  </h4>
                  <p className="text-sm">
                    EspressoBot renders Markdown formatting, code syntax highlighting, and structured data tables.
                    Responses stream in real-time so you see progress immediately.
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">
                    Conversation History
                  </h4>
                  <p className="text-sm">
                    All conversations are saved in the sidebar. Click on any conversation to resume it.
                    The full context is preserved so EspressoBot remembers your previous interactions.
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2 flex items-center gap-2">
                    <MicrophoneIcon className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                    Voice Input
                  </h4>
                  <p className="text-sm">
                    Click the microphone button in the chat input to use voice transcription. Speak your message
                    and it will be automatically transcribed using OpenAI Whisper. The transcribed text is appended
                    to your current message, allowing you to mix voice and typed input.
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2 flex items-center gap-2">
                    <SparklesIcon className="h-5 w-5 text-purple-600 dark:text-purple-400" />
                    AI Autocomplete
                  </h4>
                  <p className="text-sm mb-2">
                    As you type in chat, notes, or documentation, EspressoBot provides intelligent autocomplete
                    suggestions shown as ghost text at your cursor. Press <kbd className="px-1.5 py-0.5 text-xs font-mono bg-zinc-100 dark:bg-zinc-800 rounded border border-zinc-300 dark:border-zinc-700">Tab</kbd> to
                    accept the suggestion.
                  </p>
                  <ul className="text-sm space-y-1 ml-4 list-disc">
                    <li><strong>Context-aware in chat:</strong> Uses your last 3 messages for relevant completions</li>
                    <li><strong>Smart in notes:</strong> Suggests natural continuations, markdown formatting, and emojis</li>
                    <li><strong>Technical in docs:</strong> Maintains documentation style with precise terminology</li>
                  </ul>
                </div>
              </div>
            </Section>

            {/* Dashboard */}
            <Section
              id="dashboard"
              title="Dashboard"
              icon={ChartBarIcon}
              expanded={expandedSection === 'dashboard'}
              onToggle={() => toggleSection('dashboard')}
            >
              <div className="space-y-4 text-zinc-700 dark:text-zinc-300">
                <p className="text-sm">
                  The Dashboard provides real-time analytics and metrics for your store operations:
                </p>
                <ul className="text-sm space-y-2 ml-4 list-disc">
                  <li><strong>Sales Overview:</strong> Daily, weekly, and monthly revenue trends</li>
                  <li><strong>Google Ads Performance:</strong> Campaign ROAS, conversions, and spend</li>
                  <li><strong>Website Traffic:</strong> Visitor counts, page views, and engagement metrics from GA4</li>
                  <li><strong>MAP Compliance:</strong> Current compliance rate and recent violations</li>
                  <li><strong>Quick Actions:</strong> One-click access to common tasks</li>
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
                  EspressoBot's memory system stores and recalls important information automatically:
                </p>
                <ul className="text-sm space-y-2 ml-4 list-disc">
                  <li><strong>Automatic Extraction:</strong> Click "Extract Memories" to save key information from conversations</li>
                  <li><strong>Semantic Search:</strong> Memories are embedded with 3072-dimension vectors for intelligent retrieval</li>
                  <li><strong>Context Injection:</strong> Relevant memories are automatically included in new conversations</li>
                  <li><strong>Organization:</strong> Browse, search, and delete memories from the Memory Management page</li>
                </ul>
                <div className="mt-4 p-4 rounded-lg bg-blue-50/50 dark:bg-blue-500/5 border border-blue-200/50 dark:border-blue-500/20">
                  <p className="text-sm text-blue-800 dark:text-blue-200">
                    <strong>Pro Tip:</strong> Extract memories after important conversations about product specifications,
                    customer preferences, or operational procedures. This helps EspressoBot provide more accurate assistance in the future.
                  </p>
                </div>
              </div>
            </Section>

            {/* Price Monitor */}
            <Section
              id="price-monitor"
              title="Price Monitor"
              icon={TagIcon}
              expanded={expandedSection === 'price-monitor'}
              onToggle={() => toggleSection('price-monitor')}
            >
              <div className="space-y-4 text-zinc-700 dark:text-zinc-300">
                <p className="text-sm">
                  The Price Monitor automatically tracks MAP (Minimum Advertised Price) compliance:
                </p>
                <ul className="text-sm space-y-2 ml-4 list-disc">
                  <li><strong>Automatic Sync:</strong> Syncs Shopify products and scrapes competitor prices</li>
                  <li><strong>AI Matching:</strong> Uses embeddings to match products across different sites</li>
                  <li><strong>Severity Levels:</strong> Violations categorized as low, medium, high, or critical</li>
                  <li><strong>Detailed Reports:</strong> View violations by competitor, brand, or severity</li>
                  <li><strong>Historical Tracking:</strong> See violation trends over time</li>
                </ul>
              </div>
            </Section>

            {/* Content CMS */}
            <Section
              id="cms"
              title="Content Management System"
              icon={DocumentTextIcon}
              expanded={expandedSection === 'cms'}
              onToggle={() => toggleSection('cms')}
            >
              <div className="space-y-4 text-zinc-700 dark:text-zinc-300">
                <p className="text-sm">
                  The Content Management System provides a user-friendly interface for editing Shopify metaobjects:
                </p>
                <ul className="text-sm space-y-2 ml-4 list-disc">
                  <li><strong>Category Landing Pages:</strong> Edit hero images, descriptions, and content blocks</li>
                  <li><strong>FAQ Sections:</strong> Manage individual FAQ items within sections</li>
                  <li><strong>Comparison Tables:</strong> Edit product comparison features and values</li>
                  <li><strong>Hero Image Generation:</strong> AI-powered image generation with Gemini 3 Pro (2K output)</li>
                  <li><strong>Rich Content Blocks:</strong> Add images, text, and structured content</li>
                </ul>
                <div className="mt-4 p-4 rounded-lg bg-amber-50/50 dark:bg-amber-500/5 border border-amber-200/50 dark:border-amber-500/20">
                  <p className="text-sm text-amber-800 dark:text-amber-200">
                    <strong>Note:</strong> Changes made in the CMS are saved directly to Shopify.
                    Always preview your changes before publishing to ensure they look correct on the live site.
                  </p>
                </div>
              </div>
            </Section>

            {/* Notes System */}
            <Section
              id="notes"
              title="Notes System"
              icon={PencilSquareIcon}
              expanded={expandedSection === 'notes'}
              onToggle={() => toggleSection('notes')}
            >
              <div className="space-y-4 text-zinc-700 dark:text-zinc-300">
                <p className="text-sm">
                  The Notes System provides a powerful personal knowledge management solution with AI-powered features:
                </p>
                <ul className="text-sm space-y-2 ml-4 list-disc">
                  <li><strong>Create & Edit Notes:</strong> Write notes with a rich markdown editor and organize them by tags and categories</li>
                  <li><strong>Obsidian Vault Sync:</strong> Seamlessly integrate with your Obsidian vault for cross-platform access</li>
                  <li><strong>Semantic Search:</strong> Find notes instantly using AI-powered semantic search that understands meaning, not just keywords</li>
                  <li><strong>AI Autocomplete:</strong> Get intelligent writing suggestions as you type with Tab-to-accept ghost text</li>
                  <li><strong>Fast Loading:</strong> Optimized performance with paginated loading and intelligent content previews</li>
                  <li><strong>Tags & Categories:</strong> Organize notes with flexible tagging and categorization (personal, work, research, ideas)</li>
                </ul>
                <div className="mt-4 p-4 rounded-lg bg-emerald-50/50 dark:bg-emerald-500/5 border border-emerald-200/50 dark:border-emerald-500/20">
                  <p className="text-sm text-emerald-800 dark:text-emerald-200">
                    <strong>Pro Tip:</strong> Use the notes system as your second brain. Capture ideas, track research,
                    and build a knowledge base that EspressoBot can reference in conversations. The semantic search makes
                    it easy to find exactly what you need when you need it.
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
                    Instead of "check sales," try "show me sales for the last 7 days compared to the previous week."
                    More context helps EspressoBot provide better results.
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">
                    Multi-step workflows
                  </h4>
                  <p className="text-sm">
                    You can chain multiple tasks: "Create a new product for Breville Barista Express, set price to $699,
                    upload these images, then add it to the Espresso Machines collection."
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">
                    Extract memories regularly
                  </h4>
                  <p className="text-sm">
                    After conversations with important product specs, customer preferences, or operational details,
                    use "Extract Memories" to save that knowledge for future conversations.
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">
                    Use the scratchpad
                  </h4>
                  <p className="text-sm">
                    Keep important context, tracking numbers, or notes in the scratchpad so you can reference them
                    across multiple conversations without repeating yourself.
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">
                    Review before executing
                  </h4>
                  <p className="text-sm">
                    For important operations (pricing updates, product deletions, bulk changes), review what
                    EspressoBot plans to do. You can stop execution with the Stop button if needed.
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
                    <strong>Tab for autocomplete:</strong> Press Tab to accept AI-powered autocomplete suggestions in chat,
                    notes, and documentation. Save time with context-aware ghost text completions.
                  </li>
                  <li>
                    <strong>Voice input:</strong> Click the microphone button to dictate messages instead of typing.
                    Great for longer messages or when multitasking.
                  </li>
                  <li>
                    <strong>Notes as second brain:</strong> Use the Notes System to build a personal knowledge base.
                    Semantic search makes it easy to find information later, and autocomplete helps you write faster.
                  </li>
                  <li>
                    <strong>File context:</strong> Upload product spreadsheets or competitor pricing sheets—EspressoBot
                    can extract data and use it in operations.
                  </li>
                  <li>
                    <strong>Real-time streaming:</strong> Responses stream in real-time. You don't need to wait for
                    the full response before taking action.
                  </li>
                  <li>
                    <strong>Conversation context:</strong> EspressoBot remembers the entire conversation thread.
                    You can reference previous messages naturally.
                  </li>
                  <li>
                    <strong>Markdown support:</strong> Use markdown formatting in your messages (bold, italic, lists)
                    for better readability.
                  </li>
                  <li>
                    <strong>Copy responses:</strong> Hover over EspressoBot's messages to see a copy button for
                    easy copying of code, data, or text.
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
                    EspressoBot isn't responding
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
                    the conversation normally—just ask EspressoBot to retry or rephrase your request.
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">
                    Operation failed
                  </h4>
                  <p className="text-sm">
                    EspressoBot will show error details in the chat. Common issues include missing product IDs,
                    invalid data formats, or API rate limits. Read the error message and adjust your request.
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">
                    Can't access a feature
                  </h4>
                  <p className="text-sm">
                    Some features require specific permissions. If you don't see a section (Dashboard, CMS, Price Monitor),
                    contact an administrator to grant access to your role.
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold text-zinc-900 dark:text-white mb-2">
                    Google Workspace/Analytics not working
                  </h4>
                  <p className="text-sm">
                    These features require OAuth authentication. Go to Settings and ensure your Google account is
                    connected. You may need to re-authorize access if your token expired.
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
                  <li>Ask EspressoBot directly—it can answer questions about its own capabilities</li>
                  <li>Check the Admin Documentation section (if you have access) for technical details</li>
                  <li>Contact Pranav</li>
                  <li>Report bugs or issues to Pranav via Flock</li>
                </ul>
                <div className="mt-6 p-4 rounded-lg bg-gradient-to-br from-blue-50/80 to-purple-50/80 dark:from-blue-500/5 dark:to-purple-500/5 border border-blue-200/50 dark:border-blue-500/20">
                  <p className="text-sm font-semibold text-blue-900 dark:text-blue-100 mb-2">
                    Remember: EspressoBot is autonomous and powerful
                  </p>
                  <p className="text-sm text-blue-800 dark:text-blue-200">
                    Always review important operations before execution. EspressoBot has direct access to Shopify,
                    Google Ads, and other critical systems. Use with care and attention.
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
          <p>EspressoBot v0.4 - Created with ☕ for iDrinkCoffee.com by Pranav and Claude Code</p>
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
