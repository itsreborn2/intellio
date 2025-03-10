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
        <section className="bottom-section">
          <BottomLeftArea />
          <BottomCenterArea />
          <BottomRightArea1 />
          <BottomRightArea2 />
        </section>
      </main>
    </div>
  );
}
