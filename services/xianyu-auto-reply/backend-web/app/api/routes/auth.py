"""
认证API路由

功能：
1. 用户登录（用户名/邮箱+密码）
2. 令牌验证
3. 用户注册
4. 用户登出
"""
import ipaddress

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.routes.captcha import check_email_code
from app.core.security import decode_token, get_password_hash
from common.models.user import User, UserRole, UserStatus
from common.schemas.auth import LoginRequest, LoginResponse, VerifyResponse
from common.schemas.common import ApiResponse
from common.schemas.user import UserCreate, UserPublic
from app.services.auth import AuthService
from app.services.user_service import UserService

router = APIRouter(tags=["auth"])


class ResetPasswordRequest(BaseModel):
    """重置密码请求"""
    email: str
    verification_code: str
    new_password: str


class LocalPasswordRequest(BaseModel):
    """Initial password setup payload accepted only from the local machine."""

    username: str = Field(min_length=1, max_length=64)
    new_password: str = Field(min_length=6, max_length=128)


def _is_loopback_host(host: str | None) -> bool:
    if not host:
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    if address.is_loopback:
        return True
    return bool(address.version == 6 and address.ipv4_mapped and address.ipv4_mapped.is_loopback)


def _is_loopback_request(request: Request) -> bool:
    """Only trust forwarded client IPs when the immediate peer is local."""
    client_host = request.client.host if request.client else None
    if not _is_loopback_host(client_host):
        return False

    forwarded_host = request.headers.get("x-forwarded-for") or request.headers.get("x-real-ip")
    if not forwarded_host:
        return True
    return _is_loopback_host(forwarded_host.split(",", 1)[0].strip())


def _password_setup_response() -> LoginResponse:
    return LoginResponse(
        success=False,
        message="首次使用，请在部署机器本机设置管理员密码",
        requires_password_setup=True,
    )


def _login_failure_response(
    auth_service: AuthService,
    message: str,
    user: User | None,
) -> LoginResponse:
    return LoginResponse(
        success=False,
        message=message,
        requires_local_reset=bool(
            user
            and user.role == UserRole.ADMIN
            and auth_service.is_login_locked(user)
        ),
    )


@router.post("/login", response_model=LoginResponse)
async def login_user(
    payload: LoginRequest,
    auth_service: AuthService = Depends(deps.get_auth_service),
    session: AsyncSession = Depends(deps.get_db_session),
) -> LoginResponse:
    user: User | None = None
    candidate_user: User | None = None
    error_message: str | None = None

    # 检查是否启用了登录滑动验证码
    from app.services.system_setting_service import SystemSettingService
    setting_service = SystemSettingService(session)
    all_settings = await setting_service.list_settings()
    captcha_enabled_str = all_settings.get("login_captcha_enabled")
    captcha_enabled = captcha_enabled_str in (None, "true", "1")  # 默认开启

    # 账号密码登录和邮箱密码登录需要验证滑动验证码
    if payload.username and payload.password:
        candidate_user = await auth_service.get_by_username(payload.username)
        if candidate_user and auth_service.is_password_setup_required(candidate_user):
            return _password_setup_response()

        # 账号密码登录 - 需要滑动验证（如果开启）
        if captcha_enabled:
            from app.api.routes.geetest import check_geetest_verified
            
            if not payload.geetest_challenge:
                return LoginResponse(success=False, message="请完成滑动验证")
            
            geetest_ok, geetest_msg = check_geetest_verified(payload.geetest_challenge)
            if not geetest_ok:
                return LoginResponse(success=False, message=geetest_msg)
        
        user, error_message = await auth_service.authenticate_by_username(payload.username, payload.password)
    elif payload.email and payload.password:
        candidate_user = await auth_service.get_by_email(payload.email)
        if candidate_user and auth_service.is_password_setup_required(candidate_user):
            return _password_setup_response()

        # 邮箱密码登录 - 需要滑动验证（如果开启）
        if captcha_enabled:
            from app.api.routes.geetest import check_geetest_verified
            
            if not payload.geetest_challenge:
                return LoginResponse(success=False, message="请完成滑动验证")
            
            geetest_ok, geetest_msg = check_geetest_verified(payload.geetest_challenge)
            if not geetest_ok:
                return LoginResponse(success=False, message=geetest_msg)
        
        user, error_message = await auth_service.authenticate_by_email(payload.email, payload.password)
    elif payload.email and payload.verification_code:
        # 邮箱验证码登录
        # 验证验证码
        code_valid, code_msg = check_email_code(payload.email, payload.verification_code, "login")
        if not code_valid:
            return LoginResponse(success=False, message=code_msg)
        
        # 根据邮箱查找用户
        user_service = UserService(session)
        user = await user_service.get_by_email(payload.email)
        if not user:
            return LoginResponse(success=False, message="该邮箱未注册")
        candidate_user = user
        if auth_service.is_password_setup_required(user):
            return _password_setup_response()
        if auth_service.is_login_locked(user):
            return _login_failure_response(auth_service, "账号已被锁定，请在部署机器本机重置管理员密码", user)
    else:
        return LoginResponse(success=False, message="请提供有效的登录信息")

    if not user:
        return _login_failure_response(auth_service, error_message or "登录失败", candidate_user)

    if user.status != UserStatus.ACTIVE:
        return LoginResponse(success=False, message="账号已禁用，请联系管理员")

    await auth_service.mark_login(user)
    return LoginResponse(
        success=True,
        message="登录成功",
        token=auth_service.create_access_token(user),
        refresh_token=auth_service.create_refresh_token(user),
        user_id=user.id,
        username=user.username,
        is_admin=user.role == UserRole.ADMIN,
        account_limit=user.account_limit,
    )


