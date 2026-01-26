import React, { useState, useRef, useEffect } from 'react';
import {
    ChevronDownIcon,
    WrenchScrewdriverIcon,
    ArrowPathRoundedSquareIcon,
    SparklesIcon,
    CheckCircleIcon,
    ListBulletIcon,
} from '@heroicons/react/24/outline';

/**
 * Actions dropdown component for chat controls
 * Consolidates: Tools, Fork, Extract, Auto Mode, TODO Mode
 */
const ActionsDropdown = ({
    // Callbacks
    onViewTools,
    onForkConversation,
    onExtractMemories,
    // State
    isForkingConversation = false,
    isExtractingMemories = false,
    extractionSuccess = false,
    useTodo = false,
    onToggleTodo,
    // Display conditions
    showForkAndExtract = false,
    // Auto Mode (HITL) - if provided, will show toggle
    hitlComponent = null,
}) => {
    const [isOpen, setIsOpen] = useState(false);
    const dropdownRef = useRef(null);

    // Close dropdown when clicking outside
    useEffect(() => {
        const handleClickOutside = (event) => {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
                setIsOpen(false);
            }
        };

        if (isOpen) {
            document.addEventListener('mousedown', handleClickOutside);
        }

        return () => {
            document.removeEventListener('mousedown', handleClickOutside);
        };
    }, [isOpen]);

    const handleActionClick = (action) => {
        action();
        setIsOpen(false);
    };

    return (
        <div className="relative" ref={dropdownRef}>
            {/* Dropdown trigger button */}
            <button
                onClick={() => setIsOpen(!isOpen)}
                className={`inline-flex items-center gap-2 px-3 md:px-4 py-2 rounded-lg text-xs md:text-sm font-medium transition-all duration-200 ${isOpen
                    ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 border border-blue-300 dark:border-blue-700'
                    : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 border border-zinc-200 dark:border-zinc-700 hover:bg-zinc-200 dark:hover:bg-zinc-700'
                    }`}
                aria-label="Actions menu"
                aria-expanded={isOpen}
            >
                <span>Actions</span>
                <ChevronDownIcon
                    className={`w-4 h-4 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''
                        }`}
                />
            </button>

            {/* Dropdown menu */}
            {isOpen && (
                <div className="absolute right-0 bottom-full mb-2 w-56 sm:w-64 bg-zinc-50/70 dark:bg-zinc-800/70 border border-zinc-200 dark:border-zinc-700 rounded-lg shadow-lg overflow-hidden z-50 animate-slide-in-bottom backdrop-blur-md">
                    <div className="py-1">
                        {/* Tools */}
                        <button
                            onClick={() => handleActionClick(onViewTools)}
                            className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-zinc-700 dark:text-zinc-300 hover:bg-zinc-50 dark:hover:bg-zinc-800 transition-colors"
                        >
                            <WrenchScrewdriverIcon className="w-4 h-4 text-zinc-500 dark:text-zinc-400" />
                            <div className="flex-1 text-left">
                                <div className="font-medium">View Tools</div>
                                <div className="text-xs text-zinc-500 dark:text-zinc-400">
                                    See available tools and agents
                                </div>
                            </div>
                        </button>

                        {/* Divider if fork/extract are shown */}
                        {showForkAndExtract && (
                            <div className="border-t border-zinc-200 dark:border-zinc-700 my-1" />
                        )}

                        {/* Fork Conversation */}
                        {showForkAndExtract && (
                            <button
                                onClick={() => handleActionClick(onForkConversation)}
                                disabled={isForkingConversation}
                                className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-zinc-700 dark:text-zinc-300 hover:bg-zinc-50 dark:hover:bg-zinc-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                <ArrowPathRoundedSquareIcon className="w-4 h-4 text-blue-500 dark:text-blue-400" />
                                <div className="flex-1 text-left">
                                    <div className="font-medium">
                                        {isForkingConversation ? 'Forking...' : 'Fork Conversation'}
                                    </div>
                                    <div className="text-xs text-zinc-500 dark:text-zinc-400">
                                        Start fresh with this context
                                    </div>
                                </div>
                            </button>
                        )}

                        {/* Extract Memories */}
                        {showForkAndExtract && (
                            <button
                                onClick={() => handleActionClick(onExtractMemories)}
                                disabled={isExtractingMemories}
                                className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-zinc-700 dark:text-zinc-300 hover:bg-zinc-50 dark:hover:bg-zinc-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                <SparklesIcon
                                    className={`w-4 h-4 ${extractionSuccess
                                        ? 'text-green-500 dark:text-green-400'
                                        : 'text-purple-500 dark:text-purple-400'
                                        }`}
                                />
                                <div className="flex-1 text-left">
                                    <div className="font-medium">
                                        {isExtractingMemories
                                            ? 'Extracting...'
                                            : extractionSuccess
                                                ? '✓ Memories Extracted'
                                                : 'Extract Memories'}
                                    </div>
                                    <div className="text-xs text-zinc-500 dark:text-zinc-400">
                                        Save insights from this chat
                                    </div>
                                </div>
                            </button>
                        )}

                        {/* Divider before toggles */}
                        <div className="border-t border-zinc-200 dark:border-zinc-700 my-1" />

                        {/* Approval Mode (HITL) Toggle - if provided */}
                        {hitlComponent && (
                            <div className="px-4 py-2.5">
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-3">
                                        <CheckCircleIcon className="w-4 h-4 text-blue-500 dark:text-blue-400" />
                                        <div className="text-sm">
                                            <div className="font-medium text-zinc-700 dark:text-zinc-300">
                                                Approval Mode
                                            </div>
                                            <div className="text-xs text-zinc-500 dark:text-zinc-400">
                                                Ask before executing tools
                                            </div>
                                        </div>
                                    </div>
                                    <div className="ml-auto">{hitlComponent}</div>
                                </div>
                            </div>
                        )}

                        {/* TODO Mode Toggle */}
                        <div className="px-4 py-2.5">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                    <ListBulletIcon className="w-4 h-4 text-blue-500 dark:text-blue-400" />
                                    <div className="text-sm">
                                        <div className="font-medium text-zinc-700 dark:text-zinc-300">
                                            TODO Mode
                                        </div>
                                        <div className="text-xs text-zinc-500 dark:text-zinc-400">
                                            Track tasks and progress
                                        </div>
                                    </div>
                                </div>
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        onToggleTodo();
                                    }}
                                    className={`${useTodo ? 'bg-blue-600' : 'bg-zinc-300 dark:bg-zinc-700'
                                        } relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-offset-2 dark:focus:ring-offset-zinc-900`}
                                    aria-label="Toggle TODO mode"
                                >
                                    <span
                                        className={`${useTodo ? 'translate-x-6' : 'translate-x-1'
                                            } inline-block h-4 w-4 transform rounded-full bg-white transition-transform shadow-sm`}
                                    />
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default ActionsDropdown;
