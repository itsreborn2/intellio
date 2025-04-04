import './globals.css';
import AIChatArea from './components/AIChatArea';


export default function StockEasyLandingPage() {
  return (
    <div className="flex-1 p-0 sm:p-2 md:p-4 overflow-auto ml-0 md:ml-16 w-full">
      <div className="max-w-6xl mx-auto">
        <AIChatArea />
      </div>
    </div>
  );
}