@router.get("/verify", response_model=VerifyResponse)
async def verify_token(
    request: Request,
    session: AsyncSession = Depends(deps.get_db_session),
) -> VerifyResponse:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return VerifyResponse(authenticated=False)

    token = auth_header.split(" ", 1)[1]
    try:
        payload = decode_token(token)
    except ValueError:
        return VerifyResponse(authenticated=False)

    sub = payload.get("sub")
    if not sub:
        return VerifyResponse(authenticated=False)

    user = await session.get(User, int(sub))
    if not user or user.status != UserStatus.ACTIVE:
        return VerifyResponse(authenticated=False)

    return VerifyResponse(
        authenticated=True,
        user_id=user.id,
        username=user.username,
        is_admin=user.role == UserRole.ADMIN,
        account_limit=user.account_limit,
    )


@router.post("/logout", response_model=ApiResponse)
async def logout_user() -> ApiResponse:
    return ApiResponse(success=True, message="已退出登录")


@router.post("/refresh", response_model=LoginResponse)
async def refresh_token(
    request: Request,
    session: AsyncSession = Depends(deps.get_db_session),
    auth_service: AuthService = Depends(deps.get_auth_service),
) -> LoginResponse:
    """刷新访问令牌"""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return LoginResponse(success=False, message="未提供刷新令牌")

    refresh_token = auth_header.split(" ", 1)[1]
    try:
        payload = decode_token(refresh_token)
    except ValueError:
        return LoginResponse(success=False, message="刷新令牌无效")

    # 验证是否为refresh token
    if payload.get("type") != "refresh":
        return LoginResponse(success=False, message="令牌类型错误")

    sub = payload.get("sub")
    if not sub:
        return LoginResponse(success=False, message="刷新令牌无效")

    user = await session.get(User, int(sub))
    if (
        not user
        or user.status != UserStatus.ACTIVE
        or auth_service.is_password_setup_required(user)
    ):
        return LoginResponse(success=False, message="用户不存在或已被禁用")

    # 生成新的access token和refresh token
    return LoginResponse(
        success=True,
        message="令牌刷新成功",
        token=auth_service.create_access_token(user),
        refresh_token=auth_service.create_refresh_token(user),
        user_id=user.id,
        username=user.username,
        is_admin=user.role == UserRole.ADMIN,
        account_limit=user.account_limit,
    )


