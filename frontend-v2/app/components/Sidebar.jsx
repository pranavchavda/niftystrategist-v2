import React, { useState, useEffect, useMemo, useCallback } from "react";
import { Link, NavLink, useNavigate, useParams, useLocation } from "react-router";
import {
  MessageSquarePlus,
  Search,
  Pin,
  Trash2,
  MessageSquare,
  LayoutDashboard,
  Gift,
  DollarSign,
  Settings as SettingsIcon,
  Brain,
  CheckSquare,
  Loader2,
  LogOut,
  ChevronDown,
  FileText,
  FileEdit,
  Shield,
  HelpCircle,
  Cpu,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Zap,
  MenuIcon,
  StickyNote,
} from "lucide-react";
import TradingModeToggle from "./TradingModeToggle";
import { ArrowTrendingUpIcon } from '@heroicons/react/24/outline';
import { hasPermission, PERMISSIONS } from "../utils/permissions";
import {
  Sidebar as CatalystSidebar,
  SidebarHeader,
  SidebarBody,
  SidebarFooter,
  SidebarSection,
  SidebarHeading,
  SidebarDivider,
} from "./catalyst/sidebar";
import { Input } from "./catalyst/input";
import { Button } from "./catalyst/button";
import {
  Dropdown,
  DropdownButton,
  DropdownMenu,
  DropdownItem,
  DropdownDivider,
  DropdownLabel,
} from "./catalyst/dropdown";
import { Avatar } from "./catalyst/avatar";

/**
 * ConversationItem - Individual conversation list item
 * Adapts layout based on collapsed state
 */
