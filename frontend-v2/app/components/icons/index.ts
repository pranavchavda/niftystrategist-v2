/**
 * Icon System
 *
 * Standardized icon exports using Lucide React.
 * This barrel export ensures consistent icon usage across the app.
 *
 * Usage:
 * import { IconChat, IconSettings, IconDashboard } from '~/components/icons';
 *
 * Naming Convention:
 * - All exports prefixed with 'Icon' for clarity
 * - Names describe the icon's purpose, not its shape
 */

// Re-export from Lucide with standardized names
export {
  // Navigation & UI
  Menu as IconMenu,
  X as IconClose,
  ChevronDown as IconChevronDown,
  ChevronUp as IconChevronUp,
  ChevronLeft as IconChevronLeft,
  ChevronRight as IconChevronRight,
  ArrowLeft as IconArrowLeft,
  ArrowRight as IconArrowRight,
  ArrowUp as IconArrowUp,
  ArrowDown as IconArrowDown,
  ExternalLink as IconExternalLink,
  MoreHorizontal as IconMore,
  MoreVertical as IconMoreVertical,

  // Communication
  MessageSquare as IconChat,
  MessageSquarePlus as IconNewChat,
  Send as IconSend,
  Mail as IconMail,
  Bell as IconNotification,
  BellOff as IconNotificationOff,

  // Actions
  Plus as IconAdd,
  PlusCircle as IconAddCircle,
  Minus as IconRemove,
  Trash2 as IconDelete,
  Edit as IconEdit,
  Edit3 as IconEditPencil,
  Copy as IconCopy,
  Check as IconCheck,
  CheckCircle as IconCheckCircle,
  XCircle as IconXCircle,
  AlertCircle as IconAlert,
  AlertTriangle as IconWarning,
  Info as IconInfo,
  HelpCircle as IconHelp,
  RefreshCw as IconRefresh,
  RotateCcw as IconUndo,
  RotateCw as IconRedo,
  Download as IconDownload,
  Upload as IconUpload,
  Share2 as IconShare,

  // Files & Documents
  File as IconFile,
  FileText as IconFileText,
  FileCode as IconFileCode,
  FileImage as IconFileImage,
  Folder as IconFolder,
  FolderOpen as IconFolderOpen,
  Archive as IconArchive,
  Clipboard as IconClipboard,
  ClipboardCheck as IconClipboardCheck,

  // Data & Analytics
  BarChart as IconChart,
  BarChart2 as IconBarChart,
  LineChart as IconLineChart,
  PieChart as IconPieChart,
  TrendingUp as IconTrendingUp,
  TrendingDown as IconTrendingDown,
  Activity as IconActivity,

  // Users & Auth
  User as IconUser,
  Users as IconUsers,
  UserPlus as IconUserAdd,
  UserMinus as IconUserRemove,
  UserCheck as IconUserCheck,
  Shield as IconShield,
  ShieldCheck as IconShieldCheck,
  Lock as IconLock,
  Unlock as IconUnlock,
  Key as IconKey,
  LogIn as IconLogin,
  LogOut as IconLogout,

  // Settings & Configuration
  Settings as IconSettings,
  Settings2 as IconSettingsAlt,
  Sliders as IconSliders,
  SlidersHorizontal as IconSlidersHorizontal,
  ToggleLeft as IconToggleOff,
  ToggleRight as IconToggleOn,

  // Search & Filter
  Search as IconSearch,
  Filter as IconFilter,
  SortAsc as IconSortAsc,
  SortDesc as IconSortDesc,

  // Layout & View
  LayoutDashboard as IconDashboard,
  LayoutGrid as IconGrid,
  List as IconList,
  Columns as IconColumns,
  Maximize as IconMaximize,
  Minimize as IconMinimize,
  Sidebar as IconSidebar,
  PanelLeft as IconPanelLeft,
  PanelRight as IconPanelRight,

  // Time & Calendar
  Calendar as IconCalendar,
  Clock as IconClock,
  Timer as IconTimer,
  History as IconHistory,

  // Media
  Image as IconImage,
  Images as IconImages,
  Camera as IconCamera,
  Video as IconVideo,
  Music as IconMusic,
  Volume2 as IconVolume,
  VolumeX as IconMute,
  Play as IconPlay,
  Pause as IconPause,
  Square as IconStop,
  SkipBack as IconSkipBack,
  SkipForward as IconSkipForward,

  // Theme
  Sun as IconSun,
  Moon as IconMoon,
  Monitor as IconMonitor,
  Palette as IconPalette,

  // AI & Tech
  Bot as IconBot,
  Cpu as IconCpu,
  Brain as IconBrain,
  Sparkles as IconSparkles,
  Wand2 as IconWand,
  Zap as IconZap,
  Lightbulb as IconLightbulb,
  Rocket as IconRocket,
  Code as IconCode,
  Code2 as IconCode2,
  Terminal as IconTerminal,
  Database as IconDatabase,
  Server as IconServer,
  Cloud as IconCloud,
  CloudOff as IconCloudOff,
  Wifi as IconWifi,
  WifiOff as IconWifiOff,
  Globe as IconGlobe,
  Link as IconLink,
  Link2 as IconLink2,
  Unlink as IconUnlink,

  // Commerce
  ShoppingCart as IconCart,
  ShoppingBag as IconBag,
  CreditCard as IconCreditCard,
  DollarSign as IconDollar,
  Tag as IconTag,
  Tags as IconTags,
  Package as IconPackage,
  Truck as IconTruck,
  Store as IconStore,

  // Social
  Heart as IconHeart,
  Star as IconStar,
  ThumbsUp as IconThumbsUp,
  ThumbsDown as IconThumbsDown,
  MessageCircle as IconComment,

  // Content
  BookOpen as IconBook,
  Bookmark as IconBookmark,
  BookmarkPlus as IconBookmarkAdd,
  Newspaper as IconNews,
  Rss as IconRss,
  Hash as IconHash,
  AtSign as IconAt,

  // Status & Indicators
  Loader2 as IconLoader,
  Circle as IconCircle,
  CircleDot as IconCircleDot,
  CheckCircle2 as IconSuccess,
  XOctagon as IconError,
  AlertOctagon as IconDanger,
  Ban as IconBan,
  Eye as IconEye,
  EyeOff as IconEyeOff,

  // Misc
  Pin as IconPin,
  Paperclip as IconAttachment,
  Scissors as IconCut,
  Eraser as IconErase,
  Move as IconMove,
  GripVertical as IconGrip,
  MoreHorizontal as IconDrag,
  Maximize2 as IconExpand,
  Minimize2 as IconCollapse,
  Home as IconHome,
  Building as IconBuilding,
  MapPin as IconLocation,
  Navigation as IconNavigation,
  Compass as IconCompass,
} from 'lucide-react';

// Re-export the Icon component type for convenience
export type { LucideIcon } from 'lucide-react';

/**
 * Icon sizes (use with className or style)
 *
 * Usage:
 * <IconChat className={iconSizes.sm} />
 * <IconSettings className={iconSizes.md} />
 */
export const iconSizes = {
  xs: 'w-3 h-3',
  sm: 'w-4 h-4',
  md: 'w-5 h-5',
  lg: 'w-6 h-6',
  xl: 'w-8 h-8',
  '2xl': 'w-10 h-10',
} as const;

/**
 * Icon colors (use with className)
 *
 * Usage:
 * <IconCheck className={`${iconSizes.md} ${iconColors.success}`} />
 */
export const iconColors = {
  default: 'text-zinc-600 dark:text-zinc-400',
  muted: 'text-zinc-400 dark:text-zinc-500',
  primary: 'text-zinc-900 dark:text-zinc-100',
  accent: 'text-blue-600 dark:text-blue-400',
  success: 'text-emerald-600 dark:text-emerald-400',
  warning: 'text-amber-600 dark:text-amber-400',
  error: 'text-red-600 dark:text-red-400',
  info: 'text-blue-600 dark:text-blue-400',
  brand: 'text-amber-700 dark:text-amber-400',
} as const;
