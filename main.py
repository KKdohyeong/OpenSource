from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
from typing import Optional, List
import os
import json

app = FastAPI()

# 세션 비밀키 (실서비스는 안전하게 보관해야 함)
app.add_middleware(SessionMiddleware, secret_key="YOUR_SECRET_KEY_HERE")

# 템플릿 설정
templates = Jinja2Templates(directory="templates")

# 정적 파일 (이미지가 필요하면 static 폴더에 이미지 저장 후 사용)
app.mount("/static", StaticFiles(directory="static"), name="static")

# ----------------------------
#  User 모델 & JSON 관리 로직
# ----------------------------
class User(BaseModel):
    username: str
    password: str  # 실제로는 해싱 필요
    email: Optional[str] = None

USER_DATA_FILE = "user_data.json"

def load_users() -> List[User]:
    """JSON 파일에서 사용자 목록 읽기."""
    if not os.path.exists(USER_DATA_FILE):
        save_users([])
        return []
    with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [User(**user) for user in data]

def save_users(users: List[User]) -> None:
    """사용자 목록을 JSON 파일에 저장."""
    data = [user.dict() for user in users]
    with open(USER_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ----------------------------
#  메인/홈 페이지
# ----------------------------
@app.get("/")
def read_index(request: Request):
    """메인 페이지"""
    # 세션에서 로그인한 username 가져오기(없으면 None)
    username = request.session.get("username")
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "username": username}
    )

# ----------------------------
#  회원가입
# ----------------------------
@app.get("/register")
def register_form(request: Request):
    """회원가입 폼"""
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register")
def register_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    email: str = Form(None)
):
    """회원가입 처리"""
    users = load_users()

    # 이미 같은 username이 있는지 체크
    for u in users:
        if u.username == username:
            # username 중복
            return templates.TemplateResponse(
                "register.html",
                {
                    "request": request,
                    "error_message": f"이미 존재하는 username입니다: {username}"
                }
            )

    # 새 유저 추가
    new_user = User(username=username, password=password, email=email)
    users.append(new_user)
    save_users(users)

    # 회원가입 후 로그인 페이지로 이동
    return RedirectResponse(url="/login", status_code=303)

# ----------------------------
#  로그인 / 로그아웃
# ----------------------------
@app.get("/login")
def login_form(request: Request):
    """로그인 폼"""
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...)
):
    """로그인 처리"""
    users = load_users()
    # username & password 확인 (실서비스는 비밀번호 해시 검사)
    for u in users:
        if u.username == username and u.password == password:
            # 로그인 성공 → 세션에 저장
            request.session["username"] = username
            return RedirectResponse(url="/profile", status_code=303)

    # 로그인 실패
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "error_message": "아이디 또는 비밀번호가 틀렸습니다."
        }
    )

@app.get("/logout")
def logout(request: Request):
    """로그아웃 처리"""
    request.session.clear()  # 세션 비우기
    return RedirectResponse(url="/", status_code=303)

# ----------------------------
#  로그인해야 볼 수 있는 페이지 예시
# ----------------------------
@app.get("/profile")
def profile_page(request: Request):
    """프로필 페이지 (로그인 필요)"""
    username = request.session.get("username")
    if not username:
        # 로그인이 안되어 있다면 로그인 페이지로 리다이렉트
        return RedirectResponse(url="/login")

    # 사용자 정보 불러오기
    users = load_users()
    current_user = None
    for u in users:
        if u.username == username:
            current_user = u
            break

    if not current_user:
        # 혹시 세션에 있는 username과 매칭되는 유저가 없으면
        return RedirectResponse(url="/logout")

    return templates.TemplateResponse(
        "profile.html",
        {
            "request": request,
            "user": current_user
        }
    )
