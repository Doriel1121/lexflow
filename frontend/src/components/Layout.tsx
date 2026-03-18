import React, { useState, useEffect, ReactNode } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

interface LayoutProps {
  children: ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const { isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();
  const [isDarkMode, setIsDarkMode] = useState(false);
  const [isRTL, setIsRTL] = useState(false); // State for RTL

  useEffect(() => {
    // Check for dark mode preference
    const prefersDarkMode = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    setIsDarkMode(localStorage.getItem('theme') === 'dark' || (localStorage.getItem('theme') === null && prefersDarkMode));
  }, []);

  useEffect(() => {
    // Apply dark mode class to html element
    if (isDarkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [isDarkMode]);

  useEffect(() => {
    // Apply RTL direction to html element
    if (isRTL) {
      document.documentElement.setAttribute('dir', 'rtl');
    } else {
      document.documentElement.setAttribute('dir', 'ltr');
    }
  }, [isRTL]);

  const toggleDarkMode = () => {
    setIsDarkMode(!isDarkMode);
    localStorage.setItem('theme', !isDarkMode ? 'dark' : 'light');
  };

  const toggleRTL = () => {
    setIsRTL(!isRTL);
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="min-h-screen flex flex-col bg-gray-100 dark:bg-gray-900 text-gray-900 dark:text-gray-100">
      <header className="bg-white dark:bg-gray-800 shadow-sm p-4 flex justify-between items-center">
        <Link to="/" className="text-xl font-bold text-blue-600 dark:text-blue-400">LegalOS</Link>
        <nav>
          {isAuthenticated ? (
            <ul className="flex space-x-4">
              <li><Link to="/" className="hover:text-blue-600 dark:hover:text-blue-400">Dashboard</Link></li>
              <li><Link to="/cases" className="hover:text-blue-600 dark:hover:text-blue-400">Cases</Link></li>
              <li><Link to="/documents" className="hover:text-blue-600 dark:hover:text-blue-400">Documents</Link></li>
              <li><Link to="/search" className="hover:text-blue-600 dark:hover:text-blue-400">Search</Link></li>
              <li>
                <button onClick={toggleDarkMode} className="p-2 rounded-md bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600">
                  {isDarkMode ? '☀️ Light Mode' : '🌙 Dark Mode'}
                </button>
              </li>
              <li>
                <button onClick={toggleRTL} className="p-2 rounded-md bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600">
                  {isRTL ? 'LTR' : 'RTL'}
                </button>
              </li>
              <li>
                <button onClick={handleLogout} className="px-3 py-2 bg-red-600 text-white rounded-md hover:bg-red-700">Logout</button>
              </li>
            </ul>
          ) : (
            <Link to="/login" className="px-3 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">Login</Link>
          )}
        </nav>
      </header>
      <main className="flex-grow p-4 container mx-auto">
        {children}
      </main>
      <footer className="bg-white dark:bg-gray-800 shadow-sm p-4 text-center text-gray-500 dark:text-gray-400">
        &copy; {new Date().getFullYear()} LegalOS. All rights reserved.
      </footer>
    </div>
  );
};

export default Layout;
