from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
from typing import Optional, List
from prometheus_fastapi_instrumentator import Instrumentator
from datetime import datetime, timezone, timedelta

import os
import json

KST = timezone(timedelta(hours=9))      # 한국 표준시용 타임존 객체


app = FastAPI()

# Prometheus 메트릭스 엔드포인트 (/metrics)
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

# 세션 비밀키 (실서비스에서는 안전하게 보관)
app.add_middleware(SessionMiddleware, secret_key="YOUR_SECRET_KEY_HERE")

# 템플릿 디렉토리 설정 (templates 폴더)
BASE_DIR = os.path.dirname(__file__)  # == todo_app
templates = Jinja2Templates(
    directory=os.path.join(BASE_DIR, "templates")
)

# ------------------------------------
#  User 모델 및 JSON 관리 로직
# ------------------------------------
class User(BaseModel):
    username: str
    password: str  # 실제 서비스에서는 해싱 필요
    email: Optional[str] = None

USER_DATA_FILE = "user_data.json"

def load_users() -> List[User]:
    if not os.path.exists(USER_DATA_FILE):
        save_users([])
        return []
    with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [User(**user) for user in data]

def save_users(users: List[User]) -> None:
    data = [user.dict() for user in users]
    with open(USER_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ------------------------------------
#  Todo 모델 및 JSON 관리 로직
#  (title, description, completed 필드 추가)
# ------------------------------------
class TodoItem(BaseModel):
    id: int
    username: str
    title: str
    description: str
    completed: bool = False

TODO_DATA_FILE = "todo_data.json"


@app.get("/index")
def index(request: Request):
    username = get_current_username(request)
    todos = load_todos()
    user_todos = [t for t in todos if t.username == username]

    # ★ 현재 시간(문자열) 추가
    current_time = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "todos": user_todos,
            "username": username,
            "current_time": current_time,   # ← 전달
        },
    )

def load_todos() -> List[TodoItem]:
    if not os.path.exists(TODO_DATA_FILE):
        save_todos([])
        return []
    with open(TODO_DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [TodoItem(**item) for item in data]

def save_todos(todos: List[TodoItem]) -> None:
    data = [todo.dict() for todo in todos]
    with open(TODO_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ------------------------------------
#  루트: 로그인 페이지로 리다이렉트
# ------------------------------------
@app.get("/")
def root():
    return RedirectResponse(url="/login")

# ------------------------------------
#  회원가입
# ------------------------------------
@app.get("/register")
def register_form(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register")
def register_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    email: str = Form(None)
):
    users = load_users()
    for u in users:
        if u.username == username:
            return templates.TemplateResponse(
                "register.html",
                {"request": request, "error_message": f"이미 존재하는 username입니다: {username}"}
            )
    new_user = User(username=username, password=password, email=email)
    users.append(new_user)
    save_users(users)
    return RedirectResponse(url="/login", status_code=303)

# ------------------------------------
#  로그인 / 로그아웃
# ------------------------------------
@app.get("/login")
def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    users = load_users()
    for u in users:
        if u.username == username and u.password == password:
            request.session["username"] = username
            return RedirectResponse(url="/index", status_code=303)
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error_message": "아이디 또는 비밀번호가 틀렸습니다."}
    )

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)

# ------------------------------------
#  로그인 확인용 유틸리티 함수
# ------------------------------------
def get_current_username(request: Request) -> str:
    username = request.session.get("username")
    if not username:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    return username

# ------------------------------------
#  Todo CRUD 엔드포인트
# ------------------------------------
# Todo 목록 (index.html)
@app.get("/index")
def index(request: Request):
    username = get_current_username(request)
    todos = load_todos()
    user_todos = [todo for todo in todos if todo.username == username]
    return templates.TemplateResponse("index.html", {"request": request, "todos": user_todos, "username": username})

# Todo 생성 (create.html)
@app.get("/create")
def create_form(request: Request):
    username = get_current_username(request)
    return templates.TemplateResponse("create.html", {"request": request, "username": username})

@app.post("/create")
def create_submit(request: Request, title: str = Form(...), description: str = Form(...)):
    username = get_current_username(request)
    todos = load_todos()
    new_id = max([todo.id for todo in todos], default=0) + 1
    new_todo = TodoItem(id=new_id, username=username, title=title, description=description, completed=False)
    todos.append(new_todo)
    save_todos(todos)
    return RedirectResponse(url="/index", status_code=303)

# Todo 상세보기 (detail view: /todos/{todo_id})
@app.get("/todos/{todo_id}")
def detail_view(request: Request, todo_id: int):
    username = get_current_username(request)
    todos = load_todos()
    todo_item = next((todo for todo in todos if todo.id == todo_id and todo.username == username), None)
    if not todo_item:
        return HTMLResponse("Todo 항목을 찾을 수 없습니다.", status_code=404)
    return templates.TemplateResponse("detail.html", {"request": request, "todo": todo_item, "username": username})

# Todo 수정 (update.html)
@app.get("/update/{todo_id}")
def update_form(request: Request, todo_id: int):
    username = get_current_username(request)
    todos = load_todos()
    todo_item = next((todo for todo in todos if todo.id == todo_id and todo.username == username), None)
    if not todo_item:
        return HTMLResponse("Todo 항목을 찾을 수 없습니다.", status_code=404)
    return templates.TemplateResponse("update.html", {"request": request, "todo": todo_item, "username": username})

@app.post("/update/{todo_id}")
def update_submit(
    request: Request,
    todo_id: int,
    title: str = Form(...),
    description: str = Form(...),
    completed: Optional[str] = Form(None)
):
    username = get_current_username(request)
    todos = load_todos()
    updated = False
    for i, todo in enumerate(todos):
        if todo.id == todo_id and todo.username == username:
            todos[i].title = title
            todos[i].description = description
            todos[i].completed = True if completed == "true" else False
            updated = True
            break
    if not updated:
        return HTMLResponse("Todo 항목을 찾을 수 없습니다.", status_code=404)
    save_todos(todos)
    return RedirectResponse(url="/index", status_code=303)

# Todo 삭제 (POST)
@app.post("/delete/{todo_id}")
def delete_todo(request: Request, todo_id: int):
    username = get_current_username(request)
    todos = load_todos()
    new_todos = [todo for todo in todos if not (todo.id == todo_id and todo.username == username)]
    if len(new_todos) == len(todos):
        return HTMLResponse("Todo 항목을 찾을 수 없습니다.", status_code=404)
    save_todos(new_todos)
    return RedirectResponse(url="/index", status_code=303)
