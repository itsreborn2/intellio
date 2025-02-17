class AuthenticationRedirectException(Exception):
    """인증이 필요할 때 리다이렉트하기 위한 커스텀 예외"""
    def __init__(self, redirect_url: str):
        self.redirect_url = redirect_url
        super().__init__() 