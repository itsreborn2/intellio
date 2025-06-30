'use client';

import UserTable from './UserTable';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "intellio-common/components/ui/card";

export default function UserInfoTab() {
  return (
    <div className="grid grid-cols-1 gap-4">
      <div className="lg:col-span-12">
        <Card className="rounded-[6px] shadow-sm bg-white">
          <CardHeader>
            <CardTitle>전체 회원 검색</CardTitle>
          </CardHeader>
          <CardContent>
            <UserTable />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
