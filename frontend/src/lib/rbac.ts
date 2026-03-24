/**
 * lib/rbac.ts
 * ============
 * Central Role-Based Access Control definitions for LEXFLOW.
 *
 * This is the single source of truth for:
 *   - Role normalization
 *   - Role hierarchy / capability checks
 *   - Route permission matrix
 *   - Navigation permission matrix
 *
 * NEVER duplicate these rules in individual components.
 * Import from here everywhere.
 */

// ─── Role definitions ─────────────────────────────────────────────────────

/**
 * Canonical role enum.
 * Backend sends mixed case ("admin", "ADMIN", "org_admin", "ORG_ADMIN").
 * We normalize everything to lowercase at the boundary in `normalizeRole()`.
 */
export type AppRole =
  | 'admin'      // System-level administrator
  | 'org_admin'  // Tenant-level administrator
  | 'lawyer'     // Org member with write access
  | 'assistant'  // Org member with write access
  | 'viewer';    // Org member with read-only access

/** Normalize any backend role string to a canonical AppRole. */
export function normalizeRole(raw: string | undefined | null): AppRole {
  if (!raw) return 'viewer';
  const lower = raw.toLowerCase().replace('-', '_');
  if (lower === 'admin') return 'admin';
  if (lower === 'org_admin') return 'org_admin';
  if (lower === 'lawyer') return 'lawyer';
  if (lower === 'assistant') return 'assistant';
  return 'viewer';
}

// ─── Capability checks ────────────────────────────────────────────────────

export function isSystemAdmin(role: AppRole | string | null | undefined): boolean {
  return normalizeRole(role as string) === 'admin';
}

export function isOrgAdmin(role: AppRole | string | null | undefined): boolean {
  return normalizeRole(role as string) === 'org_admin';
}

export function isTenantUser(role: AppRole | string | null | undefined): boolean {
  const r = normalizeRole(role as string);
  return ['org_admin', 'lawyer', 'assistant', 'viewer'].includes(r);
}

export function hasWriteAccess(role: AppRole | string | null | undefined): boolean {
  const r = normalizeRole(role as string);
  return ['org_admin', 'lawyer', 'assistant'].includes(r);
}

// ─── Route permission matrix ──────────────────────────────────────────────

/**
 * Defines which roles may access each route prefix.
 *
 * Rules are checked top-down. First match wins.
 * A route with `allowedRoles: []` means NOBODY can access it (blocked).
 */
export interface RoutePermission {
  /** Route path prefix — matched with startsWith(). Use exact `/` for root only. */
  path: string;
  /** Roles that may access this route. Empty array = blocked for all. */
  allowedRoles: AppRole[];
  /** Where to redirect if access is denied. */
  redirectTo: string;
}

export const ROUTE_PERMISSIONS: RoutePermission[] = [
  // ── System Admin only ────────────────────────────────────────────────
  { path: '/admin', allowedRoles: ['admin'], redirectTo: '/' },

  // ── Tenant users only (admin is BLOCKED from these) ──────────────────
  { path: '/clients',   allowedRoles: ['org_admin', 'lawyer', 'assistant', 'viewer'], redirectTo: '/admin' },
  { path: '/cases',     allowedRoles: ['org_admin', 'lawyer', 'assistant', 'viewer'], redirectTo: '/admin' },
  { path: '/documents', allowedRoles: ['org_admin', 'lawyer', 'assistant', 'viewer'], redirectTo: '/admin' },
  { path: '/email',     allowedRoles: ['org_admin', 'lawyer', 'assistant', 'viewer'], redirectTo: '/admin' },
  { path: '/collections', allowedRoles: ['org_admin', 'lawyer', 'assistant', 'viewer'], redirectTo: '/admin' },
  { path: '/team',      allowedRoles: ['org_admin', 'admin'], redirectTo: '/' },
  { path: '/settings/audit-logs', allowedRoles: ['org_admin', 'admin'], redirectTo: '/' },

  // ── All authenticated users ───────────────────────────────────────────
  { path: '/settings',  allowedRoles: ['admin', 'org_admin', 'lawyer', 'assistant', 'viewer'], redirectTo: '/login' },
  { path: '/search',    allowedRoles: ['admin', 'org_admin', 'lawyer', 'assistant', 'viewer'], redirectTo: '/login' },
  { path: '/',          allowedRoles: ['admin', 'org_admin', 'lawyer', 'assistant', 'viewer'], redirectTo: '/login' },
];

/**
 * Returns the redirect destination if `role` cannot access `path`,
 * or `null` if access is allowed.
 */
