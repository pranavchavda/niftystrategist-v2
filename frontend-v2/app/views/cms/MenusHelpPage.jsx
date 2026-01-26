import React, { useState } from 'react';
import {
  MagnifyingGlassIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  BookOpenIcon,
  Bars3Icon,
  FolderIcon,
  ArrowsUpDownIcon,
} from '@heroicons/react/20/solid';

export default function MenusHelpPage() {
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
          title: 'What are Menus?',
          content: `Menus are the navigation structures that help customers browse your website. They appear in:
• Header navigation (main menu)
• Footer navigation (footer menu)
• Mobile navigation (hamburger menu)

Each menu contains menu items (links) organized in a hierarchy. Menu items can have:
• Top-level items (main categories)
• Nested items (subcategories/dropdowns)
• Multiple levels of nesting (mega menus)

Examples of menus:
• Main Menu: Machines, Grinders, Accessories, Sale
• Footer Menu: About Us, Shipping, Returns, Contact`,
        },
        {
          title: 'How to Access',
          content: `1. Navigate to the CMS (/cms)
2. Click "Menus" in the sidebar
3. Select the menu you want to edit (e.g., "main-menu", "footer")
4. Edit menu items using the hierarchical tree view

The Menus interface shows all available menus as cards with item counts.`,
        },
      ],
    },
    {
      id: 'menu-structure',
      title: 'Menu Structure',
      icon: FolderIcon,
      items: [
        {
          title: 'Hierarchical Organization',
          content: `Menus are organized in a tree structure:

Level 1 (Top-level items):
• Main categories
• Visible in main navigation
• Example: "Espresso Machines"

Level 2 (Nested under Level 1):
• Subcategories
• Appear in dropdown menus
• Example: "Home Machines" under "Espresso Machines"

Level 3 (Nested under Level 2):
• Further sub-categories
• Deeper navigation
• Example: "Semi-Automatic" under "Home Machines"

Best Practice: Keep menus 2-3 levels deep max. Deeper = harder to navigate.`,
        },
        {
          title: 'Menu Item Types',
          content: `Link Types:

Collection Link:
• Links to product collections
• Example: /collections/espresso-machines
• Most common type

Product Link:
• Direct link to specific product
• Example: /products/breville-barista-express
• Use for featured products

Page Link:
• Links to content pages
• Example: /pages/about-us
• For static content

External Link:
• Links to external websites
• Example: https://example.com
• Use sparingly

Custom Link:
• Any URL you specify
• Flexible for special cases`,
        },
      ],
    },
    {
      id: 'editing-menus',
      title: 'Editing Menus',
      icon: Bars3Icon,
      items: [
        {
          title: 'Adding Menu Items',
          content: `To add a new menu item:

1. Click "Add Menu Item" button
2. Fill in the form:
   - Title: Display text (e.g., "Espresso Machines")
   - URL: Link destination (e.g., /collections/espresso-machines)
   - Parent (optional): Select if this is a nested item
3. Click "Save"

Tips:
• Keep titles short (1-3 words)
• Use customer-friendly language
• Match titles to actual page names
• Test links after saving`,
        },
        {
          title: 'Reordering Menu Items',
          content: `To change menu item order:

Drag and Drop Method:
1. Click and hold the drag handle (⋮⋮) on an item
2. Drag to new position
3. Release to drop
4. Changes save automatically

Manual Method:
• Use "Move Up" / "Move Down" buttons
• Or edit item and change position number

Menu Order Matters:
• Top items appear first in navigation
• Order = priority (put important categories first)
• Common pattern: Products first, then info pages`,
        },
        {
          title: 'Nesting Menu Items',
          content: `To create nested items (dropdowns):

Option 1: When Adding New Item
1. Select "Parent Item" from dropdown
2. New item becomes child of parent

Option 2: When Editing Existing Item
1. Edit the menu item
2. Change "Parent Item" field
3. Save

Option 3: Drag and Drop
1. Drag item slightly to the right
2. Drop under parent item
3. Item becomes nested

Visual Indicator: Nested items are indented in the tree view.`,
        },
        {
          title: 'Editing Menu Items',
          content: `To edit an existing menu item:

1. Click the edit icon (pencil) next to item
2. Modify fields:
   - Title: Change display text
   - URL: Update link destination
   - Parent: Move to different parent or make top-level
3. Click "Save"

Common Edits:
• Fix typos in titles
• Update URLs when pages move
• Reorganize hierarchy
• Add/remove nesting`,
        },
        {
          title: 'Deleting Menu Items',
          content: `To delete a menu item:

1. Click the delete icon (trash) next to item
2. Confirm deletion

⚠️ Warning: Deleting a parent item will also delete all its children (nested items).

Before Deleting:
• Check if item has children (expand to see)
• Consider moving children to new parent instead
• Verify you're deleting the right item
• No undo - deletion is permanent!`,
        },
      ],
    },
    {
      id: 'best-practices',
      title: 'Best Practices',
      icon: ArrowsUpDownIcon,
      items: [
        {
          title: 'Menu Organization Tips',
          content: `Good Menu Structure:

Product Categories First:
1. Espresso Machines
   - Home Machines
   - Commercial Machines
2. Grinders
   - Manual Grinders
   - Electric Grinders
3. Accessories

Then Information Pages:
4. About Us
5. Shipping & Returns
6. Contact

Why This Works:
• Customers want products first
• Clear hierarchy aids discovery
• Info pages accessible but not primary focus`,
        },
        {
          title: 'Naming Conventions',
          content: `Menu Item Titles:

Do:
✓ "Espresso Machines" (clear, specific)
✓ "Grinders" (short, familiar)
✓ "Accessories" (broad category)
✓ "Sale" (action-oriented)

Don't:
✗ "Click here for machines" (unnecessary words)
✗ "Coffee Grinding Equipment & Solutions" (too long)
✗ "Misc" (vague, unhelpful)
✗ "Products" (too generic)

Rules of Thumb:
• 1-3 words ideal
• Use customer language (not internal jargon)
• Be specific but concise
• Capitalize Each Word (Title Case)`,
        },
        {
          title: 'Depth Guidelines',
          content: `How Deep Should Menus Go?

Recommended:
• Main Menu: 2-3 levels max
• Footer Menu: 1-2 levels max
• Mobile Menu: 2 levels max (3 gets hard to navigate)

Example of Good Depth:
Level 1: Espresso Machines
  Level 2: Home Machines
    Level 3: Semi-Automatic ✓ (3 levels ok)
      Level 4: Breville ✗ (too deep!)

Why Limit Depth?
• Mobile navigation gets cramped
• Users lose track of location
• Cognitive load increases
• Simpler = better conversion`,
        },
        {
          title: 'Mobile Considerations',
          content: `Designing for Mobile:

Keep It Simple:
• Fewer top-level items (5-7 max)
• Shorter titles (easier to tap)
• Avoid deep nesting (2 levels ideal)

Touch-Friendly:
• Items need space to tap (at least 44px)
• Avoid cramming too many items
• Consider swipe gestures

Test on Mobile:
• Actually open site on phone
• Try navigating like a customer
• Check if items are tappable
• Verify dropdowns work smoothly`,
        },
      ],
    },
    {
      id: 'troubleshooting',
      title: 'Troubleshooting',
      icon: BookOpenIcon,
      items: [
        {
          title: 'Menu not appearing on site',
          content: `Checklist:
• Menu is assigned to a location (header, footer, etc.)
• Theme is configured to use the menu
• Clear browser cache and refresh
• Check in theme settings (may need developer)
• Verify menu has at least one item`,
        },
        {
          title: 'Dropdown not working',
          content: `Possible Issues:
• Parent item doesn't have children (add nested items)
• JavaScript error on page (check console)
• Theme doesn't support dropdowns (check theme docs)
• Too many levels (some themes max at 2-3)

Solutions:
• Verify items are properly nested (indented in tree)
• Test in different browser
• Check theme dropdown settings`,
        },
        {
          title: 'Drag and drop not working',
          content: `Try These Solutions:
1. Refresh the page
2. Use "Move Up/Down" buttons instead
3. Edit item and change parent manually
4. Clear browser cache
5. Try different browser

If still not working, reach out to tech support.`,
        },
        {
          title: 'Link going to wrong page',
          content: `Common Causes:
• Typo in URL
• Product/collection was deleted
• URL changed but menu wasn't updated
• Relative vs absolute URL issue

Solutions:
1. Edit menu item
2. Check URL field for typos
3. Visit URL directly to verify it works
4. Update URL to correct path
5. Save and test again

URL Format Tips:
• Use relative URLs: /collections/grinders (not full URL)
• No spaces in URLs (use hyphens)
• Lowercase only`,
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
                Menus Help Guide
              </h1>
              <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
                Managing navigation menus and menu items
              </p>
              <div className="flex items-center gap-2 mt-2">
                <span className="inline-flex items-center rounded-md bg-blue-50 dark:bg-blue-900/30 px-2 py-1 text-xs font-medium text-blue-700 dark:text-blue-300 ring-1 ring-inset ring-blue-700/10 dark:ring-blue-300/20">
                  Menus
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
