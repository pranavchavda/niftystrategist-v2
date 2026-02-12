import React, { useState } from 'react';
import {
  MagnifyingGlassIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  BookOpenIcon,
  PhotoIcon,
  TagIcon,
  Cog6ToothIcon,
  SparklesIcon,
  QuestionMarkCircleIcon,
} from '@heroicons/react/20/solid';

export default function HelpPage() {
  const [searchTerm, setSearchTerm] = useState('');
  const [expandedSections, setExpandedSections] = useState({
    'getting-started': true, // Expand first section by default
  });

  const toggleSection = (sectionId) => {
    setExpandedSections((prev) => ({
      ...prev,
      [sectionId]: !prev[sectionId],
    }));
  };

  const expandAll = () => {
    const allSections = {};
    helpSections.forEach((section) => {
      allSections[section.id] = true;
    });
    setExpandedSections(allSections);
  };

  const collapseAll = () => {
    setExpandedSections({});
  };

  // Filter sections based on search
  const filterContent = (content) => {
    if (!searchTerm) return content;
    const term = searchTerm.toLowerCase();
    return content.filter(
      (item) =>
        item.title.toLowerCase().includes(term) ||
        item.content.toLowerCase().includes(term)
    );
  };

  const helpSections = [
    {
      id: 'getting-started',
      title: 'Getting Started',
      icon: BookOpenIcon,
      items: [
        {
          title: 'What is the CMS?',
          content: `The Content Management System (CMS) is a custom-built interface for managing content on iDrinkCoffee.com. Instead of working directly in Shopify's admin (which can be confusing), this CMS provides a clean, intuitive interface designed specifically for our needs.

This help guide covers Category Landing Pages. Additional content types (Home Banners, Header Banner, Menus, and more) have their own interfaces in the CMS.`,
        },
        {
          title: 'Accessing the CMS',
          content: `1. Navigate to Nifty Strategist
2. Log in with your Google account
3. From the landing page, click "CMS" or navigate to /cms
4. Select the "Category Pages" tab`,
        },
        {
          title: 'What You\'ll Be Creating',
          content: `Category landing pages are the main pages for product categories like "Espresso Machines", "Coffee Grinders", "Single Dose Grinders", and "La Marzocco Machines". Each page includes a hero section with image and text, featured products, sorting options, educational content, FAQs, comparison tables, and SEO metadata.

Note: This guide focuses on Category Landing Pages. Other CMS content types (Home Banners, Header Banner, Menus) are managed through their respective sections in the CMS sidebar.`,
        },
      ],
    },
    {
      id: 'page-structure',
      title: 'Page Structure',
      icon: Cog6ToothIcon,
      items: [
        {
          title: 'Hero Section',
          content: `The first thing visitors see - includes a large background image (1920×600px), hero title (big headline), and hero description (2-3 sentence intro). Example: "Precision Grinding, Zero Waste" with "Discover the perfect single dose grinder for your workflow."`,
        },
        {
          title: 'Featured Products',
          content: `A curated list of 6-10 products showcased prominently at the top. You can add products by searching, reorder them by dragging, and update them seasonally. Best practice: feature top sellers and mix price points.`,
        },
        {
          title: 'FAQ Section',
          content: `A single FAQ section containing multiple Q&A pairs. Click "Edit Items" to manage individual questions and answers. Aim for 5-10 FAQs per section, starting with the most common questions.`,
        },
        {
          title: 'Comparison Table',
          content: `A table comparing products across multiple features. Click "Edit Items" to manage features. Each feature has a name (e.g., "Portafilter Size") and description. Focus on 5-10 key differentiators.`,
        },
      ],
    },
    {
      id: 'hero-images',
      title: 'Hero Image Management',
      icon: PhotoIcon,
      items: [
        {
          title: 'AI Generation (Recommended)',
          content: `The CMS can automatically generate professional hero images using GPT-5-image-mini or Gemini. Steps:
1. Write your hero title and description first (these guide the AI)
2. Click "Regenerate with AI"
3. Choose a model (GPT-5-image-mini is faster, Gemini is more artistic)
4. Wait 15-45 seconds
5. Image appears immediately - regenerate if you want a different variation

The AI uses your hero text to create contextually relevant images.`,
        },
        {
          title: 'Manual Upload',
          content: `Upload your own images when you have specific product photos or custom photography. Supported formats: JPEG, PNG, WebP. Recommended size: 1920×600px (16:5 ratio). Max file size: 10MB. The system automatically optimizes images.`,
        },
        {
          title: 'Browse CDN Images',
          content: `Reuse images from other category pages or previously uploaded images. Click "Browse CDN Images" to see thumbnails of all Shopify images. This prevents duplicate uploads and maintains consistency across pages.`,
        },
        {
          title: 'Image Best Practices',
          content: `• Use high-quality images (at least 1920px wide)
• Avoid images with too much text
• Ensure good contrast for readable text overlay
• Coffee shop aesthetic works well (golden hour lighting, professional look)
• Test on mobile devices - images should look good at small sizes`,
        },
      ],
    },
    {
      id: 'seo-guide',
      title: 'SEO Best Practices',
      icon: TagIcon,
      items: [
        {
          title: 'SEO Title (50-60 characters)',
          content: `The blue clickable link in Google search results. Formula: [Primary Keyword] | [Benefit/Category] | iDrinkCoffee

Good examples:
✅ "Home Espresso Machines | Top Brands | iDrinkCoffee"
✅ "Single Dose Grinders | Precision Coffee Grinding | iDC"

Bad examples:
❌ "Espresso Machines" (too short)
❌ "Buy The Best Home Espresso Machines Online In Canada From iDrinkCoffee" (too long)`,
        },
        {
          title: 'SEO Description (150-160 characters)',
          content: `The gray preview text under the title in search results. Formula: [Benefit Statement] [Product Range] [Social Proof/Unique Value] [CTA]

Good example:
✅ "Shop Canada's largest selection of single dose coffee grinders. From $200 to $3000, find your perfect precision grinder. Expert advice & fast shipping."

The character counter shows optimal ranges - aim for green (optimal).`,
        },
        {
          title: 'Keyword Usage',
          content: `Include your primary keyword in: page title, SEO title, hero title, and URL handle. Use keywords naturally - don't stuff them. Write for humans first, SEO second. Match search intent: transactional pages use "Buy", "Shop", "Compare"; informational pages use "Guide", "How to", "Best".`,
        },
      ],
    },
    {
      id: 'nested-editing',
      title: 'Working with Nested Content',
      icon: QuestionMarkCircleIcon,
      items: [
        {
          title: 'Editing FAQ Items',
          content: `1. Select an FAQ section from the dropdown
2. Click the "Edit Items" button (appears after selection)
3. A modal opens showing all FAQ questions
4. Add new: Click "Add FAQ", fill in question and answer
5. Edit: Click pencil icon, modify, save
6. Delete: Click trash icon, confirm
7. Reorder: Drag and drop questions
8. Click "Save" when done - changes sync to Shopify`,
        },
        {
          title: 'Editing Comparison Features',
          content: `1. Select a comparison table from the dropdown
2. Click "Edit Items" button
3. Modal opens with Features and Products tabs
4. In Features tab:
   - Add: Click "Add Feature", enter name and description
   - Edit: Click pencil icon
   - Delete: Click trash icon
5. Click "Save" to sync changes`,
        },
        {
          title: 'Best Practices for FAQs',
          content: `• Keep answers concise (2-4 sentences)
• Start with the most common questions
• Use conversational tone
• Link to detailed guides when needed

Example:
Q: What's the difference between semi-automatic and automatic espresso machines?
A: Semi-automatic machines give you full control over shot timing, perfect for enthusiasts. Automatic machines stop the shot for you when a preset volume is reached, making them more consistent for beginners.`,
        },
      ],
    },
    {
      id: 'field-reference',
      title: 'Field Reference',
      icon: Cog6ToothIcon,
      items: [
        {
          title: 'URL Handle Rules',
          content: `Format requirements:
✅ Allowed: lowercase letters (a-z), numbers (0-9), hyphens (-)
❌ Not allowed: uppercase, spaces, underscores, special characters

Good examples:
✅ home-espresso-machines
✅ grinders-under-500
✅ la-marzocco-linea-mini

Bad examples:
❌ Home_Espresso_Machines
❌ grinders under $500
❌ La Marzocco (Linea Mini)

Once set, avoid changing URL handles as it breaks existing links.`,
        },
        {
          title: 'Hero Title Guidelines',
          content: `• Keep it short and punchy (3-8 words)
• Focus on benefits or key differentiators
• Use active language

Good examples:
✅ "Precision Grinding, Zero Waste"
✅ "Your Perfect Shot Starts Here"
✅ "Commercial-Grade Performance for Home"

Bad examples:
❌ "Welcome to Our Espresso Machines Category"
❌ "Buy Espresso Machines Online"`,
        },
        {
          title: 'Hero Description Guidelines',
          content: `• 2-3 sentences (20-50 words ideal)
• Explain what makes this category special
• Address customer pain points or desires
• Use conversational tone

Example:
"Discover the perfect single dose grinder for your workflow. Every bean counts when you're grinding fresh by weight. Explore our collection of precision grinders from $200 to $3000."`,
        },
        {
          title: 'Sorting Options',
          content: `Types of filters:
1. Price Range: "$500 - $1000", "Under $500"
2. Vendor/Brand: "Breville", "La Marzocco"
3. Specification: "Portafilter: 58mm", "Boiler: Dual"

Best practices:
• Add 4-8 sorting options
• Start with price ranges (most common filter)
• Add brand filters for popular vendors
• Use specifications that matter most to buyers`,
        },
      ],
    },
    {
      id: 'troubleshooting',
      title: 'Troubleshooting',
      icon: QuestionMarkCircleIcon,
      items: [
        {
          title: 'Failed to save changes',
          content: `Solutions:
1. Check that all required fields are filled:
   - Page title ✓
   - Hero title ✓
   - URL handle ✓
2. Ensure URL handle format is correct (lowercase, hyphens only)
3. Try saving again
4. If persists, copy your content, refresh page, and retry`,
        },
        {
          title: 'Image failed to generate',
          content: `Solutions:
1. Wait 30 seconds and try again
2. Try the other model (GPT vs Gemini)
3. Check your hero title and description are filled in
4. If both models fail, try uploading a custom image instead`,
        },
        {
          title: 'SEO character counter is red',
          content: `Solutions:
SEO Title (50-60 chars):
• Too short: Add location or benefit
• Too long: Remove filler words, use abbreviations

SEO Description (150-160 chars):
• Too short: Expand on benefits, add social proof
• Too long: Cut redundant phrases, use active voice`,
        },
        {
          title: 'Changes not appearing on live site',
          content: `Solutions:
1. Hard refresh the live page (Ctrl+Shift+R on PC, Cmd+Shift+R on Mac)
2. Clear browser cache
3. Wait 2-5 minutes for CDN to update
4. Check CMS to verify changes were saved`,
        },
      ],
    },
  ];

  const filteredSections = helpSections.map((section) => ({
    ...section,
    items: filterContent(section.items),
  })).filter((section) => section.items.length > 0);

  return (
    <div className="h-full flex flex-col bg-zinc-50 dark:bg-zinc-950">
      {/* Header */}
      <div className="flex-shrink-0 bg-white dark:bg-zinc-900 border-b border-zinc-200 dark:border-zinc-800 px-6 py-6">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-center gap-3 mb-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-blue-600 shadow-lg shadow-blue-500/25">
              <BookOpenIcon className="h-7 w-7 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
                Category Pages Help Guide
              </h1>
              <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
                Complete guide for managing category landing pages
              </p>
              <div className="flex items-center gap-2 mt-2">
                <span className="inline-flex items-center rounded-md bg-blue-50 dark:bg-blue-900/30 px-2 py-1 text-xs font-medium text-blue-700 dark:text-blue-300 ring-1 ring-inset ring-blue-700/10 dark:ring-blue-300/20">
                  Category Pages
                </span>
                <span className="text-xs text-zinc-400 dark:text-zinc-500">
                  More content types coming soon
                </span>
              </div>
            </div>
          </div>

          {/* Search Bar */}
          <div className="relative">
            <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-zinc-400" />
            <input
              type="text"
              placeholder="Search documentation..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 border border-zinc-300 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-shadow"
            />
          </div>

          {/* Expand/Collapse All */}
          <div className="flex gap-2 mt-3">
            <button
              onClick={expandAll}
              className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
            >
              Expand All
            </button>
            <span className="text-zinc-300 dark:text-zinc-700">|</span>
            <button
              onClick={collapseAll}
              className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
            >
              Collapse All
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto px-6 py-6">
        <div className="max-w-4xl mx-auto space-y-4">
          {filteredSections.length === 0 ? (
            <div className="text-center py-12">
              <QuestionMarkCircleIcon className="h-12 w-12 text-zinc-400 mx-auto mb-3" />
              <p className="text-zinc-500 dark:text-zinc-400">
                No results found for "{searchTerm}"
              </p>
            </div>
          ) : (
            filteredSections.map((section) => {
              const Icon = section.icon;
              const isExpanded = expandedSections[section.id];

              return (
                <div
                  key={section.id}
                  className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 overflow-hidden"
                >
                  {/* Section Header */}
                  <button
                    onClick={() => toggleSection(section.id)}
                    className="w-full flex items-center gap-3 px-5 py-4 hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition-colors"
                  >
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100 dark:bg-blue-900/30">
                      <Icon className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                    </div>
                    <h2 className="flex-1 text-left text-lg font-semibold text-zinc-900 dark:text-zinc-100">
                      {section.title}
                    </h2>
                    {isExpanded ? (
                      <ChevronDownIcon className="h-5 w-5 text-zinc-400" />
                    ) : (
                      <ChevronRightIcon className="h-5 w-5 text-zinc-400" />
                    )}
                  </button>

                  {/* Section Content */}
                  {isExpanded && (
                    <div className="px-5 pb-4 space-y-4">
                      {section.items.map((item, idx) => (
                        <div
                          key={idx}
                          className="pl-[52px] border-l-2 border-zinc-200 dark:border-zinc-800"
                        >
                          <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100 mb-2">
                            {item.title}
                          </h3>
                          <div className="text-sm text-zinc-600 dark:text-zinc-400 whitespace-pre-line leading-relaxed">
                            {item.content}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="flex-shrink-0 bg-white dark:bg-zinc-900 border-t border-zinc-200 dark:border-zinc-800 px-6 py-4">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-start gap-3 p-3 bg-amber-50 dark:bg-amber-900/20 rounded-lg border border-amber-200 dark:border-amber-800 mb-3">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-amber-600 dark:text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-amber-900 dark:text-amber-100">
                Other Content Types
              </p>
              <p className="text-xs text-amber-700 dark:text-amber-200 mt-1">
                This guide covers Category Landing Pages only. For help with Home Banners, Header Banner, or Menus, refer to those sections in the CMS sidebar. Additional help guides coming soon!
              </p>
            </div>
          </div>
          <p className="text-xs text-zinc-500 dark:text-zinc-400 text-center">
            Need more help?{' '}
            <a href="#" className="text-blue-600 dark:text-blue-400 hover:underline">
              Contact Pranav
            </a>{' '}
            or post in{' '}
            <span className="font-mono bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded">
              #content-team
            </span>{' '}
            Slack channel.
          </p>
        </div>
      </div>
    </div>
  );
}