export function checkRouteAccess(path: string, role: AppRole | string | null | undefined): string | null {
  const normalized = normalizeRole(role as string);

  // Find the most specific matching permission rule
  const sorted = [...ROUTE_PERMISSIONS].sort((a, b) => b.path.length - a.path.length);

  for (const rule of sorted) {
    const matches = rule.path === '/'
      ? path === '/'
      : path === rule.path || path.startsWith(rule.path + '/') || path.startsWith(rule.path);

    if (matches) {
      if (rule.allowedRoles.includes(normalized)) return null; // ✅ allowed
      return rule.redirectTo; // ❌ denied → redirect target
    }
  }

  return null; // No specific rule → allow by default
}

// ─── Navigation permission matrix ────────────────────────────────────────

export interface NavItemDef {
  labelKey: string;
  path: string;
  icon: string; // Lucide icon name
  allowedRoles: AppRole[];
  end?: boolean;
}

export interface NavGroupDef {
  labelKey: string;
  defaultOpen?: boolean;
  items: NavItemDef[];
  /** If set, entire group only shows for these roles. */
  groupRoles?: AppRole[];
}

/**
 * Master navigation definition.
 * Sidebar derives what to show purely from the user's role + this table.
 */
export const NAV_GROUPS: NavGroupDef[] = [
  {
    labelKey: 'nav.workspace',
    defaultOpen: true,
    // This group is for tenant users. Admin sees their own group below.
    groupRoles: ['org_admin', 'lawyer', 'assistant', 'viewer'],
    items: [
      { labelKey: 'nav.dashboard',  path: '/',          icon: 'LayoutDashboard', allowedRoles: ['org_admin', 'lawyer', 'assistant', 'viewer'], end: true },
      { labelKey: 'nav.cases',      path: '/cases',     icon: 'Briefcase',       allowedRoles: ['org_admin', 'lawyer', 'assistant', 'viewer'] },
      { labelKey: 'nav.clients',    path: '/clients',   icon: 'Building2',       allowedRoles: ['org_admin', 'lawyer', 'assistant', 'viewer'] },
      { labelKey: 'nav.documents',  path: '/documents', icon: 'Files',           allowedRoles: ['org_admin', 'lawyer', 'assistant', 'viewer'] },
    ],
  },
  {
    labelKey: 'nav.communication',
    defaultOpen: true,
    groupRoles: ['org_admin', 'lawyer', 'assistant', 'viewer'],
    items: [
      { labelKey: 'nav.emailIntake',   path: '/email',       icon: 'Inbox',       allowedRoles: ['org_admin', 'lawyer', 'assistant', 'viewer'] },
      { labelKey: 'nav.search',        path: '/search',      icon: 'Search',      allowedRoles: ['org_admin', 'lawyer', 'assistant', 'viewer'] },
      { labelKey: 'nav.collections',   path: '/collections', icon: 'FolderGit2',  allowedRoles: ['org_admin', 'lawyer', 'assistant', 'viewer'] },
    ],
  },
  {
    labelKey: 'nav.administration',
    defaultOpen: false,
    groupRoles: ['org_admin', 'lawyer', 'assistant', 'viewer'],
    items: [
      { labelKey: 'nav.team',       path: '/team',                 icon: 'Users',      allowedRoles: ['org_admin'] },
      { labelKey: 'nav.auditLogs',  path: '/settings/audit-logs',  icon: 'ShieldCheck', allowedRoles: ['org_admin'] },
      { labelKey: 'nav.settings',   path: '/settings',             icon: 'Settings',   allowedRoles: ['org_admin', 'lawyer', 'assistant', 'viewer'] },
    ],
  },
  // ── System Admin exclusive group ─────────────────────────────────────
  {
    labelKey: 'nav.systemAdmin',
    defaultOpen: true,
    groupRoles: ['admin'],
    items: [
      { labelKey: 'nav.systemOverview',  path: '/admin',                icon: 'Activity',      allowedRoles: ['admin'], end: true },
      { labelKey: 'nav.organizations',   path: '/admin/organizations',  icon: 'Building2',     allowedRoles: ['admin'] },
      { labelKey: 'nav.usersRoles',      path: '/admin/users',          icon: 'Users',         allowedRoles: ['admin'] },
      { labelKey: 'nav.auditLogs',       path: '/admin/audit-logs',     icon: 'ClipboardList', allowedRoles: ['admin'] },
    ],
  },
];

/**
 * Returns only the nav groups and items visible to `role`.
 */
export function getNavForRole(role: AppRole | string | null | undefined): NavGroupDef[] {
  const normalized = normalizeRole(role as string);
  return NAV_GROUPS
    .filter(group => !group.groupRoles || group.groupRoles.includes(normalized))
    .map(group => ({
      ...group,
      items: group.items.filter(item => item.allowedRoles.includes(normalized)),
    }))
    .filter(group => group.items.length > 0);
}
