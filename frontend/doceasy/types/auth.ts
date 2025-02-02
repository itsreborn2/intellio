// OAuth 응답 데이터 인터페이스
export interface IOAuthUser {
    id: string;
    email: string;
    name: string;
    provider: string;
}

export interface IOAuthResponse {
    user: IOAuthUser;
    token: string;
}
