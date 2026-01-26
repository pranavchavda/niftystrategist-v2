import React from 'react';
import {
  Navbar,
  NavbarSection,
  NavbarSpacer,
  NavbarItem,
} from './catalyst/navbar';
import { Avatar } from './catalyst/avatar';
import { Dropdown, DropdownButton, DropdownMenu, DropdownItem, DropdownDivider } from './catalyst/dropdown';
import {
  Cog6ToothIcon,
  ArrowRightStartOnRectangleIcon,
  SunIcon,
  MoonIcon,
  ChatBubbleLeftRightIcon,
  ChartBarIcon,
  CurrencyDollarIcon
} from '@heroicons/react/24/outline';
import logo from '../assets/eblogo-notext.webp';

function EspressoBotNavbar({ onLogout, darkMode, onToggleDarkMode }) {
  return (
    <Navbar className="border-b border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 px-4">
      {/* Logo */}
      <NavbarSection>
        <div className="flex items-center gap-3">
          <img
            src={logo}
            alt="EspressoBot"
            className="h-8 w-auto"
            draggable="false"
          />
          <div className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
            EspressoBot
          </div>
        </div>
      </NavbarSection>

      <NavbarSpacer />

      <NavbarSection>
        <div className="flex items-center gap-2">
          {/* Dark mode toggle */}
          <button
            onClick={onToggleDarkMode}
            className="p-2 text-zinc-500 hover:text-zinc-900 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:text-zinc-100 dark:hover:bg-zinc-800 rounded-md transition-colors"
            title={darkMode ? "Light mode" : "Dark mode"}
          >
            {darkMode ? (
              <SunIcon className="w-4 h-4" />
            ) : (
              <MoonIcon className="w-4 h-4" />
            )}
          </button>
        </div>
      </NavbarSection>
    </Navbar>
  );
}

export default EspressoBotNavbar;