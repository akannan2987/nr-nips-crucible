import { useState, useEffect } from 'react'
import { Outlet, Link, useLocation } from 'react-router-dom'
import { getChemicalNotices, getInstance } from '../services/api'
import { BASE_TITLE, styleFor } from './instanceStyle'
import { useAuth } from './AuthGate'
import {
  BeakerIcon,
  HomeIcon,
  DocumentPlusIcon,
  EyeIcon,
  Bars3Icon,
  XMarkIcon,
  ChartBarIcon,
  ExclamationTriangleIcon,
  CubeIcon,
  CommandLineIcon,
  FlagIcon,
  ArrowRightOnRectangleIcon,
} from '@heroicons/react/24/outline'

// SH-13: the instance colours and the base tab title live in instanceStyle.js,
// shared with the login page (SH-3a).

const navigation = [
  { name: 'Dashboard', href: '/', icon: HomeIcon },
  {
    name: 'Chemical Registry',
    icon: BeakerIcon,
    children: [
      { name: 'View Chemical Registry', href: '/chemicals', icon: EyeIcon },
      { name: 'Upload Chemicals (ELN)', href: '/chemicals/upload', icon: DocumentPlusIcon },
      // CR-10: everything the registry wants a person to look at, with the buttons to act
      { name: 'Needs attention', href: '/chemicals/attention', icon: FlagIcon, badge: 'attention' },
    ],
  },
  {
    name: 'Sample Management',
    icon: CubeIcon,
    children: [
      { name: 'View Samples', href: '/samples', icon: EyeIcon },
      { name: 'Upload Samples (ELN)', href: '/samples/upload', icon: DocumentPlusIcon },
    ],
  },
  {
    name: 'Screening Data',
    icon: ChartBarIcon,
    children: [
      { name: 'View Screening Data', href: '/screening', icon: EyeIcon },
      { name: 'Upload Screening Data (ELN)', href: '/screening/upload', icon: DocumentPlusIcon },
    ],
  },
  { name: 'Query', href: '/query', icon: CommandLineIcon },
  {
    name: 'Toxicology',
    icon: ExclamationTriangleIcon,
    children: [
      { name: 'View Toxicology Data', href: '/toxicology', icon: EyeIcon },
      { name: 'Upload Toxicology (ELN)', href: '/toxicology/upload', icon: DocumentPlusIcon },
    ],
  },
]

