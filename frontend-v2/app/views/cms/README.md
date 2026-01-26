# CMS Interface - Sidebar Navigation System

## Overview
Comprehensive sidebar navigation system for the Content Management System (CMS) interface, replacing the previous top-tab navigation with a professional sidebar layout using Catalyst UI components.

## Implementation Details

### Files Modified
1. **`CMSLayout.jsx`** - Main layout component with sidebar navigation
2. **`CategoryLandingPagesPage.jsx`** - Updated to work with new layout (removed redundant header)

### Architecture

#### CMSLayout Component
**Location**: `/home/pranav/pydanticebot/frontend-v2/app/views/cms/CMSLayout.jsx`

**Key Features**:
- Sidebar navigation with Catalyst UI components
- Mobile-responsive with hamburger menu
- Active state indicators
- "Coming Soon" badges for future features
- Informative footer with beta notice
- Fixed 240px sidebar width on desktop
- Overlay sidebar on mobile (< 768px breakpoint)

**Structure**:
```
CMSLayout
├── Mobile Toggle Button (< 768px)
├── Mobile Sidebar (with overlay backdrop)
├── Desktop Sidebar (≥ 768px)
│   ├── SidebarHeader (CMS branding)
│   ├── SidebarBody
│   │   ├── Content Types Section
│   │   │   ├── Category Pages (active)
│   │   │   ├── FAQ Management (coming soon)
│   │   │   ├── Educational Content (coming soon)
│   │   │   └── Comparison Tables (coming soon)
│   │   └── Administration Section
│   │       └── Settings (coming soon)
│   └── SidebarFooter (Beta notice)
└── Main Content Area
    ├── Page Header (dynamic title/description)
    └── Content (Routes)
```

### Navigation Items

#### Active
1. **Category Pages** (`/cms`)
   - Icon: `PhotoIcon`
   - Description: Edit hero banners and content for category landing pages
   - Status: Active

#### Coming Soon
2. **FAQ Management** (`/cms/faq`)
   - Icon: `QuestionMarkCircleIcon`
   - Description: Manage FAQ sections and individual FAQ items
   - Status: Coming Soon (Phase 2)

3. **Educational Content** (`/cms/education`)
   - Icon: `BookOpenIcon`
   - Description: Edit educational content blocks
   - Status: Coming Soon

4. **Comparison Tables** (`/cms/comparison`)
   - Icon: `Squares2X2Icon`
   - Description: Manage product comparison tables
   - Status: Coming Soon

5. **Settings** (`/cms/settings`)
   - Icon: `Cog6ToothIcon`
   - Description: CMS settings and configuration
   - Status: Coming Soon

### Mobile Responsiveness

#### Desktop (≥ 768px)
- Fixed 240px sidebar on the left
- Full navigation always visible
- Smooth transitions

#### Mobile (< 768px)
- Hamburger menu button (top-left, fixed position)
- Overlay sidebar that slides in from left
- Semi-transparent backdrop (black/30)
- Close button in sidebar header
- Auto-closes after navigation

### Styling & Theme

#### Colors
- **Primary**: Amber (600/500 for accents)
- **Background**: White/Zinc-900 (light/dark mode)
- **Borders**: Zinc-200/Zinc-800
- **Text**: Zinc-900/Zinc-100 for headings, Zinc-500/Zinc-400 for secondary

#### Components Used
- Catalyst UI Sidebar components
- Heroicons for icons
- Lucide React for FileEdit icon

### State Management

#### Local State
```javascript
const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
```

#### Navigation Logic
```javascript
const isActive = (item) => {
  const fullPath = `/cms${item.path ? `/${item.path}` : ''}`;
  return location.pathname === fullPath;
};

const handleNavigate = (path, comingSoon) => {
  if (comingSoon) return; // Prevent navigation for coming soon items
  navigate(`/cms${path ? `/${path}` : ''}`);
  setMobileSidebarOpen(false); // Close mobile sidebar
};
```

