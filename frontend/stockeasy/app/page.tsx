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
      <main className="main-content">
        <section className="top-section">
          <AIChatArea />
        </section>
        {/* 다른 영역은 주석 처리하여 화면에서 제거하되 코드는 유지 */}
        {/* 
        <section className="bottom-section">
          <div className="bottom-grid-container">
            <BottomLeftArea />
            <BottomCenterArea />
            <BottomRightArea1 />
            <BottomRightArea2 />
          </div>
          <TelegramSummaryArea />
        </section>
        */}
      </main>
    </div>
  );
}
