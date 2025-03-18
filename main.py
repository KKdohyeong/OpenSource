from fastapi import FastAPI, HTTPException, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List
import json
import os

app = FastAPI()

# 템플릿 설정 (templates 폴더를 사용)
templates = Jinja2Templates(directory="templates")

# TodoItem 모델
class TodoItem(BaseModel):
    id: int
    title: str
    description: str = ""
    completed: bool = False

DATA_FILE = "todo_data.json"

def load_todos() -> List[TodoItem]:
    """JSON 파일에서 투두 목록 읽기."""
    if not os.path.exists(DATA_FILE):
        save_todos([])
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [TodoItem(**item) for item in data]

def save_todos(todos: List[TodoItem]) -> None:
    """투두 목록을 JSON 파일에 저장."""
    data = [todo.dict() for todo in todos]
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ----------------------------
#  HTML 페이지 라우트
# ----------------------------
@app.get("/")
def read_index(request: Request):
    """메인 페이지 - 투두 목록 보여주기"""
    todos = load_todos()
    return templates.TemplateResponse(
        "index.html", 
        {"request": request, "todos": todos}
    )

@app.get("/create")
def create_form(request: Request):
    """새 투두 생성하는 HTML 폼"""
    return templates.TemplateResponse("create.html", {"request": request})

@app.post("/create")
def create_submit(
    request: Request,
    id: int = Form(...),
    title: str = Form(...),
    description: str = Form(""),
    completed: bool = Form(False)
):
    """새 투두 생성 처리 (POST)"""
    todos = load_todos()
    # id 중복 체크
    for t in todos:
        if t.id == id:
            # 이미 같은 id가 있다면 에러
            return templates.TemplateResponse(
                "create.html",
                {
                    "request": request,
                    "error_message": f"이미 존재하는 ID입니다: {id}"
                }
            )
    new_todo = TodoItem(id=id, title=title, description=description, completed=completed)
    todos.append(new_todo)
    save_todos(todos)
    # 생성 후 메인 페이지로 리다이렉트
    return RedirectResponse(url="/", status_code=303)


@app.get("/todos/{todo_id}")
def detail_todo(request: Request, todo_id: int):
    """특정 ID의 투두 상세 보기"""
    todos = load_todos()
    for todo in todos:
        if todo.id == todo_id:
            return templates.TemplateResponse(
                "detail.html",
                {"request": request, "todo": todo}
            )
    raise HTTPException(status_code=404, detail="해당 ID의 투두가 존재하지 않습니다.")

@app.get("/update/{todo_id}")
def update_form(request: Request, todo_id: int):
    """특정 ID의 투두 수정 폼"""
    todos = load_todos()
    for todo in todos:
        if todo.id == todo_id:
            return templates.TemplateResponse(
                "update.html",
                {"request": request, "todo": todo}
            )
    raise HTTPException(status_code=404, detail="해당 ID의 투두가 존재하지 않습니다.")

@app.post("/update/{todo_id}")
def update_submit(
    request: Request,
    todo_id: int,
    title: str = Form(...),
    description: str = Form(""),
    completed: bool = Form(False)
):
    """특정 ID의 투두 수정 처리"""
    todos = load_todos()
    for idx, todo in enumerate(todos):
        if todo.id == todo_id:
            todos[idx].title = title
            todos[idx].description = description
            todos[idx].completed = completed
            save_todos(todos)
            return RedirectResponse(url=f"/todos/{todo_id}", status_code=303)
    raise HTTPException(status_code=404, detail="해당 ID의 투두가 존재하지 않습니다.")

@app.post("/delete/{todo_id}")
def delete_todo(todo_id: int):
    """특정 투두 삭제"""
    todos = load_todos()
    for idx, todo in enumerate(todos):
        if todo.id == todo_id:
            del todos[idx]
            save_todos(todos)
            return RedirectResponse(url="/", status_code=303)
    raise HTTPException(status_code=404, detail="해당 ID의 투두가 존재하지 않습니다.")


# ----------------------------
#  REST API 라우트 (기존 예시)
# ----------------------------
@app.get("/api/todos", response_model=List[TodoItem])
def get_todos_api():
    return load_todos()

@app.post("/api/todos", response_model=TodoItem)
def create_todo_api(todo: TodoItem):
    todos = load_todos()
    for t in todos:
        if t.id == todo.id:
            raise HTTPException(status_code=400, detail="이미 존재하는 ID입니다.")
    todos.append(todo)
    save_todos(todos)
    return todo

@app.get("/api/todos/{todo_id}", response_model=TodoItem)
def get_todo_api(todo_id: int):
    todos = load_todos()
    for todo in todos:
        if todo.id == todo_id:
            return todo
    raise HTTPException(status_code=404, detail="해당 ID의 투두가 존재하지 않습니다.")

@app.put("/api/todos/{todo_id}", response_model=TodoItem)
def update_todo_api(todo_id: int, update_data: TodoItem):
    todos = load_todos()
    for idx, todo in enumerate(todos):
        if todo.id == todo_id:
            todos[idx] = update_data
            save_todos(todos)
            return update_data
    raise HTTPException(status_code=404, detail="해당 ID의 투두가 존재하지 않습니다.")

@app.delete("/api/todos/{todo_id}")
def delete_todo_api(todo_id: int):
    todos = load_todos()
    for idx, todo in enumerate(todos):
        if todo.id == todo_id:
            del todos[idx]
            save_todos(todos)
            return {"detail": "삭제가 완료되었습니다."}
    raise HTTPException(status_code=404, detail="해당 ID의 투두가 존재하지 않습니다.")
