import React from 'react';
import {
  Home,
  BarChart,
  MessageSquare,
  Users,
  Settings,
  LayoutDashboard // 로고 대신 LayoutDashboard 아이콘 사용 (V와 유사)
} from 'lucide-react';

const Sidebar: React.FC = () => {
  return (
    <aside className="sidebar">
      <div className="sidebar-buttons">
        <button className="sidebar-button">
          <Home className="icon" />
        </button>
        <button className="sidebar-button logo-button">
          <LayoutDashboard className="icon logo-icon" /> {/* LayoutDashboard 아이콘 로고 */}
        </button>
        <button className="sidebar-button">
          <BarChart className="icon" />
        </button>
        <button className="sidebar-button">
          <MessageSquare className="icon" />
        </button>
        <button className="sidebar-button">
          <Users className="icon" />
        </button>
        <button className="sidebar-button">
          <Settings className="icon" />
        </button>
      </div>
    </aside>
  );
};

export default Sidebar;
