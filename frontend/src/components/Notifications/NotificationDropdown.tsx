import { useState, useRef, useEffect } from 'react';
import { Bell, Check } from 'lucide-react';
import { useNotifications, Notification } from '../../context/NotificationContext';
import { useNavigate } from 'react-router-dom';

export function NotificationDropdown() {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const { notifications, unreadCount, markAsRead, markAllAsRead } = useNotifications();
  const navigate = useNavigate();

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);

  const handleNotificationClick = (notification: Notification) => {
    if (!notification.read) {
      markAsRead(notification.id);
    }
    setIsOpen(false);
    if (notification.link) {
      navigate(notification.link);
    } else if (notification.source_type === 'case' && notification.source_id) {
      navigate(`/cases/${notification.source_id}`);
    } else if (notification.source_type === 'document' && notification.source_id) {
      navigate(`/documents/${notification.source_id}`);
    }
  };

  const formatTime = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffDays > 0) return `${diffDays}d ago`;
    if (diffHours > 0) return `${diffHours}h ago`;
    if (diffMins > 0) return `${diffMins}m ago`;
    return 'Just now';
  };

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-2 text-muted-foreground hover:bg-muted rounded-full transition-colors flex items-center justify-center"
      >
        <Bell className="h-5 w-5" />
        {unreadCount > 0 && (
          <span className="absolute top-0 right-0 flex min-w-[18px] h-[18px] items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white border-2 border-white shadow-sm">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div className="absolute right-0 top-full mt-2 w-80 max-h-[32rem] bg-white border border-border rounded-xl shadow-lg overflow-hidden z-50 flex flex-col">
          <div className="px-4 py-3 bg-slate-50 border-b border-border flex justify-between items-center">
            <h3 className="font-semibold text-slate-800">Notifications</h3>
            {unreadCount > 0 && (
              <button
                onClick={(e) => { e.stopPropagation(); markAllAsRead(); }}
                className="text-xs text-primary font-medium hover:underline flex items-center gap-1"
              >
                <Check className="h-3 w-3" />
                Mark all read
              </button>
            )}
          </div>
          
          <div className="overflow-y-auto flex-1 p-2 space-y-1 bg-white">
            {notifications.length === 0 ? (
              <div className="p-8 text-center text-slate-500">
                <Bell className="h-8 w-8 mx-auto -mt-2 mb-3 text-slate-300 opacity-50" />
                <p className="text-sm">No notifications yet</p>
              </div>
            ) : (
              notifications.map((notif) => (
                <div
                  key={notif.id}
                  onClick={() => handleNotificationClick(notif)}
                  className={`p-3 rounded-lg cursor-pointer transition-colors border-l-2 ${
                    notif.read ? 'bg-transparent border-transparent hover:bg-slate-50' : 'bg-primary/5 border-primary hover:bg-primary/10'
                  }`}
                >
                  <div className="flex justify-between items-start gap-2 mb-1">
                    <p className={`text-sm ${notif.read ? 'text-slate-800 font-medium' : 'text-slate-900 font-semibold'}`}>
                      {notif.title}
                    </p>
                    <span className="text-[10px] text-slate-400 whitespace-nowrap pt-0.5">
                      {formatTime(notif.created_at)}
                    </span>
                  </div>
                  <p className="text-xs text-slate-600 line-clamp-2 leading-relaxed">
                    {notif.message}
                  </p>
                </div>
              ))
            )}
          </div>
          
          <div className="border-t border-border p-2 bg-slate-50">
            <button
              onClick={() => setIsOpen(false)}
              className="w-full py-1.5 text-xs text-center text-slate-500 hover:text-slate-700 font-medium transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
