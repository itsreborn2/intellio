import './globals.css';
import Sidebar from './components/Sidebar';
import AIChatArea from './components/AIChatArea';


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