### Catalyst UI Integration

The implementation follows Catalyst UI patterns:

```javascript
import {
  Sidebar,
  SidebarHeader,
  SidebarBody,
  SidebarFooter,
  SidebarSection,
  SidebarItem,
  SidebarLabel,
  SidebarHeading,
  SidebarDivider,
} from '../../components/catalyst/sidebar';
```

**SidebarItem** accepts:
- `current` - Boolean for active state (shows indicator)
- `onClick` - Click handler
- `className` - Additional classes
- `title` - Tooltip text

### CategoryLandingPagesPage Updates

**Changes**:
- Removed redundant page header (now in CMSLayout)
- Simplified toolbar with search and create button
- Better mobile layout (flex-col → flex-row on sm+)
- Status messages in toolbar section

**Structure**:
```
CategoryLandingPagesPage
├── Toolbar Section
│   ├── Search Bar (flex-1, max-w-md)
│   ├── Create Button
│   └── Status Messages (error/success)
└── Pages Grid (flex-1, overflow-auto)
```

### Future Expansion

To add new navigation items:

1. **Add to navigation array**:
```javascript
const navigation = [
  // ... existing items
  {
    name: 'New Section',
    path: 'new-section',
    icon: NewIcon,
    description: 'Description here',
    comingSoon: false, // Set to false when ready
  },
];
```

2. **Create page component**:
```javascript
// NewSectionPage.jsx
export default function NewSectionPage({ authToken }) {
  return (
    <div className="h-full">
      {/* Your content */}
    </div>
  );
}
```

3. **Add route in CMSLayout**:
```javascript
<Routes>
  <Route path="/" element={<CategoryLandingPagesPage authToken={authToken} />} />
  <Route path="/new-section" element={<NewSectionPage authToken={authToken} />} />
</Routes>
```

### Accessibility

- Semantic HTML with proper ARIA labels
- Keyboard navigation support (via Catalyst)
- Screen reader friendly
- Focus management on modal open/close

### Performance

- Minimal re-renders (navigation array is static)
- Efficient active state checking
- No unnecessary state in sidebar
- Smooth CSS transitions

## Testing Checklist

- [ ] Desktop sidebar displays correctly
- [ ] Mobile hamburger menu works
- [ ] Active state indicator shows on current page
- [ ] Mobile sidebar closes after navigation
- [ ] Coming soon items don't navigate
- [ ] Search functionality works
- [ ] Create button opens modal
- [ ] Status messages display properly
- [ ] Dark mode works correctly
- [ ] Responsive breakpoints work (768px)

## Design Specifications

### Sidebar
- **Width**: 240px (desktop), full-width overlay (mobile)
- **Breakpoint**: 768px (md)
- **Background**: White / Zinc-900
- **Border**: Right border Zinc-200 / Zinc-800

### Mobile Overlay
- **Backdrop**: `bg-black/30`
- **Z-index**: 40 (backdrop), 50 (sidebar)
- **Animation**: 300ms ease-in-out slide

### Typography
- **Section Headings**: xs/6, medium, Zinc-500/Zinc-400
- **Item Labels**: base/6 (sm: sm/5), medium
- **Page Title**: xl, bold
- **Page Description**: sm, Zinc-500/Zinc-400

## Related Documentation

- **CMS Implementation**: `/home/pranav/pydanticebot/cms_plan.md`
- **Nested Metaobjects**: `/home/pranav/pydanticebot/nested_metaobjects_plan.md`
- **CMS Roadmap**: `/home/pranav/pydanticebot/cms_phases_roadmap.md`
- **AG-UI Protocol**: `/home/pranav/pydanticebot/ag-ui-docs.txt`

## Notes

- Uses React Router v6 patterns (useNavigate, useLocation)
- Follows EspressoBot design system (amber accent color)
- Matches existing Sidebar.jsx patterns
- Compatible with dark mode throughout
- No external state management needed (local state sufficient)
