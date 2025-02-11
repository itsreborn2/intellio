import './globals.css';
import Sidebar from './components/Sidebar';
import AIChatArea from './components/AIChatArea';
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
          <TelegramSummaryArea />
        </section>
        <section className="bottom-section bottom-section-no-padding">
          <div className="bottom-area bottom-left-area">하단 좌측 영역 1</div>
          <div className="bottom-area bottom-center-area">하단 중앙 영역 2</div>
          <div className="bottom-area bottom-right-area-1">하단 우측 영역 3</div>
          <div className="bottom-area bottom-right-area-2">하단 우측 영역 4</div>
        </section>
      </main>
    </div>
  );
}
