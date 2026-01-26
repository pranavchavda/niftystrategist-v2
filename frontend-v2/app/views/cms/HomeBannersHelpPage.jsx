import React, { useState } from 'react';
import {
  MagnifyingGlassIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  BookOpenIcon,
  PhotoIcon,
  GlobeAltIcon,
  SparklesIcon,
} from '@heroicons/react/20/solid';

export default function HomeBannersHelpPage() {
  const [searchTerm, setSearchTerm] = useState('');
  const [expandedSections, setExpandedSections] = useState({
    'getting-started': true,
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
          title: 'What are Home Banners?',
          content: `Home Banners are the large promotional banners that appear on the homepage of iDrinkCoffee.com. They're the first thing visitors see and are critical for showcasing promotions, new products, and seasonal campaigns.

There are two types:
• Primary Banners: Large hero banners (usually 1-2 per market)
• Secondary Banners: Smaller promotional banners below the hero

Each banner can be configured separately for Canadian (CA) and US markets.`,
        },
        {
          title: 'How to Access',
          content: `1. Navigate to the CMS (/cms)
2. Click "Home Banners" in the sidebar
3. Use the market filter to switch between CA, US, or view All markets
4. Click "Edit" on any banner to modify it`,
        },
      ],
    },
    {
      id: 'banner-types',
      title: 'Banner Types',
      icon: PhotoIcon,
      items: [
        {
          title: 'Primary Banner (Hero)',
          content: `The main hero banner at the top of the homepage.

Components:
• Background Image: Large panoramic image (recommended 1920×800px)
• Heading: Main headline (2-8 words)
• Subheading: Supporting text (optional, 10-20 words)
• CTA Button: Call-to-action button with text and link
• Text Position: Left, Center, or Right alignment

Best Practices:
• Use high-quality, professional images
• Keep heading short and impactful
• CTA should be action-oriented ("Shop Now", "Explore Collection")
• Test on mobile - ensure text is readable`,
        },
        {
          title: 'Secondary Banner',
          content: `Smaller promotional banners that appear below the primary hero.

Components:
• Background Image: Rectangular image (recommended 1200×400px)
• Heading: Promotional headline
• Subheading: Brief description
• CTA Button: Link to relevant page

Use Cases:
• Flash sales or limited-time offers
• New product launches
• Brand spotlights
• Category promotions

Tip: Keep messaging concise - these are quick attention-grabbers.`,
        },
      ],
    },
    {
      id: 'market-management',
      title: 'Market Management',
      icon: GlobeAltIcon,
      items: [
        {
          title: 'CA vs US Markets',
          content: `iDrinkCoffee operates in both Canadian and US markets. Each market has its own set of banners to allow for:
• Different pricing/currency
• Market-specific promotions
• Regional product availability
• Localized messaging

Market Filter:
• All: View both CA and US banners
• CA: Canadian market only
• US: US market only

Important: Always check which market you're editing before making changes!`,
        },
        {
          title: 'When to Duplicate vs. Customize',
          content: `Duplicate Content Across Markets When:
✓ Promotion applies to both markets
✓ Products available in both regions
✓ Brand messaging is universal

Customize for Each Market When:
✓ Pricing differs (CAD vs USD)
✓ Product availability varies
✓ Regional holidays or events
✓ Market-specific promotions

Example: Black Friday sale might have same imagery but different discount amounts.`,
        },
      ],
    },
    {
      id: 'editing-banners',
      title: 'Editing Banners',
      icon: SparklesIcon,
      items: [
        {
          title: 'Banner Fields Explained',
          content: `When editing a banner, you'll see these fields:

Heading:
• Primary text visitors see
• Keep it short (2-8 words)
• Use action words

Subheading:
• Optional supporting text
• Provides context or urgency
• 10-20 words ideal

CTA Text:
• Button text ("Shop Now", "Learn More", "View Collection")
• Action-oriented verbs
• Keep it 1-3 words

CTA Link:
• Where button directs users
• Can be category page, product, or collection
• Use relative URLs: /collections/espresso-machines

Background Image:
• Upload or select from library
• Primary: 1920×800px
• Secondary: 1200×400px
• JPG or WebP format`,
        },
        {
          title: 'Image Best Practices',
          content: `Image Specifications:
• Primary Banner: 1920×800px (2.4:1 ratio)
• Secondary Banner: 1200×400px (3:1 ratio)
• Format: JPG or WebP
• Max file size: 2MB
• Resolution: 72-150 DPI

Design Tips:
• Leave space for text overlay (don't put important content where text will go)
• Use images with good contrast for readability
• Avoid busy backgrounds
• Test on mobile - images may crop differently
• Keep brand consistent across banners`,
        },
        {
          title: 'Text Position & Alignment',
          content: `Text Position Options:
• Left: Text aligns to left side (good for images with right-side focus)
• Center: Text centered (good for symmetrical images)
• Right: Text aligns to right (good for images with left-side focus)

Choosing Position:
1. Look at your background image
2. Find the area with best contrast
3. Position text where it's most readable
4. Avoid placing text over faces or product details

Mobile Consideration: Text may center on mobile regardless of desktop position.`,
        },
      ],
    },
    {
      id: 'best-practices',
      title: 'Best Practices',
      icon: BookOpenIcon,
      items: [
        {
          title: 'Seasonal Updates',
          content: `Update home banners regularly to keep homepage fresh:

Quarterly Updates:
• Spring: New season products, refresh imagery
• Summer: Outdoor coffee, cold brew promotions
• Fall: Back-to-school, pumpkin spice vibes
• Winter: Holiday gifts, cozy home setups

Monthly Updates:
• Rotate featured products
• Highlight new arrivals
• Seasonal sales and promotions

Weekly Updates (for active campaigns):
• Flash sales
• Limited inventory promotions
• Event-specific campaigns`,
        },
        {
          title: 'A/B Testing Ideas',
          content: `Test different banner variations to improve conversions:

Heading Variations:
• Benefit-focused: "Upgrade Your Morning Ritual"
• Product-focused: "New La Marzocco Linea Mini"
• Urgency-focused: "Last Chance: 25% Off Ends Today"

CTA Variations:
• "Shop Now" vs "Explore Collection" vs "Learn More"
• Color variations (if possible)
• Position variations

Image Variations:
• Lifestyle vs product-only
• Light vs dark backgrounds
• Minimal vs detailed compositions

Track which variations perform best and apply learnings to future banners.`,
        },
      ],
    },
    {
      id: 'troubleshooting',
      title: 'Troubleshooting',
      icon: BookOpenIcon,
      items: [
        {
          title: 'Banner not updating on live site',
          content: `Solutions:
1. Clear browser cache (Ctrl+Shift+R / Cmd+Shift+R)
2. Wait 2-5 minutes for CDN propagation
3. Check if you edited the correct market (CA vs US)
4. Verify changes saved successfully (look for success message)
5. Check if banner is active/enabled`,
        },
        {
          title: 'Image not displaying',
          content: `Checklist:
• Image uploaded successfully? (check for upload confirmation)
• Image too large? (compress to under 2MB)
• Correct format? (use JPG or WebP)
• Try re-uploading the image
• Clear browser cache and refresh`,
        },
        {
          title: 'Text not readable on image',
          content: `Solutions:
• Choose different text position (left/center/right)
• Add text shadow or background overlay (if editor supports it)
• Use different background image with better contrast
• Adjust image - darken or lighten as needed
• Keep text color high-contrast (white on dark, dark on light)`,
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
              <PhotoIcon className="h-7 w-7 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
                Home Banners Help Guide
              </h1>
              <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
                Managing homepage hero and promotional banners
              </p>
              <div className="flex items-center gap-2 mt-2">
                <span className="inline-flex items-center rounded-md bg-blue-50 dark:bg-blue-900/30 px-2 py-1 text-xs font-medium text-blue-700 dark:text-blue-300 ring-1 ring-inset ring-blue-700/10 dark:ring-blue-300/20">
                  Home Banners
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
              <PhotoIcon className="h-12 w-12 text-zinc-400 mx-auto mb-3" />
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
        <div className="max-w-4xl mx-auto text-center">
          <p className="text-xs text-zinc-500 dark:text-zinc-400">
            Need help?{' '}
            <span className="font-mono bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded">
              #content-team
            </span>{' '}
            Slack channel
          </p>
        </div>
      </div>
    </div>
  );
}