function classNames(...classes) {
  return classes.filter(Boolean).join(' ')
}

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [instance, setInstance] = useState(null)
  useEffect(() => {
    // Once per page load: the instance never changes while the tab is open.
    getInstance()
      .then((r) => {
        setInstance(r.data)
        document.title = `[${r.data.label}] ${BASE_TITLE}`
      })
      .catch(() => setInstance(null))
  }, [])
  const instanceStyle = styleFor(instance)
  // SH-3a: with a login on, the top bar offers to sign out (forget this
  // browser's cookie); with the login off there is nothing to sign out of.
  const auth = useAuth()

  const [expandedMenu, setExpandedMenu] = useState(null)
  const location = useLocation()
  // CR-10: the count on the "Needs attention" item, refreshed on every page change
  // so a merge or a review mark shows in the sidebar without a reload.
  const [attention, setAttention] = useState(0)
  useEffect(() => {
    let alive = true
    getChemicalNotices()
      .then(({ data }) => { if (alive) setAttention(data?.attention || 0) })
      .catch(() => { if (alive) setAttention(0) })
    return () => { alive = false }
  }, [location.pathname])
  const badgeFor = (child) =>
    child.badge === 'attention' && attention > 0 ? (
      <span className="ml-auto text-[11px] font-semibold bg-amber-100 text-amber-800 rounded-full px-2 py-0.5">
        {attention.toLocaleString()}
      </span>
    ) : null

  const toggleMenu = (name) => {
    setExpandedMenu(expandedMenu === name ? null : name)
  }

  const isActive = (href) => location.pathname === href

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Mobile sidebar backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-gray-600 bg-opacity-75 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Mobile sidebar */}
      <div
        className={classNames(
          'fixed inset-y-0 left-0 z-50 w-72 bg-white shadow-xl transform transition-transform duration-300 lg:hidden',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        <div className="flex h-16 items-center justify-between px-4 border-b">
          <div className="flex items-center">
            <BeakerIcon className="h-8 w-8 text-pandora-600" />
            {/* Rebrand: mobile sidebar shows the new Crucible name */}
            <span className="ml-2 text-xl font-bold text-gray-800">Crucible</span>
          </div>
          <button onClick={() => setSidebarOpen(false)}>
            <XMarkIcon className="h-6 w-6 text-gray-500" />
          </button>
        </div>
        <nav className="mt-4 px-2">
          {navigation.map((item) => (
            <div key={item.name}>
              {item.children ? (
                <>
                  <button
                    onClick={() => toggleMenu(item.name)}
                    className="w-full flex items-center justify-between px-3 py-2 text-gray-700 rounded-lg hover:bg-gray-100"
                  >
                    <div className="flex items-center">
                      <item.icon className="h-5 w-5 mr-3 text-gray-500" />
                      {item.name}
                    </div>
                    <svg
                      className={classNames(
                        'h-4 w-4 transition-transform',
                        expandedMenu === item.name ? 'rotate-180' : ''
                      )}
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>
                  {expandedMenu === item.name && (
                    <div className="ml-8 mt-1 space-y-1">
                      {item.children.map((child) => (
                        <Link
                          key={child.href}
                          to={child.href}
                          onClick={() => setSidebarOpen(false)}
                          className={classNames(
                            'flex items-center px-3 py-2 text-sm rounded-lg',
                            isActive(child.href)
                              ? 'bg-pandora-50 text-pandora-700'
                              : 'text-gray-600 hover:bg-gray-100'
                          )}
                        >
                          <child.icon className="h-4 w-4 mr-2" />
                          {child.name}
                          {badgeFor(child)}
                        </Link>
                      ))}
                    </div>
                  )}
                </>
              ) : (
                <Link
                  to={item.href}
                  onClick={() => setSidebarOpen(false)}
                  className={classNames(
                    'flex items-center px-3 py-2 rounded-lg',
                    isActive(item.href)
                      ? 'bg-pandora-50 text-pandora-700'
                      : 'text-gray-700 hover:bg-gray-100'
                  )}
                >
                  <item.icon className="h-5 w-5 mr-3 text-gray-500" />
                  {item.name}
                </Link>
              )}
            </div>
          ))}
        </nav>
      </div>

      {/* Desktop sidebar */}
      <div className="hidden lg:fixed lg:inset-y-0 lg:flex lg:w-72 lg:flex-col">
        <div className="flex flex-col flex-grow bg-white border-r shadow-sm">
          {/* Logo */}
          <div className="flex h-16 items-center px-4 border-b bg-gradient-to-r from-pandora-600 to-pandora-700">
            <BeakerIcon className="h-8 w-8 text-white" />
            {/* Rebrand: desktop sidebar logo — "Crucible" headline with the full
                "Pandora Toolbox Enhancement" tagline underneath */}
            <div className="ml-3">
              <div>
                <span className="text-lg font-bold text-white">Crucible</span>
                <span className="ml-2 text-xs bg-white/20 text-white px-2 py-0.5 rounded">v2.0</span>
              </div>
              <div className="text-[11px] text-white/80 leading-tight">Pandora Toolbox Enhancement</div>
            </div>
          </div>

          {/* Navigation */}
          <nav className="flex-1 mt-4 px-3 space-y-1 overflow-y-auto">
            {navigation.map((item) => (
              <div key={item.name}>
                {item.children ? (
                  <>
                    <button
                      onClick={() => toggleMenu(item.name)}
                      className="w-full flex items-center justify-between px-3 py-2.5 text-gray-700 rounded-lg hover:bg-gray-100 transition-colors"
                    >
                      <div className="flex items-center">
                        <item.icon className="h-5 w-5 mr-3 text-gray-500" />
                        <span className="font-medium">{item.name}</span>
                      </div>
                      <svg
                        className={classNames(
                          'h-4 w-4 transition-transform duration-200',
                          expandedMenu === item.name ? 'rotate-180' : ''
                        )}
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                      </svg>
                    </button>
                    <div
                      className={classNames(
                        'overflow-hidden transition-all duration-200',
                        expandedMenu === item.name ? 'max-h-60' : 'max-h-0'
                      )}
                    >
                      <div className="ml-8 mt-1 space-y-1 pb-2">
                        {item.children.map((child) => (
                          <Link
                            key={child.href}
                            to={child.href}
                            className={classNames(
                              'flex items-center px-3 py-2 text-sm rounded-lg transition-colors',
                              isActive(child.href)
                                ? 'bg-pandora-50 text-pandora-700 font-medium'
                                : 'text-gray-600 hover:bg-gray-100'
                            )}
                          >
                            <child.icon className="h-4 w-4 mr-2" />
                            {child.name}
                            {badgeFor(child)}
                          </Link>
                        ))}
                      </div>
                    </div>
                  </>
                ) : (
                  <Link
                    to={item.href}
                    className={classNames(
                      'flex items-center px-3 py-2.5 rounded-lg transition-colors',
                      isActive(item.href)
                        ? 'bg-pandora-50 text-pandora-700 font-medium'
                        : 'text-gray-700 hover:bg-gray-100'
                    )}
                  >
                    <item.icon className="h-5 w-5 mr-3 text-gray-500" />
                    {item.name}
                  </Link>
                )}
              </div>
            ))}
          </nav>

          {/* Footer */}
          <div className="p-4 border-t">
            <div className="text-xs text-gray-500 text-center">
              Chemical & Sample Management System
              <br />
              <span className="text-gray-400">© 2026 Computational Sciences - NIPS</span>
            </div>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="lg:pl-72">
        {/* Top bar */}
        <div className={`sticky top-0 z-30 flex h-16 items-center shadow-sm px-4 lg:px-8 ${instanceStyle.bar}`}>
          <button
            onClick={() => setSidebarOpen(true)}
            className="lg:hidden -ml-2 p-2 text-gray-500 hover:text-gray-700"
          >
            <Bars3Icon className="h-6 w-6" />
          </button>
          <div className="flex-1 flex items-center justify-between">
            <h1 className="flex items-center text-lg font-semibold text-gray-800 lg:text-xl">
              Chemical & Sample Management
              {instance && (
                <span
                  className={`ml-3 rounded-full border px-2.5 py-0.5 text-xs font-semibold tracking-wide ${instanceStyle.pill}`}
                  title={instanceStyle.title}
                  data-testid="instance-label"
                >
                  {instance.label}
                </span>
              )}
            </h1>
            <div className="flex items-center space-x-4">
              {auth.mode !== 'off' && (
                <button
                  onClick={auth.signOut}
                  className="flex items-center rounded-lg border bg-white px-2.5 py-1 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-50"
                  title="Forget this browser's login; the sign-in page comes back"
                  data-testid="sign-out"
                >
                  <ArrowRightOnRectangleIcon className="h-4 w-4 mr-1.5" />
                  Sign out
                </button>
              )}
              {/* Port is read from the browser's own URL instead of being
                  hardcoded, so this stays correct on any host/port */}
              <span className="text-sm text-gray-500">
                Running on port {window.location.port || (window.location.protocol === 'https:' ? '443' : '80')}
              </span>
            </div>
          </div>
        </div>

        {/* Page content */}
        <main className="p-4 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
