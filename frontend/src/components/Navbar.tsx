'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { BarChart3, FlaskConical } from 'lucide-react'

const links = [
  { href: '/', label: 'Dashboard' },
  { href: '/analysis', label: 'Analysis' },
]

export default function Navbar() {
  const path = usePathname()
  return (
    <header className="fixed top-0 inset-x-0 z-50 border-b border-slate-800 bg-[#020817]/90 backdrop-blur">
      <div className="mx-auto max-w-7xl px-6 flex h-16 items-center justify-between">
        <Link href="/" className="flex items-center gap-2 font-bold text-lg text-white">
          <BarChart3 className="h-5 w-5 text-violet-500" />
          YouArgue
          <span className="ml-1 text-xs font-normal text-slate-500 hidden sm:block">
            Political Opinion Monitoring
          </span>
        </Link>

        <nav className="flex gap-1">
          {links.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
                path === href
                  ? 'bg-slate-800 text-white'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
              }`}
            >
              {label}
            </Link>
          ))}
        </nav>

        <div className="flex items-center gap-2 text-xs text-slate-500">
          <FlaskConical className="h-3.5 w-3.5" />
          EACL 2027 Demo
        </div>
      </div>
    </header>
  )
}