function ConversationItem({
  conversation,
  isActive,
  onDelete,
  onPin,
  isPinned,
  isCollapsed,
}) {
  const [showActions, setShowActions] = useState(false);

  if (isCollapsed) {
    return (
      <div className="relative group px-2 py-1 flex justify-center">
        <Link
          to={`/chat/${conversation.id}`}
          className={`
            p-2 rounded-xl transition-all duration-200
            ${isActive
              ? "bg-zinc-100 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 shadow-sm ring-1 ring-zinc-200 dark:ring-zinc-700"
              : "text-zinc-400 dark:text-zinc-500 hover:bg-zinc-50 dark:hover:bg-zinc-900 hover:text-zinc-900 dark:hover:text-zinc-100"
            }
          `}
          title={conversation.title}
        >
          <MessageSquare className="w-5 h-5" />
        </Link>
        {/* Tooltip for collapsed state */}
        <div className="absolute left-full top-1/2 -translate-y-1/2 ml-2 px-2 py-1 bg-zinc-800 text-white text-xs rounded opacity-0 group-hover:opacity-100 pointer-events-none whitespace-nowrap z-50 transition-opacity duration-200">
          {conversation.title}
        </div>
      </div>
    );
  }

  // Expanded mode - full width with details
  return (
    <div
      className="group relative px-2"
      onMouseEnter={() => setShowActions(true)}
      onMouseLeave={() => setShowActions(false)}
      onTouchStart={() => setShowActions(true)}
    >
      <div
        className={`
        relative rounded-xl transition-all duration-200
        ${isActive
            ? "bg-zinc-100 dark:bg-zinc-800 shadow-sm ring-1 ring-zinc-200 dark:ring-zinc-700"
            : "hover:bg-zinc-50 dark:hover:bg-zinc-900 hover:shadow-sm"
          }
      `}
      >
        <Link
          to={`/chat/${conversation.id}`}
          className="block w-full text-left px-3 py-2.5 rounded-xl relative z-10"
        >
          <div className="flex items-start gap-3 pr-8">
            <MessageSquare
              className={`w-4 h-4 mt-0.5 flex-shrink-0 ${isActive
                ? "text-zinc-900 dark:text-zinc-100"
                : "text-zinc-400 dark:text-zinc-500"
                }`}
            />

            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1.5">
                {isPinned && (
                  <Pin className="w-3 h-3 text-amber-500 flex-shrink-0" />
                )}
                <span
                  className={`text-sm font-medium truncate ${isActive
                    ? "text-zinc-900 dark:text-zinc-100"
                    : "text-zinc-700 dark:text-zinc-300"
                    }`}
                  title={conversation.title}
                >
                  {conversation.title}
                </span>
              </div>

              {conversation.summary && (
                <div className="text-xs text-zinc-500 dark:text-zinc-400 truncate mt-0.5 leading-relaxed">
                  {conversation.summary}
                </div>
              )}

              <div className="text-xs text-zinc-400 dark:text-zinc-500 mt-1 font-medium">
                {new Date(conversation.updated_at).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </div>
            </div>
          </div>
        </Link>

        {/* Hover action buttons */}
        <div
          className={`
          absolute right-2 top-1/2 -translate-y-1/2
          flex items-center gap-0.5
          transition-opacity duration-200
          ${showActions || isActive ? "opacity-100 pointer-events-auto z-20" : "opacity-0 pointer-events-none z-0"}
        `}
        >
          <button
            onClick={(e) => {
              e.stopPropagation();
              onPin(conversation.id, !isPinned);
            }}
            className={`
              p-1.5 rounded-lg transition-all duration-200
              ${isPinned
                ? "text-amber-500 hover:bg-amber-50 dark:hover:bg-amber-900/20 shadow-sm"
                : "text-zinc-400 hover:text-amber-500 hover:bg-amber-50 dark:text-zinc-500 dark:hover:text-amber-400 dark:hover:bg-amber-900/20"
              }
            `}
            title={isPinned ? "Unpin" : "Pin"}
          >
            <Pin
              className={`w-3.5 h-3.5 ${isPinned ? "fill-amber-500" : ""}`}
            />
          </button>

          {showActions && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onDelete(conversation.id);
              }}
              className="p-1.5 text-zinc-400 hover:text-red-500 hover:bg-red-50 dark:text-zinc-500 dark:hover:text-red-400 dark:hover:bg-red-900/20 rounded-lg transition-all duration-200 shadow-sm"
              title="Delete"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * Enhanced collapsible Sidebar component using Catalyst UI
 *
 * Features:
 * - Two states: Expanded (320px) and Compact (72px)
 * - Smooth 200ms transitions
 * - Search functionality
 * - Pinned conversations
 * - Navigation items
 * - Conversation grouping by date
 * - localStorage persistence for pins and collapse state
 */
export default function Sidebar({
  authToken,
  refreshTrigger,
  onLogout,
  currentView = "chat",
  user = { name: "User", email: "user@example.com", avatarUrl: null, permissions: [] },
  isCollapsed = false,
  onToggleCollapse,
}) {
  const navigate = useNavigate();
  const location = useLocation();
  const { threadId: currentThreadId } = useParams();

  // Component state
  const [conversations, setConversations] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [pinnedIds, setPinnedIds] = useState(() => {
    try {
      const saved = localStorage.getItem("pinned-conversations");
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  // Persist pinned conversations
  useEffect(() => {
    try {
      localStorage.setItem("pinned-conversations", JSON.stringify(pinnedIds));
    } catch (error) {
      console.error("Failed to save pinned conversations:", error);
    }
  }, [pinnedIds]);

  // Load conversations
  useEffect(() => {
    loadConversations();
  }, [authToken, refreshTrigger]);

  const loadConversations = async () => {
    if (!authToken) return;

    try {
      const response = await fetch("/api/conversations/?limit=50", {
        headers: {
          Authorization: `Bearer ${authToken}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setConversations(data.conversations || []);
      } else {
        console.error("Failed to load conversations:", response.status);
      }
    } catch (error) {
      console.error("Failed to load conversations:", error);
    } finally {
      setIsLoading(false);
    }
  };

  // Handlers
  const handleDelete = useCallback(
    async (convId) => {
      if (!confirm("Delete this conversation?")) return;

      try {
        const response = await fetch(`/api/conversations/${convId}`, {
          method: "DELETE",
          headers: {
            Authorization: `Bearer ${authToken}`,
          },
        });

        if (response.ok) {
          setConversations((prev) => prev.filter((c) => c.id !== convId));
          // Redirect will happen automatically when user clicks another conversation
          // or via the Link in the UI - no need to programmatically navigate
        }
      } catch (error) {
        console.error("Failed to delete conversation:", error);
      }
    },
    [authToken],
  );

  const handlePin = useCallback((convId, shouldPin) => {
    setPinnedIds((prev) => {
      const set = new Set(prev);
      if (shouldPin) {
        set.add(convId);
      } else {
        set.delete(convId);
      }
      return Array.from(set);
    });
  }, []);

  // Removed handleNewChat - now using Link to="/chat" instead

  // Collapse toggle handler removed - sidebar is always expanded

  const handleNewTask = useCallback(() => {
    // Generate a new threadId immediately so scratchpad can work from the start
    const newThreadId = `thread_${Date.now()}`;
    navigate(`/chat/${newThreadId}`);
  }, [navigate]);

  // Memoized computations
  const pinnedSet = useMemo(() => new Set(pinnedIds), [pinnedIds]);

  const { pinnedConversations, recentConversations } = useMemo(() => {
    // Filter by search term
    const filtered = (conversations || []).filter((conv) => {
      if (!searchTerm) return true;
      return conv.title?.toLowerCase().includes(searchTerm.toLowerCase());
    });

    // Separate pinned and unpinned
    const pinned = filtered.filter((c) => pinnedSet.has(c.id));
    const unpinned = filtered.filter((c) => !pinnedSet.has(c.id));

    return {
      pinnedConversations: pinned,
      recentConversations: unpinned,
    };
  }, [conversations, searchTerm, pinnedSet]);

  // Group recent conversations by date
  const groupedRecent = useMemo(() => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    const lastWeek = new Date(today);
    lastWeek.setDate(lastWeek.getDate() - 7);

    const groups = {
      today: [],
      yesterday: [],
      lastWeek: [],
      older: [],
    };

    recentConversations.forEach((conv) => {
      const convDate = new Date(conv.updated_at);
      convDate.setHours(0, 0, 0, 0);

      if (convDate.getTime() === today.getTime()) {
        groups.today.push(conv);
      } else if (convDate.getTime() === yesterday.getTime()) {
        groups.yesterday.push(conv);
      } else if (convDate > lastWeek) {
        groups.lastWeek.push(conv);
      } else {
        groups.older.push(conv);
      }
    });

    return groups;
  }, [recentConversations]);

  return (
    <div className="relative h-[calc(100vh-4rem)] sm:h-full w-full">
      <CatalystSidebar className="h-full bg-white/85 z-50 shadow-md dark:bg-zinc-950/95 backdrop-blur-xl border-r border-zinc-200/60 dark:border-zinc-800/60">
        {/* Header Section */}
        <SidebarHeader className="pb-4">
          <div className={`flex items-center ${isCollapsed ? 'justify-center px-2' : 'px-3'} py-3`}>
            {isCollapsed ? (
              <Link to="/" className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 shadow-lg shadow-blue-500/25 ring-2 ring-blue-500/10 hover:scale-105 transition-transform">
                <ArrowTrendingUpIcon className="h-6 w-6 text-white" />
              </Link>
            ) : (
              <div className="flex items-center gap-3 px-2 w-full">
                <Link to="/" className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600">
                  <ArrowTrendingUpIcon className="h-5 w-5 text-white" />
                </Link>
                <div className="flex-1 min-w-0">
                  <div className="text-xs text-zinc-500 dark:text-zinc-400 font-medium flex items-center gap-1">

                  </div>
                </div>
                <button
                  onClick={onToggleCollapse}
                  className="p-1.5 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors hidden lg:block"
                  title="Collapse sidebar"
                >
                  <PanelLeftClose className="w-4 h-4" />
                </button>
              </div>
            )}

          </div>

          <SidebarSection className={`px-3 space-y-3 ${isCollapsed ? 'items-center' : ''}`}>
            {/* Search */}
            {isCollapsed && (
              <div className="flex justify-center mb-3">
                <button
                  onClick={onToggleCollapse}
                  className="p-2 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
                  title="Expand sidebar"
                >
                  <PanelLeftOpen className="w-5 h-5" />
                </button>
              </div>
            )}
            {!isCollapsed ? (
              <div className="relative">
                <Input
                  type="text"
                  placeholder="Search..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-9 pr-4 h-9 bg-zinc-50 dark:bg-zinc-900/50 border-zinc-200 dark:border-zinc-800 rounded-lg text-sm font-medium placeholder-zinc-500 dark:placeholder-zinc-400 focus:border-zinc-300 dark:focus:border-zinc-700 focus:ring-2 focus:ring-zinc-300/20 dark:focus:ring-zinc-700/20 transition-all duration-200"
                />
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400 dark:text-zinc-500 pointer-events-none" />
              </div>
            ) : (
              <button
                onClick={onToggleCollapse}
                className="p-2.5 rounded-xl bg-zinc-50 dark:bg-zinc-900/50 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
                title="Search"
              >
                <Search className="w-5 h-5" />
              </button>
            )}
            {/* Collapse Toggle (only visible when collapsed, otherwise in header) */}

            {/* Quick Navigation */}
            {isCollapsed ? (
              <Dropdown>
                <DropdownButton
                  as="div"
                  className="p-2.5 rounded-xl bg-zinc-50 dark:bg-zinc-900/50 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors cursor-pointer"
                  title="Quick Navigation"
                >
                  <MenuIcon className="w-5 h-5" />
                </DropdownButton>
                <DropdownMenu anchor="right start" className="z-[100] min-w-48">
                  {/* <DropdownHeading>Quick Navigation</DropdownHeading> */}
                  {hasPermission(user, PERMISSIONS.DASHBOARD_ACCESS) && (
                    <DropdownItem href="/dashboard">
                      <LayoutDashboard data-slot="icon" />
                      <DropdownLabel>Dashboard</DropdownLabel>
                    </DropdownItem>
                  )}
                  {hasPermission(user, PERMISSIONS.GOOGLE_WORKSPACE_ACCESS) && (
                    <DropdownItem href="/tasks">
                      <CheckSquare data-slot="icon" />
                      <DropdownLabel>Tasks</DropdownLabel>
                    </DropdownItem>
                  )}
                </DropdownMenu>
              </Dropdown>
            ) : (
              <div className="flex items-center gap-1 pt-1">
                {hasPermission(user, PERMISSIONS.DASHBOARD_ACCESS) && (
                  <NavLink
                    to="/dashboard"
                    title="Dashboard"
                    className={({ isActive }) =>
                      `p-2 rounded-lg transition-colors ${isActive
                        ? 'bg-amber-100 dark:bg-amber-900/30 text-amber-600 dark:text-amber-400'
                        : 'text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800'
                      }`
                    }
                  >
                    <LayoutDashboard className="w-4 h-4" />
                  </NavLink>
                )}
                <NavLink
                  to="/notes"
                  title="Notes"
                  className={({ isActive }) =>
                    `p-2 rounded-lg transition-colors ${isActive
                      ? 'bg-amber-100 dark:bg-amber-900/30 text-amber-600 dark:text-amber-400'
                      : 'text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800'
                    }`
                  }
                >
                  <StickyNote className="w-4 h-4" />
                </NavLink>
                <NavLink
                  to="/monitor"
                  title="Trade Monitor"
                  className={({ isActive }) =>
                    `p-2 rounded-lg transition-colors ${isActive
                      ? 'bg-amber-100 dark:bg-amber-900/30 text-amber-600 dark:text-amber-400'
                      : 'text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800'
                    }`
                  }
                >
                  <Shield className="w-4 h-4" />
                </NavLink>
                {hasPermission(user, PERMISSIONS.GOOGLE_WORKSPACE_ACCESS) && (
                  <NavLink
                    to="/tasks"
                    title="Tasks"
                    className={({ isActive }) =>
                      `p-2 rounded-lg transition-colors ${isActive
                        ? 'bg-amber-100 dark:bg-amber-900/30 text-amber-600 dark:text-amber-400'
                        : 'text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800'
                      }`
                    }
                  >
                    <CheckSquare className="w-4 h-4" />
                  </NavLink>
                )}
              </div>
            )}
            {/* New Task Button */}
            <Button
              onClick={handleNewTask}
              className={`
                justify-center bg-zinc-900 dark:bg-zinc-100 hover:bg-zinc-800 dark:hover:bg-zinc-200 text-white dark:text-zinc-900 shadow-lg hover:shadow-xl transition-all duration-200 hover:scale-[1.02] active:scale-[0.98] rounded-xl font-medium
                ${isCollapsed ? 'w-10 h-10 p-0' : 'w-full h-10'}
              `}
              title="New Task"
            >
              {isCollapsed ? (
                <Plus className="w-5 h-5" />
              ) : (
                <>
                  <MessageSquarePlus
                    data-slot="icon"
                    className="w-4 h-4 transition-transform duration-200 group-hover:rotate-90"
                  />
                  <span className="ml-2">New Task</span>
                </>
              )}
            </Button>


          </SidebarSection>
        </SidebarHeader>

        {/* Body - Conversations List */}
        <SidebarBody className="overflow-y-auto overflow-x-clip custom-scrollbar">
          {isLoading ? (
            <div className={`flex flex-col gap-3 ${isCollapsed ? 'items-center' : 'px-4'}`}>
              <Loader2 className="w-6 h-6 animate-spin text-zinc-400" />
              {!isCollapsed && (
                <span className="text-sm text-zinc-500">
                  Loading...
                </span>
              )}
            </div>
          ) : (
            <>
              {/* Pinned Conversations */}
              {pinnedConversations.length > 0 && (
                <SidebarSection>
                  {!isCollapsed && <SidebarHeading className="px-4">Pinned</SidebarHeading>}
                  <div className="flex flex-col space-y-1">
                    {pinnedConversations.map((conv) => (
                      <ConversationItem
                        key={conv.id}
                        conversation={conv}
                        isActive={conv.id === currentThreadId}
                        onDelete={handleDelete}
                        onPin={handlePin}
                        isPinned={true}
                        isCollapsed={isCollapsed}
                      />
                    ))}
                  </div>
                  {pinnedConversations.length > 0 &&
                    recentConversations.length > 0 && (
                      <SidebarDivider className="my-3 mx-4" />
                    )}
                </SidebarSection>
              )}

              {/* Recent Conversations - Grouped by Date */}
              <SidebarSection>
                {!isCollapsed && recentConversations.length > 0 && (
                  <SidebarHeading className="px-4">Recent</SidebarHeading>
                )}

                <div className="flex flex-col space-y-3">
                  {/* Today */}
                  {groupedRecent.today.length > 0 && (
                    <div className="space-y-1">
                      {!isCollapsed && (
                        <div className="text-xs font-medium text-zinc-500 dark:text-zinc-400 px-4 py-1">
                          Today
                        </div>
                      )}
                      <div className="flex flex-col space-y-1">
                        {groupedRecent.today.map((conv) => (
                          <ConversationItem
                            key={conv.id}
                            conversation={conv}
                            isActive={conv.id === currentThreadId}
                            onDelete={handleDelete}
                            onPin={handlePin}
                            isPinned={pinnedSet.has(conv.id)}
                            isCollapsed={isCollapsed}
                          />
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Yesterday */}
                  {groupedRecent.yesterday.length > 0 && (
                    <div className="space-y-1">
                      {!isCollapsed && (
                        <div className="text-xs font-medium text-zinc-500 dark:text-zinc-400 px-4 py-1">
                          Yesterday
                        </div>
                      )}
                      <div className="flex flex-col space-y-1">
                        {groupedRecent.yesterday.map((conv) => (
                          <ConversationItem
                            key={conv.id}
                            conversation={conv}
                            isActive={conv.id === currentThreadId}
                            onDelete={handleDelete}
                            onPin={handlePin}
                            isPinned={pinnedSet.has(conv.id)}
                            isCollapsed={isCollapsed}
                          />
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Previous 7 Days */}
                  {groupedRecent.lastWeek.length > 0 && (
                    <div className="space-y-1">
                      {!isCollapsed && (
                        <div className="text-xs font-medium text-zinc-500 dark:text-zinc-400 px-4 py-1">
                          Previous 7 Days
                        </div>
                      )}
                      <div className="flex flex-col space-y-1">
                        {groupedRecent.lastWeek.map((conv) => (
                          <ConversationItem
                            key={conv.id}
                            conversation={conv}
                            isActive={conv.id === currentThreadId}
                            onDelete={handleDelete}
                            onPin={handlePin}
                            isPinned={pinnedSet.has(conv.id)}
                            isCollapsed={isCollapsed}
                          />
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Older */}
                  {groupedRecent.older.length > 0 && (
                    <div className="space-y-1">
                      {!isCollapsed && (
                        <div className="text-xs font-medium text-zinc-500 dark:text-zinc-400 px-4 py-1">
                          Older
                        </div>
                      )}
                      <div className="flex flex-col space-y-1">
                        {groupedRecent.older.map((conv) => (
                          <ConversationItem
                            key={conv.id}
                            conversation={conv}
                            isActive={conv.id === currentThreadId}
                            onDelete={handleDelete}
                            onPin={handlePin}
                            isPinned={pinnedSet.has(conv.id)}
                            isCollapsed={isCollapsed}
                          />
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Empty State */}
                  {recentConversations.length === 0 &&
                    pinnedConversations.length === 0 && (
                      <div className={`px-4 py-12 text-center ${isCollapsed ? 'hidden' : ''}`}>
                        <MessageSquare className="w-8 h-8 mx-auto mb-3 text-zinc-300 dark:text-zinc-700" />
                        <p className="text-sm text-zinc-500 dark:text-zinc-400">
                          {searchTerm
                            ? "No conversations found"
                            : "No conversations yet"}
                        </p>
                      </div>
                    )}
                </div>
              </SidebarSection>
            </>
          )}
        </SidebarBody>

        {/* Footer - Trading Mode Toggle & User Dropdown */}
        <SidebarFooter className="pt-2 pb-3">
          <SidebarDivider className="bg-zinc-200 dark:bg-zinc-800 mb-3 mx-4" />

          {/* Trading Mode Toggle */}
          <TradingModeToggle authToken={authToken} isCollapsed={isCollapsed} />

          <SidebarDivider className="bg-zinc-200 dark:bg-zinc-800 my-2 mx-4" />

          <SidebarSection className={isCollapsed ? 'px-2' : 'px-3'}>
            <Dropdown
              as="div"
              className="bg-zinc-100/10 backdrop-blur-xl transition-all duration-200"
            >
              <DropdownButton as="div" className={`cursor-pointer ${isCollapsed ? '' : '-mx-2'}`}>
                <div className={`flex items-center ${isCollapsed ? 'justify-center' : 'gap-3 px-3'} py-2.5 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-all duration-200 group`}>
                  <Avatar
                    src={user.avatarUrl}
                    initials={user.name?.charAt(0) || "U"}
                    className="size-9 ring-2 ring-zinc-200 dark:ring-zinc-700 group-hover:ring-amber-500 dark:group-hover:ring-amber-400 transition-all duration-200"
                  />
                  {!isCollapsed && (
                    <>
                      <div className="flex-1 min-w-0 text-left">
                        <div className="text-sm font-semibold text-zinc-900 dark:text-zinc-100 truncate">
                          {user.name}
                        </div>
                        <div className="text-xs text-zinc-500 dark:text-zinc-400 truncate">
                          {user.email}
                        </div>
                      </div>
                      <ChevronDown className="w-4 h-4 text-zinc-400 group-hover:text-zinc-600 dark:group-hover:text-zinc-300 transition-colors flex-shrink-0" />
                    </>
                  )}
                </div>
              </DropdownButton>
              <DropdownMenu anchor="bottom start">
                {/* Additional Features (not in Quick Nav) */}
                {hasPermission(user, PERMISSIONS.MEMORY_ACCESS) && (
                  <DropdownItem href="/memory">
                    <Brain data-slot="icon" />
                    <DropdownLabel>Memory</DropdownLabel>
                  </DropdownItem>
                )}
                <DropdownItem href="/notes">
                  <StickyNote data-slot="icon" />
                  <DropdownLabel>Notes</DropdownLabel>
                </DropdownItem>
                {/* Seasonal trackers removed - BFCM and Boxing Week */}
                {/* Admin Section */}
                {(hasPermission(user, PERMISSIONS.ADMIN_MANAGE_USERS) || hasPermission(user, PERMISSIONS.ADMIN_MANAGE_ROLES)) && (
                  <>
                    <DropdownDivider />
                    <DropdownItem href="/admin/docs">
                      <FileText data-slot="icon" />
                      <DropdownLabel>Docs Admin</DropdownLabel>
                    </DropdownItem>
                    <DropdownItem href="/admin/users">
                      <Shield data-slot="icon" />
                      <DropdownLabel>Users & Roles</DropdownLabel>
                    </DropdownItem>
                    <DropdownItem href="/admin/models">
                      <Cpu data-slot="icon" />
                      <DropdownLabel>AI Models</DropdownLabel>
                    </DropdownItem>
                  </>
                )}
                {/* Account Section */}
                <DropdownDivider />
                {hasPermission(user, PERMISSIONS.SETTINGS_ACCESS) && (
                  <DropdownItem href="/settings">
                    <SettingsIcon data-slot="icon" />
                    <DropdownLabel>Settings</DropdownLabel>
                  </DropdownItem>
                )}
                {hasPermission(user, PERMISSIONS.SETTINGS_ACCESS) && (
                  <DropdownItem href="/automations">
                    <Zap data-slot="icon" />
                    <DropdownLabel>Automations</DropdownLabel>
                  </DropdownItem>
                )}
                {hasPermission(user, PERMISSIONS.SETTINGS_ACCESS) && (
                  <DropdownItem href="/monitor">
                    <Shield data-slot="icon" />
                    <DropdownLabel>Trade Monitor</DropdownLabel>
                  </DropdownItem>
                )}
                <DropdownDivider />
                <DropdownItem href="/help">
                  <HelpCircle data-slot="icon" />
                  <DropdownLabel>Help & Documentation</DropdownLabel>
                </DropdownItem>
                <DropdownItem onClick={onLogout}>
                  <LogOut data-slot="icon" />
                  <DropdownLabel>Sign out</DropdownLabel>
                </DropdownItem>
              </DropdownMenu>
            </Dropdown>
          </SidebarSection>
        </SidebarFooter>
      </CatalystSidebar>
    </div>
  );
}

