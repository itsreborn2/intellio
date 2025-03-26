import './globals.css';
import Sidebar from './components/Sidebar';
import AIChatArea from './components/AIChatArea';
// 컴포넌트는 남겨두지만 화면에서는 제거
import TelegramSummaryArea from './components/TelegramSummaryArea';
import BottomLeftArea from './components/BottomLeftArea';
import BottomCenterArea from './components/BottomCenterArea';
import BottomRightArea1 from './components/BottomRightArea1';
import BottomRightArea2 from './components/BottomRightArea2';

export default function StockEasyLandingPage() {
  return (
    <div className="stockeasy-landing-page">
      <Sidebar />
      <div className="chat-area-wrapper">
        <AIChatArea />
      </div>
    </div>
  );
}
