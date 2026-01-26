import React, { useState } from 'react';
import {
  MagnifyingGlassIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  BookOpenIcon,
  Bars3Icon,
  LinkIcon,
  GlobeAltIcon,
} from '@heroicons/react/20/solid';

export default function HeaderBannerHelpPage() {
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
          title: 'What is the Header Banner?',
          content: `The Header Banner is the thin promotional bar at the very top of the website, above the main navigation. It's perfect for:
• Flash sales or limited-time offers
• Shipping promotions ("Free shipping over $50")
• Store-wide discounts
• Important announcements
• Holiday messages

The header banner appears on every page of the site, making it prime real estate for your most important message.`,
        },
        {
          title: 'How to Access',
          content: `1. Navigate to the CMS (/cms)
2. Click "Header Banner" in the sidebar
3. Use the market toggle to switch between CA and US
4. Click "Edit" on any link position to modify it

There are three link positions: Left, Center, and Right.`,
        },
      ],
    },
    {
      id: 'link-positions',
      title: 'Link Positions',
      icon: Bars3Icon,
      items: [
        {
          title: 'Three Positions Available',
          content: `The header banner supports up to three text links arranged horizontally:

Left Position:
• First thing users see (high visibility)
• Good for primary promotions
• Example: "FREE SHIPPING OVER $50"

Center Position:
• Most prominent position
• Centered in banner
• Example: "SAVE 25% SITEWIDE - USE CODE: SAVE25"

Right Position:
• Secondary promotion or info
• Less prominent but still visible
• Example: "New Products Added Daily"

Mobile Behavior: Links may stack vertically or show in carousel on mobile devices.`,
        },
        {
          title: 'When to Use Each Position',
          content: `Strategic Use of Positions:

Single Message:
Use Center position only for maximum impact

Two Messages:
Left + Right (skip center for balanced look)
Example: "Free Shipping" (left) + "New Arrivals" (right)

Three Messages:
Use all positions for maximum information
Example: "Free Shipping" (left) + "25% Off Sale" (center) + "Shop New Arrivals" (right)

Best Practice: Don't overcrowd - one strong message often works better than three weak ones.`,
        },
      ],
    },
    {
      id: 'link-fields',
      title: 'Link Fields',
      icon: LinkIcon,
      items: [
        {
          title: 'Text Fields',
          content: `Text:
• The clickable text that appears in the header
• Keep it SHORT (3-8 words max)
• Use ALL CAPS for emphasis (optional)
• Action-oriented when possible

Examples:
✓ "FREE SHIPPING OVER $50"
✓ "SAVE 25% - USE CODE: SAVE25"
✓ "NEW: LA MARZOCCO LINEA MINI"
✓ "SHOP BLACK FRIDAY DEALS"

Avoid:
✗ "Click here to learn more about our shipping policy" (too long)
✗ "New products" (vague, no urgency)
✗ "We have a sale happening now" (wordy)`,
        },
        {
          title: 'URL Field',
          content: `URL:
• Where the link directs users
• Can be any page on the site or external
• Use relative URLs when possible

Relative URL Examples:
/collections/espresso-machines
/products/breville-barista-express
/pages/shipping-policy
/collections/sale

Absolute URL (External):
https://example.com/external-page

Tips:
• Test links after saving
• Use tracking parameters for campaign attribution (?utm_source=header)
• Link to relevant landing pages, not just homepage`,
        },
        {
          title: 'Has Image Toggle',
          content: `Has Image:
• Optional icon/emoji that appears before text
• Adds visual interest
• Draws attention to link

When to Use Icons:
✓ Shipping promotions (truck icon)
✓ Sale announcements (tag/percent icon)
✓ New arrivals (star/sparkle icon)
✓ Holiday messages (seasonal icons)

When to Skip Icons:
• Text is short and clear
• Multiple links (too busy)
• Professional/minimal aesthetic

Note: Icon selection may be handled through the backend or image upload.`,
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
          content: `Header banners can be configured differently for Canadian and US markets.

Why Separate Markets?
• Different promotions (CAD vs USD pricing)
• Regional product availability
• Market-specific campaigns
• Shipping thresholds differ

Examples:
CA: "FREE SHIPPING OVER $50 CAD"
US: "FREE SHIPPING OVER $50 USD"

CA: "SAVE 25% - CODE: CANADA25"
US: "SAVE 25% - CODE: USA25"

Always check which market you're editing before saving!`,
        },
      ],
    },
    {
      id: 'best-practices',
      title: 'Best Practices',
      icon: BookOpenIcon,
      items: [
        {
          title: 'Writing Effective Header Messages',
          content: `Keep It Short:
• 3-8 words ideal
• Every word counts
• Remove filler words

Create Urgency:
• "Limited Time", "Today Only", "While Supplies Last"
• Include end dates: "ENDS SUNDAY"
• Use countdown language

Be Specific:
• "25% OFF" not "Big Sale"
• "FREE SHIPPING OVER $50" not "Free Shipping Available"
• "$100 OFF LA MARZOCCO" not "Discounts on Machines"

Use Action Words:
• SAVE, SHOP, EXPLORE, DISCOVER
• GET, CLAIM, UNLOCK
• NEW, EXCLUSIVE, LIMITED`,
        },
        {
          title: 'Update Frequency',
          content: `How Often to Update:

Daily:
• Flash sales (24-hour deals)
• Inventory-specific promotions

Weekly:
• New weekly promotions
• Seasonal campaigns

Monthly:
• New month campaigns
• Holiday countdowns

Seasonally:
• Major holidays (Black Friday, Christmas)
• Seasonal transitions (Spring, Summer, Fall, Winter)

Always On:
• Shipping thresholds (unless changed)
• Store-wide perks ("Price Match Guarantee")`,
        },
        {
          title: 'Common Header Banner Uses',
          content: `Shipping Promotions:
"FREE SHIPPING OVER $50"
"FREE EXPRESS SHIPPING THIS WEEK"

Discount Codes:
"SAVE 20% - CODE: WELCOME20"
"USE CODE: FREESHIP FOR FREE SHIPPING"

Sales Events:
"BLACK FRIDAY: UP TO 40% OFF"
"CYBER WEEK DEALS - SHOP NOW"

Product Launches:
"NEW: BREVILLE ORACLE JET"
"JUST ARRIVED: LA MARZOCCO GS3"

Announcements:
"NEW STORE HOURS: 9AM-8PM"
"HOLIDAY SHIPPING DEADLINE: DEC 18"`,
        },
      ],
    },
    {
      id: 'troubleshooting',
      title: 'Troubleshooting',
      icon: BookOpenIcon,
      items: [
        {
          title: 'Link not clickable',
          content: `Checklist:
• URL field is filled in (not blank)
• URL is valid (starts with / or https://)
• No typos in URL
• Link was saved successfully
• Clear browser cache and test again

If link still not working, check browser console for JavaScript errors.`,
        },
        {
          title: 'Text too long on mobile',
          content: `Solutions:
• Shorten text (aim for 3-5 words max)
• Remove unnecessary words
• Use abbreviations: "Free Ship $50+" instead of "Free Shipping Over $50"
• Test on actual mobile device
• Consider using only 1-2 positions instead of 3`,
        },
        {
          title: 'Changes not appearing',
          content: `Solutions:
1. Verify you saved the changes (look for success message)
2. Check correct market (CA vs US)
3. Clear browser cache (Ctrl+Shift+R / Cmd+Shift+R)
4. Wait 2-5 minutes for CDN to update
5. Test in incognito/private browsing window`,
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
              <Bars3Icon className="h-7 w-7 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
                Header Banner Help Guide
              </h1>
              <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
                Managing the top promotional banner
              </p>
              <div className="flex items-center gap-2 mt-2">
                <span className="inline-flex items-center rounded-md bg-blue-50 dark:bg-blue-900/30 px-2 py-1 text-xs font-medium text-blue-700 dark:text-blue-300 ring-1 ring-inset ring-blue-700/10 dark:ring-blue-300/20">
                  Header Banner
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
              <Bars3Icon className="h-12 w-12 text-zinc-400 mx-auto mb-3" />
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
