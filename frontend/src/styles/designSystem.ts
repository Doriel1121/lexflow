/**
 * LexFlow Design System
 * Professional Legal Application Theme
 * 
 * Color Psychology for Legal Applications:
 * - Navy Blue: Trust, authority, professionalism
 * - Gold/Amber: Premium, excellence, achievement
 * - Slate Gray: Sophistication, neutrality, balance
 * - White: Clarity, transparency, honesty
 */

export const designSystem = {
  // Primary Color Palette - Legal Professional
  colors: {
    // Primary - Navy Blue (Trust & Authority)
    primary: {
      50: '#f0f4f8',
      100: '#d9e2ec',
      200: '#bcccdc',
      300: '#9fb3c8',
      400: '#829ab1',
      500: '#627d98',  // Main primary
      600: '#486581',
      700: '#334e68',  // Darker for text
      800: '#243b53',
      900: '#102a43',
    },
    
    // Secondary - Gold/Amber (Excellence & Achievement)
    secondary: {
      50: '#fffbeb',
      100: '#fef3c7',
      200: '#fde68a',
      300: '#fcd34d',
      400: '#fbbf24',
      500: '#d97706',  // Main secondary
      600: '#b45309',
      700: '#92400e',
      800: '#78350f',
      900: '#451a03',
    },
    
    // Neutral - Slate (Professional & Balanced)
    neutral: {
      50: '#f8fafc',
      100: '#f1f5f9',
      200: '#e2e8f0',
      300: '#cbd5e1',
      400: '#94a3b8',
      500: '#64748b',
      600: '#475569',
      700: '#334155',
      800: '#1e293b',
      900: '#0f172a',
    },
    
    // Status Colors
    success: {
      light: '#d1fae5',
      main: '#10b981',
      dark: '#065f46',
    },
    warning: {
      light: '#fef3c7',
      main: '#f59e0b',
      dark: '#92400e',
    },
    error: {
      light: '#fee2e2',
      main: '#ef4444',
      dark: '#991b1b',
    },
    info: {
      light: '#dbeafe',
      main: '#3b82f6',
      dark: '#1e40af',
    },
    
    // Background & Surface
    background: {
      primary: '#ffffff',
      secondary: '#f8fafc',
      tertiary: '#f1f5f9',
      dark: '#0f172a',
    },
    
    // Text Colors
    text: {
      primary: '#0f172a',
      secondary: '#475569',
      tertiary: '#94a3b8',
      inverse: '#ffffff',
      link: '#2563eb',
    },
    
    // Border Colors
    border: {
      light: '#e2e8f0',
      main: '#cbd5e1',
      dark: '#94a3b8',
    },
  },
  
  // Typography Scale
  typography: {
    fontFamily: {
      sans: '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      serif: '"Merriweather", Georgia, serif',
      mono: '"JetBrains Mono", "Fira Code", monospace',
    },
    fontSize: {
      xs: '0.75rem',      // 12px
      sm: '0.875rem',     // 14px
      base: '1rem',       // 16px
      lg: '1.125rem',     // 18px
      xl: '1.25rem',      // 20px
      '2xl': '1.5rem',    // 24px
      '3xl': '1.875rem',  // 30px
      '4xl': '2.25rem',   // 36px
      '5xl': '3rem',      // 48px
    },
    fontWeight: {
      light: 300,
      normal: 400,
      medium: 500,
      semibold: 600,
      bold: 700,
    },
    lineHeight: {
      tight: 1.25,
      normal: 1.5,
      relaxed: 1.75,
    },
  },
  
  // Spacing Scale (4px base)
  spacing: {
    0: '0',
    1: '0.25rem',   // 4px
    2: '0.5rem',    // 8px
    3: '0.75rem',   // 12px
    4: '1rem',      // 16px
    5: '1.25rem',   // 20px
    6: '1.5rem',    // 24px
    8: '2rem',      // 32px
    10: '2.5rem',   // 40px
    12: '3rem',     // 48px
    16: '4rem',     // 64px
    20: '5rem',     // 80px
    24: '6rem',     // 96px
  },
  
  // Border Radius
  borderRadius: {
    none: '0',
    sm: '0.25rem',   // 4px
    base: '0.5rem',  // 8px
    md: '0.75rem',   // 12px
    lg: '1rem',      // 16px
    xl: '1.5rem',    // 24px
    full: '9999px',
  },
  
  // Shadows
  shadows: {
    sm: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
    base: '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)',
    md: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
    lg: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
    xl: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
    inner: 'inset 0 2px 4px 0 rgba(0, 0, 0, 0.06)',
  },
  
  // Component Specific Styles
  components: {
    button: {
      primary: {
        bg: '#334e68',
        hover: '#243b53',
        text: '#ffffff',
      },
      secondary: {
        bg: '#d97706',
        hover: '#b45309',
        text: '#ffffff',
      },
      ghost: {
        bg: 'transparent',
        hover: '#f1f5f9',
        text: '#334e68',
      },
    },
    card: {
      bg: '#ffffff',
      border: '#e2e8f0',
      shadow: '0 1px 3px 0 rgba(0, 0, 0, 0.1)',
      hover: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
    },
    input: {
      bg: '#ffffff',
      border: '#cbd5e1',
      focus: '#334e68',
      placeholder: '#94a3b8',
    },
    table: {
      header: '#f8fafc',
      border: '#e2e8f0',
      hover: '#f1f5f9',
      stripe: '#f8fafc',
    },
  },
  
  // Transitions
  transitions: {
    fast: '150ms cubic-bezier(0.4, 0, 0.2, 1)',
    base: '200ms cubic-bezier(0.4, 0, 0.2, 1)',
    slow: '300ms cubic-bezier(0.4, 0, 0.2, 1)',
  },
  
  // Z-Index Scale
  zIndex: {
    dropdown: 1000,
    sticky: 1020,
    fixed: 1030,
    modalBackdrop: 1040,
    modal: 1050,
    popover: 1060,
    tooltip: 1070,
  },
};

// CSS Variables for easy theming
export const cssVariables = `
:root {
  /* Primary Colors */
  --color-primary-50: #f0f4f8;
  --color-primary-500: #627d98;
  --color-primary-700: #334e68;
  --color-primary-900: #102a43;
  
  /* Secondary Colors */
  --color-secondary-500: #d97706;
  --color-secondary-700: #92400e;
  
  /* Neutral Colors */
  --color-neutral-50: #f8fafc;
  --color-neutral-100: #f1f5f9;
  --color-neutral-200: #e2e8f0;
  --color-neutral-500: #64748b;
  --color-neutral-700: #334155;
  --color-neutral-900: #0f172a;
  
  /* Status Colors */
  --color-success: #10b981;
  --color-warning: #f59e0b;
  --color-error: #ef4444;
  --color-info: #3b82f6;
  
  /* Typography */
  --font-sans: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --font-serif: "Merriweather", Georgia, serif;
  
  /* Spacing */
  --spacing-unit: 0.25rem;
  
  /* Transitions */
  --transition-fast: 150ms cubic-bezier(0.4, 0, 0.2, 1);
  --transition-base: 200ms cubic-bezier(0.4, 0, 0.2, 1);
}
`;

export default designSystem;
