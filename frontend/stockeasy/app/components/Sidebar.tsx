import React from 'react';
import {
  Home,
  BarChart,
  ChartColumn,
  FileStack,
  FileText,
  User,
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
        <button className="sidebar-button">
          <ChartColumn className="icon" />
        </button>
        <button className="sidebar-button">
          <FileStack className="icon" />
        </button>
        <button className="sidebar-button">
          <User className="icon" />
        </button>
        <button className="sidebar-button">
          <Settings className="icon" />
        </button>
      </div>
    </aside>
  );
};

export default Sidebar;