@router.get("/check-default-password", response_model=ApiResponse)
async def check_password_setup(
    current_user: User = Depends(deps.get_current_admin_user),
    auth_service: AuthService = Depends(deps.get_auth_service),
) -> ApiResponse:
    """Backward-compatible status endpoint without checking a fixed password."""
    return ApiResponse(
        success=True,
        message="检查完成",
        data={
            "is_default": False,
            "requires_password_setup": auth_service.is_password_setup_required(current_user),
        },
    )


@router.get("/setup-status", response_model=ApiResponse)
async def get_setup_status(
    request: Request,
    session: AsyncSession = Depends(deps.get_db_session),
    auth_service: AuthService = Depends(deps.get_auth_service),
) -> ApiResponse:
    """Report the first-setup state to a browser running on the host machine."""
    if not _is_loopback_request(request):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="首次设置仅允许在部署机器本机完成")

    result = await session.execute(
        select(User)
        .where(User.role == UserRole.ADMIN)
        .order_by(User.id)
        .limit(1)
    )
    admin = result.scalar_one_or_none()
    requires_setup = bool(admin and auth_service.is_password_setup_required(admin))
    return ApiResponse(
        success=True,
        message="获取成功",
        data={
            "requires_password_setup": requires_setup,
            "username": admin.username if requires_setup else None,
        },
    )


@router.post("/local-setup-password", response_model=ApiResponse)
async def local_setup_password(
    payload: LocalPasswordRequest,
    request: Request,
    auth_service: AuthService = Depends(deps.get_auth_service),
) -> ApiResponse:
    """Set the fresh-install administrator password from loopback only."""
    if not _is_loopback_request(request):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="首次设置仅允许在部署机器本机完成")

    user = await auth_service.get_by_username(payload.username)
    if not user or user.role != UserRole.ADMIN:
        return ApiResponse(success=False, message="未找到可设置的管理员账号")
    try:
        await auth_service.set_password(user, payload.new_password, initial_only=True)
    except ValueError as exc:
        return ApiResponse(success=False, message=str(exc))
    return ApiResponse(success=True, message="管理员密码已设置，请使用新密码登录")


@router.post("/register", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    payload: UserCreate,
    user_service: UserService = Depends(deps.get_user_service),
) -> ApiResponse:
    # 验证邮箱验证码
    if payload.email and payload.verification_code:
        code_valid, code_msg = check_email_code(payload.email, payload.verification_code, "register")
        if not code_valid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=code_msg)
    elif payload.email:
        # 有邮箱但没有验证码
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请输入邮箱验证码")
    
    # 检查用户名是否已存在
    existing = await user_service.get_by_username(payload.username)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名已被注册")
    
    # 检查邮箱是否已存在
    if payload.email:
        existing_email = await user_service.get_by_email(payload.email)
        if existing_email:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="邮箱已被注册")
    
    await user_service.create(payload)
    return ApiResponse(success=True, message="注册成功")


@router.post("/reset-password", response_model=ApiResponse)
async def reset_password(
    payload: ResetPasswordRequest,
    session: AsyncSession = Depends(deps.get_db_session),
) -> ApiResponse:
    """重置密码（通过邮箱验证码）

    业务错误统一以 HTTP 200 + success=False 返回，由前端展示具体消息。
    """
    # 先校验新密码长度，避免在密码不合规时提前消费掉验证码
    if len(payload.new_password) < 6:
        return ApiResponse(success=False, message="新密码长度不能少于6位")

    # 验证邮箱验证码（校验成功后会消费该验证码）
    code_valid, code_msg = check_email_code(payload.email, payload.verification_code, "reset_password")
    if not code_valid:
        return ApiResponse(success=False, message=code_msg)

    # 查找用户
    user_service = UserService(session)
    user = await user_service.get_by_email(payload.email)
    if not user:
        return ApiResponse(success=False, message="该邮箱未注册")

    # 更新密码（直接操作 ORM 对象后 commit）
    user.password_hash = get_password_hash(payload.new_password)
    user.login_fail_count = 0
    user.login_locked_until = None
    await session.commit()

    return ApiResponse(success=True, message="密码重置成功")
