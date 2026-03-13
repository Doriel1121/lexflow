import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { useTranslation } from 'react-i18next';

export function Layout() {
  const { i18n } = useTranslation();
  const isRTL = i18n.language === 'he';

  return (
    <div className="min-h-screen bg-slate-50 flex">
      <Sidebar />
      <div className="flex-1 ms-60 flex flex-col min-h-screen">
        <Header />
        <main className="flex-1 px-8 py-6 overflow-y-auto">
          <div className="max-w-7xl mx-auto w-full">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
