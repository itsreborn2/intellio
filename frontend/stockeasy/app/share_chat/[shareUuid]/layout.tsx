import { Metadata } from 'next';

export const metadata: Metadata = {
  title: '공유된 채팅 - StockEasy',
  description: 'StockEasy 공유된 주식 채팅 내용',
};

export default function SharedChatLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-gray-50">
      <div className="fixed top-0 left-0 w-full h-[44px] bg-[#F4F4F4] z-40 flex items-center px-4">
        <div className="flex justify-between items-center w-full">
          <div className="flex items-center">
            <div className="text-lg font-semibold">StockEasy 공유 채팅</div>
          </div>
        </div>
      </div>
      <div className="pt-[60px]">
        {children}
      </div>
    </div>
  );
} 