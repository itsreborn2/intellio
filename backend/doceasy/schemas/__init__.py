"""스키마 모듈"""
from doceasy.schemas.project import (
    ProjectBase,
    ProjectCreate,
    ProjectUpdate,
    ProjectInDB,
    ProjectSimpleResponse,
    ProjectListResponse,
    RecentProjectsResponse
)
# from doceasy.schemas.user import (
#     # 사용자 관련 스키마
#     UserBase,
#     UserCreate,
#     UserUpdate,
#     UserInDB,
#     UserLogin,
#     UserResponse,
#     UserListResponse,
#     # 세션 관련 스키마
#     SessionBase,
#     SessionCreate,
#     SessionUpdate,
#     SessionInDB,
#     SessionResponse,
#     SessionListResponse
# )
from doceasy.schemas.document import (
    DocumentCreate,
    DocumentUpdate,
    DocumentInDB,
    DocumentResponse,
    DocumentListResponse
)

__all__ = [
    # 프로젝트 스키마
    "ProjectBase",
    "ProjectCreate",
    "ProjectUpdate",
    "ProjectInDB",
    "ProjectSimpleResponse",
    "ProjectListResponse",
    "RecentProjectsResponse",
    # # 사용자 스키마
    # "UserBase",
    # "UserCreate",
    # "UserUpdate",
    # "UserInDB",
    # "UserLogin",
    # "UserResponse",
    # "UserListResponse",
    # # 세션 스키마
    # "SessionBase",
    # "SessionCreate",
    # "SessionUpdate",
    # "SessionInDB",
    # "SessionResponse",
    # "SessionListResponse",
    # 문서 스키마
    "DocumentCreate",
    "DocumentUpdate",
    "DocumentInDB",
    "DocumentResponse",
    "DocumentListResponse"
]
