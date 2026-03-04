import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Header } from './Header';

export function Layout() {
  return (
    <div className="min-h-screen bg-slate-50/50 flex">
      <Sidebar />
      <div className="flex-1 ml-64 flex flex-col">
        <Header />
        <main className="flex-1 p-8 overflow-y-auto">
          <div className="max-w-7xl mx-auto w-full animate-accordion-down">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
